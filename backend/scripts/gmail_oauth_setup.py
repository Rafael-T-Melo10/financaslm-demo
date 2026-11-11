"""Script manual para conectar a caixa do Gmail de um usuario.

Uso:
    python scripts/gmail_oauth_setup.py usuario@exemplo.com

Abre o fluxo de consentimento OAuth2 no navegador (google_auth_oauthlib
InstalledAppFlow), e ao concluir grava o refresh token em GmailConexao
para o usuario informado. Alternativa as rotas /gmail/oauth/iniciar e
/gmail/oauth/callback, uteis quando ha acesso a um navegador local
(fora do container Docker).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import gmail_settings
from app.database import SessionLocal
from app import models
from app.services.gmail_auth import SCOPES


def main() -> None:
    if len(sys.argv) != 2:
        print("Uso: python scripts/gmail_oauth_setup.py usuario@exemplo.com")
        sys.exit(1)

    email_usuario = sys.argv[1]

    if not gmail_settings.google_client_id or not gmail_settings.google_client_secret:
        print("Configure GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET no .env antes de rodar este script.")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": gmail_settings.google_client_id,
            "client_secret": gmail_settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    credenciais = flow.run_local_server(port=0)

    db = SessionLocal()
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.email == email_usuario).first()
        if not usuario:
            print(f"Usuario com email {email_usuario} nao encontrado.")
            sys.exit(1)

        conexao = db.query(models.GmailConexao).filter(
            models.GmailConexao.usuario_id == usuario.id
        ).first()
        if not conexao:
            conexao = models.GmailConexao(usuario_id=usuario.id)
            db.add(conexao)

        conexao.email_conectado = email_usuario
        conexao.refresh_token = credenciais.refresh_token
        conexao.ativo = True
        conexao.ultimo_erro = None
        db.commit()
        print(f"Conexao Gmail salva para {email_usuario}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
