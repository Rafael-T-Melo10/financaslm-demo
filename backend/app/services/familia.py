from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models

PAPEIS_VALIDOS = {"admin", "membro"}


def obter_membro(db: Session, usuario_id: int) -> models.MembroFamilia | None:
    return db.query(models.MembroFamilia).filter(
        models.MembroFamilia.usuario_id == usuario_id
    ).first()


def obter_familia_do_usuario(db: Session, usuario_id: int) -> models.Familia | None:
    membro = obter_membro(db, usuario_id)
    if not membro:
        return None
    return db.query(models.Familia).options(
        joinedload(models.Familia.membros).joinedload(models.MembroFamilia.usuario)
    ).filter(models.Familia.id == membro.familia_id).first()


def exigir_admin(db: Session, usuario_id: int) -> models.MembroFamilia:
    membro = obter_membro(db, usuario_id)
    if not membro or membro.papel != "admin":
        raise HTTPException(status_code=403, detail="Apenas administradores da família podem realizar esta ação.")
    return membro


def validar_papel(papel: str) -> str:
    valor = papel.strip().lower()
    if valor not in PAPEIS_VALIDOS:
        raise HTTPException(status_code=422, detail="Papel deve ser 'admin' ou 'membro'.")
    return valor


def quantidade_admins(db: Session, familia_id: int) -> int:
    return db.query(models.MembroFamilia).filter(
        models.MembroFamilia.familia_id == familia_id,
        models.MembroFamilia.papel == "admin",
    ).count()
