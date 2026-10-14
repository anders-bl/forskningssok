"""Verifiserer /api/retningssamtale — tynt HTTP-lag over retningssamtale.py sin
lag_retningsrapport() (forretningslogikken er alt testet i test_retningssamtale.py).
Samme mønster som test_api_syntese.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api


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


def test_review_eksponerer_stabil_kontrakt(monkeypatch):
    monkeypatch.setattr(api.retningssamtale_modul, "lag_review",
                        lambda fritekst, kontekst="", uten_ai=False: {"kontrakt": "review.v1", "status": "fullfort",
                                          "input": {"fritekst": fritekst}})
    r = _client().post("/api/review", json={"fritekst": "noe"})
    assert r.status_code == 200
    assert r.json() == {"kontrakt": "review.v1", "status": "fullfort",
                        "input": {"fritekst": "noe"}}


def test_review_sender_kontekst_videre_kappet(monkeypatch):
    fanget = {}

    def fake(fritekst, kontekst="", uten_ai=False):
        fanget["kontekst"] = kontekst
        fanget["uten_ai"] = uten_ai
        return {"kontrakt": "review.v1"}

    monkeypatch.setattr(api.retningssamtale_modul, "lag_review", fake)
    _client().post("/api/review", json={"fritekst": "hvorfor radiologi", "kontekst": "x" * 5000})
    assert fanget["kontekst"] == "x" * 1000
    _client().post("/api/review", json={"fritekst": "noe"})
    assert fanget["kontekst"] == ""


def test_review_tom_fritekst_gir_400():
    assert _client().post("/api/review", json={"fritekst": ""}).status_code == 400


def test_review_sender_uten_ai_bare_naar_det_er_eksplisitt_true(monkeypatch):
    fanget = []
    monkeypatch.setattr(api.retningssamtale_modul, "lag_review",
                        lambda fritekst, kontekst="", uten_ai=False: fanget.append(uten_ai) or {"kontrakt": "review.v1"})
    _client().post("/api/review", json={"fritekst": "x", "uten_ai": True})
    _client().post("/api/review", json={"fritekst": "x", "uten_ai": "ja"})
    _client().post("/api/review", json={"fritekst": "x"})
    assert fanget == [True, False, False]


def test_profilert_review_krever_intern_tilgang(monkeypatch):
    monkeypatch.delenv("FORSKNINGSSOK_TILGANG", raising=False)
    monkeypatch.delenv("FORSKNINGSSOK_TILGANG_PREVIOUS", raising=False)

    r = _client().post("/api/review", json={"fritekst": "generisk sporring"},
                       headers={"X-Forskningssok-Profil": "psykologi"})

    assert r.status_code == 503


def test_profilvalg_avvises_pa_alle_andre_ruter(monkeypatch):
    monkeypatch.setenv("FORSKNINGSSOK_TILGANG", "intern-testnokkel")

    r = _client().get("/api/profil", headers={
        "X-Forskningssok-Tilgang": "intern-testnokkel",
        "X-Forskningssok-Profil": "psykologi",
    })

    assert r.status_code == 400


def test_profilert_review_bruker_profilen_fjerner_kontekst_og_resetter(monkeypatch):
    monkeypatch.setenv("FORSKNINGSSOK_TILGANG", "intern-testnokkel")
    sett = {}

    def fake(fritekst, kontekst="", uten_ai=False):
        sett["profil"] = api.domeneprofil.gjeldende_navn()
        sett["kontekst"] = kontekst
        sett["uten_ai"] = uten_ai
        return {"profil": sett["profil"]}

    monkeypatch.setattr(api.retningssamtale_modul, "lag_review", fake)
    standardprofil = api.domeneprofil.PROFIL["navn"]
    r = _client().post(
        "/api/review",
        json={"fritekst": "generisk sporring", "kontekst": "tidligere sensitiv tekst", "uten_ai": True},
        headers={
            "X-Forskningssok-Tilgang": "intern-testnokkel",
            "X-Forskningssok-Profil": "psykologi",
        },
    )

    assert r.status_code == 200
    assert r.json() == {"profil": "Psykologi og helsefremmende arbeid"}
    assert sett == {"profil": "Psykologi og helsefremmende arbeid", "kontekst": "", "uten_ai": True}
    assert api.domeneprofil.gjeldende_navn() == standardprofil


def test_ukjent_profil_gir_400_uten_a_endres_stille(monkeypatch):
    monkeypatch.setenv("FORSKNINGSSOK_TILGANG", "intern-testnokkel")
    kalt = []
    monkeypatch.setattr(api.retningssamtale_modul, "lag_review",
                        lambda *args, **kwargs: kalt.append(True) or {})

    r = _client().post("/api/review", json={"fritekst": "generisk sporring"}, headers={
        "X-Forskningssok-Tilgang": "intern-testnokkel",
        "X-Forskningssok-Profil": "ukjent-profil-til-test",
    })

    assert r.status_code == 400
    assert kalt == []


def test_feil_internnokkel_avviser_profilert_review(monkeypatch):
    monkeypatch.setenv("FORSKNINGSSOK_TILGANG", "riktig-testnokkel")
    monkeypatch.setattr(api.retningssamtale_modul, "lag_review", lambda *args, **kwargs: {})

    r = _client().post("/api/review", json={"fritekst": "generisk sporring"}, headers={
        "X-Forskningssok-Tilgang": "feil-testnokkel",
        "X-Forskningssok-Profil": "psykologi",
    })

    assert r.status_code == 401
