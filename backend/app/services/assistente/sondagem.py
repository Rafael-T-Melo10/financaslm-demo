"""ETAPA 0 do protocolo (ver plano): sondagem de cobertura determinística,
sem chamar o modelo, antes de qualquer chamada ao LLM.

Parser de período em português DELIBERADAMENTE simples -- reconhece nomes de
mês, "mês passado/atual", "ano passado/atual", "últimos N meses/anos" (janela
corrida terminando hoje, não alinhada a mês/ano civil) e ano isolado. Quando a
pergunta não casa com nenhum desses padrões, a sondagem simplesmente não
antecipa nada: o modelo decide o período sozinho na chamada 1, e a
verificação de cobertura acontece só quando a consulta dele rodar.

Quando um período FICA explícito e a sondagem mostra zero linhas para ele,
o veredito "nao_sei" é decidido aqui, em Python, sem gastar uma chamada ao
modelo -- menos latência e menos superfície de alucinação (o modelo nunca
vê um resultado vazio para "inventar" uma resposta em cima dele).
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

from dateutil.relativedelta import relativedelta

from app.services.assistente.execucao_sql import ResultadoSql, executar
from app.services.assistente.validador import validar

_MESES_PT = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}


@dataclass(frozen=True)
class PeriodoDetectado:
    inicio: date
    fim: date
    rotulo: str


@dataclass(frozen=True)
class ResultadoSondagem:
    periodo: PeriodoDetectado | None
    contagem: int | None
    data_min: str | None
    data_max: str | None
    veredito_antecipado: str | None
    """'nao_sei' quando um periodo explicito nao tem nenhum dado -- servico.py
    encerra aqui, sem chamar o modelo."""
    resumo_texto: str
    """Bloco pronto para o placeholder {sondagem_resultado} dos dois prompts."""


def _ultimo_dia(ano: int, mes: int) -> int:
    return calendar.monthrange(ano, mes)[1]


def _periodo_mes(ano: int, mes: int, rotulo: str) -> PeriodoDetectado:
    return PeriodoDetectado(
        inicio=date(ano, mes, 1),
        fim=date(ano, mes, _ultimo_dia(ano, mes)),
        rotulo=rotulo,
    )


def _periodo_ano(ano: int, rotulo: str) -> PeriodoDetectado:
    return PeriodoDetectado(inicio=date(ano, 1, 1), fim=date(ano, 12, 31), rotulo=rotulo)


def _periodo_ultimos(hoje: date, n: int, unidade: str, rotulo: str) -> PeriodoDetectado:
    """Janela CORRIDA terminando hoje -- ao contrario de _periodo_mes/_periodo_ano, NAO alinha a
    limite de mes/ano civil. "ultimos N meses" no gabarito (avaliacao/gabarito/perguntas.jsonl,
    q23/q51-q58) e definido como data_competencia >= CURRENT_DATE - INTERVAL 'N months', sem teto
    alem de hoje -- replicado aqui via relativedelta para casar com a mesma semantica."""
    delta = relativedelta(years=n) if unidade == "ano" else relativedelta(months=n)
    return PeriodoDetectado(inicio=hoje - delta, fim=hoje, rotulo=rotulo)


def extrair_periodo(pergunta: str, hoje: date) -> PeriodoDetectado | None:
    """Melhor esforco, nao exaustivo -- ver docstring do modulo."""
    texto = (pergunta or "").lower()

    casamento_ultimos = re.search(r"\b[uú]ltimos?\s+(\d+)\s+(m[eê]s|meses|anos?)\b", texto)
    if casamento_ultimos:
        n = int(casamento_ultimos.group(1))
        unidade_bruta = casamento_ultimos.group(2)
        unidade = "ano" if unidade_bruta.startswith("ano") else "mes"
        if n > 0:
            rotulo_unidade = "ano" if unidade == "ano" and n == 1 else (
                "anos" if unidade == "ano" else ("mês" if n == 1 else "meses")
            )
            return _periodo_ultimos(hoje, n, unidade, f"últimos {n} {rotulo_unidade}")

    if re.search(r"\bm[eê]s passado\b", texto):
        referencia = hoje - relativedelta(months=1)
        return _periodo_mes(referencia.year, referencia.month, f"mês passado ({referencia.strftime('%m/%Y')})")

    _QUALIFICADOR_ATUAL = r"(?:este|esse|nesse|neste|desse|deste|no)"

    if re.search(rf"\b{_QUALIFICADOR_ATUAL} m[eê]s\b|\bm[eê]s atual\b", texto):
        return _periodo_mes(hoje.year, hoje.month, f"mês atual ({hoje.strftime('%m/%Y')})")

    if re.search(r"\bano passado\b", texto):
        return _periodo_ano(hoje.year - 1, f"ano passado ({hoje.year - 1})")

    if re.search(rf"\b{_QUALIFICADOR_ATUAL} ano\b|\bano atual\b", texto):
        return _periodo_ano(hoje.year, f"ano atual ({hoje.year})")

    for nome_mes, numero_mes in _MESES_PT.items():
        padrao = rf"\b{nome_mes}\b(?:\s*(?:de|/)\s*(\d{{4}}))?"
        casamento = re.search(padrao, texto)
        if casamento:
            ano = int(casamento.group(1)) if casamento.group(1) else hoje.year
            return _periodo_mes(ano, numero_mes, f"{nome_mes} de {ano}")

    casamento_ano = re.search(r"\bem (\d{4})\b|\bano de (\d{4})\b", texto)
    if casamento_ano:
        ano = int(casamento_ano.group(1) or casamento_ano.group(2))
        if 2000 <= ano <= 2100:
            return _periodo_ano(ano, f"ano de {ano}")

    return None


def _resumo_sem_periodo() -> str:
    return (
        "Nenhum período específico foi identificado na pergunta antes da chamada ao "
        "modelo -- decida o período pela própria pergunta, dentro do SQL que você gerar."
    )


def sondar(pergunta: str, usuario_id: int, dialeto: str, hoje: date | None = None) -> ResultadoSondagem:
    """Roda um COUNT/MIN/MAX contra vw_despesas_reconciliadas, ja isolado por
    usuario pelo mesmo mecanismo de sombreamento de execucao_sql.py -- a
    sondagem NAO e um caminho de execucao separado, e o SQL de sempre.
    """
    hoje = hoje or date.today()
    periodo = extrair_periodo(pergunta, hoje)

    if periodo is None:
        return ResultadoSondagem(
            periodo=None, contagem=None, data_min=None, data_max=None,
            veredito_antecipado=None, resumo_texto=_resumo_sem_periodo(),
        )

    sql = (
        "SELECT COUNT(*) AS contagem, MIN(data_competencia) AS data_min, "
        "MAX(data_competencia) AS data_max FROM vw_despesas_reconciliadas "
        f"WHERE data_competencia BETWEEN '{periodo.inicio.isoformat()}' AND '{periodo.fim.isoformat()}'"
    )
    sql_validado = validar(sql, dialeto)
    resultado: ResultadoSql = executar(sql_validado, usuario_id, limite_linhas=1)
    linha = resultado.linhas[0] if resultado.linhas else {}
    contagem = int(linha.get("contagem") or 0)
    data_min = linha.get("data_min")
    data_max = linha.get("data_max")

    veredito_antecipado = "nao_sei" if contagem == 0 else None

    resumo = (
        f"Período identificado na pergunta: {periodo.rotulo} "
        f"({periodo.inicio.isoformat()} a {periodo.fim.isoformat()}). "
        f"Sondagem contra vw_despesas_reconciliadas para esse período: "
        f"contagem={contagem}, data_min={data_min}, data_max={data_max}."
    )
    if veredito_antecipado:
        resumo += " Nenhum lançamento existe nesse período -- não é possível responder."

    return ResultadoSondagem(
        periodo=periodo, contagem=contagem, data_min=data_min, data_max=data_max,
        veredito_antecipado=veredito_antecipado, resumo_texto=resumo,
    )
