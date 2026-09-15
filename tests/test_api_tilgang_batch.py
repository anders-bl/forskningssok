"""Verifiserer /api/tilgang/batch — flere DOI-er i ett kall, samme flett-logikk som
/api/tilgang/{doi} (test_api_status.py el.l. dekker allerede _flett_tilgang isolert).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402


def _client():
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def test_returnerer_tilgang_per_doi(monkeypatch):
    monkeypatch.setattr(api.openalex, "tilgang",
                         lambda doi: {"fri_pdf_url": f"https://oa.example/{doi}", "lisens": None,
                                      "utgiver": None, "oa_status": "gold"} if doi == "10.1/a" else None)
    monkeypatch.setattr(api.unpaywall, "tilgang", lambda doi: None)
    r = _client().get("/api/tilgang/batch", params={"ids": "10.1/a,10.1/b"})
    assert r.status_code == 200
    data = r.json()["tilgang"]
    assert data["10.1/a"]["fri_pdf_url"] == "https://oa.example/10.1/a"
    assert data["10.1/b"]["fri_pdf_url"] is None


def test_ikke_doi_verdier_filtreres_bort(monkeypatch):
    monkeypatch.setattr(api.openalex, "tilgang", lambda doi: None)
    monkeypatch.setattr(api.unpaywall, "tilgang", lambda doi: None)
    r = _client().get("/api/tilgang/batch", params={"ids": "10.1/a,ikke-en-doi,"})
    assert list(r.json()["tilgang"].keys()) == ["10.1/a"]


def test_batch_er_begrenset_ikke_ubegrenset_fan_out(monkeypatch):
    kalt = []
    monkeypatch.setattr(api.openalex, "tilgang", lambda doi: kalt.append(doi) or None)
    monkeypatch.setattr(api.unpaywall, "tilgang", lambda doi: None)
    mange = ",".join(f"10.1/{i}" for i in range(50))
    r = _client().get("/api/tilgang/batch", params={"ids": mange})
    assert len(r.json()["tilgang"]) == api.MAKS_TILGANG_BATCH
    assert len(kalt) == api.MAKS_TILGANG_BATCH


def test_en_kilde_nede_degraderer_ikke_hele_batchen(monkeypatch):
    def sprenger(doi):
        raise RuntimeError("OpenAlex nede")
    monkeypatch.setattr(api.openalex, "tilgang", sprenger)
    monkeypatch.setattr(api.unpaywall, "tilgang",
                         lambda doi: {"fri_pdf_url": "https://unpaywall.example/x", "lisens": None,
                                      "utgiver": None, "oa_status": None})
    r = _client().get("/api/tilgang/batch", params={"ids": "10.1/a"})
    assert r.status_code == 200
    assert r.json()["tilgang"]["10.1/a"]["fri_pdf_url"] == "https://unpaywall.example/x"
