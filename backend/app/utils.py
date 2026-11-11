from datetime import date

from dateutil.relativedelta import relativedelta


def intervalo_mes(mes: int, ano: int) -> tuple[date, date]:
    """Retorna (primeiro_dia, ultimo_dia) do mês informado."""
    primeiro_dia = date(ano, mes, 1)
    ultimo_dia = primeiro_dia + relativedelta(months=1, days=-1)
    return primeiro_dia, ultimo_dia
