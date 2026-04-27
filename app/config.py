from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    api_title: str = Field(default="Encontra.ai Lead Discovery API", alias="API_TITLE")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    streamlit_server_port: int = Field(default=8501, alias="STREAMLIT_SERVER_PORT")
    timezone: str = Field(default="America/Sao_Paulo", alias="TIMEZONE")
    database_url: str = Field(default="sqlite:///./data/app.db", alias="DATABASE_URL")
    export_dir: str = Field(default="./data/exports", alias="EXPORT_DIR")
    sqlite_journal_mode: str = Field(default="TRUNCATE", alias="SQLITE_JOURNAL_MODE")

    sending_enabled: bool = Field(default=False, alias="SENDING_ENABLED")
    email_sending_enabled: bool = Field(default=False, alias="EMAIL_SENDING_ENABLED")
    whatsapp_sending_enabled: bool = Field(default=False, alias="WHATSAPP_SENDING_ENABLED")
    daily_email_limit: int = Field(default=25, alias="DAILY_EMAIL_LIMIT")
    daily_whatsapp_limit: int = Field(default=25, alias="DAILY_WHATSAPP_LIMIT")
    duplicate_send_window_hours: int = Field(default=72, alias="DUPLICATE_SEND_WINDOW_HOURS")

    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    google_places_base_url: str = Field(
        default="https://places.googleapis.com/v1",
        alias="GOOGLE_PLACES_BASE_URL",
    )
    google_geocode_base_url: str = Field(
        default="https://maps.googleapis.com/maps/api/geocode/json",
        alias="GOOGLE_GEOCODE_BASE_URL",
    )

    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from_email: str | None = Field(default=None, alias="SMTP_FROM_EMAIL")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")

    resend_api_key: str | None = Field(default=None, alias="RESEND_API_KEY")

    whatsapp_access_token: str | None = Field(default=None, alias="WHATSAPP_ACCESS_TOKEN")
    whatsapp_phone_number_id: str | None = Field(default=None, alias="WHATSAPP_PHONE_NUMBER_ID")
    whatsapp_business_account_id: str | None = Field(
        default=None,
        alias="WHATSAPP_BUSINESS_ACCOUNT_ID",
    )

    @property
    def export_path(self) -> Path:
        return Path(self.export_dir)

    @property
    def google_places_enabled(self) -> bool:
        return bool(self.google_api_key)

    @property
    def smtp_configured(self) -> bool:
        return all([self.smtp_host, self.smtp_username, self.smtp_password, self.smtp_from_email])

    @property
    def resend_configured(self) -> bool:
        return bool(self.resend_api_key)

    @property
    def whatsapp_cloud_configured(self) -> bool:
        return all(
            [
                self.whatsapp_access_token,
                self.whatsapp_phone_number_id,
                self.whatsapp_business_account_id,
            ]
        )

    def ensure_directories(self) -> None:
        self.export_path.mkdir(parents=True, exist_ok=True)
        Path("./data/demo").mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
