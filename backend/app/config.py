from pydantic_settings import BaseSettings, SettingsConfigDict


class GmailSettings(BaseSettings):
    """Configuracao para a importacao automatica via Gmail.

    Escopo restrito a essa funcionalidade - o restante da configuracao do
    projeto continua usando os.getenv (nao migrado aqui, fora de escopo).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    google_client_id: str = ""
    google_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/gmail/oauth/callback"
    frontend_base_url: str = "http://localhost:3000"

    gmail_sync_labels: str = "contas,trabalho"
    gmail_sync_query_extra: str = "has:attachment filename:pdf"
    gmail_sync_interval_minutes: int = 30
    gmail_sync_enabled: bool = True

    @property
    def labels_lista(self) -> list[str]:
        """Labels do Gmail varridos na sincronizacao, separados por virgula."""
        return [label.strip() for label in self.gmail_sync_labels.split(",") if label.strip()]

gmail_settings = GmailSettings()


class AssistenteSettings(BaseSettings):
    """Configuracao do assistente financeiro local (text2SQL via runtime HTTP).

    O backend NUNCA carrega pesos de modelo: so fala HTTP com um runtime
    local (Ollama). Nenhum dado sai da maquina do usuario.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    assistente_habilitado: bool = True
    assistente_runtime_url: str = "http://localhost:11434"
    assistente_modelo: str = "qwen3:4b-instruct-2507"

    assistente_timeout_status_s: float = 2.0
    assistente_timeout_chamada1_s: float = 20.0
    assistente_timeout_chamada2_s: float = 30.0
    assistente_timeout_sql_s: float = 5.0

    assistente_num_ctx: int = 4096
    assistente_max_tokens_chamada1: int = 400
    assistente_max_tokens_chamada2: int = 400
    assistente_temperatura_sql: float = 0.0
    assistente_temperatura_redacao: float = 0.2
    assistente_seed: int = 7
    assistente_keep_alive: str = "10m"

    assistente_max_pergunta_chars: int = 400
    assistente_limite_linhas_resultado: int = 500
    assistente_log_dir: str = "logs_assistente"  # vazio desliga o log de auditoria


assistente_settings = AssistenteSettings()


class WhatsAppSettings(BaseSettings):
    """Configuracao da ponte WhatsApp -> assistente, via Meta WhatsApp Business
    Cloud API (oficial). Uso pessoal: so o numero em whatsapp_numero_autorizado
    conversa com o bot, e toda pergunta roda como whatsapp_usuario_id.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    whatsapp_habilitado: bool = False
    meta_access_token: str = ""
    meta_phone_number_id: str = ""
    meta_verify_token: str = ""
    meta_app_secret: str = ""
    meta_graph_api_version: str = "v21.0"
    whatsapp_numero_autorizado: str = ""  # E.164, ex "5511999998888"
    whatsapp_usuario_id: int = 0  # Usuario.id dono da conversa
    whatsapp_modelo: str = ""  # vazio = usa assistente_settings.assistente_modelo


whatsapp_settings = WhatsAppSettings()
