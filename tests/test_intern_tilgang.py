"""FDR-107 M5b (2026-09-29): X-Forskningssok-Tilgang kreves på alt unntatt live/ready.

Begge retninger: uten FORSKNINGSSOK_TILGANG er appen uendret (utrullingsrekkefølgen hviler
på det); med den satt slipper bare riktig header gjennom, og helse-rutene som Docker, Kuma
og portalen bruker står åpne.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

HEMMELIG = "test-tilgang-9f2c"


@pytest.fixture
def klient():
    from fastapi.testclient import TestClient
    import api
    return TestClient(api.app)


def test_av_naar_verdien_mangler(klient, monkeypatch):
    monkeypatch.delenv("FORSKNINGSSOK_TILGANG", raising=False)
    assert klient.get("/api/versjon").status_code == 200


def test_uten_header_401(klient, monkeypatch):
    monkeypatch.setenv("FORSKNINGSSOK_TILGANG", HEMMELIG)
    r = klient.get("/api/versjon")
    assert r.status_code == 401
    assert r.json() == {"detail": "Ikke autentisert"}


def test_feil_header_401(klient, monkeypatch):
    monkeypatch.setenv("FORSKNINGSSOK_TILGANG", HEMMELIG)
    for feil in ("feil", HEMMELIG + "x", HEMMELIG[:-1], ""):
        assert klient.get("/api/versjon", headers={"X-Forskningssok-Tilgang": feil}).status_code == 401


def test_riktig_header_slipper_gjennom(klient, monkeypatch):
    monkeypatch.setenv("FORSKNINGSSOK_TILGANG", HEMMELIG)
    r = klient.get("/api/versjon", headers={"X-Forskningssok-Tilgang": HEMMELIG})
    assert r.status_code == 200


def test_frontend_og_data_er_gatet(klient, monkeypatch):
    monkeypatch.setenv("FORSKNINGSSOK_TILGANG", HEMMELIG)
    for sti in ("/", "/api/utkast", "/api/dokumenter", "/api/sitater", "/health"):
        assert klient.get(sti).status_code == 401, sti


def test_live_og_ready_staar_aapne(klient, monkeypatch):
    monkeypatch.setenv("FORSKNINGSSOK_TILGANG", HEMMELIG)
    for sti in ("/health/live", "/health/ready"):
        assert klient.get(sti).status_code != 401, sti


def test_unntaket_er_eksakt_ikke_prefiks(klient, monkeypatch):
    monkeypatch.setenv("FORSKNINGSSOK_TILGANG", HEMMELIG)
    for sti in ("/health/live/../../api/utkast", "/health/readyx", "/health/live2"):
        assert klient.get(sti).status_code in (401, 404), sti
        assert klient.get(sti).status_code != 200, sti
