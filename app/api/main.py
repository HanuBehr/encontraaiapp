from __future__ import annotations

from fastapi import FastAPI

from app.api.routes.dedupe import router as dedupe_router
from app.api.routes.discovery import router as discovery_router
from app.api.routes.exclusion_rules import router as exclusion_rules_router
from app.api.routes.exports import router as exports_router
from app.api.routes.health import router as health_router
from app.api.routes.leads import router as leads_router
from app.api.routes.outreach import router as outreach_router
from app.api.routes.scoring import router as scoring_router
from app.api.routes.settings import router as settings_router
from app.config import get_settings
from app.logging_config import configure_logging

configure_logging()
settings = get_settings()

app = FastAPI(title=settings.api_title)
app.include_router(health_router)
app.include_router(discovery_router)
app.include_router(exclusion_rules_router)
app.include_router(dedupe_router)
app.include_router(scoring_router)
app.include_router(outreach_router)
app.include_router(exports_router)
app.include_router(leads_router)
app.include_router(settings_router)
