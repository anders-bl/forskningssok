"""Contract checks for user-started EPO OPS search and readiness routes."""
from unittest.mock import patch

from fastapi.testclient import TestClient

import api

client = TestClient(api.app)


def test_epo_readiness_does_not_expose_credentials():
    with patch("api.epo_ops.tilgjengelig", return_value={
        "provider": "epo_ops", "configured": False, "status": "unconfigured",
    }):
        response = client.get("/api/patenter/epo/tilgjengelig")
    assert response.status_code == 200
    assert response.json() == {"provider": "epo_ops", "configured": False, "status": "unconfigured"}


def test_epo_search_is_bounded_and_passes_query():
    payload = {"provider": "epo_ops", "status": "unconfigured", "records": [], "total_available": None}
    with patch("api.epo_ops.sok", return_value=payload) as search:
        response = client.get("/api/patenter/epo", params={"q": "sensor"})
    assert response.status_code == 200
    assert response.json() == payload
    search.assert_called_once_with("sensor", limit=10)
    assert client.get("/api/patenter/epo", params={"q": "x" * 301}).status_code == 422
    assert client.get("/api/patenter/epo", params={"q": "sensor", "limit": 21}).status_code == 422


def test_epo_provider_failure_is_not_empty_result():
    with patch("api.epo_ops.sok", side_effect=RuntimeError("EPO OPS nede")):
        response = client.get("/api/patenter/epo", params={"q": "sensor"})
    assert response.status_code == 502
