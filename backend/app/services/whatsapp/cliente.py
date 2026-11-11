"""Cliente HTTP do Meta WhatsApp Business Cloud API -- so envio de mensagem de
texto. Mesma convencao de app/services/assistente/runtime.py: nenhuma excecao
de rede escapa deste modulo, so loga e devolve.
"""
from __future__ import annotations

import logging

import httpx

from app.config import whatsapp_settings

logger = logging.getLogger(__name__)


def enviar_mensagem_texto(wa_id: str, texto: str) -> bool:
    """POST /{phone_number_id}/messages. Nunca levanta -- devolve True/False."""
    url = (
        f"https://graph.facebook.com/{whatsapp_settings.meta_graph_api_version}"
        f"/{whatsapp_settings.meta_phone_number_id}/messages"
    )
    corpo = {
        "messaging_product": "whatsapp",
        "to": wa_id,
        "type": "text",
        "text": {"body": texto},
    }
    headers = {"Authorization": f"Bearer {whatsapp_settings.meta_access_token}"}
    try:
        resposta = httpx.post(url, json=corpo, headers=headers, timeout=10.0)
        resposta.raise_for_status()
        return True
    except httpx.HTTPError:
        logger.exception("Falha ao enviar mensagem WhatsApp para wa_id=%s", wa_id)
        return False
