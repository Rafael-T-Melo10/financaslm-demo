import logging

import pdfplumber
import re
import unicodedata
from datetime import datetime, date
from typing import Dict, List, Any
import io
import os
import subprocess
import tempfile

from pdfminer.pdfdocument import PDFPasswordIncorrect

logger = logging.getLogger(__name__)

try:
    import pypdfium2 as pdfium
except Exception:
    pdfium = None


class SenhaInvalidaError(Exception):
    """Levantado quando a senha informada nao abre o PDF protegido."""


def extrair_dados_pdf(arquivo, tipo: str = "fatura", senha: str | None = None) -> Dict[str, Any]:
    if tipo == "holerite":
        return extrair_holerite(arquivo, senha=senha)
    elif tipo == "fatura":
        return extrair_fatura(arquivo, senha=senha)
    elif tipo == "conta":
        return extrair_conta(arquivo, senha=senha)
    else:
        raise ValueError(f"Tipo de arquivo não suportado: {tipo}")

def extrair_holerite(arquivo, senha: str | None = None) -> Dict[str, List[Dict]]:
    receitas = []
    itens = []

    try:
        with pdfplumber.open(arquivo, password=senha or "") as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                competencia = extrair_competencia_documento(text)
                item = extrair_liquido_a_receber(text, competencia)
                if item:
                    receitas.append(item)

                for linha in text.splitlines():
                    item_linha = extrair_item_holerite(linha, text, competencia)
                    if item_linha:
                        itens.append(item_linha)

    except PDFPasswordIncorrect:
        raise SenhaInvalidaError("Senha incorreta ou ausente para abrir o PDF.")
    except Exception:
        raise

    # Se não encontrou receitas, retornar vazio
    return {
        "receitas": remover_duplicatas_receitas(receitas),
        "itens": remover_duplicatas_receitas(itens),
    }

def extrair_liquido_a_receber(texto: str, competencia: date) -> Dict[str, Any] | None:
    """Extrai apenas o líquido a receber do contracheque."""
    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    padrao_valor = r"(?<!\d)(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}(?!\d)"

    for indice, linha in enumerate(linhas):
        texto_upper = linha.upper()
        if "LIQUIDO A RECEBER" not in texto_upper and "LÍQUIDO A RECEBER" not in texto_upper:
            continue

        # O valor normalmente fica na linha seguinte e costuma ser o último número da linha.
        candidatos = re.findall(padrao_valor, linha)

        if not candidatos and indice + 1 < len(linhas):
            proxima_linha = linhas[indice + 1]
            candidatos = re.findall(padrao_valor, proxima_linha)

        if not candidatos:
            continue

        valor = limpar_valor(candidatos[-1])
        if valor <= 0:
            continue

        return {
            "descricao": "LIQUIDO A RECEBER",
            "valor": valor,
            "data": competencia,
        }

    return None

PALAVRAS_DESCONTO_HOLERITE = [
    "MENSALIDADE",
    "IRRF",
    "INSS",
    "SULAMERICA",
    "ODONTO",
    "PLANO",
    "SAÚDE",
    "SAUDE",
    "CONTRIBUIÇÃO",
    "CONTRIBUICAO",
    "ALIMENTACAO",
    "ALIMENTAÇÃO",
    "DIF ANTECIPACAO",
    "DIF ANTECIPAÇÃO",
    "REAJUSTE SALARIAL",
    "DESCONTO",
    "FGTS",
    "VALE",
    "ADIANTAMENTO",
]


def extrair_item_holerite(line: str, texto_completo: str, competencia: date) -> Dict[str, Any] | None:
    """Extrai um item (provento ou desconto) de uma linha do contracheque."""
    if not line:
        return None

    texto = line.strip()
    if not texto:
        return None

    # Linhas de item típicas começam com código numérico e hífen.
    match_item = re.match(r"^(\d{3})\s*-\s*(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})$", texto)
    if not match_item:
        return None

    descricao = match_item.group(2).strip()
    valor = limpar_valor(match_item.group(3))
    if valor <= 0:
        return None

    descricao_upper = descricao.upper()
    tipo = "desconto" if any(palavra in descricao_upper for palavra in PALAVRAS_DESCONTO_HOLERITE) else "provento"

    return {
        "descricao": descricao,
        "valor": valor,
        "tipo": tipo,
        "data": competencia,
    }

def extrair_competencia_documento(texto: str) -> date:
    """Extrai a competência do contracheque a partir do cabeçalho."""
    match = re.search(r"Folha\s+(\d{2})/(\d{4})", texto, re.IGNORECASE)
    if match:
        mes = int(match.group(1))
        ano = int(match.group(2))
        return normalizar_competencia_holerite(mes, ano, texto)

    match = re.search(r"(\d{2})/(\d{4})", texto)
    if match:
        mes = int(match.group(1))
        ano = int(match.group(2))
        return normalizar_competencia_holerite(mes, ano, texto)

    return date.today()

def normalizar_competencia_holerite(mes: int, ano: int, texto: str = "") -> date:
    if 1 <= mes <= 12:
        return date(ano, mes, 1)

    texto_busca = normalizar_texto_busca(texto)
    if mes == 14 or "1PARCELA13" in texto_busca:
        return date(ano, 11, 1)
    if mes == 13:
        return date(ano, 12, 1)

    return date.today().replace(day=1)

def processar_tabela_holerite(table: List[List]) -> List[Dict]:
    """Processa uma tabela extraída de holerite/contracheque."""
    receitas = []

    for row in table or []:
        if not row:
            continue

        texto_linha = " ".join(str(cell or "").strip() for cell in row if cell)
        if not texto_linha:
            continue

        # Procurar descrição + valor na mesma linha
        match_valor = re.search(r"(?<!\d)(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}(?!\d)", texto_linha)
        if not match_valor:
            continue

        valor = limpar_valor(match_valor.group(0))
        if valor <= 0:
            continue

        texto_upper = texto_linha.upper()
        if any(keyword in texto_upper for keyword in ["DESCONTO", "INSS", "FGTS", "IRRF", "VALE", "ADIANTAMENTO SALARIAL", "CONTRIBUIÇÃO", "CONTRIBUICAO", "SULAMERICA", "ODONTO", "MENSALIDADE", "PLANO"]):
            # Descontos não devem virar receitas
            continue

        descricao = re.sub(r"(?<!\d)(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}(?!\d)", "", texto_linha).strip()
        if len(descricao) < 2:
            descricao = "Receita"

        receitas.append({
            "descricao": descricao,
            "valor": valor,
            "data": date.today()
        })

    return receitas

def remover_duplicatas_receitas(receitas: List[Dict]) -> List[Dict]:
    """Remove receitas duplicadas por descrição e valor."""
    vistos = set()
    resultado = []

    for receita in receitas:
        chave = (receita.get("descricao", "").strip().upper(), receita.get("valor"))
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append(receita)

    return resultado

def extrair_fatura(arquivo, senha: str | None = None) -> Dict[str, List[Dict]]:
    """Extrai dados de uma fatura em PDF."""
    despesas = []
    total_fatura = None
    informacoes_fatura: Dict[str, Any] = {}
    parcelas_futuras = []

    try:
        with pdfplumber.open(arquivo, password=senha or "") as pdf:
            texto_completo = "\n".join(page.extract_text() or "" for page in pdf.pages)
            if not texto_completo.strip():
                texto_completo = extrair_texto_ocr(arquivo)

            if parece_fatura_xp(texto_completo):
                return extrair_fatura_xp_texto(texto_completo)

            if not parece_fatura_cartao(texto_completo):
                return {
                    "despesas": [],
                    "total_fatura": None,
                    "informacoes_fatura": {},
                    "erro": "O arquivo enviado não parece ser uma fatura de cartão.",
                }

            for page in pdf.pages:
                text = page.extract_text() or ""
                total_pagina = extrair_total_fatura(text)
                if total_pagina is not None:
                    total_fatura = total_pagina
                informacoes_fatura = combinar_informacoes_fatura(
                    informacoes_fatura,
                    extrair_informacoes_fatura(text)
                )

            despesas = extrair_lancamentos_fatura_pdf(pdf, informacoes_fatura)
            parcelas_futuras = extrair_parcelas_futuras_fatura_pdf(pdf, informacoes_fatura)

    except PDFPasswordIncorrect:
        raise SenhaInvalidaError("Senha incorreta ou ausente para abrir o PDF.")
    except Exception:
        logger.exception("Falha inesperada ao extrair fatura")
        return {
            "despesas": [],
            "total_fatura": None,
            "informacoes_fatura": {},
            "parcelas_futuras": [],
            "erro": "Não foi possível ler a fatura.",
        }

    despesas = remover_duplicatas(despesas)

    if total_fatura is None and despesas:
        total_fatura = round(sum(despesa.get("valor", 0) for despesa in despesas), 2)

    return {
        "despesas": despesas,
        "total_fatura": total_fatura,
        "informacoes_fatura": informacoes_fatura,
        "parcelas_futuras": parcelas_futuras,
    }

def parece_fatura_cartao(texto: str) -> bool:
    """Confirma que o PDF tem marcadores de fatura de cartao antes de extrair valores."""
    texto_busca = normalizar_texto_busca(texto)
    marcadores = [
        "RESUMODAFATURA",
        "TOTALDESTAFATURA",
        "LANCAMENTOSCOMPRAS",
        "LIMITETOTALDECREDITO",
        "COMPRASPARCELADASPROXIMASFATURAS",
    ]
    return sum(1 for marcador in marcadores if marcador in texto_busca) >= 2

def extrair_texto_pdf(arquivo, senha: str | None = None) -> str:
    """Extrai texto normal do PDF e usa OCR quando o PDF for imagem."""
    try:
        if hasattr(arquivo, "seek"):
            arquivo.seek(0)
        with pdfplumber.open(arquivo, password=senha or "") as pdf:
            texto = "\n".join(page.extract_text() or "" for page in pdf.pages)
        if texto.strip():
            return texto
    except PDFPasswordIncorrect:
        raise SenhaInvalidaError("Senha incorreta ou ausente para abrir o PDF.")
    except Exception:
        pass

    return extrair_texto_ocr(arquivo)

def extrair_texto_ocr(arquivo, max_paginas: int | None = None) -> str:
    """Renderiza o PDF e chama tesseract quando o documento nao tem texto embutido."""
    if pdfium is None:
        return ""

    if hasattr(arquivo, "seek"):
        arquivo.seek(0)
        origem = arquivo.read()
    elif isinstance(arquivo, (str, os.PathLike)):
        with open(arquivo, "rb") as origem_file:
            origem = origem_file.read()
    else:
        origem = arquivo

    textos: List[str] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "documento.pdf")
        with open(pdf_path, "wb") as pdf_file:
            pdf_file.write(origem)

        doc = pdfium.PdfDocument(pdf_path)
        try:
            total_paginas = len(doc)
            if max_paginas:
                total_paginas = min(total_paginas, max_paginas)

            for indice in range(total_paginas):
                page = doc[indice]
                image_path = os.path.join(tmpdir, f"pagina-{indice + 1}.png")
                page.render(scale=2.2).to_pil().save(image_path)
                page.close()

                try:
                    resultado = subprocess.run(
                        ["tesseract", image_path, "stdout", "-l", "por+eng", "--psm", "6"],
                        capture_output=True,
                        text=True,
                        timeout=45,
                        check=False,
                    )
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    return ""

                if resultado.stdout:
                    textos.append(resultado.stdout)
        finally:
            doc.close()

    if hasattr(arquivo, "seek"):
        arquivo.seek(0)

    return "\n".join(textos)

def parece_fatura_xp(texto: str) -> bool:
    texto_busca = normalizar_texto_busca(texto)
    return "CARTA0XP" in texto_busca or "CARTAOXP" in texto_busca or (
        "XP" in texto_busca and "RESUMODASUAFATURA" in texto_busca
    )

def extrair_fatura_xp_texto(texto: str) -> Dict[str, Any]:
    informacoes: Dict[str, Any] = {}
    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    texto_busca = normalizar_texto_busca(texto)

    vencimento = extrair_data_por_rotulo(texto, ["Vencimento"])
    if vencimento:
        informacoes["vencimento"] = vencimento

    total = None
    for linha in linhas:
        linha_busca = normalizar_texto_busca(linha)
        valores = extrair_valores_monetarios(linha)
        if valores and any(rotulo in linha_busca for rotulo in ["PAGAMENTOTOTAL", "VALORTOTALDEVIDO", "VALORDOCUMENTO"]):
            total = valores[-1]
        elif valores and "NOVALORDER" in linha_busca:
            total = valores[-1]
    if total is None:
        match = re.search(r"valor\s+de\s+R\$\s*([\d.,]+)", texto, re.IGNORECASE)
        if match:
            total = limpar_valor(match.group(1))

    limite_total = procurar_valor_apos_rotulo(linhas, ["Limite total de credito", "Limite total de crédito"])
    limite_usado = procurar_valor_apos_rotulo(linhas, ["Limite utilizado"])
    if limite_total is not None:
        informacoes["limite_total_credito"] = limite_total
    if limite_usado is not None:
        informacoes["limite_total_utilizado"] = limite_usado

    despesas = extrair_lancamentos_xp(linhas, vencimento.year if vencimento else date.today().year)
    if total is None and despesas:
        total = round(sum(item["valor"] for item in despesas), 2)

    return {
        "despesas": remover_duplicatas(despesas),
        "total_fatura": total,
        "informacoes_fatura": informacoes,
        "parcelas_futuras": [],
    }

def extrair_lancamentos_xp(linhas: List[str], ano_base: int) -> List[Dict[str, Any]]:
    despesas: List[Dict[str, Any]] = []
    lendo_lancamentos = False

    for linha in linhas:
        linha_busca = normalizar_texto_busca(linha)
        if linha_busca.startswith("DATA") and ("DESCRICAO" in linha_busca or "DESCRI" in linha_busca):
            lendo_lancamentos = True
            continue

        if not lendo_lancamentos:
            continue

        if linha_busca.startswith("SUBTOTAL"):
            continue
        if linha_busca.startswith(("TITULAR", "ASINFORMACOES", "FATURAFECHADA", "LIMITETOTAL")):
            continue

        despesa = extrair_linha_compra_coluna(linha, ano_base)
        if not despesa:
            despesa = extrair_linha_xp_ocr(linha, ano_base)
        if not despesa:
            continue

        if despesa["valor"] < 0 or "PAGAMENTO" in normalizar_texto_busca(despesa["descricao"]):
            continue
        despesas.append(despesa)

    return despesas

def extrair_linha_xp_ocr(texto: str, ano_base: int) -> Dict[str, Any] | None:
    match = re.match(
        r"^(?P<data>\d{2}/\d{2}/\d{2,4})\s+(?P<descricao>.+?)\s+(?P<valor>-?(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2})(?:\s+0,00)?$",
        texto,
    )
    if not match:
        return None

    descricao = limpar_descricao_lancamento(match.group("descricao"))
    valor = limpar_valor(match.group("valor"))
    return {
        "descricao": descricao,
        "estabelecimento": remover_parcelamento_descricao(descricao),
        "valor": valor,
        "categoria": classificar_categoria(descricao),
        "data": parsear_data(match.group("data")) if len(match.group("data")) >= 8 else parsear_data_fatura(match.group("data")[:5], ano_base),
        "tipo": "compra",
    }

def extrair_lancamentos_fatura_pdf(pdf, informacoes_fatura: Dict[str, Any] | None = None) -> List[Dict]:
    """Extrai lancamentos de fatura respeitando as colunas visuais do PDF."""
    despesas: List[Dict[str, Any]] = []
    ano_base = obter_ano_base_fatura(informacoes_fatura)

    for page in pdf.pages:
        for xmin, xmax in [(130, 350), (360, 570)]:
            linhas = extrair_linhas_coluna_pdf(page, xmin, xmax)
            despesas.extend(processar_linhas_coluna_fatura(linhas, ano_base))

    return remover_duplicatas(despesas)

def extrair_parcelas_futuras_fatura_pdf(pdf, informacoes_fatura: Dict[str, Any] | None = None) -> List[Dict]:
    """Extrai compras parceladas listadas para proximas faturas."""
    parcelas: List[Dict[str, Any]] = []
    ano_base = obter_ano_base_fatura(informacoes_fatura)
    proximo_vencimento = calcular_proximo_vencimento((informacoes_fatura or {}).get("vencimento"))

    for page in pdf.pages:
        linhas = extrair_linhas_coluna_pdf(page, 130, 350)
        modo_futuras = False

        for linha in linhas:
            texto = linha["texto"].strip()
            texto_busca = normalizar_texto_busca(texto)

            if "COMPRASPARCELADASPROXIMASFATURAS" in texto_busca:
                modo_futuras = True
                continue

            if not modo_futuras:
                continue

            if texto_busca.startswith(("PROXIMAFATURA", "DEMAISFATURAS", "TOTALPARAPROXIMASFATURAS", "LIMITESDECREDITO")):
                if texto_busca.startswith("LIMITESDECREDITO"):
                    break
                continue

            parcela = extrair_linha_parcela_futura(texto, ano_base, proximo_vencimento)
            if parcela:
                parcelas.append(parcela)

    return remover_duplicatas_parcelas(parcelas)

def extrair_linha_parcela_futura(texto: str, ano_base: int, proximo_vencimento: date) -> Dict[str, Any] | None:
    match = re.match(
        r"^(?P<data>\d{2}/\d{2})\s+(?P<descricao>.+?)\s+(?P<valor>-?(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2})$",
        texto,
    )
    if not match:
        return None

    descricao = limpar_descricao_lancamento(match.group("descricao"))
    parcela_atual, total_parcelas = extrair_parcelamento_descricao(descricao)
    if not parcela_atual or not total_parcelas:
        return None

    valor_parcela = limpar_valor(match.group("valor"))
    parcelas_restantes = max(total_parcelas - parcela_atual + 1, 1)

    return {
        "descricao": descricao,
        "valor_parcela": valor_parcela,
        "valor_total": round(valor_parcela * parcelas_restantes, 2),
        "parcelas_restantes": parcelas_restantes,
        "total_parcelas": total_parcelas,
        "parcela_atual": parcela_atual,
        "data_inicio": parsear_data_fatura(match.group("data"), ano_base),
        "data_proxima_parcela": proximo_vencimento,
    }

def calcular_proximo_vencimento(vencimento: date | None) -> date:
    if not isinstance(vencimento, date):
        return date.today()

    mes = vencimento.month + 1
    ano = vencimento.year
    if mes == 13:
        mes = 1
        ano += 1

    try:
        return date(ano, mes, vencimento.day)
    except ValueError:
        return date(ano, mes, 28)

def remover_duplicatas_parcelas(parcelas: List[Dict]) -> List[Dict]:
    vistas = set()
    resultado = []

    for parcela in parcelas:
        chave = (
            parcela.get("descricao", "").strip().upper(),
            parcela.get("valor_parcela"),
            parcela.get("parcela_atual"),
            parcela.get("total_parcelas"),
        )
        if chave in vistas:
            continue
        vistas.add(chave)
        resultado.append(parcela)

    return resultado

def extrair_linhas_coluna_pdf(page, xmin: int, xmax: int) -> List[Dict[str, Any]]:
    """Agrupa palavras por linha dentro de uma coluna visual."""
    linhas_por_y: Dict[int, List[Dict[str, Any]]] = {}

    for palavra in page.extract_words(x_tolerance=2, y_tolerance=3) or []:
        if xmin <= palavra["x0"] <= xmax:
            y = round(palavra["top"] / 3) * 3
            linhas_por_y.setdefault(y, []).append(palavra)

    linhas = []
    for y, palavras in sorted(linhas_por_y.items()):
        texto = " ".join(
            palavra["text"] for palavra in sorted(palavras, key=lambda item: item["x0"])
        ).strip()
        if texto:
            linhas.append({"y": y, "texto": texto})

    return linhas

def processar_linhas_coluna_fatura(linhas: List[Dict[str, Any]], ano_base: int) -> List[Dict]:
    """Processa uma coluna ja separada do PDF e retorna compras reais."""
    despesas = []
    modo = "compras"
    ultima_despesa = None

    for linha in linhas:
        texto = linha["texto"].strip()
        texto_busca = normalizar_texto_busca(texto)

        if not texto:
            continue

        if "COMPRASPARCELADASPROXIMASFATURAS" in texto_busca:
            modo = "futuras"
            ultima_despesa = None
            continue

        if "LANCAMENTOSINTERNACIONAIS" in texto_busca:
            modo = "internacional"
            ultima_despesa = None
            continue

        if "OUTROSLANCAMENTOS" in texto_busca:
            modo = "outros"
            ultima_despesa = None
            continue

        if texto_busca.startswith("LIMITESDECREDITO") or texto_busca.startswith("ENCARGOSCOBRADOS"):
            modo = "ignorar"
            ultima_despesa = None
            continue

        if modo in ["futuras", "ignorar"]:
            ultima_despesa = None
            continue

        if modo == "internacional" and texto_busca.startswith("REPASSEDEIOFEMR"):
            valores = extrair_valores_monetarios(texto)
            if valores:
                despesas.append({
                    "descricao": "IOF internacional",
                    "estabelecimento": "IOF internacional",
                    "valor": valores[-1],
                    "categoria": "Impostos",
                    "data": ultima_despesa.get("data") if ultima_despesa else date(ano_base, 1, 1),
                    "tipo": "iof",
                })
            continue

        if modo == "outros":
            despesa = extrair_linha_outro_lancamento(texto, ano_base)
            if despesa:
                despesas.append(despesa)
            ultima_despesa = None
            continue

        despesa = extrair_linha_compra_coluna(texto, ano_base)
        if despesa:
            if modo == "internacional":
                despesa["tipo"] = "internacional"
            despesas.append(despesa)
            ultima_despesa = despesa
            continue

        if ultima_despesa and eh_linha_categoria_fatura(texto):
            categoria_banco = texto.strip()
            ultima_despesa["categoria_banco"] = categoria_banco
            ultima_despesa["categoria"] = classificar_categoria(
                f"{ultima_despesa['descricao']} {categoria_banco}"
            )
            ultima_despesa = None

    return despesas

def extrair_linha_compra_coluna(texto: str, ano_base: int) -> Dict[str, Any] | None:
    """Extrai linhas no formato DATA ESTABELECIMENTO VALOR."""
    match = re.match(
        r"^(?P<data>\d{2}/\d{2})\s+(?P<descricao>.+?)\s+(?P<valor>-?(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2})$",
        texto,
    )
    if not match:
        return None

    descricao = limpar_descricao_lancamento(match.group("descricao"))
    descricao_busca = normalizar_texto_busca(descricao)
    if not descricao or descricao_busca.startswith(("DATA", "TOTAL", "LANCAMENTOS")):
        return None

    valor = limpar_valor(match.group("valor"))
    if valor == 0:
        return None

    parcela_atual, parcelas_total = extrair_parcelamento_descricao(descricao)

    return {
        "descricao": descricao,
        "estabelecimento": remover_parcelamento_descricao(descricao),
        "valor": valor,
        "categoria": classificar_categoria(descricao),
        "data": parsear_data_fatura(match.group("data"), ano_base),
        "parcela_atual": parcela_atual,
        "parcelas_total": parcelas_total,
        "tipo": "compra",
    }

def extrair_linha_outro_lancamento(texto: str, ano_base: int) -> Dict[str, Any] | None:
    match = re.match(
        r"^(?P<data>\d{2}/\d{2})\s+(?P<descricao>.+?)\s+(?P<valor>-?(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2})$",
        texto,
    )
    if not match:
        return None

    descricao = limpar_descricao_lancamento(match.group("descricao"))
    valor = limpar_valor(match.group("valor"))
    if valor == 0:
        return None

    return {
        "descricao": descricao,
        "estabelecimento": descricao,
        "valor": valor,
        "categoria": "Ajustes",
        "data": parsear_data_fatura(match.group("data"), ano_base),
        "tipo": "ajuste",
    }

def eh_linha_categoria_fatura(texto: str) -> bool:
    texto_busca = normalizar_texto_busca(texto)
    categorias = [
        "ALIMENTACAO",
        "SAUDE",
        "VEICULOS",
        "VESTUARIO",
        "DIVERSOS",
        "TURISMOEENTRETENIM",
    ]
    return any(texto_busca.startswith(categoria) for categoria in categorias)

def limpar_descricao_lancamento(descricao: str) -> str:
    return re.sub(r"\s+", " ", descricao or "").strip()

def extrair_parcelamento_descricao(descricao: str) -> tuple[int | None, int | None]:
    match = re.search(r"(\d{2})/(\d{2})\s*$", descricao or "")
    if not match:
        match = re.search(r"(?<!\d)(\d{2})/(\d{2})(?!\d)", descricao or "")
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))

def remover_parcelamento_descricao(descricao: str) -> str:
    return re.sub(r"\s+(?<!\d)\d{2}/\d{2}(?!\d)", "", descricao or "").strip()

def obter_ano_base_fatura(informacoes_fatura: Dict[str, Any] | None = None) -> int:
    vencimento = (informacoes_fatura or {}).get("vencimento")
    if isinstance(vencimento, date):
        return vencimento.year
    return date.today().year

def parsear_data_fatura(data_str: str, ano_base: int) -> date:
    dia, mes = [int(parte) for parte in data_str.split("/")]
    if mes > date.today().month:
        ano_base -= 1
    return date(ano_base, mes, dia)

def extrair_total_fatura(texto: str) -> float | None:
    """Extrai o valor total da fatura a partir de frases comuns do documento."""
    if not texto:
        return None

    rotulos_prioritarios = [
        "TOTALDESTAFATURA",
        "TOTALDASUAFATURAE",
        "OTOTALDASUAFATURAE",
        "VALORTOTALDAFATURA",
        "VALORDODOCUMENTO",
    ]

    for linha in texto.splitlines():
        linha_normalizada = normalizar_texto_busca(linha)
        if any(rotulo in linha_normalizada for rotulo in rotulos_prioritarios):
            if any(termo in linha_normalizada for termo in [
                "ANTERIOR",
                "PROXIMA",
                "PROXIMAS",
                "PARCELAMENTO",
                "FINANCIADO",
                "APAGAR",
            ]):
                continue

            valores = extrair_valores_monetarios(linha)
            if valores:
                return valores[-1]

    linhas = texto.splitlines()
    for indice, linha in enumerate(linhas[:-1]):
        linha_normalizada = normalizar_texto_busca(linha)
        if "OTOTALDASUAFATURAE" in linha_normalizada and "LIMITETOTALDECREDITO" in linha_normalizada:
            valores = extrair_valores_monetarios(linhas[indice + 1])
            if valores:
                return valores[0]

    return None

def processar_tabela_fatura(table: List[List]) -> List[Dict]:
    """Processa uma tabela extraída de uma fatura"""
    despesas = []

    for row in table[1:]:  # Pular cabeçalho
        if len(row) >= 3:
            try:
                descricao = str(row[0]).strip()
                # Procurar valor em qualquer coluna
                valor = None
                data = None

                for cell in row:
                    if cell:
                        # Procurar padrão de valor monetário
                        match = re.search(r"R\$?\s*([\d.,]+)", str(cell))
                        if match:
                            valor = limpar_valor(match.group(1))

                        # Procurar padrão de data
                        data_match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", str(cell))
                        if data_match:
                            data = parsear_data(data_match.group(0))

                if valor and valor > 0 and descricao:
                    descricao_upper = descricao.upper()
                    if any(palavra in descricao_upper for palavra in [
                        "LIMITE",
                        "SALDO",
                        "TOTAL",
                        "PAGAMENTO",
                        "CRÉDITO",
                        "CREDITO",
                        "DISPONÍVEL",
                        "DISPONIVEL",
                        "FINANCIADO",
                        "RESUMO",
                        "ENCARGOS",
                        "IOF",
                        "JUROS",
                        "TAXA",
                    ]):
                        continue

                    despesas.append({
                        "descricao": descricao,
                        "valor": valor,
                        "categoria": classificar_categoria(descricao),
                        "data": data or date.today()
                    })
            except (TypeError, ValueError, AttributeError):
                continue

    return despesas

def extrair_informacoes_fatura(texto: str) -> Dict[str, Any]:
    """Extrai informações de resumo da fatura sem transformar em despesas."""
    if not texto:
        return {}

    informacoes: Dict[str, Any] = {}
    linhas = texto.splitlines()

    for indice, linha in enumerate(linhas):
        linha_normalizada = normalizar_texto_busca(linha)
        valores = extrair_valores_monetarios(linha)

        if "TOTALDAFATURAANTERIOR" in linha_normalizada and valores:
            informacoes["total_fatura_anterior"] = valores[-1]
        elif "PAGAMENTOEFETUADOEM" in linha_normalizada and valores:
            informacoes["pagamento_efetuado"] = -abs(valores[-1]) if "-" in linha else valores[-1]
            data_pagamento = re.search(r"(\d{2}/\d{2}/\d{4})", linha)
            if data_pagamento:
                informacoes["data_pagamento_efetuado"] = parsear_data(data_pagamento.group(1))
        elif "SALDOFINANCIADO" in linha_normalizada and valores:
            informacoes["saldo_financiado"] = valores[-1]
        elif "LANCAMENTOSATUAIS" in linha_normalizada and valores:
            informacoes["lancamentos_atuais"] = valores[-1]
        elif "TOTALDESTAFATURA" in linha_normalizada and valores:
            informacoes["valor_total_da_fatura"] = valores[-1]
        elif "LIMITEDISPONIVEL" in linha_normalizada and valores:
            informacoes["limite_disponivel"] = valores[0]
        elif "LIMITETOTALUTILIZADO" in linha_normalizada and valores:
            informacoes["limite_total_utilizado"] = valores[0]
        elif "LIMITETOTALDECREDITO" in linha_normalizada and valores:
            informacoes["limite_total_credito"] = valores[0]

        vencimento_match = re.search(r"vencimento[:\s]*(\d{2}/\d{2}/\d{4})", linha, re.IGNORECASE)
        if vencimento_match:
            informacoes["vencimento"] = parsear_data(vencimento_match.group(1))

        if (
            "OTOTALDASUAFATURAE" in linha_normalizada
            and "COMVENCIMENTOEM" in linha_normalizada
            and "LIMITETOTALDECREDITO" in linha_normalizada
            and indice + 1 < len(linhas)
        ):
            valores_resumo = extrair_valores_monetarios(linhas[indice + 1])
            datas_resumo = re.findall(r"\d{2}/\d{2}/\d{4}", linhas[indice + 1])
            if valores_resumo:
                informacoes["valor_total_da_fatura"] = valores_resumo[0]
            if datas_resumo:
                informacoes["vencimento"] = parsear_data(datas_resumo[0])
            if len(valores_resumo) >= 2:
                informacoes["limite_total_credito"] = valores_resumo[1]

    total_fatura = extrair_total_fatura(texto)
    if total_fatura is not None:
        informacoes["valor_total_da_fatura"] = total_fatura

    return informacoes

def normalizar_texto_busca(texto: str) -> str:
    """Normaliza texto extraido do PDF para buscas tolerantes a espacos e acentos."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]", "", texto.upper())

def extrair_valores_monetarios(texto: str) -> List[float]:
    valores = []
    for match in re.finditer(r"(?<!\d)(?:R\$?\s*)?(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})(?!\d)", texto or ""):
        valores.append(limpar_valor(f"{match.group(1)},{match.group(2)}"))
    return valores

def combinar_informacoes_fatura(base: Dict[str, Any], novas: Dict[str, Any]) -> Dict[str, Any]:
    """Mescla informações de várias páginas sem sobrescrever valores válidos."""
    resultado = dict(base or {})
    for chave, valor in (novas or {}).items():
        if chave not in resultado or resultado[chave] in (None, ""):
            resultado[chave] = valor
    return resultado


def _competencia_referencia_conta(referencia: str | None) -> date | None:
    """Converte uma referência mensal como JUN/2026 para a competência da conta."""
    match = re.fullmatch(
        r"\s*(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)/(\d{4})\s*",
        referencia or "",
        re.IGNORECASE,
    )
    if not match:
        return None

    meses = {
        "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4,
        "MAI": 5, "JUN": 6, "JUL": 7, "AGO": 8,
        "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12,
    }
    return date(int(match.group(2)), meses[match.group(1).upper()], 1)


def extrair_conta(arquivo, senha: str | None = None) -> Dict[str, Any]:
    """Extrai contas de consumo/servicos como uma despesa unica."""
    texto = extrair_texto_pdf(arquivo, senha=senha)
    if not texto.strip():
        return {
            "despesas": [],
            "informacoes_conta": {},
            "erro": "Nao foi possivel ler texto deste PDF. Recrie a imagem com OCR ou use outro arquivo.",
        }

    texto_busca = normalizar_texto_busca(texto)
    if "NIO" in texto_busca and ("FIBRA" in texto_busca or "EXTRATO" in texto_busca):
        conta = extrair_conta_nio_texto(texto)
    elif "LIGHT" in texto_busca or "ENERGIAELETRICA" in texto_busca:
        conta = extrair_conta_light_texto(texto)
    elif "NATURGY" in texto_busca or "GASNATURAL" in texto_busca or "CEG" in texto_busca:
        conta = extrair_conta_naturgy_texto(texto)
    else:
        conta = None

    if not conta:
        return {
            "despesas": [],
            "informacoes_conta": {},
            "erro": "O arquivo enviado nao parece ser uma conta suportada.",
        }

    competencia = _competencia_referencia_conta(conta.get("referencia"))
    despesa = {
        "descricao": conta["descricao"],
        "valor": conta["valor"],
        "data": competencia or conta.get("vencimento") or conta.get("emissao") or date.today(),
        "categoria": conta.get("categoria", "Moradia"),
    }
    return {"despesas": [despesa], "informacoes_conta": conta}

def extrair_conta_nio_texto(texto: str) -> Dict[str, Any] | None:
    valor = procurar_valor_linha_nio(texto)
    vencimento = extrair_data_por_rotulo(texto, ["Data de vencimento", "vencimento"])
    emissao = extrair_data_por_rotulo(texto, ["Emissao", "Emissão"])
    referencia = extrair_referencia_mes_ano(texto)

    if valor is None:
        return None

    return {
        "fornecedor": "Nio",
        "tipo": "internet",
        "descricao": f"Internet Nio {referencia}" if referencia else "Internet Nio",
        "valor": valor,
        "vencimento": vencimento,
        "emissao": emissao,
        "referencia": referencia,
        "categoria": "Moradia",
    }

def procurar_valor_linha_nio(texto: str) -> float | None:
    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    for linha in linhas:
        linha_busca = normalizar_texto_busca(linha)
        if "TOTALDOSSERVICOS" in linha_busca or "TOTALDOSSERVIOS" in linha_busca:
            valores = extrair_valores_monetarios(linha)
            if valores:
                return valores[-1]

    for linha in linhas:
        linha_busca = normalizar_texto_busca(linha)
        if "NIOFIBRASUPER" in linha_busca:
            valores = extrair_valores_monetarios(linha)
            if valores:
                return valores[-1]

    for linha in linhas:
        linha_busca = normalizar_texto_busca(linha)
        if "VALORDODOCUMENTO" in linha_busca or "VALORCOBRADO" in linha_busca:
            valores = extrair_valores_monetarios(linha)
            valores_validos = [valor for valor in valores if valor > 0]
            if valores_validos:
                return valores_validos[-1]

    valores_validos = [valor for valor in extrair_valores_monetarios(texto) if valor > 0]
    return valores_validos[0] if valores_validos else None

def extrair_conta_light_texto(texto: str) -> Dict[str, Any] | None:
    valor = procurar_valor_por_rotulo(texto, ["Total a pagar", "Valor total", "R$"])
    vencimento = extrair_data_por_rotulo(texto, ["Vencimento"])
    referencia = extrair_referencia_mes_ano(texto)

    match_linha = re.search(
        r"([A-Z]{3}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+R?\$?\s*([\d.,]+)",
        texto,
        re.IGNORECASE,
    )
    if match_linha:
        referencia = referencia or match_linha.group(1).upper()
        vencimento = vencimento or parsear_data(match_linha.group(2))
        valor = valor or limpar_valor(match_linha.group(3))

    if valor is None:
        return None

    return {
        "fornecedor": "Light",
        "tipo": "luz",
        "descricao": f"Conta de luz Light {referencia}" if referencia else "Conta de luz Light",
        "valor": valor,
        "vencimento": vencimento,
        "referencia": referencia,
        "categoria": "Moradia",
    }

def extrair_conta_naturgy_texto(texto: str) -> Dict[str, Any] | None:
    valor = procurar_valor_por_rotulo(texto, ["Valor a pagar R$", "ValorapagarR$", "Valor a pagar"])
    vencimento = extrair_data_por_rotulo(texto, ["Data de vencimento", "Vencimento"])
    emissao = extrair_data_por_rotulo(texto, ["Data de emissao", "Data de emissão", "Emissao", "Emissão"])
    referencia = extrair_referencia_mes_ano(texto)

    if valor is None:
        valores = extrair_valores_monetarios(texto)
        if valores:
            valor = valores[0]
    if valor is None:
        return None

    return {
        "fornecedor": "Naturgy",
        "tipo": "gas",
        "descricao": f"Conta de gas Naturgy {referencia}" if referencia else "Conta de gas Naturgy",
        "valor": valor,
        "vencimento": vencimento,
        "emissao": emissao,
        "referencia": referencia,
        "categoria": "Moradia",
    }

def procurar_valor_por_rotulo(texto: str, rotulos: List[str]) -> float | None:
    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    valor = procurar_valor_apos_rotulo(linhas, rotulos)
    if valor is not None:
        return valor

    for linha in linhas:
        linha_busca = normalizar_texto_busca(linha)
        if any(normalizar_texto_busca(rotulo) in linha_busca for rotulo in rotulos):
            valores = extrair_valores_monetarios(linha)
            if valores:
                return valores[-1]
    return None

def procurar_valor_apos_rotulo(linhas: List[str], rotulos: List[str]) -> float | None:
    rotulos_busca = [normalizar_texto_busca(rotulo) for rotulo in rotulos]
    for indice, linha in enumerate(linhas):
        linha_busca = normalizar_texto_busca(linha)
        if not any(rotulo in linha_busca for rotulo in rotulos_busca):
            continue

        valores = extrair_valores_monetarios(linha)
        if valores:
            return valores[-1]

        for proxima in linhas[indice + 1: indice + 4]:
            valores = extrair_valores_monetarios(proxima)
            if valores:
                return valores[-1]
    return None

def extrair_data_por_rotulo(texto: str, rotulos: List[str]) -> date | None:
    """Busca a data que vem logo apos um dos rotulos. Quando rotulo e data
    estao na mesma linha, a busca comeca a partir do fim do rotulo (nao do
    inicio da linha), para nao confundir com outro rotulo/data que apareca
    antes na mesma linha (ex: 'Emissao:23/10/2025 Vencimento:10/11/2025',
    comum em contas de gas/energia com layout compacto)."""
    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    padrao_data = r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Z]{3,}\s+DE\s+\d{4}"
    padroes_rotulo = [
        re.compile(r"\s*".join(re.escape(c) for c in rotulo), re.IGNORECASE)
        for rotulo in rotulos
    ]

    for indice, linha in enumerate(linhas):
        linha_sem_acento = unicodedata.normalize("NFKD", linha).encode("ascii", "ignore").decode("ascii")

        posicao_fim_rotulo = None
        for padrao in padroes_rotulo:
            match_rotulo = padrao.search(linha_sem_acento)
            if match_rotulo and (posicao_fim_rotulo is None or match_rotulo.start() < posicao_fim_rotulo[0]):
                posicao_fim_rotulo = (match_rotulo.start(), match_rotulo.end())

        if posicao_fim_rotulo is None:
            continue

        resto_da_linha = linha_sem_acento[posicao_fim_rotulo[1]:]
        match = re.search(padrao_data, resto_da_linha, re.IGNORECASE)
        if match:
            return parsear_data_extenso(match.group(0))

        trecho_seguinte = " ".join(linhas[indice + 1: indice + 3])
        match = re.search(padrao_data, trecho_seguinte, re.IGNORECASE)
        if match:
            return parsear_data_extenso(match.group(0))

    return None

def extrair_referencia_mes_ano(texto: str) -> str | None:
    match = re.search(r"\b([A-Z]{3})/(\d{4})\b", texto, re.IGNORECASE)
    if match:
        return f"{match.group(1).upper()}/{match.group(2)}"

    match = re.search(r"\b(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)\s+(\d{4})\b", texto, re.IGNORECASE)
    if match:
        return f"{match.group(1).upper()}/{match.group(2)}"

    return None

def parsear_data_extenso(valor: str) -> date:
    valor_limpo = re.sub(r"\s+", " ", valor.strip().upper())
    meses = {
        "JAN": 1, "JANEIRO": 1,
        "FEV": 2, "FEVEREIRO": 2,
        "MAR": 3, "MARCO": 3, "MARÇO": 3,
        "ABR": 4, "ABRIL": 4,
        "MAI": 5, "MAIO": 5,
        "JUN": 6, "JUNHO": 6,
        "JUL": 7, "JULHO": 7,
        "AGO": 8, "AGOSTO": 8,
        "SET": 9, "SETEMBRO": 9,
        "OUT": 10, "OUTUBRO": 10,
        "NOV": 11, "NOVEMBRO": 11,
        "DEZ": 12, "DEZEMBRO": 12,
    }
    match = re.match(r"(\d{1,2})\s+([A-ZÇ]+)(?:\s+DE)?\s+(\d{4})", valor_limpo)
    if match:
        mes = meses.get(match.group(2))
        if mes:
            return date(int(match.group(3)), mes, int(match.group(1)))
    return parsear_data(valor)

def extrair_linhas_fatura(text: str) -> List[Dict]:
    """Extrai despesas de texto de fatura"""
    despesas = []

    linhas = text.split('\n')
    for line in linhas:
        texto = line.strip()
        if not texto:
            continue

        texto_upper = texto.upper()

        # Ignorar blocos de resumo, limite, saldo, pagamento mínimo, taxas e totais.
        if any(palavra in texto_upper for palavra in [
            "LIMITE",
            "SALDO",
            "TOTAL DA FATURA",
            "TOTAL DESTA FATURA",
            "VALOR TOTAL",
            "PAGAMENTO EFETUADO",
            "PAGAMENTO MÍNIMO",
            "PAGAMENTO MINIMO",
            "VALOR MÍNIMO",
            "VALOR MINIMO",
            "TOTAL A PAGAR",
            "CRÉDITO",
            "CREDITO",
            "DISPONÍVEL",
            "DISPONIVEL",
            "FINANCIADO",
            "RESUMO",
            "ENCARGOS",
            "IOF",
            "JUROS",
            "TAXA",
            "PARCELA FIXA",
            "LANÇAMENTOS ATUAIS",
            "LANCAMENTOS ATUAIS",
            "LANÇAMENTOS",
            "LANCAMENTOS",
            "LIMITE TOTAL DE CRÉDITO",
            "LIMITE TOTAL DE CREDITO",
        ]):
            continue

        # Aceitar apenas linhas que pareçam transações reais:
        # - normalmente têm data ou descrição mais longa + valor ao fim
        if not ('R$' in texto or re.search(r"\d,\d{2}$", texto) or re.search(r"\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?", texto)):
            continue

        # Procurar padrão de descrição + valor ao final da linha
        match = re.search(r"(.+?)\s+(?:R\$?\s*)?([\d.,]+)\s*$", texto)
        if not match:
            continue

        descricao = match.group(1).strip()
        valor = limpar_valor(match.group(2))
        if valor <= 0 or len(descricao) <= 2:
            continue

        # Descartar descrições claramente não transacionais.
        if any(palavra in descricao.upper() for palavra in [
            "LIMITE",
            "SALDO",
            "TOTAL",
            "PAGAMENTO",
            "CREDITO",
            "CRÉDITO",
            "DISPONIVEL",
            "DISPONÍVEL",
            "RESUMO",
            "FINANCIADO",
        ]):
            continue

        data_match = re.search(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", texto)
        data = parsear_data(data_match.group(0)) if data_match else date.today()

        despesas.append({
            "descricao": descricao,
            "valor": valor,
            "categoria": classificar_categoria(descricao),
            "data": data
        })

    return despesas

def limpar_valor(valor_str: str) -> float:
    """Converte string de valor para float"""
    # Remover espaços e caracteres especiais
    valor_str = valor_str.strip().replace('R$', '').strip()

    # Tratar diferentes formatos de número
    # Formato brasileiro: 1.234,56
    if ',' in valor_str and '.' in valor_str:
        valor_str = valor_str.replace('.', '').replace(',', '.')
    elif ',' in valor_str:
        valor_str = valor_str.replace(',', '.')

    try:
        return float(valor_str)
    except (TypeError, ValueError):
        return 0.0

def parsear_data(data_str: str) -> date:
    """Converte string de data para objeto date"""
    formatos = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%Y-%m-%d"
    ]

    for formato in formatos:
        try:
            return datetime.strptime(data_str, formato).date()
        except ValueError:
            continue

    return date.today()

def extrair_data_documento(text: str) -> date:
    """Extrai data do documento procurando por padrões comuns"""
    # Procurar padrões de data
    padroes = [
        r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",
        r"[Dd]ata[:\s]+(\d{1,2})[/-](\d{1,2})[/-](\d{4})"
    ]

    for padrao in padroes:
        match = re.search(padrao, text)
        if match:
            return parsear_data(match.group(0))

    return date.today()

def classificar_categoria(descricao: str) -> str:
    """Classifica despesa em categoria baseado na descrição"""
    descricao_lower = descricao.lower()
    descricao_busca = normalizar_texto_busca(descricao)

    categorias_banco = {
        "Alimentacao": ["ALIMENTACAO", "GOODBURGER", "MEGAMATTE", "MIXPREMIERE", "KFC", "CHOCOLATE", "KOPENHAGEN"],
        "Transporte": ["VEICULOS", "UBER", "99RIDE", "POP"],
        "Saude": ["SAUDE", "DROGARIA", "FARMA", "RAIA"],
        "Roupas": ["VESTUARIO", "RENNER", "CEAMODAS"],
        "Lazer": ["TURISMOEENTRETENIM", "GOOGLEONE", "OPENAICHATGPT"],
        "Diversos": ["DIVERSOS"],
    }

    for categoria, palavras_chave in categorias_banco.items():
        if any(palavra in descricao_busca for palavra in palavras_chave):
            return categoria

    categorias = {
        "Alimentação": ["supermercado", "restaurante", "café", "padaria", "açougue", "mercado"],
        "Transporte": ["uber", "táxi", "combustível", "gasolina", "estacionamento", "transporte"],
        "Saúde": ["farmácia", "hospital", "médico", "dentista", "laboratório"],
        "Educação": ["escola", "universidade", "curso", "educação"],
        "Diversão": ["cinema", "teatro", "jogo", "lazer"],
        "Moradia": ["aluguel", "condomínio", "água", "luz", "energia", "gás"],
        "Assinaturas": ["netflix", "spotify", "assinatura", "plano"],
        "Roupas": ["roupas", "sapatos", "vestuário"],
        "Eletrônicos": ["eletrônico", "informática", "computador"]
    }

    for categoria, palavras_chave in categorias.items():
        if any(palavra in descricao_lower for palavra in palavras_chave):
            return categoria

    return "Outros"

def remover_duplicatas(despesas: List[Dict]) -> List[Dict]:
    """Remove despesas duplicadas"""
    vistas = set()
    resultado = []

    for despesa in despesas:
        chave = (
            despesa.get("data"),
            despesa.get("valor"),
            despesa.get("descricao", "").strip().upper(),
            despesa.get("categoria_banco", ""),
        )
        if chave not in vistas:
            vistas.add(chave)
            resultado.append(despesa)

    return resultado
