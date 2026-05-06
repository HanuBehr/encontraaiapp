from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

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
    cnpja_api_key: str | None = Field(default=None, alias="CNPJA_API_KEY")
    cnpja_api_base_url: str | None = Field(default=None, alias="CNPJA_API_BASE_URL")
    cnpja_open_api_base_url: str = Field(
        default="https://open.cnpja.com",
        alias="CNPJA_OPEN_API_BASE_URL",
    )
    cnpj_lookup_provider: Literal["cnpja_open", "cnpj_ws"] = Field(
        default="cnpja_open",
        alias="CNPJ_LOOKUP_PROVIDER",
    )
    cnpj_ws_base_url: str = Field(
        default="https://publica.cnpj.ws",
        alias="CNPJ_WS_BASE_URL",
    )
    cnpj_company_search_provider: Literal["cnpja_commercial", "cnpj_ws_premium", "cnpjota"] = Field(
        default="cnpja_commercial",
        alias="CNPJ_COMPANY_SEARCH_PROVIDER",
    )
    cnpj_company_search_enabled: bool = Field(
        default=False,
        alias="CNPJ_COMPANY_SEARCH_ENABLED",
    )
    cnpj_ws_premium_base_url: str = Field(
        default="https://comercial.cnpj.ws",
        alias="CNPJ_WS_PREMIUM_BASE_URL",
    )
    cnpj_ws_premium_token: str | None = Field(
        default=None,
        alias="CNPJ_WS_PREMIUM_TOKEN",
    )
    cnpj_ws_premium_auth_mode: Literal["x_api_token", "authorization_bearer"] = Field(
        default="x_api_token",
        alias="CNPJ_WS_PREMIUM_AUTH_MODE",
    )
    cnpjota_base_url: str = Field(
        default="https://api.cnpjota.com.br/api/v1",
        alias="CNPJOTA_BASE_URL",
    )
    cnpjota_token: str | None = Field(
        default=None,
        alias="CNPJOTA_TOKEN",
    )
    cnpjota_use_preview: bool = Field(
        default=True,
        alias="CNPJOTA_USE_PREVIEW",
    )
    cnpja_search_endpoint: str | None = Field(default=None, alias="CNPJA_SEARCH_ENDPOINT")
    cnpja_enable_company_search: bool = Field(default=False, alias="CNPJA_ENABLE_COMPANY_SEARCH")
    cnpja_search_strategy: Literal["CACHE", "CACHE_IF_FRESH", "CACHE_IF_ERROR", "ONLINE"] = Field(
        default="CACHE_IF_ERROR",
        alias="CNPJA_SEARCH_STRATEGY",
    )
    cnpja_search_max_age: int = Field(default=45, alias="CNPJA_SEARCH_MAX_AGE")
    cnpja_company_search_limit: int = Field(default=10, alias="CNPJA_COMPANY_SEARCH_LIMIT")
    cnpja_name_variant_limit: int = Field(default=4, alias="CNPJA_NAME_VARIANT_LIMIT")
    cnpja_max_search_attempts_per_lead: int = Field(
        default=2,
        alias="CNPJA_MAX_SEARCH_ATTEMPTS_PER_LEAD",
    )
    cnpja_use_email_domain_filter: bool = Field(
        default=False,
        alias="CNPJA_USE_EMAIL_DOMAIN_FILTER",
    )
    cnpja_use_cnae_search_filter: bool = Field(
        default=False,
        alias="CNPJA_USE_CNAE_SEARCH_FILTER",
    )
    cnpja_rate_limit_per_minute: int = Field(default=10, alias="CNPJA_RATE_LIMIT_PER_MINUTE")
    cnpja_batch_size: int = Field(default=8, alias="CNPJA_BATCH_SIZE")
    cnpja_rate_limit_cooldown_seconds: int = Field(
        default=65,
        alias="CNPJA_RATE_LIMIT_COOLDOWN_SECONDS",
    )
    cnpja_stop_batch_on_rate_limit: bool = Field(
        default=True,
        alias="CNPJA_STOP_BATCH_ON_RATE_LIMIT",
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
    def cnpja_commercial_configured(self) -> bool:
        return bool(self.cnpja_api_key and self.cnpja_api_base_url)

    @property
    def cnpja_company_search_configured(self) -> bool:
        return bool(
            (
                self.cnpj_company_search_enabled
                and self.cnpj_company_search_provider == "cnpja_commercial"
                and self.cnpja_api_key
                and self.cnpja_api_base_url
            )
            or (
                self.cnpja_enable_company_search
                and self.cnpja_api_key
                and self.cnpja_search_endpoint
            )
        )

    @property
    def cnpj_company_search_requested(self) -> bool:
        return bool(self.cnpj_company_search_enabled or self.cnpja_enable_company_search)

    @property
    def cnpj_ws_premium_company_search_configured(self) -> bool:
        return bool(
            self.cnpj_company_search_enabled
            and self.cnpj_company_search_provider == "cnpj_ws_premium"
            and self.cnpj_ws_premium_base_url
            and self.cnpj_ws_premium_token
        )

    @property
    def cnpjota_company_search_configured(self) -> bool:
        return bool(
            self.cnpj_company_search_enabled
            and self.cnpj_company_search_provider == "cnpjota"
            and self.cnpjota_base_url
            and self.cnpjota_token
        )

    @property
    def cnpj_company_search_configured(self) -> bool:
        return bool(
            self.cnpj_ws_premium_company_search_configured
            or self.cnpjota_company_search_configured
            or self.cnpja_company_search_configured
        )

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
