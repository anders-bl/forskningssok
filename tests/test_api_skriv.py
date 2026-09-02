"""Verifiserer Skriv-modus-endepunktene (utkast/relevans/omfang). Mocker på bank.py/
scoping.py-funksjonsnivå, ikke DB-sti — api.py sine nye endepunkter kaller bank.X() uten
eksplisitt db_path, og bank sine funksjoners db_path-default bindes ved IMPORT (samme
felle api_status()s egen kommentar dokumenterer for CACHE_DB) — å patche bank.DB etter
import ville derfor ikke truffet dem. Funksjonsnivå-mocking unngår fellen helt.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(api.app)


def test_utkast_lagre_og_hente():
    with patch("api.bank.lagre_utkast", return_value={"id": 1, "tittel": "t", "innhold": "i", "oppdatert": 123.0}) as m:
        r = client.post("/api/utkast", json={"tittel": "t", "innhold": "i"})
    assert r.status_code == 200
    assert r.json()["id"] == 1
    m.assert_called_once_with("t", "i", None)


def test_utkast_lagre_tom_tittel_degraderer_ikke_feiler():
    with patch("api.bank.lagre_utkast", return_value={"id": 1, "tittel": "Uten tittel", "innhold": "i", "oppdatert": 1.0}) as m:
        client.post("/api/utkast", json={"innhold": "i"})
    m.assert_called_once_with("Uten tittel", "i", None)


def test_utkast_hent_ukjent_gir_404():
    with patch("api.bank.hent_utkast", return_value=None):
        r = client.get("/api/utkast/999")
    assert r.status_code == 404


def test_relevans_returnerer_naboer():
    naboer = [{"id": "10.1/x", "tittel": "t", "avstand": 0.3}]
    with patch("api.bank.lignende_tekst", return_value=naboer) as m:
        r = client.get("/api/relevans", params={"tekst": "noe langt nok tekst her"})
    assert r.status_code == 200
    assert r.json()["naboer"] == naboer
    m.assert_called_once()


def test_relevans_tomt_svar_er_200_ikke_feil():
    """Ærlig tomt (ingen treff/for kort tekst) skal se ut som stillhet, ikke en feil —
    FDR-038s eget krav."""
    with patch("api.bank.lignende_tekst", return_value=[]):
        r = client.get("/api/relevans", params={"tekst": "kort"})
    assert r.status_code == 200
    assert r.json()["naboer"] == []


def test_omfang_returnerer_akser():
    akser = {"Lever": 1.0, "Faser": 0.0}
    with patch("api.scoping.akse_dekning", return_value=akser):
        r = client.get("/api/omfang", params={"tekst": "noe om lever"})
    assert r.status_code == 200
    assert r.json()["akser"] == akser
