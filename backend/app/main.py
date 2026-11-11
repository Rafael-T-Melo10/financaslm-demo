import logging
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.api.routes import router
from app.config import gmail_settings
from app.database import SessionLocal
from app import models
from app.security import validar_configuracao_seguranca
from app.services.gmail_sync import sincronizar_gmail

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def executar_sincronizacao_gmail() -> None:
    db = SessionLocal()
    try:
        usuarios_conectados = (
            db.query(models.Usuario)
            .join(models.GmailConexao)
            .filter(models.GmailConexao.ativo == True)
            .all()
        )
        for usuario in usuarios_conectados:
            try:
                sincronizar_gmail(db, usuario)
            except Exception:
                logger.exception("Falha ao sincronizar Gmail para usuario_id=%s", usuario.id)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    validar_configuracao_seguranca()
    if gmail_settings.gmail_sync_enabled:
        scheduler.add_job(
            executar_sincronizacao_gmail,
            trigger=IntervalTrigger(minutes=gmail_settings.gmail_sync_interval_minutes),
            id="gmail_sync",
            replace_existing=True,
        )
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="API de Controle de Gastos",
    description="API para gerenciar receitas, despesas e cartões de crédito",
    version="1.0.0",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = [
    origem.strip()
    for origem in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
    if origem.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
async def root():
    return {
        "message": "API de Controle de Gastos",
        "versao": "1.0.0",
        "documentacao": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
