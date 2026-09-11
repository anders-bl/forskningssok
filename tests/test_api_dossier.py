"""Verifiserer /api/dossier og /api/dossier/tilgjengelig — det tynne HTTP-laget over
dossier.py (ingen ny forretningslogikk her, se api.py sin egen modul-docstring).
dossier_modul.lag_dossier() mockes: selve genereringen (ai-proxy/Ollama) er allerede
testet i test_dossier.py, dette laget tester kun serialisering/feilhåndtering.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402


def _client():
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def test_tilgjengelig_speiler_dossier_modulens_egen_dom(monkeypatch):
    monkeypatch.setattr(api.dossier_modul, "tilgjengelig", lambda: True)
    assert _client().get("/api/dossier/tilgjengelig").json() == {"tilgjengelig": True}

    monkeypatch.setattr(api.dossier_modul, "tilgjengelig", lambda: False)
    assert _client().get("/api/dossier/tilgjengelig").json() == {"tilgjengelig": False}


def test_tomt_emne_gir_400_ikke_et_tomt_dossier():
    r = _client().post("/api/dossier", json={"emne": ""})
    assert r.status_code == 400


def test_manglende_emne_felt_gir_400():
    r = _client().post("/api/dossier", json={})
    assert r.status_code == 400


def test_ekte_emne_returnerer_dossier_teksten(monkeypatch):
    monkeypatch.setattr(api.dossier_modul, "lag_dossier",
                         lambda emne: f"## Hard vitenskap\net dossier om {emne}")
    r = _client().post("/api/dossier", json={"emne": "nephrocalcinosis"})
    assert r.status_code == 200
    assert r.json() == {"dossier": "## Hard vitenskap\net dossier om nephrocalcinosis"}


def test_runtimeerror_fra_llm_kallet_blir_502_ikke_500(monkeypatch):
    """kall_llm() kaster RuntimeError ved død Ollama/ai-proxy (se dossier.py) — flaten
    skal vise en ærlig oppstrøms-feil (502: forskningssok selv er frisk, avhengigheten
    ikke), aldri en ukjent 500."""
    def _feiler(emne):
        raise RuntimeError("ai-proxy utilgjengelig: connection refused")

    monkeypatch.setattr(api.dossier_modul, "lag_dossier", _feiler)
    r = _client().post("/api/dossier", json={"emne": "noe"})
    assert r.status_code == 502
    assert "ai-proxy utilgjengelig" in r.json()["detail"]
