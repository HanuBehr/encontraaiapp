from __future__ import annotations

from pydantic import BaseModel


class ProviderStatus(BaseModel):
    google_places_configured: bool
    cnpj_company_search_configured: bool
    smtp_configured: bool
    resend_configured: bool
    whatsapp_cloud_configured: bool


class SettingsSummary(BaseModel):
    app_env: str
    database_url_redacted: str
    export_dir: str
    sending_enabled: bool
    email_sending_enabled: bool
    whatsapp_sending_enabled: bool
    daily_email_limit: int
    daily_whatsapp_limit: int
    duplicate_send_window_hours: int
    providers: ProviderStatus
