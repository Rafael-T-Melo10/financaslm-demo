from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.services.parser import classificar_categoria, normalizar_texto_busca


CATEGORIAS_PADRAO = (
    "Alimentação", "Transporte", "Moradia", "Saúde", "Lazer",
    "Assinaturas", "Educação", "Roupas", "Impostos", "Outros",
)


def normalizar_chave(valor: str) -> str:
    return normalizar_texto_busca(valor or "").strip()


def seed_categorias_padrao(db: Session, usuario_id: int) -> None:
    existentes = {
        normalizar_chave(item.nome)
        for item in db.query(models.Categoria).filter(models.Categoria.usuario_id == usuario_id).all()
    }
    for nome in CATEGORIAS_PADRAO:
        if normalizar_chave(nome) not in existentes:
            db.add(models.Categoria(usuario_id=usuario_id, nome=nome, sistema=True))


def carregar_regras(db: Session, usuario_id: int) -> list[models.RegraClassificacao]:
    return db.query(models.RegraClassificacao).filter(
        models.RegraClassificacao.usuario_id == usuario_id,
        models.RegraClassificacao.ativa.is_(True),
    ).order_by(
        models.RegraClassificacao.prioridade.desc(),
        func.length(models.RegraClassificacao.palavra_chave).desc(),
    ).all()


def aplicar_regras(db: Session, usuario_id: int, descricao: str, estabelecimento: str | None = None) -> str | None:
    texto = normalizar_chave(f"{descricao or ''} {estabelecimento or ''}")
    for regra in carregar_regras(db, usuario_id):
        chave = normalizar_chave(regra.palavra_chave)
        if chave and chave in texto:
            return regra.categoria
    return None


def classificar(
    db: Session,
    usuario_id: int,
    descricao: str,
    categoria_extraida: str | None = None,
    estabelecimento: str | None = None,
) -> str:
    return aplicar_regras(db, usuario_id, descricao, estabelecimento) or categoria_extraida or classificar_categoria(descricao)
