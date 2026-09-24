"""Tests for authenticated, bounded context preview from the linked conversation."""

from __future__ import annotations

from unittest.mock import Mock

import httpx
from fastapi.testclient import TestClient

import api


def test_context_proxy_requires_portal_access_cookie(monkeypatch) -> None:
    upstream = Mock()
    monkeypatch.setattr(api.httpx, "get", upstream)

    response = TestClient(api.app).get("/api/context/luna/517")

    assert response.status_code == 401
    upstream.assert_not_called()


def test_context_proxy_forwards_only_access_cookie_and_bounds_messages(monkeypatch) -> None:
    messages = [
        {"role": "user", "content": f"spørsmål {index}", "created_at": None}
        for index in range(10)
    ]
    messages[9]["content"] = "x" * 1300
    messages.append({"role": "system", "content": "internt"})
    payload = {
        "samtale": {"title": "Kontekst", "scope": "project", "updated_at": None},
        "meldinger": messages,
    }
    upstream_response = Mock(status_code=200)
    upstream_response.json.return_value = payload
    upstream = Mock(return_value=upstream_response)
    monkeypatch.setattr(api.httpx, "get", upstream)

    client = TestClient(
        api.app,
        cookies={"access_token": "session-token", "refresh_token": "must-not-forward"},
    )
    response = client.get("/api/context/luna/517")

    assert response.status_code == 200
    upstream.assert_called_once_with(
        f"{api._PORTAL_API_URL}/api/luna/samtaler/517",
        cookies={"access_token": "session-token"},
        timeout=8.0,
    )
    body = response.json()
    assert body["kontrakt"] == "luna-context.v1"
    assert body["samtale"]["antall_meldinger"] == 11
    assert [message["content"] for message in body["meldinger"]] == [
        f"spørsmål {index}" for index in range(2, 10)
    ][:7] + ["x" * 1200]
    assert body["meldinger"][-1]["forkortet"] is True


def test_context_proxy_preserves_owner_scope_not_found(monkeypatch) -> None:
    upstream_response = Mock(status_code=404)
    upstream = Mock(return_value=upstream_response)
    monkeypatch.setattr(api.httpx, "get", upstream)

    client = TestClient(api.app, cookies={"access_token": "session-token"})
    response = client.get("/api/context/luna/517")

    assert response.status_code == 404
    assert "ikke tilgjengelig" in response.json()["detail"]


def test_context_proxy_maps_transport_failure_to_bad_gateway(monkeypatch) -> None:
    monkeypatch.setattr(
        api.httpx,
        "get",
        Mock(side_effect=httpx.ConnectError("offline")),
    )

    client = TestClient(api.app, cookies={"access_token": "session-token"})
    response = client.get("/api/context/luna/517")

    assert response.status_code == 502
