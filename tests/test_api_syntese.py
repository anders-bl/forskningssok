"""Verifiserer /api/syntese og /api/syntese/tilgjengelig — det tynne HTTP-laget over
syntese_fortelling.py (ingen ny forretningslogikk her, se api.py sin egen modul-docstring).
syntese_modul.lag_syntese_fortelling() mockes: selve genereringen (ai-proxy/Ollama) er
allerede testet i test_syntese_fortelling.py, dette laget tester kun serialisering/
feilhåndtering.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402


def _client():
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def test_tilgjengelig_speiler_syntese_modulens_egen_dom(monkeypatch):
    monkeypatch.setattr(api.syntese_modul, "tilgjengelig", lambda: True)
    assert _client().get("/api/syntese/tilgjengelig").json() == {"tilgjengelig": True}

    monkeypatch.setattr(api.syntese_modul, "tilgjengelig", lambda: False)
    assert _client().get("/api/syntese/tilgjengelig").json() == {"tilgjengelig": False}


def test_tomt_emne_gir_400_ikke_en_tom_syntese():
    r = _client().post("/api/syntese", json={"emne": ""})
    assert r.status_code == 400


def test_manglende_emne_felt_gir_400():
    r = _client().post("/api/syntese", json={})
    assert r.status_code == 400


def test_ekte_emne_returnerer_syntese_teksten(monkeypatch):
    monkeypatch.setattr(api.syntese_modul, "lag_syntese_fortelling",
                         lambda emne: f"Én sammenhengende fortelling om {emne}")
    r = _client().post("/api/syntese", json={"emne": "nephrocalcinosis"})
    assert r.status_code == 200
    assert r.json() == {"syntese": "Én sammenhengende fortelling om nephrocalcinosis"}


def test_runtimeerror_fra_llm_kallet_blir_502_ikke_500(monkeypatch):
    """kall_llm() kaster RuntimeError ved død Ollama/ai-proxy (se syntese_fortelling.py)
    — flaten skal vise en ærlig oppstrøms-feil (502: forskningssok selv er frisk,
    avhengigheten ikke), aldri en ukjent 500."""
    def _feiler(emne):
        raise RuntimeError("ai-proxy utilgjengelig: connection refused")

    monkeypatch.setattr(api.syntese_modul, "lag_syntese_fortelling", _feiler)
    r = _client().post("/api/syntese", json={"emne": "noe"})
    assert r.status_code == 502
    assert "ai-proxy utilgjengelig" in r.json()["detail"]
