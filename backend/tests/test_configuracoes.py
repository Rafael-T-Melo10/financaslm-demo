from app import models
from app.database import SessionLocal
from app.security import criar_token_acesso, gerar_hash_senha
from app.services import senhas_pdf


def _usuario(db, email, nome="Teste"):
    usuario = models.Usuario(nome=nome, email=email, senha=gerar_hash_senha("senha!"))
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def _headers(usuario_id):
    return {"Authorization": f"Bearer {criar_token_acesso(usuario_id)}"}


def test_senhas_pdf_sao_cifradas_e_nao_vazam_na_api(client):
    db = SessionLocal()
    try:
        usuario = _usuario(db, "senhas-api@teste.com")
    finally:
        db.close()

    headers = _headers(usuario.id)
    resposta = client.patch("/configuracoes/senhas-pdf", headers=headers, json={"itau": "segredo-pdf"})
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["itau"]["configurada"] is True
    assert resposta.json()["itau"]["legivel"] is True
    assert "segredo-pdf" not in resposta.text

    db = SessionLocal()
    try:
        registro = db.query(models.SenhaPdf).filter_by(usuario_id=usuario.id, instituicao="itau").one()
        assert registro.valor_criptografado != "segredo-pdf"
        assert senhas_pdf.obter_senhas(db, usuario.id, ["itau"]) == ["segredo-pdf"]
    finally:
        db.close()

    assert client.patch("/configuracoes/senhas-pdf", headers=headers, json={"itau": ""}).status_code == 422
    resposta = client.patch("/configuracoes/senhas-pdf", headers=headers, json={"itau": None})
    assert resposta.status_code == 200
    assert resposta.json()["itau"]["configurada"] is False


def test_senhas_pdf_sao_isoladas_por_usuario(client):
    db = SessionLocal()
    try:
        primeiro = _usuario(db, "senhas-primeiro@teste.com")
        primeiro_id = primeiro.id
        segundo = _usuario(db, "senhas-segundo@teste.com")
        segundo_id = segundo.id
    finally:
        db.close()

    assert client.patch(
        "/configuracoes/senhas-pdf", headers=_headers(primeiro_id), json={"xp": "senha-primeira"}
    ).status_code == 200
    resposta = client.get("/configuracoes/senhas-pdf", headers=_headers(segundo_id))
    assert resposta.status_code == 200
    assert resposta.json()["xp"]["configurada"] is False


def test_status_indica_recadastro_quando_a_chave_da_aplicacao_muda(client, monkeypatch):
    db = SessionLocal()
    try:
        usuario = _usuario(db, "senhas-chave-trocada@teste.com")
        usuario_id = usuario.id
    finally:
        db.close()

    headers = _headers(usuario_id)
    assert client.patch(
        "/configuracoes/senhas-pdf", headers=headers, json={"light": "senha-da-conta"}
    ).status_code == 200
    monkeypatch.setattr(senhas_pdf, "SECRET_KEY", "outra-chave-para-teste")
    resposta = client.get("/configuracoes/senhas-pdf", headers=headers)
    assert resposta.status_code == 200
    assert resposta.json()["light"]["configurada"] is True
    assert resposta.json()["light"]["legivel"] is False


def test_cartao_manual_reconhece_instituicoes_com_acentos():
    assert senhas_pdf.chave_para_cartao("Itaú Personnalité") == "itau"
    assert senhas_pdf.chave_para_cartao("Cartão XP") == "xp"


def test_admin_renomeia_e_membro_sai_da_familia(client):
    db = SessionLocal()
    try:
        admin = _usuario(db, "familia-config-admin@teste.com", "Admin")
        admin_id = admin.id
        membro = _usuario(db, "familia-config-membro@teste.com", "Membro")
        membro_id = membro.id
        membro_email = membro.email
    finally:
        db.close()

    headers_admin = _headers(admin_id)
    headers_membro = _headers(membro_id)
    assert client.post("/familias", headers=headers_admin, json={"nome": "Casa"}).status_code == 200
    assert client.post("/familias/membros", headers=headers_admin, json={"email": membro_email}).status_code == 200

    resposta = client.patch("/familias/minha", headers=headers_admin, json={"nome": "Casa Nova"})
    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Casa Nova"

    assert client.delete("/familias/minha/participacao", headers=headers_membro).status_code == 204
    resposta = client.get("/familias/minha", headers=headers_admin)
    assert resposta.status_code == 200
    assert len(resposta.json()["membros"]) == 1


def test_ultimo_admin_nao_sai_com_outros_membros(client):
    db = SessionLocal()
    try:
        admin = _usuario(db, "familia-ultimo-admin@teste.com", "Admin")
        admin_id = admin.id
        membro = _usuario(db, "familia-ultimo-membro@teste.com", "Membro")
        membro_email = membro.email
    finally:
        db.close()

    headers_admin = _headers(admin_id)
    assert client.post("/familias", headers=headers_admin, json={"nome": "Casa Segura"}).status_code == 200
    assert client.post("/familias/membros", headers=headers_admin, json={"email": membro_email}).status_code == 200
    assert client.delete("/familias/minha/participacao", headers=headers_admin).status_code == 409
