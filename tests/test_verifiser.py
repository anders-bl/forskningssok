"""Verifiserer verifiser.py: FDR-028-disiplinen om at et verdikt UTEN kilder er
uverifisert, og at feil forplantes som RuntimeError, aldri et stille tomt svar.

Nettverksfri (CLAUDE.md §Testing): ai-proxy-kallet mockes via `post_fn`. Suiten skal aldri
røre en ekte tredjepart, og verifisering er nettopp et kostet web-søk.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import verifiser  # noqa: E402


class _Svar:
    def __init__(self, status=200, data=None, tekst="", ugyldig_json=False):
        self.status_code = status
        self._data = data if data is not None else {}
        self._ugyldig = ugyldig_json
        self.text = tekst

    def json(self):
        if self._ugyldig:
            raise ValueError("ikke JSON")
        return self._data


def _post(status=200, data=None, tekst="", ugyldig_json=False):
    return lambda *a, **k: _Svar(status, data, tekst, ugyldig_json)


@pytest.fixture(autouse=True)
def _proxy(monkeypatch):
    monkeypatch.setenv("AI_PROXY_URL", "http://ai-proxy:8000")
    monkeypatch.setenv("AI_PROXY_WIKI_ID", "forskningssok")


def test_verdikt_med_kilder_er_verifisert():
    ut = verifiser.verifiser(
        "Nefrokalsinose hos laks er koblet til CO2 i RAS-anlegg.",
        post_fn=_post(data={"verdict": "Delvis støttet av litteraturen.",
                            "sources": [{"url": "https://example.org/a", "title": "Studie A"}]}))
    assert ut["verifisert"] is True
    assert ut["verdikt"].startswith("Delvis")
    assert len(ut["kilder"]) == 1


def test_verdikt_UTEN_kilder_er_uverifisert_ikke_gronn():
    """FDR-028s bærende regel. Mistral svarer noen ganger fra egen trening uten å hente
    kilder — da MÅ svaret leses som uverifisert, ikke som en bekreftelse."""
    ut = verifiser.verifiser(
        "En påstand modellen tror den kan fra trening.",
        post_fn=_post(data={"verdict": "Ja, dette stemmer.", "sources": []}))
    assert ut["verifisert"] is False
    assert ut["verdikt"] == "Ja, dette stemmer.", "verdiktet vises fortsatt, bare umerket"


def test_kilde_uten_url_teller_ikke():
    """En kilde uten hentbar url er ikke en kilde. `verifisert` skal ikke kunne heves av
    et tomt referanse-objekt."""
    ut = verifiser.verifiser(
        "Noe som skal verifiseres her.",
        post_fn=_post(data={"verdict": "Uklart.", "sources": [{"title": "uten url"}]}))
    assert ut["verifisert"] is False and ut["kilder"] == []


def test_for_kort_paastand_avvises():
    with pytest.raises(RuntimeError, match="for kort"):
        verifiser.verifiser("nei", post_fn=_post())


def test_manglende_proxy_gir_aerlig_feil(monkeypatch):
    monkeypatch.delenv("AI_PROXY_URL", raising=False)
    with pytest.raises(RuntimeError, match="AI_PROXY_URL"):
        verifiser.verifiser("En påstand som ikke kan verifiseres lokalt.")


def test_rate_limit_forplantes_lesbart():
    with pytest.raises(RuntimeError, match="rate-limitert"):
        verifiser.verifiser("En påstand.", post_fn=_post(status=429, tekst="for mange"))


def test_ai_proxy_feil_gir_runtimeerror_ikke_tomt_svar():
    with pytest.raises(RuntimeError, match="502"):
        verifiser.verifiser("En påstand.", post_fn=_post(status=502, tekst="nede"))


def test_ugyldig_json_er_en_feil_ikke_et_verdikt():
    with pytest.raises(RuntimeError, match="ugyldig JSON"):
        verifiser.verifiser("En påstand.", post_fn=_post(ugyldig_json=True))


def test_nettverksfeil_forplantes():
    import httpx

    def kaster(*a, **k):
        raise httpx.ConnectError("nede")
    with pytest.raises(RuntimeError, match="utilgjengelig"):
        verifiser.verifiser("En påstand.", post_fn=kaster)


def test_tilgjengelig_folger_env(monkeypatch):
    assert verifiser.tilgjengelig() is True
    monkeypatch.delenv("AI_PROXY_URL", raising=False)
    assert verifiser.tilgjengelig() is False


# ── Endepunktet ──────────────────────────────────────────────────────────────────────

def test_endepunkt_gir_502_ved_feil_ikke_500(monkeypatch):
    monkeypatch.delenv("AI_PROXY_URL", raising=False)
    import api
    from fastapi.testclient import TestClient
    r = TestClient(api.app).post("/api/verifiser", json={"paastand": "En testpåstand her."})
    assert r.status_code == 502
    assert "AI_PROXY_URL" in r.json()["detail"]


def test_endepunkt_tilgjengelig_speiler_env(monkeypatch):
    monkeypatch.setenv("AI_PROXY_URL", "http://ai-proxy:8000")
    import api
    from fastapi.testclient import TestClient
    r = TestClient(api.app).get("/api/verifiser/tilgjengelig")
    assert r.json() == {"tilgjengelig": True}
