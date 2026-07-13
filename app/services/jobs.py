from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import hashlib
import json
import time
from typing import Any, TypeVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.job import JobRecord
from app.services.observability import (
    classify_provider_error,
    is_transient_provider_error,
    new_correlation_id,
    operation_log,
)

T = TypeVar("T")


@dataclass(slots=True)
class JobRunResult[T]:
    value: T
    job: JobRecord


class JobRunner:
    def __init__(self, db: Session, *, max_attempts: int = 3, backoff_seconds: tuple[float, ...] = (0.0, 0.1, 0.25)) -> None:
        self.db = db
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds

    def run(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        operation: Callable[[str], T],
        result_serializer: Callable[[T], dict[str, Any]] | None = None,
        cached_result_factory: Callable[[dict[str, Any]], T] | None = None,
        idempotency_key: str | None = None,
    ) -> JobRunResult[T]:
        job_key = idempotency_key or build_job_key(job_type, payload)
        job = self._get_or_create_job(job_type=job_type, job_key=job_key, payload=payload)
        if job.status == "completed" and job.result_json:
            operation_log("job.idempotent_replay", job_type=job.job_type, job_key=job.job_key, correlation_id=job.correlation_id)
            if cached_result_factory:
                return JobRunResult(value=cached_result_factory(job.result_json), job=job)

        last_exc: BaseException | None = None
        for attempt in range(job.attempts + 1, self.max_attempts + 1):
            job.status = "running"
            job.attempts = attempt
            job.started_at = job.started_at or utcnow()
            job.error_class = None
            job.error_message = None
            self.db.add(job)
            self.db.commit()
            operation_log("job.attempt_started", job_type=job.job_type, job_key=job.job_key, correlation_id=job.correlation_id, attempt=attempt)
            try:
                value = operation(job.correlation_id)
            except Exception as exc:
                self.db.rollback()
                last_exc = exc
                job.error_class = classify_provider_error(exc)
                job.error_message = _safe_error_message(exc)
                job.status = "retrying" if attempt < self.max_attempts and is_transient_provider_error(exc) else "failed"
                job.next_retry_at = utcnow() + timedelta(seconds=self._backoff_for_attempt(attempt)) if job.status == "retrying" else None
                self.db.add(job)
                self.db.commit()
                operation_log(
                    "job.attempt_failed",
                    job_type=job.job_type,
                    job_key=job.job_key,
                    correlation_id=job.correlation_id,
                    attempt=attempt,
                    error_class=job.error_class,
                    retrying=job.status == "retrying",
                )
                if job.status != "retrying":
                    raise
                time.sleep(self._backoff_for_attempt(attempt))
                continue

            job.status = "completed"
            job.completed_at = utcnow()
            job.next_retry_at = None
            job.result_json = result_serializer(value) if result_serializer else {"completed": True}
            self.db.add(job)
            self.db.commit()
            operation_log("job.completed", job_type=job.job_type, job_key=job.job_key, correlation_id=job.correlation_id, attempts=job.attempts)
            return JobRunResult(value=value, job=job)

        if last_exc:
            raise last_exc
        raise RuntimeError("Job runner exited without a result.")

    def _get_or_create_job(self, *, job_type: str, job_key: str, payload: dict[str, Any]) -> JobRecord:
        existing = self.db.query(JobRecord).filter(JobRecord.job_key == job_key).one_or_none()
        if existing:
            return existing
        job = JobRecord(
            job_key=job_key,
            job_type=job_type,
            status="pending",
            correlation_id=new_correlation_id(job_type.replace("_", "-")),
            max_attempts=self.max_attempts,
            payload_json=payload,
        )
        self.db.add(job)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            return self.db.query(JobRecord).filter(JobRecord.job_key == job_key).one()
        return job

    def _backoff_for_attempt(self, attempt: int) -> float:
        index = min(attempt - 1, len(self.backoff_seconds) - 1)
        return self.backoff_seconds[index]


def build_job_key(job_type: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    return f"{job_type}:{digest}"


def _safe_error_message(exc: BaseException) -> str:
    message = str(exc)
    if len(message) > 500:
        return f"{message[:497]}..."
    return message
