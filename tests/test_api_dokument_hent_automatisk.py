"""Verifiserer /api/dokument/hent-automatisk — kobler /api/tilgang sitt fri_pdf_url-
signal sammen med dokumenter.py sin eksisterende, testede PDF->tekst-pipeline.
Nettverksfri: httpx.get og dokumenter.lagre monkeypatches, samme disiplin som resten
av forskningssok sin testsuite.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402


def _client():
    from fastapi.testclient import TestClient
    return TestClient(api.app)


class _FakeResp:
    def __init__(self, content=b"%PDF-1.4 ..."):
        self.content = content
    def raise_for_status(self):
        pass


def test_ikke_doi_gir_400():
    r = _client().post("/api/dokument/hent-automatisk", data={"paper_id": "ikke-en-doi"})
    assert r.status_code == 400


def test_ingen_kjent_fri_pdf_url_gir_404(monkeypatch):
    monkeypatch.setattr(api.openalex, "tilgang", lambda doi: None)
    monkeypatch.setattr(api.unpaywall, "tilgang", lambda doi: None)
    r = _client().post("/api/dokument/hent-automatisk", data={"paper_id": "10.1/x"})
    assert r.status_code == 404


def test_pdf_fetch_feiler_gir_502(monkeypatch):
    monkeypatch.setattr(api.openalex, "tilgang", lambda doi: {"fri_pdf_url": "https://example.org/x.pdf"})
    monkeypatch.setattr(api.unpaywall, "tilgang", lambda doi: None)

    def sprenger(*a, **kw):
        import httpx
        raise httpx.ConnectError("nede")
    monkeypatch.setattr(api.httpx, "get", sprenger)
    r = _client().post("/api/dokument/hent-automatisk", data={"paper_id": "10.1/x"})
    assert r.status_code == 502


def test_ugyldig_pdf_gir_400(monkeypatch):
    monkeypatch.setattr(api.openalex, "tilgang", lambda doi: {"fri_pdf_url": "https://example.org/x.pdf"})
    monkeypatch.setattr(api.unpaywall, "tilgang", lambda doi: None)
    monkeypatch.setattr(api.httpx, "get", lambda *a, **kw: _FakeResp())
    monkeypatch.setattr(api.dokumenter, "lagre",
                         lambda *a, **kw: (_ for _ in ()).throw(ValueError("kunne ikke leses som PDF")))
    r = _client().post("/api/dokument/hent-automatisk", data={"paper_id": "10.1/x"})
    assert r.status_code == 400


def test_suksess_kaller_lagre_med_paper_id_eksplisitt(monkeypatch):
    monkeypatch.setattr(api.openalex, "tilgang", lambda doi: None)
    monkeypatch.setattr(api.unpaywall, "tilgang",
                         lambda doi: {"fri_pdf_url": "https://example.org/x.pdf"})
    monkeypatch.setattr(api.httpx, "get", lambda *a, **kw: _FakeResp())
    kalt = {}

    def fake_lagre(filnavn, data, *, paper_id=None, db_path=None):
        kalt["filnavn"] = filnavn
        kalt["paper_id"] = paper_id
        return {"paper_id": paper_id, "doc_id": "abc123", "tegn": 42}

    monkeypatch.setattr(api.dokumenter, "lagre", fake_lagre)
    monkeypatch.setattr(api, "_varm_stille", lambda *a, **kw: None)
    r = _client().post("/api/dokument/hent-automatisk", data={"paper_id": "10.1/x"})
    assert r.status_code == 200
    assert kalt["paper_id"] == "10.1/x"  # eksplisitt gitt, ikke gjettet fra PDF-forsiden
    assert r.json()["doc_id"] == "abc123"
