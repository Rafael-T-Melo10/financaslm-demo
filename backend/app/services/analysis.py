from datetime import datetime, date
from typing import List, Dict, Any
from collections import defaultdict
import unicodedata

from dateutil.relativedelta import relativedelta

from app.utils import intervalo_mes

def calcular_analise_gastos(receitas: List, despesas: List, cartoes: List, parcelas: List, mes: int = None, ano: int = None) -> Dict[str, Any]:
    """
    Calcula análise completa de gastos
    """

    # Filtrar por período se especificado
    if mes and ano:
        primeiro_dia, ultimo_dia = intervalo_mes(mes, ano)

        receitas = [r for r in receitas if primeiro_dia <= r.data <= ultimo_dia]
        despesas = [d for d in despesas if primeiro_dia <= d.data <= ultimo_dia]

    # Calcular totais
    total_receitas = float(sum(r.valor for r in receitas))
    total_despesas = float(sum(d.valor for d in despesas))
    saldo = total_receitas - total_despesas

    # Despesas por categoria
    despesas_por_categoria = defaultdict(float)
    for despesa in despesas:
        despesas_por_categoria[despesa.categoria] += float(despesa.valor)

    # Gastos mensais
    gastos_mensais = calcular_gastos_mensais(despesas)

    # Informações dos cartões
    cartoes_info = []
    for cartao in cartoes:
        limite = float(cartao.limite or 0)
        saldo_usado = float(cartao.saldo_usado or 0)
        cartoes_info.append({
            "id": cartao.id,
            "nome": cartao.nome,
            "saldo_usado": saldo_usado,
            "saldo_disponivel": limite - saldo_usado,
            "limite": limite,
            "percentual_uso": (saldo_usado / limite * 100) if limite else 0,
            "ativo": cartao.ativo
        })

    # Previsão futura
    previsao = calcular_previsao_basica(despesas, parcelas)

    return {
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "saldo": saldo,
        "despesas_por_categoria": dict(despesas_por_categoria),
        "gastos_mensais": gastos_mensais,
        "cartoes_info": cartoes_info,
        "previsao_futura": previsao
    }

def calcular_gastos_mensais(despesas: List) -> Dict[str, float]:
    """Calcula gastos por mês (chaves no formato YYYY-MM)"""
    gastos = defaultdict(float)

    for despesa in despesas:
        mes_ano = despesa.data.strftime("%Y-%m")
        gastos[mes_ano] += float(despesa.valor)

    return dict(gastos)

def calcular_previsao_basica(despesas: List, parcelas: List) -> Dict[str, Any]:
    """Calcula previsão básica de gastos futuros"""

    if not despesas:
        return {
            "media_mensal": 0,
            "previsao_proximos_3_meses": []
        }

    gastos_por_mes = calcular_gastos_mensais(despesas)
    media_mensal = sum(gastos_por_mes.values()) / len(gastos_por_mes) if gastos_por_mes else 0

    # Previsão para próximos 3 meses
    previsao_proximos_3_meses = []
    hoje = date.today()

    for i in range(1, 4):
        mes_futuro = hoje + relativedelta(months=i)

        parcelas_mes = float(sum(
            p.valor_parcela for p in parcelas
            if p.data_proxima_parcela.month == mes_futuro.month
            and p.data_proxima_parcela.year == mes_futuro.year
            and not p.pago
        ))

        previsao_proximos_3_meses.append({
            "mes": mes_futuro.strftime("%Y-%m"),
            "media_gastos": media_mensal,
            "parcelas_previstas": parcelas_mes,
            "total_estimado": media_mensal + parcelas_mes
        })

    return {
        "media_mensal": media_mensal,
        "previsao_proximos_3_meses": previsao_proximos_3_meses
    }

def previsao_gastos(despesas: List, parcelas: List, meses: int = 3) -> Dict[str, Any]:
    """
    Gera previsão de gastos para os próximos meses
    """

    # Média mensal por categoria: agrupa por (categoria, mês) e tira a média
    # entre os meses — média por transação distorceria a previsão.
    totais_categoria_mes = defaultdict(lambda: defaultdict(float))
    for despesa in despesas:
        mes_ano = despesa.data.strftime("%Y-%m")
        totais_categoria_mes[despesa.categoria][mes_ano] += float(despesa.valor)

    media_por_categoria = {
        categoria: sum(por_mes.values()) / len(por_mes)
        for categoria, por_mes in totais_categoria_mes.items()
        if por_mes
    }

    # Gerar previsão
    previsao = []
    hoje = date.today()

    for i in range(1, meses + 1):
        mes_futuro = hoje + relativedelta(months=i)

        total_parcelas = float(sum(
            p.valor_parcela for p in parcelas
            if p.data_proxima_parcela.month == mes_futuro.month
            and p.data_proxima_parcela.year == mes_futuro.year
            and not p.pago
        ))

        total_categorias = sum(media_por_categoria.values())

        previsao.append({
            "mes": mes_futuro.strftime("%Y-%m"),
            "previsao_categorias": media_por_categoria,
            "total_estimado_despesas": total_categorias,
            "total_parcelas": total_parcelas,
            "gasto_total_previsto": total_categorias + total_parcelas,
            "data": mes_futuro.isoformat()
        })

    return {
        "previsao": previsao,
        "data_geracao": datetime.now().isoformat()
    }


def _chave_mes(valor: date) -> str:
    return valor.strftime("%Y-%m")


def _inicio_mes(valor: date) -> date:
    return valor.replace(day=1)


def _proximo_mes(valor: date) -> date:
    return _inicio_mes(valor + relativedelta(months=1))


def _periodo_anterior(mes: int, ano: int, deslocamento: int = 1) -> tuple[int, int]:
    referencia = date(ano, mes, 1) - relativedelta(months=deslocamento)
    return referencia.month, referencia.year


def _valor_despesas_no_periodo(despesas: List, mes: int, ano: int, dia_limite: int | None = None) -> float:
    inicio, fim = intervalo_mes(mes, ano)
    if dia_limite:
        fim = min(fim, inicio.replace(day=min(dia_limite, fim.day)))
    return float(sum(float(item.valor) for item in despesas if inicio <= item.data <= fim))


CATEGORIAS_DASHBOARD = {
    "alimentacao": "Alimentação",
    "transporte": "Transporte",
    "saude": "Saúde",
    "educacao": "Educação",
    "lazer": "Lazer",
    "diversao": "Lazer",
    "moradia": "Moradia",
    "assinaturas": "Assinaturas",
    "roupas": "Roupas",
    "vestuario": "Roupas",
    "impostos": "Impostos",
    "cartao de credito": "Cartão de Crédito",
    "ajustes": "Ajustes da fatura",
    "ajustes da fatura": "Ajustes da fatura",
    "outros": "Outros",
}


def _normalizar_categoria_dashboard(categoria: str | None) -> str:
    texto = str(categoria or "Outros").strip()
    chave = "".join(
        caractere for caractere in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caractere) != "Mn"
    ).lower()
    return CATEGORIAS_DASHBOARD.get(chave, texto or "Outros")


def _eh_ajuste_categoria(categoria: str) -> bool:
    return _normalizar_categoria_dashboard(categoria) == "Ajustes da fatura"


def _categorias_do_periodo(despesas: List, faturas: List, mes: int, ano: int) -> Dict[str, float]:
    """Agrupa despesas sem contar a fatura e seus itens duas vezes."""
    inicio, fim = intervalo_mes(mes, ano)
    faturas_por_despesa = {
        fatura.despesa_id: fatura
        for fatura in faturas
        if fatura.despesa_id and inicio <= fatura.data_referencia <= fim
    }
    totais = defaultdict(float)

    for despesa in despesas:
        if not inicio <= despesa.data <= fim:
            continue

        fatura = faturas_por_despesa.get(despesa.id)
        if not fatura or not fatura.itens:
            totais[_normalizar_categoria_dashboard(despesa.categoria)] += float(despesa.valor)
            continue

        total_itens = 0.0
        for item in fatura.itens:
            valor = float(item.valor)
            totais[_normalizar_categoria_dashboard(item.categoria)] += valor
            total_itens += valor

        ajuste = float(despesa.valor) - total_itens
        if abs(ajuste) >= 0.01:
            totais[_normalizar_categoria_dashboard("Ajustes da fatura")] += ajuste

    return dict(totais)


def _compromissos_de_parcelas(parcelas: List, inicio: date, fim: date) -> List[Dict[str, Any]]:
    compromissos = []
    for parcela in parcelas:
        if parcela.pago or parcela.parcelas_restantes <= 0:
            continue
        vencimento = parcela.data_proxima_parcela
        for indice in range(int(parcela.parcelas_restantes)):
            if inicio <= vencimento <= fim:
                compromissos.append({
                    "id": f"parcela-{parcela.id}-{indice}",
                    "tipo": "Parcela",
                    "descricao": parcela.descricao,
                    "data": vencimento.isoformat(),
                    "valor": float(parcela.valor_parcela),
                    "contabilizado": False,
                    "rota": "/parcelas",
                })
            vencimento = vencimento + relativedelta(months=1)
    return compromissos


def _compromissos_de_recorrencias(recorrentes: List, inicio: date, fim: date) -> List[Dict[str, Any]]:
    """Inclui recorrências futuras que ainda não foram materializadas como despesa."""
    hoje = date.today()
    if fim < _inicio_mes(hoje):
        return []

    compromissos = []
    for recorrente in recorrentes:
        if not recorrente.ativo or recorrente.data_inicio > fim:
            continue
        ultima_geracao = _inicio_mes(recorrente.ultima_geracao) if recorrente.ultima_geracao else None
        if ultima_geracao and ultima_geracao >= inicio:
            continue
        dia = min(recorrente.dia_vencimento, fim.day)
        vencimento = inicio.replace(day=dia)
        if vencimento >= recorrente.data_inicio:
            compromissos.append({
                "id": f"recorrente-{recorrente.id}-{_chave_mes(inicio)}",
                "tipo": "Recorrente",
                "descricao": recorrente.descricao,
                "data": vencimento.isoformat(),
                "valor": float(recorrente.valor),
                "contabilizado": False,
                "rota": "/recorrentes",
            })
    return compromissos


def montar_dashboard(
    receitas: List,
    despesas: List,
    faturas: List,
    cartoes: List,
    parcelas: List,
    recorrentes: List,
    orcamentos: List[Dict[str, Any]],
    mes: int,
    ano: int,
) -> Dict[str, Any]:
    """Monta uma visão mensal consistente para o dashboard financeiro."""
    inicio, fim = intervalo_mes(mes, ano)
    hoje = date.today()
    chave_periodo = _chave_mes(inicio)
    status_periodo = "atual" if inicio <= hoje <= fim else ("passado" if fim < hoje else "futuro")

    receitas_periodo = [item for item in receitas if inicio <= item.data <= fim]
    despesas_periodo = [item for item in despesas if inicio <= item.data <= fim]
    total_receitas = float(sum(float(item.valor) for item in receitas_periodo))
    total_despesas = float(sum(float(item.valor) for item in despesas_periodo))

    compromissos = _compromissos_de_parcelas(parcelas, inicio, fim)
    compromissos += _compromissos_de_recorrencias(recorrentes, inicio, fim)
    for fatura in faturas:
        if inicio <= fatura.data_referencia <= fim and fatura.vencimento:
            compromissos.append({
                "id": f"fatura-{fatura.id}",
                "tipo": "Fatura",
                "descricao": fatura.descricao or "Fatura do cartão",
                "data": fatura.vencimento.isoformat(),
                "valor": float(fatura.valor_total),
                "contabilizado": True,
                "rota": "/cartoes",
            })

    compromissos.sort(key=lambda item: item["data"])
    compromissos_pendentes = float(sum(item["valor"] for item in compromissos if not item["contabilizado"]))
    despesas_projetadas = total_despesas + compromissos_pendentes
    saldo_lancado = total_receitas - total_despesas
    saldo_projetado = total_receitas - despesas_projetadas
    taxa_economia = (saldo_projetado / total_receitas * 100) if total_receitas else None

    comparacao_anterior = None
    comparacao_media = None
    if status_periodo != "futuro":
        corte = hoje.day if status_periodo == "atual" else None
        total_comparavel = _valor_despesas_no_periodo(despesas, mes, ano, corte)
        mes_anterior, ano_anterior = _periodo_anterior(mes, ano)
        anterior = _valor_despesas_no_periodo(despesas, mes_anterior, ano_anterior, corte)
        if anterior:
            comparacao_anterior = (total_comparavel - anterior) / anterior * 100

        base_media = []
        for deslocamento in range(1, 4):
            mes_base, ano_base = _periodo_anterior(mes, ano, deslocamento)
            base_media.append(_valor_despesas_no_periodo(despesas, mes_base, ano_base, corte))
        media = sum(base_media) / len(base_media) if base_media else 0
        if media:
            comparacao_media = (total_comparavel - media) / media * 100

    categorias_atual = _categorias_do_periodo(despesas, faturas, mes, ano)
    mes_anterior, ano_anterior = _periodo_anterior(mes, ano)
    categorias_anterior = _categorias_do_periodo(despesas, faturas, mes_anterior, ano_anterior)
    categorias_media = defaultdict(list)
    for deslocamento in range(1, 4):
        mes_base, ano_base = _periodo_anterior(mes, ano, deslocamento)
        for categoria, valor in _categorias_do_periodo(despesas, faturas, mes_base, ano_base).items():
            categorias_media[categoria].append(valor)

    total_categorias = sum(
        valor for nome, valor in categorias_atual.items()
        if valor > 0 and not _eh_ajuste_categoria(nome)
    )
    categorias = []
    for nome in categorias_atual:
        valor = float(categorias_atual.get(nome, 0))
        if abs(valor) < 0.01:
            continue
        anterior = float(categorias_anterior.get(nome, 0))
        media = float(sum(categorias_media.get(nome, [])) / len(categorias_media[nome])) if categorias_media.get(nome) else 0
        categorias.append({
            "nome": nome,
            "valor": valor,
            "percentual": (valor / total_categorias * 100) if total_categorias and valor > 0 and not _eh_ajuste_categoria(nome) else None,
            "eh_ajuste": _eh_ajuste_categoria(nome),
            "anterior": anterior,
            "variacao_anterior": ((valor - anterior) / anterior * 100) if anterior and status_periodo != "futuro" else None,
            "media_3_meses": media,
            "variacao_media": ((valor - media) / media * 100) if media and status_periodo != "futuro" else None,
        })
    categorias.sort(key=lambda item: item["valor"], reverse=True)

    orcamentos_dashboard = []
    for orcamento in orcamentos:
        categoria_orcamento = _normalizar_categoria_dashboard(orcamento["categoria"])
        gasto = float(categorias_atual.get(categoria_orcamento, 0))
        limite = float(orcamento["limite"])
        percentual = gasto / limite * 100 if limite else 0
        orcamentos_dashboard.append({
            "categoria": categoria_orcamento,
            "limite": limite,
            "gasto": gasto,
            "percentual": percentual,
            "status": "critico" if percentual >= 100 else ("atencao" if percentual >= 80 else "ok"),
        })
    orcamentos_dashboard.sort(key=lambda item: item["percentual"], reverse=True)

    evolucao = []
    referencia = inicio
    for deslocamento in range(11, -1, -1):
        mes_base = referencia - relativedelta(months=deslocamento)
        receitas_mes = float(sum(float(item.valor) for item in receitas if item.data.year == mes_base.year and item.data.month == mes_base.month))
        despesas_mes = float(sum(float(item.valor) for item in despesas if item.data.year == mes_base.year and item.data.month == mes_base.month))
        evolucao.append({
            "periodo": _chave_mes(mes_base),
            "receitas": receitas_mes,
            "despesas": despesas_mes,
            "saldo": receitas_mes - despesas_mes,
        })

    projecao_compromissos = []
    for deslocamento in range(6):
        periodo = inicio + relativedelta(months=deslocamento)
        proximo_inicio, proximo_fim = intervalo_mes(periodo.month, periodo.year)
        parcelas_mes = _compromissos_de_parcelas(parcelas, proximo_inicio, proximo_fim)
        recorrentes_mes = _compromissos_de_recorrencias(recorrentes, proximo_inicio, proximo_fim)
        projecao_compromissos.append({
            "periodo": _chave_mes(periodo),
            "parcelas": float(sum(item["valor"] for item in parcelas_mes)),
            "recorrentes": float(sum(item["valor"] for item in recorrentes_mes)),
            "total": float(sum(item["valor"] for item in parcelas_mes + recorrentes_mes)),
        })

    ultima_fatura_por_cartao = {}
    for fatura in sorted(faturas, key=lambda item: item.data_referencia, reverse=True):
        ultima_fatura_por_cartao.setdefault(fatura.cartao_id, fatura)
    cartoes_dashboard = []
    for cartao in cartoes:
        limite = float(cartao.limite or 0)
        usado = float(cartao.saldo_usado or 0)
        ultima = ultima_fatura_por_cartao.get(cartao.id)
        cartoes_dashboard.append({
            "id": cartao.id,
            "nome": cartao.nome,
            "limite": limite,
            "usado": usado,
            "disponivel": max(limite - usado, 0),
            "percentual_uso": usado / limite * 100 if limite else 0,
            "atualizado_em": ultima.data_referencia.isoformat() if ultima else None,
        })
    cartoes_dashboard.sort(key=lambda item: item["percentual_uso"], reverse=True)

    alertas = []
    if saldo_projetado < 0:
        alertas.append({"chave": f"financeiro:deficit:{chave_periodo}", "escopo": "No mês selecionado", "severidade": "critical", "titulo": "Déficit projetado", "mensagem": f"Os compromissos cadastrados deixam o mês com déficit de R$ {abs(saldo_projetado):.2f}.", "rota": "/despesas"})
    if comparacao_anterior is not None and comparacao_anterior > 20:
        alertas.append({"chave": f"financeiro:gastos-alta:{chave_periodo}", "escopo": "No mês selecionado", "severidade": "warning", "titulo": "Gastos em alta", "mensagem": f"As despesas estão {comparacao_anterior:.0f}% acima do mês anterior.", "rota": "/despesas"})

    orcamentos_em_alerta = [item for item in orcamentos_dashboard if item["percentual"] >= 80]
    if orcamentos_em_alerta:
        criticos = [item for item in orcamentos_em_alerta if item["percentual"] >= 100]
        destaques = ", ".join(f"{item['categoria']} ({item['percentual']:.0f}%)" for item in orcamentos_em_alerta[:3])
        complemento = f" e mais {len(orcamentos_em_alerta) - 3}" if len(orcamentos_em_alerta) > 3 else ""
        alertas.append({
            "chave": f"financeiro:orcamentos:{chave_periodo}",
            "escopo": "No mês selecionado",
            "severidade": "critical" if criticos else "warning",
            "titulo": "Orçamentos precisam de atenção",
            "mensagem": f"{destaques}{complemento}.",
            "rota": "/",
        })

    cartoes_em_alerta = [cartao for cartao in cartoes_dashboard if cartao["percentual_uso"] >= 60]
    if cartoes_em_alerta:
        maior_uso = max(cartoes_em_alerta, key=lambda item: item["percentual_uso"])
        alertas.append({
            "chave": "financeiro:cartoes",
            "escopo": "Situação atual",
            "severidade": "critical" if maior_uso["percentual_uso"] >= 80 else "warning",
            "titulo": "Uso de cartão elevado",
            "mensagem": f"{len(cartoes_em_alerta)} cartão(ões) acima de 60% do limite; {maior_uso['nome']} está em {maior_uso['percentual_uso']:.0f}%.",
            "rota": "/cartoes",
        })

    parcelas_vencidas = []
    parcelas_proximas = []
    for parcela in parcelas:
        if parcela.pago:
            continue
        dias = (parcela.data_proxima_parcela - hoje).days
        if dias < 0:
            parcelas_vencidas.append(parcela)
        elif dias <= 7:
            parcelas_proximas.append(parcela)

    if parcelas_vencidas:
        total_vencido = sum(float(item.valor_parcela) for item in parcelas_vencidas)
        alertas.append({
            "chave": "financeiro:parcelas-vencidas",
            "escopo": "Situação atual",
            "severidade": "critical",
            "titulo": "Parcelas vencidas",
            "mensagem": f"{len(parcelas_vencidas)} parcela(s) vencida(s), totalizando R$ {total_vencido:.2f}.",
            "rota": "/parcelas",
        })
    if parcelas_proximas:
        total_proximo = sum(float(item.valor_parcela) for item in parcelas_proximas)
        alertas.append({
            "chave": "financeiro:parcelas-proximas",
            "escopo": "Situação atual",
            "severidade": "warning",
            "titulo": "Parcelas vencem em até 7 dias",
            "mensagem": f"{len(parcelas_proximas)} parcela(s), totalizando R$ {total_proximo:.2f}.",
            "rota": "/parcelas",
        })
    ordem_alertas = {"critical": 0, "warning": 1, "info": 2}
    alertas.sort(key=lambda item: ordem_alertas[item["severidade"]])

    faturas_por_despesa = {fatura.despesa_id: fatura for fatura in faturas if fatura.despesa_id}
    movimentacoes = []
    for receita in receitas_periodo:
        movimentacoes.append({"id": f"receita-{receita.id}", "tipo": "Receita", "data": receita.data.isoformat(), "descricao": receita.descricao, "categoria": None, "origem": receita.origem, "valor": float(receita.valor), "fatura_itens": []})
    for despesa in despesas_periodo:
        fatura = faturas_por_despesa.get(despesa.id)
        movimentacoes.append({
            "id": f"despesa-{despesa.id}", "tipo": "Despesa", "data": despesa.data.isoformat(), "descricao": despesa.descricao,
            "categoria": despesa.categoria, "origem": despesa.origem, "valor": float(despesa.valor),
            "fatura_itens": [{"descricao": item.descricao, "categoria": item.categoria, "data": item.data.isoformat(), "valor": float(item.valor)} for item in (fatura.itens if fatura else [])],
        })
    movimentacoes.sort(key=lambda item: (item["data"], item["tipo"]), reverse=True)

    periodos_com_movimento = [item.data for item in receitas + despesas] + [item.data_referencia for item in faturas]
    ultimo_periodo = _chave_mes(max(periodos_com_movimento)) if periodos_com_movimento else None

    return {
        "periodo": {"referencia": chave_periodo, "status": status_periodo, "ultimo_periodo_com_movimento": ultimo_periodo},
        "resumo": {"receitas": total_receitas, "despesas_lancadas": total_despesas, "saldo_lancado": saldo_lancado, "compromissos_pendentes": compromissos_pendentes, "despesas_projetadas": despesas_projetadas, "saldo_projetado": saldo_projetado, "taxa_economia_projetada": taxa_economia, "comparacao_mes_anterior": comparacao_anterior, "comparacao_media_3_meses": comparacao_media},
        "evolucao": evolucao,
        "categorias": categorias,
        "orcamentos": orcamentos_dashboard,
        "projecao_compromissos": projecao_compromissos,
        "compromissos": compromissos,
        "cartoes": cartoes_dashboard,
        "movimentacoes": movimentacoes,
        "alertas": alertas,
    }

def gerar_alertas(receitas: List, despesas: List, cartoes: List, parcelas: List) -> List[Dict[str, str]]:
    """Gera alertas sobre situação financeira"""
    alertas = []

    # Alerta: Saldo negativo
    total_receitas = float(sum(r.valor for r in receitas))
    total_despesas = float(sum(d.valor for d in despesas))
    if total_despesas > total_receitas:
        diferenca = total_despesas - total_receitas
        alertas.append({
            "tipo": "AVISO",
            "mensagem": f"Seus gastos excedem suas receitas em R$ {diferenca:.2f}"
        })

    # Alerta: Cartão com alto saldo
    for cartao in cartoes:
        if cartao.limite:
            percentual = float(cartao.saldo_usado or 0) / float(cartao.limite) * 100
            if percentual > 80:
                alertas.append({
                    "tipo": "CRÍTICO",
                    "mensagem": f"Cartão {cartao.nome} com {percentual:.0f}% de utilização"
                })
            elif percentual > 60:
                alertas.append({
                    "tipo": "AVISO",
                    "mensagem": f"Cartão {cartao.nome} com {percentual:.0f}% de utilização"
                })

    # Alerta: Muitas parcelas
    parcelas_ativas = sum(1 for p in parcelas if not p.pago)
    if parcelas_ativas > 5:
        alertas.append({
            "tipo": "AVISO",
            "mensagem": f"Você tem {parcelas_ativas} parcelas ativas em aberto"
        })

    return alertas


def montar_relatorio_anual(receitas: List, despesas: List, faturas: List, ano: int) -> Dict[str, Any]:
    """Consolida o ano sem duplicar a despesa-resumo de faturas importadas."""
    meses = [{"mes": mes, "receitas": 0.0, "despesas": 0.0, "saldo": 0.0} for mes in range(1, 13)]
    categorias: Dict[str, List[float]] = {}
    estabelecimentos: Dict[str, float] = {}
    total_receitas = 0.0

    for receita in receitas:
        if receita.data.year == ano:
            valor = float(receita.valor)
            total_receitas += valor
            meses[receita.data.month - 1]["receitas"] += valor

    for despesa in despesas:
        if despesa.data.year == ano and despesa.origem != "fatura":
            valor = float(despesa.valor)
            meses[despesa.data.month - 1]["despesas"] += valor
            categorias.setdefault(despesa.categoria, [0.0] * 12)[despesa.data.month - 1] += valor

    for fatura in faturas:
        for item in fatura.itens:
            if item.data.year != ano:
                continue
            valor = float(item.valor)
            meses[item.data.month - 1]["despesas"] += valor
            categorias.setdefault(item.categoria, [0.0] * 12)[item.data.month - 1] += valor
            estabelecimentos[item.estabelecimento or item.descricao] = estabelecimentos.get(item.estabelecimento or item.descricao, 0.0) + valor

    for mes in meses:
        mes["saldo"] = mes["receitas"] - mes["despesas"]
    total_despesas = sum(item["despesas"] for item in meses)
    return {
        "ano": ano,
        "resumo": {"receitas": total_receitas, "despesas": total_despesas, "saldo": total_receitas - total_despesas, "media_mensal": total_despesas / 12, "taxa_economia": ((total_receitas - total_despesas) / total_receitas * 100) if total_receitas else 0},
        "meses": meses,
        "categorias": [{"categoria": nome, "total": sum(valores), "mensal": valores} for nome, valores in sorted(categorias.items(), key=lambda item: sum(item[1]), reverse=True)],
        "top_estabelecimentos": [{"nome": nome, "total": total} for nome, total in sorted(estabelecimentos.items(), key=lambda item: item[1], reverse=True)[:10]],
    }
