"""Run the backend against its own SQLite demonstration database."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--prepare-only', action='store_true')
args = parser.parse_args()
env = os.environ.copy()
for line in (root / '.env').read_text(encoding='utf-8').splitlines():
    if line and not line.startswith('#'):
        key, value = line.split('=', 1)
        env[key] = value
data = root / '.demo'
data.mkdir(exist_ok=True)
env.update(PORTFOLIO_DEMO='1', POSTGRES_HOST='', DATABASE_URL='sqlite:///' + (data / 'portfolio.sqlite3').as_posix(),
           GMAIL_SYNC_ENABLED='false', WHATSAPP_HABILITADO='false', ASSISTENTE_LOG_DIR='',
           GOOGLE_CLIENT_ID='', GOOGLE_CLIENT_SECRET='', META_ACCESS_TOKEN='', META_APP_SECRET='',
           ALLOWED_ORIGINS='http://localhost:3012,http://127.0.0.1:3012')
for command in [['-m', 'alembic', 'upgrade', 'head'], ['scripts/seed_portfolio.py']]:
    subprocess.run([sys.executable, *command], cwd=root / 'backend', env=env, check=True)
if not args.prepare_only:
    subprocess.run([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8012'],
                   cwd=root / 'backend', env=env, check=True)
