import itertools
import json
from datetime import datetime, timedelta

from app import models
from app.api import routes
from app.database import SessionLocal

_contador_mensagem = itertools.count()


def _criar_pendente(usuario_email: str, **overrides) -> int:
    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.email == usuario_email).first()
        base = dict(
            usuario_id=usuario.id,
            gmail_message_id=f"msg-{datetime.utcnow().timestamp()}-{next(_contador_mensagem)}",
            remetente="Remetente Teste",
            assunto="Assunto Teste",
            tipo_detectado="conta",
            dados_extraidos_json=json.dumps({
                "despesas": [{"descricao": "Conta Teste", "valor": 50.0, "data": "2026-07-01", "categoria": "Moradia"}],
            }),
            status="pendente",
        )
        base.update(overrides)
        item = models.ImportacaoPendente(**base)
        db.add(item)
        db.commit()
        return item.id
    finally:
        db.close()


def test_listar_importacoes_pendentes(client, auth_headers):
    _criar_pendente("teste@t.com")

    resposta = client.get("/importacoes-pendentes", headers=auth_headers)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] >= 1
    assert len(corpo["items"]) >= 1
    assert corpo["page"] == 1
    assert corpo["page_size"] == 15


def test_listar_importacoes_pendentes_pagina(client, auth_headers):
    for _ in range(20):
        _criar_pendente("teste@t.com")

    pagina1 = client.get("/importacoes-pendentes", headers=auth_headers, params={"page": 1, "page_size": 15}).json()
    pagina2 = client.get("/importacoes-pendentes", headers=auth_headers, params={"page": 2, "page_size": 15}).json()

    assert len(pagina1["items"]) == 15
    assert len(pagina2["items"]) >= 1
    ids_pagina1 = {item["id"] for item in pagina1["items"]}
    ids_pagina2 = {item["id"] for item in pagina2["items"]}
    assert ids_pagina1.isdisjoint(ids_pagina2)


def test_confirmar_importacao_pendente_tipo_conta_cria_despesa(client, auth_headers):
    item_id = _criar_pendente("teste@t.com")

    resposta = client.post(f"/importacoes-pendentes/{item_id}/confirmar", headers=auth_headers, json={})
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["despesas_importadas"] == 1

    detalhe = client.get(f"/importacoes-pendentes/{item_id}", headers=auth_headers).json()
    assert detalhe["status"] == "confirmada"
    assert detalhe["data_revisao"] is not None


def test_confirmar_fatura_sem_cartao_falha(client, auth_headers):
    item_id = _criar_pendente(
        "teste@t.com",
        tipo_detectado="fatura",
        dados_extraidos_json=json.dumps({
            "total_fatura": 100.0,
            "informacoes_fatura": {"vencimento": "2026-07-10"},
            "despesas": [{"descricao": "Compra", "valor": 100.0, "categoria": "Outros", "data": "2026-06-10"}],
            "parcelas_futuras": [],
        }),
    )

    resposta = client.post(f"/importacoes-pendentes/{item_id}/confirmar", headers=auth_headers, json={})
    assert resposta.status_code == 400


def test_confirmar_fatura_usa_cartao_sugerido(client, auth_headers):
    cartao = client.post("/cartoes", headers=auth_headers, json={"nome": "Cartao Pendente Teste"}).json()

    item_id = _criar_pendente(
        "teste@t.com",
        tipo_detectado="fatura",
        cartao_id_sugerido=cartao["id"],
        dados_extraidos_json=json.dumps({
            "total_fatura": 200.0,
            "informacoes_fatura": {"vencimento": "2026-07-10"},
            "despesas": [{"descricao": "Compra", "valor": 200.0, "categoria": "Outros", "data": "2026-06-10"}],
            "parcelas_futuras": [],
        }),
    )

    resposta = client.post(f"/importacoes-pendentes/{item_id}/confirmar", headers=auth_headers, json={})
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["fatura"]["cartao_id"] == cartao["id"]


def test_rejeitar_importacao_pendente_nao_cria_despesa(client, auth_headers):
    total_antes = len(client.get("/despesas", headers=auth_headers).json())
    item_id = _criar_pendente("teste@t.com")

    resposta = client.post(f"/importacoes-pendentes/{item_id}/rejeitar", headers=auth_headers)
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "rejeitada"

    total_depois = len(client.get("/despesas", headers=auth_headers).json())
    assert total_depois == total_antes


def test_confirmar_item_ja_revisado_falha(client, auth_headers):
    item_id = _criar_pendente("teste@t.com")
    client.post(f"/importacoes-pendentes/{item_id}/rejeitar", headers=auth_headers)

    resposta = client.post(f"/importacoes-pendentes/{item_id}/confirmar", headers=auth_headers, json={})
    assert resposta.status_code == 400


def test_rejeitar_item_com_status_erro_funciona(client, auth_headers):
    item_id = _criar_pendente("teste@t.com", status="erro", mensagem_erro="Erro ao processar anexo: ValueError")

    resposta = client.post(f"/importacoes-pendentes/{item_id}/rejeitar", headers=auth_headers)
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "rejeitada"


def test_reabrir_item_rejeitado_volta_para_pendente(client, auth_headers):
    item_id = _criar_pendente("teste@t.com")
    client.post(f"/importacoes-pendentes/{item_id}/rejeitar", headers=auth_headers)

    resposta = client.post(f"/importacoes-pendentes/{item_id}/reabrir", headers=auth_headers)
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "pendente"
    assert resposta.json()["data_revisao"] is None


def test_reabrir_item_com_erro_reprocessa_anexo(client, auth_headers, monkeypatch):
    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.email == "teste@t.com").first()
        conexao = models.GmailConexao(
            usuario_id=usuario.id,
            email_conectado="teste@t.com",
            refresh_token="fake-token",
            ativo=True,
        )
        db.add(conexao)
        db.commit()
    finally:
        db.close()

    item_id = _criar_pendente(
        "teste@t.com",
        status="erro",
        tipo_detectado="holerite",
        gmail_attachment_id="att-1",
        dados_extraidos_json=None,
        mensagem_erro="Erro ao processar anexo: ValueError",
    )
    dados_reprocessados = {
        "receitas": [{"descricao": "LIQUIDO A RECEBER", "valor": 2281.0, "data": "2025-11-01"}],
        "itens": [],
    }
    monkeypatch.setattr(routes.gmail_auth, "montar_cliente_gmail", lambda refresh_token: object())
    monkeypatch.setattr(routes, "_baixar_anexo", lambda servico, message_id, attachment_id: b"%PDF-1.4")
    monkeypatch.setattr(routes, "extrair_dados_pdf", lambda arquivo, tipo, senha=None: dados_reprocessados)

    resposta = client.post(f"/importacoes-pendentes/{item_id}/reabrir", headers=auth_headers)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "pendente"
    assert corpo["mensagem_erro"] is None
    assert corpo["dados_extraidos"] == dados_reprocessados

    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.email == "teste@t.com").first()
        db.query(models.GmailConexao).filter(models.GmailConexao.usuario_id == usuario.id).delete()
        db.commit()
    finally:
        db.close()


def test_reabrir_item_confirmado_falha(client, auth_headers):
    item_id = _criar_pendente("teste@t.com")
    resposta_confirmar = client.post(f"/importacoes-pendentes/{item_id}/confirmar", headers=auth_headers, json={})
    assert resposta_confirmar.status_code == 200

    resposta = client.post(f"/importacoes-pendentes/{item_id}/reabrir", headers=auth_headers)
    assert resposta.status_code == 400


def test_reabrir_item_pendente_falha(client, auth_headers):
    item_id = _criar_pendente("teste@t.com")

    resposta = client.post(f"/importacoes-pendentes/{item_id}/reabrir", headers=auth_headers)
    assert resposta.status_code == 400


def test_atualizar_importacao_pendente_edita_dados_extraidos(client, auth_headers):
    item_id = _criar_pendente("teste@t.com")

    resposta = client.patch(
        f"/importacoes-pendentes/{item_id}",
        headers=auth_headers,
        json={"dados_extraidos": {"despesas": [{"descricao": "Conta Corrigida", "valor": 75.0, "data": "2026-07-05", "categoria": "Moradia"}]}},
    )
    assert resposta.status_code == 200
    assert resposta.json()["dados_extraidos"]["despesas"][0]["descricao"] == "Conta Corrigida"


def test_gmail_status_sem_conexao(client, auth_headers):
    resposta = client.get("/gmail/status", headers=auth_headers)
    assert resposta.status_code == 200
    assert resposta.json()["conectado"] is False


def test_gmail_sync_manual_sem_conexao_falha(client, auth_headers):
    resposta = client.post("/gmail/sync", headers=auth_headers)
    assert resposta.status_code == 404


def test_gmail_sync_manual_ja_em_andamento_nao_reprocessa(client, auth_headers):
    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.email == "teste@t.com").first()
        conexao = db.query(models.GmailConexao).filter(
            models.GmailConexao.usuario_id == usuario.id
        ).first()
        if not conexao:
            conexao = models.GmailConexao(
                usuario_id=usuario.id,
                email_conectado="teste@t.com",
                refresh_token="fake-token",
                ativo=True,
            )
            db.add(conexao)
        conexao.ativo = True
        conexao.sincronizando = True
        conexao.sync_processados = 3
        conexao.sync_iniciado_em = datetime.utcnow()
        db.commit()
    finally:
        db.close()

    resposta = client.post("/gmail/sync", headers=auth_headers)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["iniciado"] is False
    assert corpo["ja_em_andamento"] is True

    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.email == "teste@t.com").first()
        conexao = db.query(models.GmailConexao).filter(
            models.GmailConexao.usuario_id == usuario.id
        ).first()
        assert conexao.sync_processados == 3
        conexao.sincronizando = False
        conexao.sync_processados = None
        db.commit()
    finally:
        db.close()


def test_gmail_sync_manual_reinicia_lock_vencido(client, auth_headers, monkeypatch):
    monkeypatch.setattr(routes, "_executar_sync_usuario_background", lambda usuario_id: None)

    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.email == "teste@t.com").first()
        conexao = db.query(models.GmailConexao).filter(
            models.GmailConexao.usuario_id == usuario.id
        ).first()
        if not conexao:
            conexao = models.GmailConexao(
                usuario_id=usuario.id,
                email_conectado="teste@t.com",
                refresh_token="fake-token",
                ativo=True,
            )
            db.add(conexao)
        conexao.ativo = True
        conexao.sincronizando = True
        conexao.sync_processados = 6
        conexao.sync_total = 83
        conexao.sync_iniciado_em = datetime.utcnow() - timedelta(minutes=11)
        db.commit()
    finally:
        db.close()

    resposta = client.post("/gmail/sync", headers=auth_headers)
    assert resposta.status_code == 200
    assert resposta.json() == {"iniciado": True}

def test_listar_importacoes_pendentes_inclui_nome_cartao_detectado(client, auth_headers):
    item_id = _criar_pendente(
        "teste@t.com",
        tipo_detectado="fatura",
        nome_cartao_detectado="Itaú",
        dados_extraidos_json=json.dumps({
            "total_fatura": 100.0,
            "informacoes_fatura": {"vencimento": "2026-07-10"},
            "despesas": [],
            "parcelas_futuras": [],
        }),
    )

    resposta = client.get("/importacoes-pendentes", headers=auth_headers)
    assert resposta.status_code == 200
    itens = resposta.json()["items"]
    item = next(i for i in itens if i["id"] == item_id)
    assert item["nome_cartao_detectado"] == "Itaú"
