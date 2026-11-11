"""Testes do webhook do WhatsApp (Meta Cloud API) -- runtime do assistente e
cliente do Graph API sempre mockados (nunca fala com Ollama nem com a Meta de
verdade), mesmo padrão de monkeypatch.setattr(...) usado em test_assistente.py.
"""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from app.config import whatsapp_settings
from app.services.whatsapp import cliente, servico

_APP_SECRET = "segredo-de-teste"
_NUMERO_AUTORIZADO = "5511999998888"
_USUARIO_ID = 42


@pytest.fixture(autouse=True)
def _configurar_whatsapp(monkeypatch):
    monkeypatch.setattr(whatsapp_settings, "whatsapp_habilitado", True)
    monkeypatch.setattr(whatsapp_settings, "meta_app_secret", _APP_SECRET)
    monkeypatch.setattr(whatsapp_settings, "meta_verify_token", "verify-token-teste")
    monkeypatch.setattr(whatsapp_settings, "whatsapp_numero_autorizado", _NUMERO_AUTORIZADO)
    monkeypatch.setattr(whatsapp_settings, "whatsapp_usuario_id", _USUARIO_ID)


def _assinar(corpo: bytes) -> str:
    return "sha256=" + hmac.new(_APP_SECRET.encode("utf-8"), corpo, hashlib.sha256).hexdigest()


def _payload_mensagem(wa_id: str, texto: str) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {"messages": [{"from": wa_id, "type": "text", "text": {"body": texto}}]},
                "field": "messages",
            }],
        }],
    }


def _payload_status() -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {"statuses": [{"id": "wamid.abc", "status": "delivered"}]},
                "field": "messages",
            }],
        }],
    }


# ==================== verificar_assinatura ====================

def test_assinatura_valida():
    corpo = json.dumps({"a": 1}).encode("utf-8")
    assert servico.verificar_assinatura(corpo, _assinar(corpo)) is True


def test_assinatura_invalida():
    corpo = json.dumps({"a": 1}).encode("utf-8")
    assert servico.verificar_assinatura(corpo, "sha256=deadbeef") is False


def test_assinatura_ausente():
    corpo = json.dumps({"a": 1}).encode("utf-8")
    assert servico.verificar_assinatura(corpo, None) is False


# ==================== extrair_mensagem ====================

def test_extrair_mensagem_de_texto():
    extraido = servico.extrair_mensagem(_payload_mensagem(_NUMERO_AUTORIZADO, "Quanto gastei em julho?"))
    assert extraido == (_NUMERO_AUTORIZADO, "Quanto gastei em julho?")


def test_extrair_mensagem_ignora_status_de_entrega():
    assert servico.extrair_mensagem(_payload_status()) is None


def test_extrair_mensagem_payload_vazio():
    assert servico.extrair_mensagem({"entry": []}) is None


# ==================== processar_mensagem_em_background ====================

def test_processa_pergunta_de_numero_autorizado(monkeypatch):
    chamadas_responder = []
    chamadas_envio = []

    def _responder_fake(pergunta, usuario_id, hoje=None, modelo=None):
        chamadas_responder.append((pergunta, usuario_id))
        return {"dados": {"resposta": "Você gastou R$ 100 em julho.", "divergencia": None, "falta": None}}

    monkeypatch.setattr("app.services.assistente.servico.responder", _responder_fake)
    monkeypatch.setattr(cliente, "enviar_mensagem_texto", lambda wa_id, texto: chamadas_envio.append((wa_id, texto)) or True)

    servico.processar_mensagem_em_background(_NUMERO_AUTORIZADO, "Quanto gastei em julho?")

    assert chamadas_responder == [("Quanto gastei em julho?", _USUARIO_ID)]
    assert chamadas_envio == [(_NUMERO_AUTORIZADO, "Você gastou R$ 100 em julho.")]


def test_ignora_numero_nao_autorizado(monkeypatch):
    chamadas_envio = []
    monkeypatch.setattr(cliente, "enviar_mensagem_texto", lambda wa_id, texto: chamadas_envio.append((wa_id, texto)) or True)

    servico.processar_mensagem_em_background("5500000000000", "Quanto gastei em julho?")

    assert chamadas_envio == []


def test_erro_no_assistente_envia_mensagem_generica(monkeypatch):
    chamadas_envio = []

    def _responder_com_erro(pergunta, usuario_id, hoje=None, modelo=None):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr("app.services.assistente.servico.responder", _responder_com_erro)
    monkeypatch.setattr(cliente, "enviar_mensagem_texto", lambda wa_id, texto: chamadas_envio.append((wa_id, texto)) or True)

    servico.processar_mensagem_em_background(_NUMERO_AUTORIZADO, "Quanto gastei em julho?")

    assert len(chamadas_envio) == 1
    assert chamadas_envio[0][0] == _NUMERO_AUTORIZADO


# ==================== rotas HTTP ====================

def test_get_webhook_verifica_com_sucesso(client):
    resposta = client.get("/whatsapp/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "verify-token-teste", "hub.challenge": "12345",
    })
    assert resposta.status_code == 200
    assert resposta.text == "12345"


def test_get_webhook_rejeita_token_invalido(client):
    resposta = client.get("/whatsapp/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "token-errado", "hub.challenge": "12345",
    })
    assert resposta.status_code == 403


def test_post_webhook_rejeita_assinatura_invalida(client):
    corpo = json.dumps(_payload_mensagem(_NUMERO_AUTORIZADO, "oi")).encode("utf-8")
    resposta = client.post(
        "/whatsapp/webhook", content=corpo,
        headers={"content-type": "application/json", "x-hub-signature-256": "sha256=invalida"},
    )
    assert resposta.status_code == 403


def test_post_webhook_aceita_e_processa_em_background(client, monkeypatch):
    chamadas_envio = []
    monkeypatch.setattr(
        "app.services.assistente.servico.responder",
        lambda pergunta, usuario_id, hoje=None, modelo=None: {"dados": {"resposta": "ok", "divergencia": None, "falta": None}},
    )
    monkeypatch.setattr(cliente, "enviar_mensagem_texto", lambda wa_id, texto: chamadas_envio.append((wa_id, texto)) or True)

    corpo = json.dumps(_payload_mensagem(_NUMERO_AUTORIZADO, "Quanto gastei este mês?")).encode("utf-8")
    resposta = client.post(
        "/whatsapp/webhook", content=corpo,
        headers={"content-type": "application/json", "x-hub-signature-256": _assinar(corpo)},
    )

    assert resposta.status_code == 200
    assert chamadas_envio == [(_NUMERO_AUTORIZADO, "ok")]
