from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Email Outreach Manager"
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'email_outreach.db').as_posix()}"
    upload_dir: str = str(BASE_DIR / "data" / "uploads")
    export_dir: str = str(BASE_DIR / "data" / "exports")
    log_level: str = "INFO"
    log_file: str = str(BASE_DIR / "data" / "email_outreach.log")
    email_outreach_secret_key: str = ""
    worker_poll_seconds: float = 1.0
    max_retry_attempts: int = 3
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://127.0.0.1:8000/api/oauth/gmail/callback"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
Path(settings.export_dir).mkdir(parents=True, exist_ok=True)
