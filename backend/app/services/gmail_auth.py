from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import gmail_settings

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def montar_flow(state: str | None = None) -> Flow:
    client_config = {
        "web": {
            "client_id": gmail_settings.google_client_id,
            "client_secret": gmail_settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [gmail_settings.google_oauth_redirect_uri],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        state=state,
        redirect_uri=gmail_settings.google_oauth_redirect_uri,
        autogenerate_code_verifier=False,
    )


def montar_credenciais(refresh_token: str) -> Credentials:
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=gmail_settings.google_client_id,
        client_secret=gmail_settings.google_client_secret,
        scopes=SCOPES,
    )


def montar_cliente_gmail(refresh_token: str):
    credenciais = montar_credenciais(refresh_token)
    return build("gmail", "v1", credentials=credenciais, cache_discovery=False)
