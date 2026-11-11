from datetime import date

from app import models
from app.database import SessionLocal
from app.services import classificacao, importacao


def _usuario(db, email: str) -> models.Usuario:
    usuario = models.Usuario(nome="Categorias", email=email, senha="hash")
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def test_regra_do_usuario_tem_precedencia_sobre_categoria_extraida(client):
    db = SessionLocal()
    try:
        usuario = _usuario(db, "regra-classificacao@teste.com")
        db.add(models.RegraClassificacao(
            usuario_id=usuario.id,
            palavra_chave="MERCADO CENTRAL",
            categoria="Mercado",
            prioridade=10,
        ))
        db.commit()

        categoria = classificacao.classificar(
            db, usuario.id, "Mercado Central - compra", "Outros"
        )
        assert categoria == "Mercado"
    finally:
        db.close()


def test_importacao_de_conta_nao_duplica_mesma_conta(client):
    db = SessionLocal()
    try:
        usuario = _usuario(db, "nio-duplicada@teste.com")
        dados = {
            "despesas": [{
                "descricao": "Internet Nio JUL/2026",
                "valor": 130.0,
                "categoria": "Moradia",
                "data": date(2026, 7, 1),
            }]
        }

        primeira = importacao.persistir_conta(db, usuario, dados)
        segunda = importacao.persistir_conta(db, usuario, dados)

        assert primeira["despesas_importadas"] == 1
        assert segunda["despesas_importadas"] == 0
        assert db.query(models.Despesa).filter_by(usuario_id=usuario.id).count() == 1
    finally:
        db.close()


def test_importacao_de_conta_aplica_regra_do_usuario(client):
    db = SessionLocal()
    try:
        usuario = _usuario(db, "regra-conta@teste.com")
        db.add(models.RegraClassificacao(
            usuario_id=usuario.id,
            palavra_chave="LIGHT",
            categoria="Energia",
            prioridade=1,
        ))
        db.commit()

        importacao.persistir_conta(db, usuario, {
            "despesas": [{
                "descricao": "LIGHT JUL/2026",
                "valor": 125.5,
                "categoria": "Moradia",
                "data": date(2026, 7, 1),
            }]
        })
        despesa = db.query(models.Despesa).filter_by(usuario_id=usuario.id).one()
        assert despesa.categoria == "Energia"
    finally:
        db.close()
