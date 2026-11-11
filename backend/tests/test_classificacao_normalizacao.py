import pytest

from app import models
from app.database import SessionLocal
from app.services.classificacao import classificar


@pytest.mark.parametrize('chave,descricao,esperada', [
    ('ÁGUA MINERAL', 'agua mineral - compra', 'Preferida'),
    ('   ', 'qualquer compra', 'Outros'),
])
def test_normaliza_regra_legada_sem_transformar_vazio_em_curinga(client, chave, descricao, esperada):
    with SessionLocal() as db:
        usuario = models.Usuario(nome='Normalizacao', email=f'normalizacao-{esperada}@example.org', senha='hash')
        db.add(usuario)
        db.flush()
        db.add(models.RegraClassificacao(usuario_id=usuario.id, palavra_chave=chave, categoria='Preferida', prioridade=10))
        db.commit()
        assert classificar(db, usuario.id, descricao, 'Outros') == esperada
