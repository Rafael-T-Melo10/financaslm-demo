"""Cliente HTTP do runtime local (Ollama) -- as duas chamadas do protocolo.

O backend nunca carrega pesos de modelo: fala HTTP com um processo Ollama
rodando localmente (ver AssistenteSettings em app/config.py). Nenhuma
excecao de rede escapa deste modulo sem virar um dos dois erros tipados
abaixo -- servico.py decide o que fazer (degradar para "nao_sei tecnico",
nunca deixar uma excecao crua derrubar a resposta HTTP).
"""
from __future__ import annotations

import json
import time
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.config import assistente_settings
from app.services.assistente.prompts import montar_prompt_chamada1, montar_prompt_chamada2

_LITERAIS_NULOS = {"null", "none", "nulo", "n/a", "na", ""}
"""Modelos pequenos as vezes preenchem um campo Optional com a STRING "null"
em vez do null JSON de verdade, mesmo sob decodificacao restrita por schema
-- observado empiricamente com llama3.1:8b em RespostaChamada1.sql. Sem essa
normalizacao, essa string vira uma consulta SQL invalida e cai no caminho de
"SQL rejeitado pelo validador" em vez do caminho correto (o modelo ja disse
sql=null + falta preenchido, so o tipo saiu errado)."""


class RuntimeIndisponivelError(RuntimeError):
    """Nao foi possivel falar com o runtime local (conexao recusada, timeout)."""


class RespostaInvalidaError(RuntimeError):
    """O modelo respondeu, mas o conteudo nao e um JSON valido para o
    formato esperado, mesmo apos a retentativa."""


class RespostaChamada1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sql: str | None = None
    premissas: list[str] = []
    data_solicitada: str | None = None
    falta: str | None = None

    @field_validator("sql", "data_solicitada", "falta", mode="before")
    @classmethod
    def _normalizar_literal_nulo(cls, valor):
        if isinstance(valor, str) and valor.strip().lower() in _LITERAIS_NULOS:
            return None
        return valor


class RespostaChamada2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    veredito: Literal["ok", "ressalva", "nao_sei"]
    divergencia: str | None = None
    premissas: list[str] = []
    falta: str | None = None
    resposta: str

    @field_validator("divergencia", "falta", mode="before")
    @classmethod
    def _normalizar_literal_nulo(cls, valor):
        if isinstance(valor, str) and valor.strip().lower() in _LITERAIS_NULOS:
            return None
        return valor


_cache_descricao_modelo: dict[str, tuple[dict[str, Any], float]] = {}
_TTL_CACHE_MODELO_S = 60.0


def _url(caminho: str) -> str:
    return assistente_settings.assistente_runtime_url.rstrip("/") + caminho


def verificar_disponibilidade() -> dict[str, Any]:
    """Nunca levanta. Sempre devolve um dict com 'disponivel': bool."""
    if not assistente_settings.assistente_habilitado:
        return {"disponivel": False, "motivo": "assistente desabilitado por configuracao"}
    try:
        resposta = httpx.get(_url("/api/tags"), timeout=assistente_settings.assistente_timeout_status_s)
        resposta.raise_for_status()
        modelos = [m.get("name") for m in resposta.json().get("models", [])]
        modelo_esperado = assistente_settings.assistente_modelo
        return {
            "disponivel": True,
            "modelo_carregado": modelo_esperado if modelo_esperado in modelos else None,
            "modelos_instalados": modelos,
            "runtime": "ollama",
        }
    except httpx.HTTPError as exc:
        return {"disponivel": False, "motivo": f"runtime local inacessivel: {exc}"}


def descrever_modelo(modelo: str | None = None) -> dict[str, Any]:
    """POST /api/show, cacheado por modelo por _TTL_CACHE_MODELO_S. Nunca levanta."""
    nome = modelo or assistente_settings.assistente_modelo

    agora = time.monotonic()
    em_cache = _cache_descricao_modelo.get(nome)
    if em_cache and agora < em_cache[1]:
        return em_cache[0]

    try:
        resposta = httpx.post(
            _url("/api/show"),
            json={"name": nome},
            timeout=assistente_settings.assistente_timeout_status_s,
        )
        resposta.raise_for_status()
        dados = resposta.json()
        detalhes = dados.get("details", {})
        info = {
            "nome": nome,
            "quantizacao": detalhes.get("quantization_level"),
            "parametros": detalhes.get("parameter_size"),
            "digest": dados.get("digest") or (dados.get("model_info") or {}).get("general.name"),
            "runtime": "ollama",
            "local": True,
        }
    except httpx.HTTPError:
        info = {
            "nome": nome,
            "quantizacao": None,
            "parametros": None,
            "digest": None,
            "runtime": "ollama",
            "local": True,
        }

    _cache_descricao_modelo[nome] = (info, agora + _TTL_CACHE_MODELO_S)
    return info


def carregar_modelo(modelo: str) -> dict[str, Any]:
    """POST /api/generate sem "prompt" -- pedido documentado do Ollama pra so
    carregar os pesos em memoria (RAM/VRAM) sem gerar nada, evitando que a
    PRIMEIRA pergunta do usuario pague o custo de carregar o modelo (Ollama
    descarrega um modelo ocioso apos assistente_keep_alive, ver config.py).
    Nunca levanta -- mesma convencao de verificar_disponibilidade/descrever_modelo."""
    try:
        resposta = httpx.post(
            _url("/api/generate"),
            json={"model": modelo, "keep_alive": assistente_settings.assistente_keep_alive},
            timeout=assistente_settings.assistente_timeout_chamada1_s,
        )
        resposta.raise_for_status()
        return {"carregado": True, "mensagem": None}
    except httpx.HTTPError as exc:
        return {"carregado": False, "mensagem": f"não foi possível carregar o modelo: {exc}"}


def _chamar_chat(
    prompt: str,
    esquema: dict,
    *,
    temperatura: float,
    num_predict: int,
    timeout_s: float,
    modelo: str | None = None,
) -> str:
    corpo = {
        "model": modelo or assistente_settings.assistente_modelo,
        "messages": [{"role": "user", "content": prompt}],
        "format": esquema,
        "stream": False,
        "think": False,
        # Modelos "thinking" (ex. qwen3) geram uma cadeia de raciocinio longa antes da
        # resposta -- ~25x mais lento num teste real (27,7s vs 1,17s para a mesma
        # pergunta trivial) e nao muda o conteudo final, que ja vem sob o schema
        # restrito de qualquer forma. Ollama ignora este campo silenciosamente em
        # modelos sem essa capacidade (confirmado com llama3.1 e phi4-mini).
        "keep_alive": assistente_settings.assistente_keep_alive,
        "options": {
            "temperature": temperatura,
            "seed": assistente_settings.assistente_seed,
            "num_ctx": assistente_settings.assistente_num_ctx,
            "num_predict": num_predict,
        },
    }
    try:
        resposta = httpx.post(_url("/api/chat"), json=corpo, timeout=timeout_s)
        resposta.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeIndisponivelError(f"falha ao chamar o runtime local: {exc}") from exc

    dados = resposta.json()
    conteudo = (dados.get("message") or {}).get("content", "")
    if not conteudo:
        raise RespostaInvalidaError("resposta do modelo veio vazia")
    return conteudo


def _analisar_json(conteudo: str, modelo_pydantic: type[BaseModel]) -> BaseModel:
    try:
        bruto = json.loads(conteudo)
    except json.JSONDecodeError as exc:
        raise RespostaInvalidaError(f"conteudo nao e JSON valido: {exc}") from exc
    try:
        return modelo_pydantic.model_validate(bruto)
    except ValidationError as exc:
        raise RespostaInvalidaError(f"JSON nao corresponde ao formato esperado: {exc}") from exc


def gerar_sql(
    pergunta: str,
    dialeto: str,
    sondagem_resultado: str,
    modelo: str | None = None,
    nota_correcao: str | None = None,
) -> RespostaChamada1:
    """Chamada 1: pergunta -> SQL (ou sql=null + 'falta'). Temperatura 0 e
    seed fixa -- essa chamada precisa ser reproduzivel para a avaliacao.
    `modelo` sobrescreve assistente_settings.assistente_modelo so nesta
    chamada -- usado quando o usuario escolhe o modelo no frontend.
    `nota_correcao` repassa para o prompt uma correcao semantica encontrada por
    verificacao.checar_leitura_media_mensal numa tentativa anterior (ver servico.py) -- distinto
    do retry por JSON invalido logo abaixo, que usa a mesma `prompt` sem essa nota."""
    prompt = montar_prompt_chamada1(pergunta, dialeto, sondagem_resultado, nota_correcao)
    esquema = RespostaChamada1.model_json_schema()

    ultimo_erro: Exception | None = None
    for tentativa in range(2):
        prompt_tentativa = prompt if tentativa == 0 else (
            prompt + f"\n\n(Sua resposta anterior nao era um JSON valido: {ultimo_erro}. Responda so com o JSON.)"
        )
        try:
            conteudo = _chamar_chat(
                prompt_tentativa,
                esquema,
                temperatura=assistente_settings.assistente_temperatura_sql,
                num_predict=assistente_settings.assistente_max_tokens_chamada1,
                timeout_s=assistente_settings.assistente_timeout_chamada1_s,
                modelo=modelo,
            )
            return _analisar_json(conteudo, RespostaChamada1)  # type: ignore[return-value]
        except RespostaInvalidaError as exc:
            ultimo_erro = exc
    raise RespostaInvalidaError(f"chamada 1 nao produziu JSON valido apos retentativa: {ultimo_erro}")


def classificar_e_redigir(
    pergunta: str,
    sondagem_resultado: str,
    sql: str | None,
    resultado_ou_erro: str,
    modelo: str | None = None,
    premissas_chamada1: list[str] | None = None,
) -> RespostaChamada2:
    """Chamada 2: pergunta + resultado REAL da execucao -> veredito + resposta em portugues.
    `premissas_chamada1` repassa as premissas declaradas na chamada 1 (ex.: qual leitura de
    "media" foi assumida) -- sem isso, a chamada 2 classificaria "ok" mesmo quando a chamada 1 ja
    tinha assumido uma interpretacao ambigua para a pergunta."""
    prompt = montar_prompt_chamada2(pergunta, sondagem_resultado, sql, resultado_ou_erro, premissas_chamada1)
    esquema = RespostaChamada2.model_json_schema()

    ultimo_erro: Exception | None = None
    for tentativa in range(2):
        prompt_tentativa = prompt if tentativa == 0 else (
            prompt + f"\n\n(Sua resposta anterior nao era um JSON valido: {ultimo_erro}. Responda so com o JSON.)"
        )
        try:
            conteudo = _chamar_chat(
                prompt_tentativa,
                esquema,
                temperatura=assistente_settings.assistente_temperatura_redacao,
                num_predict=assistente_settings.assistente_max_tokens_chamada2,
                timeout_s=assistente_settings.assistente_timeout_chamada2_s,
                modelo=modelo,
            )
            return _analisar_json(conteudo, RespostaChamada2)  # type: ignore[return-value]
        except RespostaInvalidaError as exc:
            ultimo_erro = exc
    raise RespostaInvalidaError(f"chamada 2 nao produziu JSON valido apos retentativa: {ultimo_erro}")
