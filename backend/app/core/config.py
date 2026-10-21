from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Personal OS API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://personal_os:change_me_locally@localhost:5432/personal_os"
    frontend_origin: str = "http://localhost:5173"
    cookie_secure: bool = False
    bootstrap_invitation_secret: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    token_encryption_key: str | None = None
    telegram_bot_token: str | None = None
    telegram_bot_username: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
