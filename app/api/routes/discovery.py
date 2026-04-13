from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db_session
from app.config import Settings
from app.schemas.discovery import DiscoverySearchRequest, DiscoverySearchResponse
from app.services.discovery import DiscoveryService

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post("/search", response_model=DiscoverySearchResponse)
def run_discovery_search(
    payload: DiscoverySearchRequest,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> DiscoverySearchResponse:
    service = DiscoveryService(db=db, settings=settings)
    return service.search(payload)
