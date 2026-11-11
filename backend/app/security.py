import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app import models
from app.database import get_db

DEFAULT_SECRET_KEY = "dev-secret-troque-em-producao"
SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 dias

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def validar_configuracao_seguranca() -> None:
    """Impede que uma chave JWT insegura chegue a produção."""
    ambiente = os.getenv("ENVIRONMENT", "development").strip().lower()
    if ambiente in {"development", "dev", "test", "testing"}:
        return

    if SECRET_KEY == DEFAULT_SECRET_KEY or len(SECRET_KEY) < 32:
        raise RuntimeError(
            "SECRET_KEY deve ser uma chave aleatória de pelo menos 32 caracteres fora de desenvolvimento."
        )


def gerar_hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return pwd_context.verify(senha, senha_hash)
    except ValueError:
        return False


def senha_esta_hasheada(senha_armazenada: str) -> bool:
    return senha_armazenada.startswith(("$2a$", "$2b$", "$2y$"))


def criar_token_acesso(usuario_id: int) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(usuario_id), "exp": expira}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.Usuario:
    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessão inválida ou expirada. Faça login novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise credenciais_invalidas

    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise credenciais_invalidas

    return usuario


def autenticar_usuario(db: Session, email: str, senha: str) -> models.Usuario | None:
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if not usuario:
        return None

    # Contas criadas antes do hash guardavam a senha em texto puro:
    # valida direto e aproveita para re-hashear no primeiro login.
    if not senha_esta_hasheada(usuario.senha):
        if usuario.senha != senha:
            return None
        usuario.senha = gerar_hash_senha(senha)
        db.commit()
        return usuario

    if not verificar_senha(senha, usuario.senha):
        return None
    return usuario
