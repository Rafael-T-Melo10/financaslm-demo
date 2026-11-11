from datetime import date

from app.utils import intervalo_mes


def test_mes_comum():
    assert intervalo_mes(7, 2026) == (date(2026, 7, 1), date(2026, 7, 31))


def test_fevereiro_bissexto():
    assert intervalo_mes(2, 2024) == (date(2024, 2, 1), date(2024, 2, 29))


def test_fevereiro_nao_bissexto():
    assert intervalo_mes(2, 2026) == (date(2026, 2, 1), date(2026, 2, 28))


def test_dezembro_vira_ano():
    assert intervalo_mes(12, 2026) == (date(2026, 12, 1), date(2026, 12, 31))
