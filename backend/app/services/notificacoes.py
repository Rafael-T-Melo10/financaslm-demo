from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from app import models


CHAVE_ULTIMA_SINCRONIZACAO_FINANCEIRA = "notificacoes:ultima_sincronizacao_financeira"


def criar_ou_atualizar(
    db: Session,
    *,
    usuario_id: int,
    chave: str,
    tipo: str,
    severidade: str,
    estado: str,
    titulo: str,
    mensagem: str,
    rota: str | None = None,
    progresso_atual: int | None = None,
    progresso_total: int | None = None,
    reabrir_ao_mudar: bool = True,
    forcar_nao_lida: bool = False,
    lida_inicialmente: bool = False,
) -> models.Notificacao:
    """Faz upsert por usuário/chave e preserva leitura em atualizações de progresso."""
    agora = datetime.utcnow()
    item = db.query(models.Notificacao).filter(
        models.Notificacao.usuario_id == usuario_id,
        models.Notificacao.chave == chave,
    ).first()

    if not item:
        item = models.Notificacao(
            usuario_id=usuario_id,
            chave=chave,
            tipo=tipo,
            severidade=severidade,
            estado=estado,
            titulo=titulo,
            mensagem=mensagem,
            rota=rota,
            progresso_atual=progresso_atual,
            progresso_total=progresso_total,
            lida_em=agora if lida_inicialmente else None,
            criada_em=agora,
            atualizada_em=agora,
        )
        db.add(item)
        db.flush()
        return item

    conteudo_mudou = (
        item.severidade != severidade
        or item.estado != estado
        or item.titulo != titulo
        or item.mensagem != mensagem
        or item.rota != rota
    )
    estava_resolvida = item.resolvida_em is not None or item.estado == "resolvida"

    item.tipo = tipo
    item.severidade = severidade
    item.estado = estado
    item.titulo = titulo
    item.mensagem = mensagem
    item.rota = rota
    item.progresso_atual = progresso_atual
    item.progresso_total = progresso_total
    item.resolvida_em = None
    item.atualizada_em = agora

    if forcar_nao_lida or estava_resolvida or (reabrir_ao_mudar and conteudo_mudou):
        item.lida_em = None

    db.flush()
    return item


def resolver(db: Session, item: models.Notificacao) -> None:
    agora = datetime.utcnow()
    item.estado = "resolvida"
    item.resolvida_em = agora
    item.lida_em = item.lida_em or agora
    item.atualizada_em = agora


def sincronizar_alertas_financeiros(
    db: Session,
    usuario_id: int,
    alertas: Iterable[dict],
) -> None:
    chaves_ativas: set[str] = set()
    for alerta in alertas:
        chave = alerta.get("chave")
        if not chave:
            continue
        chaves_ativas.add(chave)
        criar_ou_atualizar(
            db,
            usuario_id=usuario_id,
            chave=chave,
            tipo="financeiro",
            severidade=alerta["severidade"],
            estado="ativa",
            titulo=alerta["titulo"],
            mensagem=alerta["mensagem"],
            rota=alerta.get("rota"),
        )

    anteriores = db.query(models.Notificacao).filter(
        models.Notificacao.usuario_id == usuario_id,
        models.Notificacao.tipo == "financeiro",
        models.Notificacao.resolvida_em.is_(None),
    ).all()
    for item in anteriores:
        if item.chave not in chaves_ativas:
            resolver(db, item)

    db.commit()


def sincronizar_alertas_financeiros_se_necessario(
    db: Session,
    usuario_id: int,
    alertas: Iterable[dict],
    intervalo_minimo: timedelta = timedelta(minutes=5),
) -> bool:
    """Sincroniza alertas financeiros no máximo uma vez por intervalo e usuário."""
    configuracao = db.query(models.Configuracao).filter(
        models.Configuracao.usuario_id == usuario_id,
        models.Configuracao.preferencia == CHAVE_ULTIMA_SINCRONIZACAO_FINANCEIRA,
    ).first()
    agora = datetime.utcnow()

    if configuracao:
        try:
            ultima_sincronizacao = datetime.fromisoformat(configuracao.valor)
        except (TypeError, ValueError):
            ultima_sincronizacao = None
        if ultima_sincronizacao and agora - ultima_sincronizacao < intervalo_minimo:
            return False
    else:
        configuracao = models.Configuracao(
            usuario_id=usuario_id,
            preferencia=CHAVE_ULTIMA_SINCRONIZACAO_FINANCEIRA,
            valor="",
        )
        db.add(configuracao)

    configuracao.valor = agora.isoformat(timespec="seconds")
    sincronizar_alertas_financeiros(db, usuario_id, alertas)
    return True


def _resolver_gmail_em_andamento_orfaos(db: Session, usuario_id: int) -> None:
    """Fecha qualquer notificação de sincronização do Gmail ainda marcada
    'em_andamento' para este usuário.

    A chave de cada notificação é amarrada ao timestamp exato daquela
    tentativa (gmail:sync:<iniciado_em>) -- se um sync anterior travou/morreu
    sem chamar finalizar_sync_gmail, a notificação dele fica órfã para
    sempre, e o frontend (que trata "existe notificação gmail em_andamento"
    como "sincronização em curso") acha que está sincronizando pra sempre,
    mesmo depois de uma tentativa nova ter concluído com sucesso. Só chega
    aqui depois que sincronizar_gmail já confirmou que o lock anterior está
    obsoleto (LOCK_TIMEOUT_MINUTOS), então qualquer 'em_andamento' que sobrar
    é garantidamente órfã.
    """
    orfaos = db.query(models.Notificacao).filter(
        models.Notificacao.usuario_id == usuario_id,
        models.Notificacao.tipo == "gmail",
        models.Notificacao.estado == "em_andamento",
    ).all()
    for orfa in orfaos:
        resolver(db, orfa)


def iniciar_sync_gmail(
    db: Session,
    usuario_id: int,
    origem: str,
    iniciado_em: datetime,
) -> str:
    _resolver_gmail_em_andamento_orfaos(db, usuario_id)
    chave = f"gmail:sync:{iniciado_em.isoformat(timespec='microseconds')}"
    if origem == "automatica":
        return chave
    criar_ou_atualizar(
        db,
        usuario_id=usuario_id,
        chave=chave,
        tipo="gmail",
        severidade="info",
        estado="em_andamento",
        titulo="Sincronizando Gmail",
        mensagem="Buscando emails com contas e faturas...",
        rota="/importacoes-pendentes",
        progresso_atual=0,
        progresso_total=None,
        reabrir_ao_mudar=False,
        lida_inicialmente=False,
    )
    return chave


def atualizar_sync_gmail(
    db: Session,
    usuario_id: int,
    chave: str,
    processados: int,
    total: int | None,
) -> None:
    mensagem = "Buscando emails com contas e faturas..."
    if total is not None:
        mensagem = f"Processando {processados} de {total} email(s)..."
    criar_ou_atualizar(
        db,
        usuario_id=usuario_id,
        chave=chave,
        tipo="gmail",
        severidade="info",
        estado="em_andamento",
        titulo="Sincronizando Gmail",
        mensagem=mensagem,
        rota="/importacoes-pendentes",
        progresso_atual=processados,
        progresso_total=total,
        reabrir_ao_mudar=False,
    )


def finalizar_sync_gmail(
    db: Session,
    usuario_id: int,
    chave: str,
    origem: str,
    resumo: dict,
) -> None:
    encontrados = int(resumo.get("encontrados", 0))
    novos = int(resumo.get("novos", 0))
    erros = int(resumo.get("erros", 0))

    item = db.query(models.Notificacao).filter(
        models.Notificacao.usuario_id == usuario_id,
        models.Notificacao.chave == chave,
    ).first()

    if origem == "automatica" and not novos and not erros:
        if item:
            item.mensagem = "Sincronização automática concluída sem novidades."
            resolver(db, item)
        return

    if erros:
        titulo = "Sincronização do Gmail com erro"
        mensagem = (
            f"A sincronização terminou com {erros} erro(s): "
            f"{encontrados} email(s) encontrado(s) e {novos} novo(s) item(ns)."
        )
        severidade = "critical"
        estado = "erro"
    else:
        titulo = "Sincronização do Gmail concluída"
        mensagem = f"{encontrados} email(s) encontrado(s) e {novos} novo(s) item(ns) para revisar."
        severidade = "success"
        estado = "concluida"

    criar_ou_atualizar(
        db,
        usuario_id=usuario_id,
        chave=chave,
        tipo="gmail",
        severidade=severidade,
        estado=estado,
        titulo=titulo,
        mensagem=mensagem,
        rota="/importacoes-pendentes",
        progresso_atual=encontrados,
        progresso_total=encontrados,
        reabrir_ao_mudar=False,
        forcar_nao_lida=True,
    )
