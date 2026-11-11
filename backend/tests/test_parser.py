import io
from datetime import date

import pytest

from app.services.parser import (
    SenhaInvalidaError,
    classificar_categoria,
    extrair_competencia_documento,
    extrair_conta,
    extrair_conta_light_texto,
    extrair_conta_naturgy_texto,
    extrair_conta_nio_texto,
    extrair_dados_pdf,
    extrair_data_por_rotulo,
    extrair_item_holerite,
    extrair_liquido_a_receber,
    extrair_parcelamento_descricao,
    extrair_total_fatura,
    limpar_valor,
    parsear_data,
    remover_duplicatas,
    remover_parcelamento_descricao,
)


# ---------- valores e datas ----------

def test_limpar_valor_formato_brasileiro():
    assert limpar_valor("1.234,56") == 1234.56
    assert limpar_valor("R$ 99,90") == 99.90
    assert limpar_valor("15,00") == 15.0


def test_limpar_valor_invalido_vira_zero():
    assert limpar_valor("abc") == 0.0


def test_parsear_data_formatos():
    assert parsear_data("05/07/2026") == date(2026, 7, 5)
    assert parsear_data("2026-07-05") == date(2026, 7, 5)
    assert parsear_data("05-07-26") == date(2026, 7, 5)


# ---------- categorização ----------

def test_classificar_categoria():
    assert classificar_categoria("UBER TRIP") == "Transporte"
    assert classificar_categoria("DROGARIA PACHECO") == "Saude"
    assert classificar_categoria("Restaurante do Zé") == "Alimentação"
    assert classificar_categoria("NETFLIX.COM") == "Assinaturas"
    assert classificar_categoria("XPTO SEM PISTA") == "Outros"


# ---------- parcelamento na descrição ----------

def test_extrair_parcelamento_descricao():
    assert extrair_parcelamento_descricao("LOJA TAL 03/10") == (3, 10)
    assert extrair_parcelamento_descricao("SEM PARCELA") == (None, None)


def test_remover_parcelamento_descricao():
    assert remover_parcelamento_descricao("LOJA TAL 03/10") == "LOJA TAL"


# ---------- holerite ----------

def test_extrair_liquido_a_receber_valor_na_linha():
    texto = "Salário base 8.000,00\nLIQUIDO A RECEBER 5.432,10\nRodapé"
    item = extrair_liquido_a_receber(texto, date(2026, 4, 1))
    assert item == {"descricao": "LIQUIDO A RECEBER", "valor": 5432.10, "data": date(2026, 4, 1)}


def test_extrair_liquido_a_receber_valor_na_linha_seguinte():
    texto = "LÍQUIDO A RECEBER\n5.432,10"
    item = extrair_liquido_a_receber(texto, date(2026, 4, 1))
    assert item is not None and item["valor"] == 5432.10


def test_extrair_competencia_documento():
    assert extrair_competencia_documento("Folha 04/2026 - Mensal") == date(2026, 4, 1)


def test_extrair_competencia_documento_decimo_terceiro():
    assert extrair_competencia_documento("Contracheque - Folha 13/2025\n012 - 13º SALARIO 2025") == date(2025, 12, 1)
    assert extrair_competencia_documento("Contracheque - Folha 14/2025\n012 - 1ª PARCELA 13º SALARIO 2025") == date(2025, 11, 1)


def test_extrair_item_holerite_provento():
    item = extrair_item_holerite("001 - SALARIO BASE 8.000,00", "", date(2026, 4, 1))
    assert item == {"descricao": "SALARIO BASE", "valor": 8000.0, "tipo": "provento", "data": date(2026, 4, 1)}


def test_extrair_item_holerite_desconto():
    item = extrair_item_holerite("901 - INSS 800,00", "", date(2026, 4, 1))
    assert item == {"descricao": "INSS", "valor": 800.0, "tipo": "desconto", "data": date(2026, 4, 1)}


def test_extrair_item_holerite_linha_sem_padrao():
    assert extrair_item_holerite("LIQUIDO A RECEBER", "", date(2026, 4, 1)) is None


# ---------- fatura ----------

def test_extrair_total_fatura():
    texto = "Olá\nO total da sua fatura é R$ 2.345,67\nVencimento 10/05/2026"
    assert extrair_total_fatura(texto) == 2345.67


def test_extrair_total_fatura_ignora_total_anterior():
    texto = "Total da sua fatura anterior R$ 999,99\nValor total da fatura R$ 1.500,00"
    assert extrair_total_fatura(texto) == 1500.0


def test_remover_duplicatas():
    despesas = [
        {"data": date(2026, 5, 1), "valor": 10.0, "descricao": "UBER"},
        {"data": date(2026, 5, 1), "valor": 10.0, "descricao": "uber "},
        {"data": date(2026, 5, 2), "valor": 10.0, "descricao": "UBER"},
    ]
    assert len(remover_duplicatas(despesas)) == 2


# ---------- contas de consumo ----------

def test_extrair_conta_light():
    texto = "LIGHT SERVIÇOS\nABR/2026 10/05/2026 R$ 187,65\nConsumo 120 kWh"
    conta = extrair_conta_light_texto(texto)
    assert conta is not None
    assert conta["fornecedor"] == "Light"
    assert conta["valor"] == 187.65
    assert conta["vencimento"] == date(2026, 5, 10)
    assert conta["categoria"] == "Moradia"


def test_extrair_conta_nio():
    texto = "NIO INTERNET\nTotal dos serviços R$ 119,90\nData de vencimento 15/05/2026"
    conta = extrair_conta_nio_texto(texto)
    assert conta is not None
    assert conta["valor"] == 119.90
    assert conta["vencimento"] == date(2026, 5, 15)


def test_extrair_conta_naturgy():
    texto = "NATURGY\nValor a pagar R$ 96,30\nData de vencimento 20/05/2026"
    conta = extrair_conta_naturgy_texto(texto)
    assert conta is not None
    assert conta["valor"] == 96.30
    assert conta["vencimento"] == date(2026, 5, 20)


def test_extrair_conta_reconhece_ceg_como_naturgy():
    """A distribuidora regional (CEG - Companhia Distribuidora de Gas do Rio
    de Janeiro) emite a fatura sem a palavra 'Naturgy' no texto; o dispatcher
    extrair_conta precisa reconhecer 'CEG' tambem."""
    pdf = _pdf_sintetico([
        "COMPANHIA DISTRIBUIDORA DE GAS DO RIO DE JANEIRO - CEG",
        "Nº Cliente: 0000000-0 Mes:OUT/2025 Titular:PESSOA DEMO",
        "Valor a pagar R$:R$123,45 Emissao:23/10/2025 Vencimento:10/11/2025",
    ])
    resultado = extrair_conta(pdf)
    assert "erro" not in resultado
    assert resultado["despesas"][0]["valor"] == 123.45
    assert resultado["despesas"][0]["data"] == date(2025, 10, 1)


def test_extrair_conta_usa_mes_referencia_em_vez_do_vencimento():
    pdf = _pdf_sintetico([
        "LIGHT SERVIÇOS DE ELETRICIDADE",
        "JUN/2026 03/07/2026 R$ 289,20",
        "Consumo 180 kWh",
    ])

    resultado = extrair_conta(pdf)

    assert "erro" not in resultado
    assert resultado["despesas"][0]["data"] == date(2026, 6, 1)
    assert resultado["despesas"][0]["descricao"].endswith("JUN/2026")


def test_extrair_conta_sem_referencia_preserva_vencimento_como_fallback():
    pdf = _pdf_sintetico([
        "NIO FIBRA",
        "Total dos serviços R$ 130,00",
        "Data de vencimento 13/07/2026",
    ])

    resultado = extrair_conta(pdf)

    assert "erro" not in resultado
    assert resultado["despesas"][0]["data"] == date(2026, 7, 13)


def test_extrair_data_por_rotulo_emissao_e_vencimento_na_mesma_linha():
    """Quando emissao e vencimento estao na mesma linha (layout compacto,
    comum em contas de gas/energia), cada rotulo deve pegar a data que vem
    depois dele, nao a primeira data da linha."""
    texto = "Valor a pagar R$:R$123,45 Emissão:23/10/2025 Vencimento:10/11/2025"
    vencimento = extrair_data_por_rotulo(texto, ["Data de vencimento", "Vencimento"])
    emissao = extrair_data_por_rotulo(texto, ["Data de emissao", "Data de emissão", "Emissao", "Emissão"])
    assert vencimento == date(2025, 11, 10)
    assert emissao == date(2025, 10, 23)



# ---------- PDF sintético de ponta a ponta ----------

def _pdf_sintetico(linhas):
    """Gera um PDF mínimo (uma página, texto Helvetica) em memória."""
    conteudo_linhas = []
    y = 760
    for linha in linhas:
        texto = linha.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        conteudo_linhas.append(f"BT /F1 12 Tf 72 {y} Td ({texto}) Tj ET")
        y -= 16
    stream = ("\n".join(conteudo_linhas)).encode("latin-1")

    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    saida = io.BytesIO()
    saida.write(b"%PDF-1.4\n")
    offsets = []
    for numero, corpo in enumerate(objetos, start=1):
        offsets.append(saida.tell())
        saida.write(f"{numero} 0 obj\n".encode())
        saida.write(corpo)
        saida.write(b"\nendobj\n")

    xref_pos = saida.tell()
    saida.write(f"xref\n0 {len(objetos) + 1}\n".encode())
    saida.write(b"0000000000 65535 f \n")
    for offset in offsets:
        saida.write(f"{offset:010d} 00000 n \n".encode())
    saida.write(
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode()
    )
    saida.seek(0)
    return saida


def test_holerite_pdf_sintetico():
    pdf = _pdf_sintetico([
        "CONTRACHEQUE Folha 04/2026",
        "001 - SALARIO BASE 8.000,00",
        "901 - INSS 800,00",
        "LIQUIDO A RECEBER",
        "5.432,10",
    ])

    dados = extrair_dados_pdf(pdf, tipo="holerite")
    receitas = dados.get("receitas", [])
    itens = dados.get("itens", [])

    assert len(receitas) == 1
    assert receitas[0]["valor"] == 5432.10
    assert receitas[0]["data"] == date(2026, 4, 1)

    assert len(itens) == 2
    provento = next(item for item in itens if item["tipo"] == "provento")
    desconto = next(item for item in itens if item["tipo"] == "desconto")
    assert provento == {"descricao": "SALARIO BASE", "valor": 8000.0, "tipo": "provento", "data": date(2026, 4, 1)}
    assert desconto == {"descricao": "INSS", "valor": 800.0, "tipo": "desconto", "data": date(2026, 4, 1)}


def test_holerite_pdf_decimo_terceiro_nao_falha_com_folha_14():
    pdf = _pdf_sintetico([
        "CONTRACHEQUE Folha 14/2025",
        "012 - 1 PARCELA 13 SALARIO 2025 2.281,00",
        "LIQUIDO A RECEBER",
        "2.281,00",
    ])

    dados = extrair_dados_pdf(pdf, tipo="holerite")
    receitas = dados.get("receitas", [])

    assert len(receitas) == 1
    assert receitas[0]["valor"] == 2281.00
    assert receitas[0]["data"] == date(2025, 11, 1)


# ---------- PDF protegido por senha ----------

def _pdf_protegido(linhas, senha):
    """Gera o PDF sintético e o criptografa com a senha informada."""
    from PyPDF2 import PdfReader, PdfWriter

    pdf_original = _pdf_sintetico(linhas)
    leitor = PdfReader(pdf_original)
    escritor = PdfWriter()
    for pagina in leitor.pages:
        escritor.add_page(pagina)
    escritor.encrypt(senha)

    saida = io.BytesIO()
    escritor.write(saida)
    saida.seek(0)
    return saida


def test_holerite_pdf_protegido_senha_correta():
    pdf = _pdf_protegido([
        "CONTRACHEQUE Folha 04/2026",
        "LIQUIDO A RECEBER",
        "5.432,10",
    ], senha="segredo123")

    dados = extrair_dados_pdf(pdf, tipo="holerite", senha="segredo123")
    receitas = dados.get("receitas", [])

    assert len(receitas) == 1
    assert receitas[0]["valor"] == 5432.10


def test_holerite_pdf_protegido_senha_incorreta():
    pdf = _pdf_protegido([
        "CONTRACHEQUE Folha 04/2026",
        "LIQUIDO A RECEBER",
        "5.432,10",
    ], senha="segredo123")

    with pytest.raises(SenhaInvalidaError):
        extrair_dados_pdf(pdf, tipo="holerite", senha="senha-errada")


def test_holerite_pdf_protegido_sem_senha():
    pdf = _pdf_protegido([
        "CONTRACHEQUE Folha 04/2026",
        "LIQUIDO A RECEBER",
        "5.432,10",
    ], senha="segredo123")

    with pytest.raises(SenhaInvalidaError):
        extrair_dados_pdf(pdf, tipo="holerite")
