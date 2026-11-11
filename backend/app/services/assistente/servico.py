"""Orquestrador do assistente text2SQL -- responder() e status().

Fluxo com curto-circuitos explicitos em Python sempre que possivel: reduz
chamadas ao modelo e a superficie de alucinacao (o modelo nunca ve um
resultado vazio ou uma consulta rejeitada para "explicar em cima").

    sanitizar pergunta
    -> sondagem (ETAPA 0): periodo explicito sem dado -> nao_sei aqui, sem LLM
    -> chamada 1 (LLM): gera SQL
       -> JSON invalido apos retentativa -> nao_sei tecnico, sem chamada 2
    -> validador.py: SQL rejeitado -> nao_sei tecnico, sem chamada 2
    -> execucao_sql.py: falha de execucao -> nao_sei tecnico, sem chamada 2
    -> chamada 2 (LLM): classifica + redige a partir do RESULTADO REAL
       -> JSON invalido apos retentativa -> nao_sei tecnico
    -> verificacao.checar_afirmacoes: numero sem suporte -> rebaixa p/ nao_sei
    -> auditoria.registrar (motivo_tecnico so entra no log, nunca na resposta)
    -> envelope {filtros_aplicados, cobertura, dados}

Cada motivo_tecnico e uma metrica PROPRIA no harness de avaliacao (S6),
distinta do modelo genuinamente decidir veredito="nao_sei" -- uma coisa e o
modelo se abster corretamente; outra e a consulta dele ter sido rejeitada
antes de rodar.
"""
from __future__ import annotations

import time
from datetime import date
from typing import Any

from app.config import assistente_settings
from app.services.assistente import auditoria, runtime, sondagem, verificacao
from app.services.assistente.execucao_sql import ExecucaoSqlError, ResultadoSql, executar
from app.services.assistente.runtime import RespostaChamada1, RespostaInvalidaError, RuntimeIndisponivelError
from app.services.assistente.validador import SqlRejeitadoError, validar

_RESPOSTA_INDISPONIVEL = (
    "O assistente local não está disponível no momento. Verifique se o runtime "
    "está em execução na sua máquina e tente novamente."
)
_RESPOSTA_FALHA_TECNICA = (
    "Não consegui processar essa pergunta agora. Tente reformular ou pergunte novamente em instantes."
)
_RESPOSTA_SEM_DADOS = "Não encontrei nenhum lançamento para o filtro que você pediu."


def status() -> dict[str, Any]:
    disponibilidade = runtime.verificar_disponibilidade()
    modelo_confirmado = disponibilidade.get("modelo_carregado")
    # descrever_modelo() so e chamado quando o /api/tags do Ollama confirmou que o
    # modelo configurado esta de fato entre os instalados -- caso contrario, seu
    # fallback interno (em caso de erro no /api/show) ecoaria o nome configurado
    # mesmo que o modelo nunca tenha sido baixado, o que enganaria o usuario.
    info_modelo = runtime.descrever_modelo() if modelo_confirmado else {}
    return {
        "habilitado": assistente_settings.assistente_habilitado,
        "disponivel": bool(disponibilidade.get("disponivel")),
        "runtime": "ollama",
        "modelo": info_modelo.get("nome"),
        "quantizacao": info_modelo.get("quantizacao"),
        "digest": info_modelo.get("digest"),
        "modelos_instalados": disponibilidade.get("modelos_instalados") or [],
        "processamento_local": True,
        "mensagem": disponibilidade.get("motivo"),
    }


def carregar_modelo(modelo: str) -> dict[str, Any]:
    """Pre-carrega um modelo instalado em memoria no Ollama (botao "Carregar
    modelo" do frontend) -- so aceita um nome que ja apareceu em
    modelos_instalados (status()), pra nao repassar ao Ollama um nome
    arbitrario digitado em algum lugar fora da UI."""
    if not assistente_settings.assistente_habilitado:
        return {"carregado": False, "mensagem": "assistente desabilitado por configuração"}

    disponibilidade = runtime.verificar_disponibilidade()
    if not disponibilidade.get("disponivel"):
        return {"carregado": False, "mensagem": _RESPOSTA_INDISPONIVEL}

    instalados = disponibilidade.get("modelos_instalados") or []
    if modelo not in instalados:
        return {"carregado": False, "mensagem": f"modelo '{modelo}' não está instalado no Ollama."}

    return runtime.carregar_modelo(modelo)


def _envelope(
    *,
    resposta: str,
    sql: str | None,
    resultado: list[dict] | None,
    veredito: str,
    divergencia: str | None,
    premissas: list[str],
    falta: str | None,
    data_solicitada: str | None,
    data_utilizada: str | None,
    modelo_info: dict,
    latencias: dict[str, int],
    pergunta: str,
) -> dict[str, Any]:
    return {
        "filtros_aplicados": {"pergunta": pergunta},
        "cobertura": {
            "estado": "completa" if veredito == "ok" else "parcial" if veredito == "ressalva" else "sem_configuracao",
            "percentual": None,
            "fontes_esperadas": 0,
            "fontes_confirmadas": 0,
            "pendencias": [],
        },
        "dados": {
            "sql": sql,
            "resultado": resultado,
            "veredito": veredito,
            "divergencia": divergencia,
            "premissas": premissas,
            "falta": falta,
            "resposta": resposta,
            "data_solicitada": data_solicitada,
            "data_utilizada": data_utilizada,
            "modelo": modelo_info,
            "latencia_ms": latencias,
        },
    }


def _envelope_curto_circuito(
    *, pergunta: str, resposta: str, falta: str | None, motivo_tecnico: str,
    usuario_id: int, latencias: dict[str, int], data_solicitada: str | None = None,
    modelo: str | None = None,
) -> dict[str, Any]:
    auditoria.registrar(usuario_id, {
        "pergunta": pergunta, "veredito": "nao_sei", "motivo_tecnico": motivo_tecnico,
        "latencia_ms": latencias,
    })
    return _envelope(
        resposta=resposta, sql=None, resultado=None, veredito="nao_sei", divergencia=None,
        premissas=[], falta=falta, data_solicitada=data_solicitada, data_utilizada=None,
        modelo_info=runtime.descrever_modelo(modelo), latencias=latencias, pergunta=pergunta,
    )


def responder(pergunta: str, usuario_id: int, hoje: date | None = None, modelo: str | None = None) -> dict[str, Any]:
    """`modelo` sobrescreve assistente_settings.assistente_modelo so nesta
    pergunta -- o usuario escolhe entre os modelos instalados no frontend
    (GET /assistente/status expoe modelos_instalados)."""
    inicio_total = time.monotonic()
    latencias: dict[str, int] = {}
    pergunta_sanitizada = verificacao.sanitizar_pergunta(pergunta, assistente_settings.assistente_max_pergunta_chars)

    if not assistente_settings.assistente_habilitado:
        latencias["total"] = int((time.monotonic() - inicio_total) * 1000)
        return _envelope_curto_circuito(
            pergunta=pergunta_sanitizada, resposta=_RESPOSTA_INDISPONIVEL, falta=None,
            motivo_tecnico="desabilitado", usuario_id=usuario_id, latencias=latencias, modelo=modelo,
        )

    disponibilidade = runtime.verificar_disponibilidade()
    if not disponibilidade.get("disponivel"):
        latencias["total"] = int((time.monotonic() - inicio_total) * 1000)
        return _envelope_curto_circuito(
            pergunta=pergunta_sanitizada, resposta=_RESPOSTA_INDISPONIVEL, falta=None,
            motivo_tecnico="runtime_indisponivel", usuario_id=usuario_id, latencias=latencias, modelo=modelo,
        )

    dialeto = _motor_para_dialeto()
    inicio_sondagem = time.monotonic()
    sondagem_resultado = sondagem.sondar(pergunta_sanitizada, usuario_id, dialeto, hoje)
    latencias["sondagem"] = int((time.monotonic() - inicio_sondagem) * 1000)

    if sondagem_resultado.veredito_antecipado == "nao_sei":
        latencias["total"] = int((time.monotonic() - inicio_total) * 1000)
        periodo_iso = _periodo_iso(sondagem_resultado)
        return _envelope_curto_circuito(
            pergunta=pergunta_sanitizada,
            resposta=f"Não encontrei nenhum lançamento em {sondagem_resultado.periodo.rotulo}.",
            falta=f"Nenhum dado disponível para {sondagem_resultado.periodo.rotulo}.",
            motivo_tecnico="sondagem_vazia", usuario_id=usuario_id, latencias=latencias,
            data_solicitada=periodo_iso, modelo=modelo,
        )

    # ---- chamada 1: gerar SQL ----
    inicio_c1 = time.monotonic()
    try:
        chamada1 = runtime.gerar_sql(pergunta_sanitizada, dialeto, sondagem_resultado.resumo_texto, modelo=modelo)
    except (RespostaInvalidaError, RuntimeIndisponivelError) as exc:
        latencias["chamada1"] = int((time.monotonic() - inicio_c1) * 1000)
        latencias["total"] = int((time.monotonic() - inicio_total) * 1000)
        return _envelope_curto_circuito(
            pergunta=pergunta_sanitizada, resposta=_RESPOSTA_FALHA_TECNICA, falta=None,
            motivo_tecnico=f"chamada1_invalida: {exc}", usuario_id=usuario_id, latencias=latencias, modelo=modelo,
        )
    latencias["chamada1"] = int((time.monotonic() - inicio_c1) * 1000)

    data_solicitada = chamada1.data_solicitada or _periodo_iso(sondagem_resultado)

    sql_validado = None
    resultado: ResultadoSql | None = None
    resultado_ou_erro_texto = f"(nenhuma consulta -- {chamada1.falta or 'a pergunta nao e respondivel com o schema disponivel'})"

    if chamada1.sql:
        # ---- validador ----
        try:
            sql_validado = validar(chamada1.sql, dialeto)
        except SqlRejeitadoError as exc:
            latencias["total"] = int((time.monotonic() - inicio_total) * 1000)
            return _envelope_curto_circuito(
                pergunta=pergunta_sanitizada, resposta=_RESPOSTA_FALHA_TECNICA,
                falta="A consulta gerada não passou nas regras de segurança do assistente.",
                motivo_tecnico=f"sql_rejeitado: {exc}", usuario_id=usuario_id, latencias=latencias,
                data_solicitada=data_solicitada, modelo=modelo,
            )

        # ---- guarda-corpo: leitura "media mensal" vs "por lancamento" ----
        # Nao confia no texto de chamada1.premissas -- so na FORMA do SQL de fato gerado (ver
        # verificacao.checar_leitura_media_mensal). Achado real: o modelo as vezes declara a
        # premissa "leitura mensal" e gera SQL para a leitura por lancamento mesmo assim. Uma unica
        # retentativa com a divergencia anexada ao prompt, depois desiste com seguranca (mesmo
        # padrao do retry por JSON invalido em runtime.py, mas aqui e um erro semantico).
        divergencia_media = verificacao.checar_leitura_media_mensal(pergunta_sanitizada, sql_validado.arvore)
        if divergencia_media:
            inicio_c1_retry = time.monotonic()
            chamada1_corrigida: RespostaChamada1 | None = None
            sql_validado_corrigido = None
            try:
                chamada1_corrigida = runtime.gerar_sql(
                    pergunta_sanitizada, dialeto, sondagem_resultado.resumo_texto,
                    modelo=modelo, nota_correcao=divergencia_media,
                )
                if chamada1_corrigida.sql:
                    sql_validado_corrigido = validar(chamada1_corrigida.sql, dialeto)
            except (RespostaInvalidaError, RuntimeIndisponivelError, SqlRejeitadoError):
                pass
            latencias["chamada1_retry"] = int((time.monotonic() - inicio_c1_retry) * 1000)

            ainda_divergente = sql_validado_corrigido is None or verificacao.checar_leitura_media_mensal(
                pergunta_sanitizada, sql_validado_corrigido.arvore
            )
            if ainda_divergente:
                latencias["total"] = int((time.monotonic() - inicio_total) * 1000)
                return _envelope_curto_circuito(
                    pergunta=pergunta_sanitizada, resposta=_RESPOSTA_FALHA_TECNICA,
                    falta="Não consegui montar com segurança a consulta de média pedida.",
                    motivo_tecnico="media_mensal_incorreta_apos_retentativa", usuario_id=usuario_id,
                    latencias=latencias, data_solicitada=data_solicitada, modelo=modelo,
                )

            chamada1 = chamada1_corrigida
            sql_validado = sql_validado_corrigido
            data_solicitada = chamada1.data_solicitada or _periodo_iso(sondagem_resultado)

        # ---- execucao ----
        inicio_exec = time.monotonic()
        try:
            resultado = executar(
                sql_validado, usuario_id,
                limite_linhas=assistente_settings.assistente_limite_linhas_resultado,
                timeout_s=assistente_settings.assistente_timeout_sql_s,
            )
        except ExecucaoSqlError as exc:
            latencias["execucao"] = int((time.monotonic() - inicio_exec) * 1000)
            latencias["total"] = int((time.monotonic() - inicio_total) * 1000)
            return _envelope_curto_circuito(
                pergunta=pergunta_sanitizada, resposta=_RESPOSTA_FALHA_TECNICA,
                falta="A consulta não pôde ser executada.",
                motivo_tecnico=f"falha_execucao: {exc}", usuario_id=usuario_id, latencias=latencias,
                data_solicitada=data_solicitada, modelo=modelo,
            )
        latencias["execucao"] = int((time.monotonic() - inicio_exec) * 1000)

        linhas_sanitizadas = verificacao.sanitizar_linhas_resultado(resultado.linhas)
        resultado_ou_erro_texto = _formatar_resultado_para_prompt(linhas_sanitizadas, resultado.truncado)

    # ---- chamada 2: classificar + redigir ----
    inicio_c2 = time.monotonic()
    try:
        chamada2 = runtime.classificar_e_redigir(
            pergunta_sanitizada, sondagem_resultado.resumo_texto, chamada1.sql, resultado_ou_erro_texto,
            modelo=modelo, premissas_chamada1=chamada1.premissas,
        )
    except (RespostaInvalidaError, RuntimeIndisponivelError) as exc:
        latencias["chamada2"] = int((time.monotonic() - inicio_c2) * 1000)
        latencias["total"] = int((time.monotonic() - inicio_total) * 1000)
        return _envelope_curto_circuito(
            pergunta=pergunta_sanitizada, resposta=_RESPOSTA_FALHA_TECNICA, falta=None,
            motivo_tecnico=f"chamada2_invalida: {exc}", usuario_id=usuario_id, latencias=latencias,
            data_solicitada=data_solicitada, modelo=modelo,
        )
    latencias["chamada2"] = int((time.monotonic() - inicio_c2) * 1000)

    # ---- verificacao de afirmacoes numericas ----
    veredito_final = chamada2.veredito
    resposta_final = chamada2.resposta
    falta_final = chamada2.falta
    divergencia_final = chamada2.divergencia
    motivo_tecnico = None

    # Curto-circuito em Python, nao so instrucao no prompt: modelos pequenos as vezes
    # classificam "ok" mesmo com uma premissa declarada na chamada 1 (interpretacao assumida
    # pra pergunta ambigua, ex. qual leitura de "media" foi usada) -- observado empiricamente
    # com llama3.1 ignorando a regra dura do prompt da chamada 2. Nao confiar so na obediencia
    # do modelo pra essa classificacao, do mesmo jeito que checar_afirmacoes abaixo nao confia
    # nele pra numeros sem suporte.
    if chamada1.premissas and veredito_final == "ok":
        motivo_tecnico = "premissa_sem_ressalva: chamada2 classificou ok apesar de premissa declarada na chamada1"
        veredito_final = "ressalva"
        divergencia_final = divergencia_final or "; ".join(chamada1.premissas)

    # Mesmo padrao: a regra (b) do veredito em PROMPT_CHAMADA2 ja diz que sql=null (chamada1 nao
    # conseguiu escrever uma consulta -- grandeza inexistente ou pergunta nao respondivel) e'
    # sempre "nao_sei". Achado real com Phi-4 Mini: devolveu sql=null com um texto honesto ("nao
    # existe uma consulta que forneca isso"), mas classificou "ressalva" em vez de "nao_sei" --
    # diferente do guarda de resultado vazio abaixo, aqui o texto do modelo geralmente ja e' uma
    # explicacao razoavel (nao cita numero nenhum), entao so o veredito/falta sao corrigidos, sem
    # trocar a resposta.
    if not chamada1.sql and veredito_final != "nao_sei":
        motivo_tecnico = motivo_tecnico or "sql_nulo_sem_nao_sei: chamada1 nao gerou SQL mas o veredito nao veio nao_sei"
        veredito_final = "nao_sei"
        falta_final = falta_final or chamada1.falta or "A pergunta não é respondível com o schema disponível."

    # Mesmo curto-circuito em Python: o proprio PROMPT_CHAMADA2 ja diz que zero linhas para o
    # filtro exato pedido deveria ser "nao_sei" (regra "a" do veredito), mas o modelo pequeno as
    # vezes ignora isso e devolve "ok"/"ressalva" com um texto vago tipo "n/a" -- achado real com
    # Phi-4 Mini, que inventou um periodo de 3 anos atras (sem nenhum lancamento) em vez de usar o
    # periodo literal que sondagem.py ja calculou. A consulta roda sem erro (resultado vazio nao e
    # uma falha de execucao), entao so aqui, depois da chamada 2, da pra saber que o resultado veio
    # vazio para uma pergunta que nao era sobre zero. verificacao.checar_resultado_sem_dados cobre
    # tanto lista vazia quanto o caso de uma consulta de AVG escalar (ex. "media mensal") sobre
    # zero linhas, que em SQL sempre devolve uma linha com valor None, nunca lista vazia.
    arvore_final = sql_validado.arvore if sql_validado is not None else None
    if (
        verificacao.checar_resultado_sem_dados(resultado, arvore_final)
        and veredito_final != "nao_sei"
    ):
        motivo_tecnico = motivo_tecnico or "resultado_sem_dados: consulta rodou sem erro mas nao encontrou nenhum dado"
        veredito_final = "nao_sei"
        falta_final = falta_final or "A consulta não encontrou nenhum lançamento para o filtro pedido."
        resposta_final = _RESPOSTA_SEM_DADOS

    nao_suportados = verificacao.checar_afirmacoes(resposta_final, resultado, pergunta_sanitizada)
    if nao_suportados and veredito_final != "nao_sei":
        motivo_tecnico = f"afirmacao_sem_suporte: {nao_suportados}"
        veredito_final = "nao_sei"
        falta_final = falta_final or "A resposta mencionava números que não vieram do resultado da consulta."
        resposta_final = _RESPOSTA_FALHA_TECNICA

    latencias["total"] = int((time.monotonic() - inicio_total) * 1000)

    resultado_para_envelope = (
        verificacao.sanitizar_linhas_resultado(resultado.linhas) if resultado is not None else None
    )

    auditoria.registrar(usuario_id, {
        "pergunta": pergunta_sanitizada,
        "sql": chamada1.sql,
        "veredito": veredito_final,
        "motivo_tecnico": motivo_tecnico,
        "linhas_resultado": len(resultado.linhas) if resultado is not None else None,
        "latencia_ms": latencias,
    })

    return _envelope(
        resposta=resposta_final, sql=chamada1.sql, resultado=resultado_para_envelope,
        veredito=veredito_final, divergencia=divergencia_final,
        premissas=list(chamada1.premissas) + [p for p in chamada2.premissas if p not in chamada1.premissas],
        falta=falta_final, data_solicitada=data_solicitada,
        data_utilizada=_periodo_iso(sondagem_resultado), modelo_info=runtime.descrever_modelo(modelo),
        latencias=latencias, pergunta=pergunta_sanitizada,
    )


def _motor_para_dialeto() -> str:
    from app.services.assistente.execucao_sql import motor_atual

    return motor_atual()


def _periodo_iso(sondagem_resultado: sondagem.ResultadoSondagem) -> str | None:
    if sondagem_resultado.periodo is None:
        return None
    return f"{sondagem_resultado.periodo.inicio.isoformat()}..{sondagem_resultado.periodo.fim.isoformat()}"


def _formatar_resultado_para_prompt(linhas: list[dict], truncado: bool) -> str:
    import json as _json

    if not linhas:
        return "[] (a consulta rodou sem erro, mas não retornou nenhuma linha)"
    texto = _json.dumps(linhas, ensure_ascii=False, default=str)
    if truncado:
        texto += "\n(resultado truncado -- há mais linhas do que as exibidas acima)"
    return texto
