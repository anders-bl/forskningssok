"""Tests the read-only OpenAlex forward-citation route and its honest failure states."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(api.app)


def test_siterer_returnerer_sidebegrenset_grafkontrakt():
    payload = {
        "status": "ok", "provider": "openalex", "seed_doi": "10.1/seed",
        "works": [], "edges": [], "total_available": 0, "retrieved": 0,
        "next_cursor": None, "complete": True,
    }
    with patch("api.openalex.siterende_verk", return_value=payload) as fetch:
        response = client.get("/api/siterer/10.1/seed", params={"limit": 7})
    assert response.status_code == 200
    assert response.json() == payload
    fetch.assert_called_once_with("10.1/seed", limit=7, cursor="*")


def test_siterer_avviser_ikke_doi_og_for_stor_cursor():
    assert client.get("/api/siterer/W123").status_code == 422
    assert client.get("/api/siterer/10.1/seed", params={"limit": 101}).status_code == 422
    assert client.get("/api/siterer/10.1/seed", params={"cursor": "x" * 513}).status_code == 422


def test_siterer_oppslagssvikt_er_502_ikke_tomt_funn():
    with patch("api.openalex.siterende_verk", side_effect=RuntimeError("OpenAlex utilgjengelig")):
        response = client.get("/api/siterer/10.1/seed")
    assert response.status_code == 502
