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
