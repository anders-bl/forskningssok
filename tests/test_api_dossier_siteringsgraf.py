"""Verifiserer /api/dossier/siteringsgraf — tynt HTTP-lag over dossier_siteringsgraf.py.
Nettverksfri: monkeypatcher selve graf-byggingen, ikke Semantic Scholar-kallene inni den
(de er alt dekket i test_dossier_siteringsgraf.py).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402


def _client():
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def test_tomt_emne_gir_400():
    r = _client().get("/api/dossier/siteringsgraf", params={"emne": ""})
    assert r.status_code == 400


def test_ekte_emne_returnerer_grafen(monkeypatch):
    monkeypatch.setattr(api.dossier_siteringsgraf_modul, "siteringsgraf_for_emne",
                         lambda emne: {"noder": ["a"], "kanter": [], "inn_grad": {"a": 0},
                                        "feilede_oppslag": [], "noder_meta": {"a": {"tittel": "X"}}})
    r = _client().get("/api/dossier/siteringsgraf", params={"emne": "nephrocalcinosis salmon"})
    assert r.status_code == 200
    assert r.json()["noder"] == ["a"]


def test_eksplisitt_kildesett_bevares_i_grafen(monkeypatch):
    mottatt = []
    monkeypatch.setattr(api.dossier_siteringsgraf_modul, "siteringsgraf_for_papirer",
                         lambda papirer: mottatt.extend(papirer) or {"noder": [p["id"] for p in papirer], "kanter": []})
    r = _client().post("/api/siteringsgraf/kilder", json={"papirer": [
        {"id": "doi:10.5555/a", "doi": "https://doi.org/10.5555/a", "tittel": "Paper A", "aar": 2024},
        {"id": "doi:10.5555/b", "doi": "10.5555/b", "tittel": "Paper B", "aar": 2010},
    ]})
    assert r.status_code == 200
    assert r.json()["noder"] == ["doi:10.5555/a", "doi:10.5555/b"]
    assert [p["doi"] for p in mottatt] == ["10.5555/a", "10.5555/b"]


def test_eksplisitt_kildesett_avviser_tomt_for_stort_og_duplisert_input():
    client = _client()
    assert client.post("/api/siteringsgraf/kilder", json={"papirer": []}).status_code == 400
    assert client.post("/api/siteringsgraf/kilder", json={"papirer": [{"id": "a"}] * 26}).status_code == 400
    assert client.post("/api/siteringsgraf/kilder", json={"papirer": [{"id": "a"}, {"id": "a"}]}).status_code == 400
    assert client.post("/api/siteringsgraf/kilder", json={"papirer": [{"id": "a", "doi": "not-a-doi"}]}).status_code == 400
