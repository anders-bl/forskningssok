"""Verifiserer /api/dossier/innsikt — det tynne HTTP-laget over dossier_innsikt.py
(ingen ny forretningslogikk her, forretningslogikken er alt testet i
test_dossier_innsikt.py). Samme mønster som test_api_dossier.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402


def _client():
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def test_tomt_emne_gir_400():
    r = _client().get("/api/dossier/innsikt", params={"emne": ""})
    assert r.status_code == 400


def test_manglende_emne_gir_422_fastapi_validering():
    r = _client().get("/api/dossier/innsikt")
    assert r.status_code == 422


def test_ekte_emne_returnerer_de_tre_innsiktsfeltene(monkeypatch):
    monkeypatch.setattr(api.dossier_innsikt_modul, "hent_kandidater",
                         lambda emne, db_path: [
                             {"aar": 2022, "tittel": "Nephrocalcinosis in Atlantic salmon Salmo salar",
                              "abstract": ""},
                         ])
    r = _client().get("/api/dossier/innsikt", params={"emne": "nephrocalcinosis salmon"})
    assert r.status_code == 200
    data = r.json()
    assert data["antall_kandidater"] == 1
    assert data["tidslinje"] == {"2020": 1}  # JSON-nøkler er alltid strenger
    assert data["art_konfidens"]["bekreftet"] == 1


def test_gjor_ikke_et_llm_kall_i_det_hele_tatt(monkeypatch):
    """Regresjon mot at noen ved en feil kobler denne til dossier_modul.lag_dossier()
    (det kostbare LLM-kallet) i stedet for den mekaniske aggregeringen."""
    def sprenger(*a, **kw):
        raise AssertionError("api_dossier_innsikt skal ALDRI kalle lag_dossier()")
    monkeypatch.setattr(api.dossier_modul, "lag_dossier", sprenger)
    monkeypatch.setattr(api.dossier_innsikt_modul, "hent_kandidater", lambda emne, db_path: [])
    r = _client().get("/api/dossier/innsikt", params={"emne": "hva som helst"})
    assert r.status_code == 200
