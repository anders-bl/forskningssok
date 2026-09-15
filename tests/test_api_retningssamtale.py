"""Verifiserer /api/retningssamtale — tynt HTTP-lag over retningssamtale.py sin
lag_retningsrapport() (forretningslogikken er alt testet i test_retningssamtale.py).
Samme mønster som test_api_syntese.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402


def _client():
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def test_tilgjengelig_speiler_retningssamtale_modulens_egen_dom(monkeypatch):
    monkeypatch.setattr(api.retningssamtale_modul, "tilgjengelig", lambda: True)
    assert _client().get("/api/retningssamtale/tilgjengelig").json() == {"tilgjengelig": True}
    monkeypatch.setattr(api.retningssamtale_modul, "tilgjengelig", lambda: False)
    assert _client().get("/api/retningssamtale/tilgjengelig").json() == {"tilgjengelig": False}


def test_tom_fritekst_gir_400():
    r = _client().post("/api/retningssamtale", json={"fritekst": ""})
    assert r.status_code == 400


def test_manglende_fritekst_felt_gir_400():
    r = _client().post("/api/retningssamtale", json={})
    assert r.status_code == 400


def test_ekte_fritekst_returnerer_rapporten(monkeypatch):
    monkeypatch.setattr(api.retningssamtale_modul, "lag_retningsrapport",
                         lambda fritekst: f"## Retninger\net svar om {fritekst}")
    r = _client().post("/api/retningssamtale", json={"fritekst": "nephrocalcinosis salmon"})
    assert r.status_code == 200
    assert "nephrocalcinosis salmon" in r.json()["rapport"]


def test_runtime_error_gir_502_ikke_500(monkeypatch):
    def sprenger(fritekst):
        raise RuntimeError("Ollama utilgjengelig (test)")
    monkeypatch.setattr(api.retningssamtale_modul, "lag_retningsrapport", sprenger)
    r = _client().post("/api/retningssamtale", json={"fritekst": "noe"})
    assert r.status_code == 502
