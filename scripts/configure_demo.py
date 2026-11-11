"""Generate secrets for this isolated fictional demonstration only."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
target = root / '.env'
if target.exists():
    raise SystemExit('.env already exists; it was preserved.')
target.write_text(
    'PORTFOLIO_DEMO=1\nPOSTGRES_DB=financas_portfolio\nPOSTGRES_USER=financas_portfolio\n'
    f'POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n'
    f'SECRET_KEY={secrets.token_urlsafe(48)}\n'
    f'DEMO_PASSWORD={secrets.token_urlsafe(18)}\n'
    'ENVIRONMENT=demo\nGMAIL_SYNC_ENABLED=false\nWHATSAPP_HABILITADO=false\n'
    'ASSISTENTE_HABILITADO=false\nASSISTENTE_LOG_DIR=\n', encoding='utf-8')
print('Created .env. Demo accounts: alex@example.com / sam@example.com.')
print('Their password is DEMO_PASSWORD in .env. Keep this file private.')
