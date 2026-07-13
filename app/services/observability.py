from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4


LOGGER_NAME = "encontraai.operations"


def new_correlation_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def operation_log(event: str, **fields: Any) -> None:
    logging.getLogger(LOGGER_NAME).info(event, extra={"structured": sanitize_log_fields(fields)})


def sanitize_log_fields(fields: dict[str, Any]) -> dict[str, Any]:
    sensitive_names = {"email", "phone", "whatsapp", "cnpj", "token", "api_key", "password", "secret"}
    sanitized: dict[str, Any] = {}
    for key, value in fields.items():
        lowered = key.lower()
        if any(name in lowered for name in sensitive_names):
            sanitized[key] = "[redacted]"
        else:
            sanitized[key] = value
    return sanitized


def classify_provider_error(exc: BaseException) -> str:
    status_code = getattr(exc, "status_code", None)
    message = str(exc).lower()
    if status_code == 429 or "rate limit" in message or "limited" in message:
        return "rate_limited"
    if status_code in {401, 403} or "api_key" in message or "token" in message or "credential" in message:
        return "configuration"
    if status_code == 404 or "not found" in message:
        return "not_found"
    if status_code and int(status_code) >= 500:
        return "provider_unavailable"
    if "timeout" in message or "timed out" in message:
        return "timeout"
    return "provider_error"


def is_transient_provider_error(exc: BaseException) -> bool:
    return classify_provider_error(exc) in {"rate_limited", "provider_unavailable", "timeout", "provider_error"}
