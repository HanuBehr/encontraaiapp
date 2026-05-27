from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings
from app.config import Settings
from app.schemas.settings import ProviderStatus, SettingsSummary

router = APIRouter(prefix="/settings", tags=["settings"])


def _redact_database_url(database_url: str) -> str:
    if "@" not in database_url:
        return database_url
    _, suffix = database_url.split("@", maxsplit=1)
    return f"***@{suffix}"


@router.get("/summary", response_model=SettingsSummary)
def settings_summary(settings: Settings = Depends(get_app_settings)) -> SettingsSummary:
    return SettingsSummary(
        app_env=settings.app_env,
        database_url_redacted=_redact_database_url(settings.database_url),
        export_dir=str(settings.export_path),
        sending_enabled=settings.sending_enabled,
        email_sending_enabled=settings.email_sending_enabled,
        whatsapp_sending_enabled=settings.whatsapp_sending_enabled,
        daily_email_limit=settings.daily_email_limit,
        daily_whatsapp_limit=settings.daily_whatsapp_limit,
        duplicate_send_window_hours=settings.duplicate_send_window_hours,
        providers=ProviderStatus(
            google_places_configured=settings.google_places_enabled,
            cnpj_company_search_configured=settings.cnpj_company_search_configured,
            smtp_configured=settings.smtp_configured,
            resend_configured=settings.resend_configured,
            whatsapp_cloud_configured=settings.whatsapp_cloud_configured,
        ),
    )
