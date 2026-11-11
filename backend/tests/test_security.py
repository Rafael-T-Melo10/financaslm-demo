import pytest

from app import security


def test_configuracao_seguranca_permite_chave_padrao_em_desenvolvimento(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setattr(security, "SECRET_KEY", security.DEFAULT_SECRET_KEY)

    security.validar_configuracao_seguranca()


def test_configuracao_seguranca_recusa_chave_padrao_em_producao(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(security, "SECRET_KEY", security.DEFAULT_SECRET_KEY)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        security.validar_configuracao_seguranca()
