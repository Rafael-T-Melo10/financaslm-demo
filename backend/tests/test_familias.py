from app import models
from app.database import SessionLocal
from app.security import criar_token_acesso, gerar_hash_senha


def _criar_usuario(db, email: str, nome: str = "Membro"):
    usuario = models.Usuario(nome=nome, email=email, senha=gerar_hash_senha("s3nha!"))
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    db.expunge(usuario)
    return usuario


def _headers(usuario):
    return {"Authorization": f"Bearer {criar_token_acesso(usuario.id)}"}


def test_admin_cria_familia_adiciona_membro_e_gerencia_papel(client):
    db = SessionLocal()
    try:
        admin = _criar_usuario(db, "familia-admin@teste.com", "Admin")
        membro = _criar_usuario(db, "familia-membro@teste.com", "Membro")
    finally:
        db.close()

    resposta = client.post("/familias", headers=_headers(admin), json={"nome": "Casa Teste"})
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["membros"][0]["papel"] == "admin"

    resposta = client.post(
        "/familias/membros",
        headers=_headers(admin),
        json={"email": membro.email, "papel": "membro"},
    )
    assert resposta.status_code == 200, resposta.text
    membro_familia = next(item for item in resposta.json()["membros"] if item["usuario_id"] == membro.id)

    resposta = client.patch(
        f"/familias/membros/{membro_familia['id']}",
        headers=_headers(admin),
        json={"papel": "admin"},
    )
    assert resposta.status_code == 200, resposta.text
    assert any(item["usuario_id"] == membro.id and item["papel"] == "admin" for item in resposta.json()["membros"])


def test_membro_nao_pode_gerenciar_familia(client):
    db = SessionLocal()
    try:
        admin = _criar_usuario(db, "familia-admin-seg@teste.com", "Admin")
        membro = _criar_usuario(db, "familia-membro-seg@teste.com", "Membro")
        terceiro = _criar_usuario(db, "familia-terceiro@teste.com", "Terceiro")
    finally:
        db.close()

    assert client.post("/familias", headers=_headers(admin), json={"nome": "Casa Segura"}).status_code == 200
    assert client.post(
        "/familias/membros", headers=_headers(admin), json={"email": membro.email}
    ).status_code == 200

    resposta = client.post(
        "/familias/membros", headers=_headers(membro), json={"email": terceiro.email}
    )
    assert resposta.status_code == 403
