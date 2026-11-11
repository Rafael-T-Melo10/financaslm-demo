"""Orquestra o webhook do WhatsApp: valida a assinatura da Meta, extrai a
pergunta do payload e repassa para o assistente (servico.responder), que ja
e' o mesmo pipeline text2SQL usado pela pagina web -- so muda quem chama.

Uso pessoal: so whatsapp_settings.whatsapp_numero_autorizado tem resposta;
qualquer outro remetente e' ignorado em silencio (nao revela que o bot
existe). A pergunta sempre roda como whatsapp_settings.whatsapp_usuario_id,
ja que nao ha' cadastro de telefone por usuario (ver Usuario em models.py).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from app.config import whatsapp_settings
from app.services.assistente import servico as assistente_service
from app.services.whatsapp import cliente

logger = logging.getLogger(__name__)

_RESPOSTA_ERRO_INTERNO = "Não consegui processar sua pergunta agora. Tente de novo em instantes."


def verificar_assinatura(corpo_bruto: bytes, assinatura_header: str | None) -> bool:
    """Confere X-Hub-Signature-256 (HMAC-SHA256 do corpo bruto com o app
    secret). Sem isso, qualquer um que descobrisse a URL do webhook poderia
    forjar mensagens em nome da Meta."""
    if not whatsapp_settings.meta_app_secret or not assinatura_header:
        return False
    prefixo = "sha256="
    if not assinatura_header.startswith(prefixo):
        return False
    assinatura_esperada = hmac.new(
        whatsapp_settings.meta_app_secret.encode("utf-8"), corpo_bruto, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(assinatura_esperada, assinatura_header[len(prefixo):])


def extrair_mensagem(payload: dict[str, Any]) -> tuple[str, str] | None:
    """Devolve (wa_id, texto) da primeira mensagem de texto do payload, ou
    None se nao houver nenhuma processavel (ex.: payload so de "statuses" --
    confirmacao de entrega/leitura -- ou mensagem de midia, fora do escopo
    do MVP)."""
    for entrada in payload.get("entry", []):
        for mudanca in entrada.get("changes", []):
            valor = mudanca.get("value", {})
            for mensagem in valor.get("messages", []):
                if mensagem.get("type") == "text":
                    texto = (mensagem.get("text") or {}).get("body")
                    remetente = mensagem.get("from")
                    if texto and remetente:
                        return remetente, texto
    return None


def _formatar_resposta(envelope: dict[str, Any]) -> str:
    dados = envelope.get("dados", {})
    partes = [dados.get("resposta") or _RESPOSTA_ERRO_INTERNO]
    if dados.get("divergencia"):
        partes.append(dados["divergencia"])
    if dados.get("falta"):
        partes.append(dados["falta"])
    return "\n\n".join(partes)


def processar_mensagem_em_background(wa_id: str, texto: str) -> None:
    """Roda fora do request/response do webhook (ver BackgroundTasks na rota)
    porque assistente_service.responder pode levar varios segundos (chamadas
    ao Ollama) e a Meta exige um 200 rapido no POST do webhook."""
    if not whatsapp_settings.whatsapp_habilitado:
        return
    if wa_id != whatsapp_settings.whatsapp_numero_autorizado:
        logger.warning("Mensagem WhatsApp de remetente nao autorizado ignorada: wa_id=%s", wa_id)
        return

    try:
        envelope = assistente_service.responder(
            texto,
            whatsapp_settings.whatsapp_usuario_id,
            modelo=whatsapp_settings.whatsapp_modelo or None,
        )
        resposta_texto = _formatar_resposta(envelope)
    except Exception:
        logger.exception("Falha ao processar pergunta do WhatsApp de wa_id=%s", wa_id)
        resposta_texto = _RESPOSTA_ERRO_INTERNO

    cliente.enviar_mensagem_texto(wa_id, resposta_texto)
