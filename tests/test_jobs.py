from __future__ import annotations

import pytest

from app.models.job import JobRecord
from app.services.jobs import JobRunner, build_job_key
from app.services.observability import classify_provider_error, sanitize_log_fields


class TransientProviderError(RuntimeError):
    status_code = 503


def test_job_runner_retries_transient_failures_and_records_completion(db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.jobs.time.sleep", lambda _: None)
    calls = {"count": 0}

    def operation(correlation_id: str) -> dict[str, object]:
        calls["count"] += 1
        assert correlation_id.startswith("provider-sync-")
        if calls["count"] == 1:
            raise TransientProviderError("provider timed out")
        return {"ok": True}

    result = JobRunner(db_session).run(
        job_type="provider_sync",
        payload={"lead_ids": [1, 2, 3]},
        operation=operation,
        result_serializer=lambda value: value,
    )

    assert result.value == {"ok": True}
    assert calls["count"] == 2
    assert result.job.status == "completed"
    assert result.job.attempts == 2
    assert result.job.completed_at is not None
    assert result.job.result_json == {"ok": True}


def test_job_runner_records_terminal_failure_after_bounded_retries(db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.jobs.time.sleep", lambda _: None)

    def operation(_: str) -> dict[str, object]:
        raise TransientProviderError("provider unavailable")

    with pytest.raises(TransientProviderError):
        JobRunner(db_session, max_attempts=2).run(
            job_type="provider_sync",
            payload={"lead_ids": [9]},
            operation=operation,
            result_serializer=lambda value: value,
        )

    job = db_session.query(JobRecord).one()
    assert job.status == "failed"
    assert job.attempts == 2
    assert job.error_class == "provider_unavailable"
    assert "provider unavailable" in (job.error_message or "")


def test_job_key_is_idempotent_for_payload_ordering() -> None:
    assert build_job_key("x", {"b": 2, "a": 1}) == build_job_key("x", {"a": 1, "b": 2})


def test_job_runner_reuses_idempotent_job_record(db_session) -> None:
    calls = {"count": 0}

    def operation(_: str) -> dict[str, object]:
        calls["count"] += 1
        return {"call": calls["count"]}

    runner = JobRunner(db_session)
    first = runner.run(
        job_type="lead_batch_enrichment",
        payload={"lead_ids": [1]},
        operation=operation,
        result_serializer=lambda value: value,
        cached_result_factory=lambda value: value,
    )
    second = runner.run(
        job_type="lead_batch_enrichment",
        payload={"lead_ids": [1]},
        operation=operation,
        result_serializer=lambda value: value,
        cached_result_factory=lambda value: value,
    )

    assert first.job.id == second.job.id
    assert first.value == {"call": 1}
    assert second.value == {"call": 1}
    assert calls["count"] == 1
    assert db_session.query(JobRecord).count() == 1


def test_provider_error_classification_and_log_sanitization() -> None:
    assert classify_provider_error(TransientProviderError("upstream")) == "provider_unavailable"
    sanitized = sanitize_log_fields({"email": "a@example.com", "lead_count": 2, "api_key": "secret"})
    assert sanitized == {"email": "[redacted]", "lead_count": 2, "api_key": "[redacted]"}
