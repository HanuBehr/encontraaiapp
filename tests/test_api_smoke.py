from __future__ import annotations


def test_health_endpoint(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database_ok"] is True


def test_settings_summary_endpoint(client) -> None:
    response = client.get("/settings/summary")

    assert response.status_code == 200
    payload = response.json()
    assert "providers" in payload
    assert "sending_enabled" in payload
