from datetime import datetime, timedelta

from app import models
from app.database import SessionLocal
from app.services import notificacoes as notificacoes_service


def _criar_usuario(db, email: str) -> models.Usuario:
    usuario = models.Usuario(nome="Notificações", email=email, senha="hash-de-teste")
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def test_api_notificacoes_isola_usuario_e_marca_leitura(client, auth_headers):
    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.email == "teste@t.com").first()
        outro = _criar_usuario(db, "outro-notificacoes@teste.com")
        item = notificacoes_service.criar_ou_atualizar(
            db,
            usuario_id=usuario.id,
            chave="teste:usuario-autenticado",
            tipo="sistema",
            severidade="info",
            estado="ativa",
            titulo="Visível",
            mensagem="Somente para o usuário autenticado.",
        )
        notificacoes_service.criar_ou_atualizar(
            db,
            usuario_id=outro.id,
            chave="teste:outro-usuario",
            tipo="sistema",
            severidade="info",
            estado="ativa",
            titulo="Privada",
            mensagem="Não pode aparecer para outro usuário.",
        )
        db.commit()
        item_id = item.id
    finally:
        db.close()

    resposta = client.get("/notificacoes?atualizar_financeiro=false", headers=auth_headers)
    assert resposta.status_code == 200
    dados = resposta.json()
    assert any(item["id"] == item_id for item in dados["items"])
    assert all(item["titulo"] != "Privada" for item in dados["items"])

    resposta = client.patch(
        f"/notificacoes/{item_id}", json={"lida": True}, headers=auth_headers
    )
    assert resposta.status_code == 200
    assert resposta.json()["lida_em"] is not None

    resposta = client.post("/notificacoes/marcar-todas-lidas", headers=auth_headers)
    assert resposta.status_code == 200


def test_reconciliacao_financeira_deduplica_resolve_e_reabre(client):
    db = SessionLocal()
    try:
        usuario = _criar_usuario(db, "reconciliacao-notificacoes@teste.com")
        alerta = {
            "chave": "financeiro:deficit:2026-07",
            "severidade": "critical",
            "titulo": "Déficit projetado",
            "mensagem": "Déficit de R$ 100,00.",
            "rota": "/despesas",
        }

        notificacoes_service.sincronizar_alertas_financeiros(db, usuario.id, [alerta])
        item = db.query(models.Notificacao).filter_by(usuario_id=usuario.id, chave=alerta["chave"]).one()
        item.lida_em = datetime.utcnow()
        db.commit()

        alerta_alterado = {**alerta, "mensagem": "Déficit de R$ 250,00."}
        notificacoes_service.sincronizar_alertas_financeiros(db, usuario.id, [alerta_alterado])
        db.refresh(item)
        assert item.lida_em is None
        assert item.mensagem == "Déficit de R$ 250,00."
        assert db.query(models.Notificacao).filter_by(usuario_id=usuario.id).count() == 1

        notificacoes_service.sincronizar_alertas_financeiros(db, usuario.id, [])
        db.refresh(item)
        assert item.resolvida_em is not None

        notificacoes_service.sincronizar_alertas_financeiros(db, usuario.id, [alerta])
        db.refresh(item)
        assert item.resolvida_em is None
        assert item.lida_em is None
    finally:
        db.close()


def test_sincronizacao_financeira_respeita_intervalo_por_usuario(client):
    db = SessionLocal()
    try:
        usuario = _criar_usuario(db, "intervalo-notificacoes@teste.com")
        alerta = {
            "chave": "financeiro:intervalo",
            "severidade": "info",
            "titulo": "Alerta",
            "mensagem": "Mensagem.",
        }

        assert notificacoes_service.sincronizar_alertas_financeiros_se_necessario(
            db, usuario.id, [alerta]
        ) is True
        assert notificacoes_service.sincronizar_alertas_financeiros_se_necessario(
            db, usuario.id, []
        ) is False

        configuracao = db.query(models.Configuracao).filter_by(
            usuario_id=usuario.id,
            preferencia=notificacoes_service.CHAVE_ULTIMA_SINCRONIZACAO_FINANCEIRA,
        ).one()
        configuracao.valor = (datetime.utcnow() - timedelta(minutes=6)).isoformat()
        db.commit()

        assert notificacoes_service.sincronizar_alertas_financeiros_se_necessario(
            db, usuario.id, []
        ) is True
    finally:
        db.close()


def test_sync_automatico_vazio_fica_silencioso(client):
    db = SessionLocal()
    try:
        usuario = _criar_usuario(db, "gmail-silencioso@teste.com")
        inicio = datetime.utcnow()
        chave = notificacoes_service.iniciar_sync_gmail(db, usuario.id, "automatica", inicio)
        notificacoes_service.finalizar_sync_gmail(
            db,
            usuario.id,
            chave,
            "automatica",
            {"encontrados": 0, "novos": 0, "erros": 0},
        )
        db.commit()
        total = db.query(models.Notificacao).filter_by(usuario_id=usuario.id, chave=chave).count()

        assert total == 0
    finally:
        db.close()
