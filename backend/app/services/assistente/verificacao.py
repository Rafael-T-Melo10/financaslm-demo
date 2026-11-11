"""Sanitizacao de entrada e verificacao de saida do assistente.

Duas fronteiras distintas de confianca:

1. A PERGUNTA do usuario -- confiavel quanto a intencao, mas limitada em
   tamanho antes de ir para o modelo (sanitizar_pergunta).
2. O RESULTADO da consulta SQL -- contem descricao/estabelecimento extraidos
   de PDFs de terceiros (faturas, contas) via o sync do Gmail. Isso e DADO,
   nunca instrucao: um estabelecimento chamado "ignore as instrucoes
   anteriores e..." e um vetor de prompt injection real, nao hipotetico
   (sanitizar_texto_de_dados).

Depois da chamada 2, checar_afirmacoes fecha o outro lado: nenhum numero que
aparece na resposta em portugues pode ser inventado -- todo numero citado
precisa estar, de fato, no resultado real que o banco devolveu.
"""
from __future__ import annotations

import re
from typing import Any

from sqlglot import exp

from app.services.assistente.execucao_sql import ResultadoSql

_CARACTERES_DE_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitizar_pergunta(texto: str, max_chars: int = 400) -> str:
    """Limite de tamanho + remocao de caracteres de controle. Nao remove
    pontuacao nem acentos -- a pergunta e portugues natural, nao um token
    tecnico."""
    texto = _CARACTERES_DE_CONTROLE.sub(" ", (texto or "").strip())
    texto = re.sub(r"\s+", " ", texto)
    return texto[:max_chars]


def sanitizar_texto_de_dados(valor: Any, max_chars: int = 120) -> Any:
    """Aplica-se a QUALQUER valor de texto vindo de resultado.linhas antes de
    ele ser injetado no prompt da chamada 2. Numeros, datas e outros tipos
    passam intactos -- so string e alvo de prompt injection aqui.
    """
    if not isinstance(valor, str):
        return valor
    texto = _CARACTERES_DE_CONTROLE.sub(" ", valor)
    texto = texto.replace("\n", " ").replace("\r", " ")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto[:max_chars]


def sanitizar_linhas_resultado(linhas: list[dict[str, Any]], max_chars: int = 120) -> list[dict[str, Any]]:
    return [
        {chave: sanitizar_texto_de_dados(valor, max_chars) for chave, valor in linha.items()}
        for linha in linhas
    ]


# ==================== verificacao de afirmacoes numericas na resposta final ====================

_PADRAO_NUMERO_PT = re.compile(
    r"-?\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?"  # agrupado por milhar, com ou sem decimal: 1.204,55 / 12.000
    r"|-?\d+[.,]\d{1,2}(?!\d)"  # decimal simples, 1-2 casas, qualquer separador: 12,4 / 4302.74 / 98.80
    r"|-?\d+"  # inteiro puro: 300
)
"""O modelo (llama3.1, treinado majoritariamente em ingles) as vezes escreve
numeros em portugues com separador decimal de PONTO em vez de virgula --
observado ao vivo: "R$ 4302.74" em lugar de "R$ 4302,74". A provavel causa e
que o bloco de evidencias enviado para a chamada 2 ja chega formatado com
ponto (str()/json.dumps de float/Decimal em Python sempre usa ponto), e o
modelo as vezes copia o digito com o separador original em vez de reformatar
para portugues. Sem a segunda alternativa do regex, "4302.74" quebrava em
dois tokens separados ("4302" e "74"), nenhum dos dois batendo com o valor
real -- por isso a mesma resposta correta era rebaixada para nao_sei."""

_ANOS_PLAUSIVEIS = range(2000, 2101)


def _normalizar_numero_pt(bruto: str) -> float:
    """Aceita separador decimal de virgula OU ponto -- o separador decimal e
    sempre o ULTIMO da string, desde que seguido de 1-2 digitos (senao e
    separador de milhar). '1.204,55' -> 1204.55 ; '12,4' -> 12.4 ;
    '4302.74' -> 4302.74 ; '98.80' -> 98.8 ; '12.000' -> 12000.0 (milhar,
    3 digitos apos o separador) ; '300' -> 300.0"""
    texto = bruto.strip()
    casamento = re.search(r"[.,](\d{1,2})$", texto)
    if casamento:
        parte_decimal = casamento.group(1)
        parte_inteira = re.sub(r"[.,]", "", texto[: casamento.start()])
        texto = f"{parte_inteira}.{parte_decimal}"
    else:
        texto = re.sub(r"[.,]", "", texto)
    return float(texto)


def extrair_afirmacoes_numericas(resposta: str) -> list[float]:
    """Todo numero mencionado no texto da resposta, normalizado. Anos
    plausiveis (2000-2100) escritos sozinhos, sem separador decimal, sao
    ignorados aqui -- aparecem tratados a parte em _valores_esperados via
    substring nas datas do resultado, para nao gerar falso positivo em
    "em julho de 2026"."""
    valores = []
    for bruto in _PADRAO_NUMERO_PT.findall(resposta):
        try:
            numero = _normalizar_numero_pt(bruto)
        except ValueError:
            continue
        if bruto.isdigit() and int(bruto) in _ANOS_PLAUSIVEIS:
            continue
        valores.append(numero)
    return valores


def _valores_esperados(resultado: ResultadoSql) -> set[float]:
    """Todo numero que legitimamente pode aparecer na resposta: os valores
    numericos das colunas do resultado, mais a contagem de linhas (uma
    contagem de linhas retornadas e uma agregacao deterministica do lado
    Python, nao uma alucinacao do modelo)."""
    esperados: set[float] = {float(len(resultado.linhas)), 0.0}
    # 0.0 sempre permitido: SUM/COUNT/AVG sobre zero linhas casadas devolve
    # NULL em SQL, nao 0 -- mas a frase natural para isso e sempre "R$ 0,00"
    # ou "nenhuma", nunca "NULL". Sem isso, "Você não tem despesas
    # recorrentes ativas (R$ 0,00)" era rebaixado por citar um "0" que
    # nunca aparecia literalmente no resultado (o valor la e None).

    for linha in resultado.linhas:
        for valor in linha.values():
            if isinstance(valor, bool):
                continue
            if isinstance(valor, (int, float)):
                esperados.add(round(float(valor), 2))
            elif isinstance(valor, str):
                try:
                    esperados.add(round(float(valor.replace(",", ".")), 2))
                except ValueError:
                    pass
            else:  # Decimal, date, datetime
                try:
                    esperados.add(round(float(valor), 2))
                except (TypeError, ValueError):
                    pass

    return esperados


def _numeros_da_pergunta(pergunta: str) -> set[float]:
    """Numeros que o proprio USUARIO escreveu na pergunta (ex.: "ultimos 3
    meses", "compras acima de R$ 5.000") sao seguros para o modelo ecoar de
    volta na resposta -- nao sao uma afirmacao sobre o resultado, sao so a
    resposta repetindo o que foi perguntado. Achado ao vivo: "Qual a media
    de gastos dos ultimos 3 meses em luz?" -> resposta mencionando "3
    meses" era rebaixada porque o "3" nao aparecia em lugar nenhum do
    resultado (a consulta, correta ou nao, nunca devolve o "3" que so
    existe como parametro de filtro, nao como coluna de saida)."""
    valores = set()
    for bruto in _PADRAO_NUMERO_PT.findall(pergunta or ""):
        try:
            valores.add(_normalizar_numero_pt(bruto))
        except ValueError:
            continue
    return valores


def checar_afirmacoes(
    resposta: str, resultado: ResultadoSql | None, pergunta: str = "", tolerancia: float = 0.01
) -> list[str]:
    """Devolve, formatados como string, os numeros citados na resposta que
    NAO estao no resultado real -- lista vazia significa que toda afirmacao
    numerica e rastreavel. Chamador decide o que fazer com isso (rebaixar
    para 'nao_sei').

    Anos plausiveis (2000-2100) escritos sozinhos, sem separador decimal ou
    de milhar, NUNCA sao sinalizados -- o periodo da pergunta e estabelecido
    pela sondagem/chamada 1, nao precisa estar como coluna no resultado (uma
    consulta de SUM(valor) GROUP BY categoria, por exemplo, nao traz nenhuma
    coluna de data, mas "em julho de 2026" continua uma afirmacao legitima).
    Numeros que ja apareciam na PERGUNTA tambem nunca sao sinalizados -- ver
    _numeros_da_pergunta.
    """
    if resultado is None:
        numeros = extrair_afirmacoes_numericas(resposta)
        return [f"{n:g}" for n in numeros] if numeros else []

    esperados = _valores_esperados(resultado) | _numeros_da_pergunta(pergunta)
    nao_suportados = []

    for bruto in _PADRAO_NUMERO_PT.findall(resposta):
        if bruto.isdigit() and int(bruto) in _ANOS_PLAUSIVEIS:
            continue
        try:
            numero = _normalizar_numero_pt(bruto)
        except ValueError:
            continue
        if any(abs(numero - esperado) <= tolerancia for esperado in esperados):
            continue
        nao_suportados.append(bruto)

    return nao_suportados


# ==================== leitura "média mensal" vs "por lançamento" ====================

_PADRAO_MEDIA = re.compile(r"\bm[eé]dia\b", re.IGNORECASE)
_PADRAO_POR_LANCAMENTO = re.compile(
    r"\bpor (compra|lan[cç]amento|transa[cç][aã]o)\b|\bcada vez\b", re.IGNORECASE
)

_SUGESTAO_LEITURA_MENSAL = (
    'a pergunta pede "média" sobre um período -- a leitura padrão (ver prompts.py e '
    "avaliacao/gabarito/perguntas.jsonl q56) é MENSAL: somar por mês, depois tirar a média dos "
    "totais mensais. A consulta gerada calculou AVG diretamente sobre os lançamentos individuais, "
    "sem agrupar por mês antes -- isso é a leitura POR LANÇAMENTO, não a mensal. Refaça usando "
    "exatamente este formato: SELECT ROUND(AVG(total_mes), 2) AS media_mensal FROM (SELECT "
    "<ano-mes de data_competencia> AS mes, SUM(valor) AS total_mes FROM vw_despesas_reconciliadas "
    "WHERE <mesmos filtros da pergunta> GROUP BY 1) sub"
)


def _contem_group_by(no: exp.Expression | None) -> bool:
    return no is not None and no.find(exp.Group) is not None


def checar_leitura_media_mensal(pergunta: str, arvore: exp.Expression) -> str | None:
    """Guarda-corpo determinístico para a ambiguidade "média" documentada em prompts.py: quando a
    pergunta pede "média" sobre um período, a leitura padrão é MENSAL (soma por mês, depois média
    dos totais), não AVG(valor) direto sobre cada lançamento. Achado real (ver plano desta mudança):
    modelos pequenos as vezes declaram a premissa "leitura mensal" mas geram SQL para a leitura
    contrária -- por isso esta checagem olha só a FORMA do SQL de fato executado, nunca o texto da
    premissa declarada pelo modelo.

    Devolve None quando não há nada a checar (pergunta não menciona "média", ou pede
    explicitamente a leitura por lançamento -- "por compra", "por lançamento", "cada vez") ou uma
    string com a divergência encontrada e a correção esperada, para o chamador decidir o que fazer
    (servico.py: pedir uma segunda tentativa ao modelo com essa nota anexada).
    """
    if not _PADRAO_MEDIA.search(pergunta or ""):
        return None
    if _PADRAO_POR_LANCAMENTO.search(pergunta or ""):
        return None

    ctes_com_group_by = {
        cte.alias_or_name.lower() for cte in arvore.find_all(exp.CTE) if _contem_group_by(cte.this)
    }

    for media in arvore.find_all(exp.Avg):
        select_pai = media.find_ancestor(exp.Select)
        if select_pai is None:
            continue
        fonte = select_pai.args.get("from_")  # sqlglot 30.x usa "from_" (nao "from") como chave
        origem = fonte.this if fonte is not None else None
        if isinstance(origem, exp.Subquery) and _contem_group_by(origem.this):
            continue
        if isinstance(origem, exp.Table) and (origem.name or "").lower() in ctes_com_group_by:
            continue
        return _SUGESTAO_LEITURA_MENSAL

    return None


def checar_resultado_sem_dados(resultado: ResultadoSql | None, arvore: exp.Expression | None) -> bool:
    """Devolve True quando o resultado real, apesar de a consulta ter rodado sem erro, na verdade
    nao tem dado nenhum -- em dois formatos possiveis:

    1. Lista vazia -- consultas sem agregado escalar no topo (ranking, filtro sem GROUP BY) nao
       devolvem nenhuma linha quando nada casa com o filtro.
    2. Uma unica linha com TODOS os valores None -- um agregado escalar (sem GROUP BY na consulta
       mais externa) sobre zero linhas de origem sempre devolve exatamente UMA linha, nunca lista
       vazia -- e' assim que agregacao funciona em SQL. Achado real (ver plano da mudanca): a
       consulta de "media mensal" (AVG por fora de uma subconsulta com GROUP BY por mes) sobre um
       periodo sem nenhum lancamento devolve `[{"media_mensal": None}]`, nao `[]`.

       SUM/COUNT nesse mesmo formato (uma linha, valor None) TEM uma leitura natural de
       "R$0,00"/"nenhuma" -- ja e' o comportamento aceito em checar_afirmacoes (SUM sobre zero
       linhas e' uma resposta completa e correta, nao uma ausencia de dado). AVG NAO tem essa
       leitura -- "media de nada" e' indefinida, nao R$0,00 -- entao esta funcao so sinaliza esse
       formato quando a consulta usa AVG.
    """
    if resultado is None:
        return False
    if not resultado.linhas:
        return True
    if len(resultado.linhas) == 1 and all(v is None for v in resultado.linhas[0].values()):
        return arvore is not None and arvore.find(exp.Avg) is not None
    return False
