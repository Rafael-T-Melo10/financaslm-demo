"""Log de auditoria local das execucoes do assistente -- gitignored, nunca
enviado a lugar nenhum.

Nunca persiste valores monetarios, descricao ou estabelecimento -- so
metadados de execucao (latencias, veredito, motivo tecnico de curto-circuito,
contagem de linhas do resultado). Falha ao gravar e engolida como warning:
a auditoria nunca pode derrubar a resposta ao usuario.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.config import assistente_settings
from app.security import SECRET_KEY

logger = logging.getLogger(__name__)

_RAIZ_BACKEND = Path(__file__).resolve().parents[3]


def _usuario_hash(usuario_id: int) -> str:
    return sha256(f"{usuario_id}:{SECRET_KEY}".encode("utf-8")).hexdigest()[:12]


def registrar(usuario_id: int, evento: dict[str, Any]) -> None:
    if not assistente_settings.assistente_log_dir:
        return
    try:
        raiz = _RAIZ_BACKEND / assistente_settings.assistente_log_dir
        raiz.mkdir(parents=True, exist_ok=True)
        arquivo = raiz / f"execucoes-{date.today():%Y-%m}.jsonl"
        linha = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "usuario_hash": _usuario_hash(usuario_id),
            **evento,
        }
        with arquivo.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")
    except OSError as exc:
        logger.warning("falha ao gravar log de auditoria do assistente: %s", exc)
