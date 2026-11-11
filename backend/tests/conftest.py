import os
import sys
import tempfile

import pytest

# Configura o banco de testes ANTES de importar a aplicação
# (app.database lê DATABASE_URL no import).
_tmpdir = tempfile.mkdtemp(prefix="gastos-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/teste.db"
# Nunca selecionar o Postgres pessoal por heranca do Compose ou de .env.
# Testes PostgreSQL exigem TEST_POSTGRES_* e base descartavel explicitamente.
os.environ["POSTGRES_HOST"] = ""
os.environ["GMAIL_SYNC_ENABLED"] = "false"
os.environ["WHATSAPP_HABILITADO"] = "false"
os.environ["ASSISTENTE_HABILITADO"] = "true"
os.environ["ASSISTENTE_LOG_DIR"] = _tmpdir

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    init_db()
    return TestClient(app)


@pytest.fixture(scope="session")
def auth_headers(client):
    client.post("/usuarios", json={"nome": "Teste", "email": "teste@t.com", "senha": "s3nha!"})
    resposta = client.post("/auth/login", json={"email": "teste@t.com", "senha": "s3nha!"})
    token = resposta.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
