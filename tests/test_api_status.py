"""Verifiserer /api/status: teller riktig, og en nede kilde gir False — ALDRI en 500
fra selve statusendepunktet. Kilde-nåbarhet mockes (ingen live-kall i testsuiten,
samme disiplin som resten av forskningssok — se README §Testet).
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bank  # noqa: E402
from schemas import PaperDossier  # noqa: E402


def _fake_embed(texts):
    return [[0.0] * 1024 for _ in texts]


def test_status_teller_papirer_og_sitater(tmp_path, monkeypatch):
    db = tmp_path / "cache.db"
    import api
    monkeypatch.setattr(api, "CACHE_DB", db)

    p = PaperDossier(pmid="1", doi="10.1/x", tittel="t", forfattere="", tidsskrift="",
                      aar=2024, abstract="noe abstract", siteringstall=0, open_access=False,
                      kilde_url="u")
    bank.lagre([p], embed_fn=_fake_embed, db_path=db)
    bank.lagre_sitat("10.1/x", "et sitat", db_path=db)

    with patch("api._kilde_naabar", return_value=True):
        from fastapi.testclient import TestClient
        client = TestClient(api.app)
        r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert data["papirer_cachet"] == 1
    assert data["sitater_lagret"] == 1
    assert data["kilder"]["europe_pmc"] is True
    assert data["kilder"]["core"] is True  # CORE er tredje kilde i søket, hørte ikke hjemme i status


def test_status_nede_kilde_gir_false_ikke_500(tmp_path, monkeypatch):
    db = tmp_path / "cache.db"
    import api
    monkeypatch.setattr(api, "CACHE_DB", db)

    with patch("api._kilde_naabar", return_value=False):
        from fastapi.testclient import TestClient
        client = TestClient(api.app)
        r = client.get("/api/status")
    assert r.status_code == 200
    assert r.json()["kilder"]["europe_pmc"] is False
    assert r.json()["kilder"]["core"] is False
    assert r.json()["siste_sok"] is None


def test_status_skiller_europe_pmc_sok_fra_referanselister(tmp_path, monkeypatch):
    """De to er ulike delressurser med ulik oppetid: /search har vært oppe hele tiden
    mens /references har svart 503 sammenhengende siden 2026-09-02. Slått sammen til én
    linje sa panelet «Europe PMC — nåbar nå» mens gap-rapporten samtidig skrev «kilde:
    openalex + crossref» — to utsagn som motsa hverandre uten at noen av dem var usanne."""
    import api
    monkeypatch.setattr(api, "CACHE_DB", tmp_path / "cache.db")
    with patch("api._kilde_naabar", side_effect=lambda url, **k: "/references" not in url):
        from fastapi.testclient import TestClient
        kilder = TestClient(api.app).get("/api/status").json()["kilder"]
    assert kilder["europe_pmc"] is True
    assert kilder["europe_pmc_referanser"] is False
    assert kilder["crossref"] is True
