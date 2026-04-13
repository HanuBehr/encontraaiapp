from __future__ import annotations

from pydantic import BaseModel


class ExportMetadataResponse(BaseModel):
    filename: str
    content_type: str
