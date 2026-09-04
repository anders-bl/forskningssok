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


def test_glitchtip_er_av_uten_dsn_og_velter_aldri_oppstarten():
    """Feilsporing er en observasjonstjeneste. Den skal ALDRI kunne hindre at appen
    starter — hverken ved å mangle, ved å ha tom DSN, eller ved at pakken ikke er
    installert i utviklingsmiljøet. Tom DSN = ingen sentry_sdk.init i det hele tatt."""
    import importlib
    import os
    import api
    with patch.dict(os.environ, {"GLITCHTIP_DSN": ""}, clear=False):
        importlib.reload(api)
    assert api.app is not None
    assert api._GLITCHTIP_DSN == ""
    importlib.reload(api)


def test_glitchtip_init_kalles_naar_dsn_er_satt():
    import importlib
    import os
    import sys
    from unittest.mock import MagicMock
    falsk = MagicMock()
    with patch.dict(sys.modules, {"sentry_sdk": falsk}), \
         patch.dict(os.environ, {"GLITCHTIP_DSN": "https://x@feil.lauvasdata.no/1"}, clear=False):
        import api
        importlib.reload(api)
    falsk.init.assert_called_once()
    # traces_sample_rate=0 med vilje: vi vil ha FEIL, ikke ytelsessporing — det siste ville
    # sendt hver request til en tredjepart uten at noen ba om det.
    assert falsk.init.call_args.kwargs["traces_sample_rate"] == 0
    import api as _a
    importlib.reload(_a)


# ---------- Scoping-porten for feilsporing (2026-09-04) ----------

def test_kilde_nede_er_vaer_ikke_en_hendelse():
    """EBI lå nede i DAGEVIS i september. Uten porten ville hvert eneste brukersøk blitt
    en hendelse i GlitchTip, og kanalen ville druknet — 1851 uleste varsler hvorav ett
    fra et menneske er husets egen måling av den feilmodusen."""
    from fastapi import HTTPException
    import api
    for kode in (502, 503, 504):
        assert api._skal_rapporteres({"x": 1}, {"exc_info": HTTPException(kode, "nede")}) is None


def test_forventet_avvisning_er_ikke_en_bug():
    from fastapi import HTTPException
    import api
    for kode in (400, 404, 422):
        assert api._skal_rapporteres({"x": 1}, {"exc_info": HTTPException(kode, "input")}) is None


def test_vaar_egen_feil_slipper_gjennom():
    from fastapi import HTTPException
    import api
    hendelse = {"x": 1}
    assert api._skal_rapporteres(hendelse, {"exc_info": HTTPException(500, "vår")}) is hendelse
    assert api._skal_rapporteres(hendelse, {"exc_info": ValueError("ufanget")}) is hendelse
    assert api._skal_rapporteres(hendelse, None) is hendelse
    assert api._skal_rapporteres(hendelse, {}) is hendelse


def test_degraderingsrapport_er_noop_uten_dsn_og_kaster_aldri():
    """En feil i feilsporingen som velter forespørselen ville vært verre enn den
    opprinnelige feilen."""
    import api
    assert api._GLITCHTIP_DSN == ""
    api._rapporter_degradering("test")     # skal ikke kaste


def test_live_er_billig_og_rorer_verken_disk_eller_nett():
    """/health/live skal svare så lenge prosessen lever. Ingen eksterne kall, ingen disk —
    en Docker HEALTHCHECK som leser databasen ville drept containeren ved disk-treghet."""
    import api
    from fastapi.testclient import TestClient
    with patch("api._kilde_naabar") as naabar, patch("api.bank._db") as db:
        r = TestClient(api.app).get("/health/live")
    assert r.status_code == 200 and r.json() == {"status": "pass"}
    assert r.headers["content-type"].startswith("application/health+json")
    naabar.assert_not_called()
    db.assert_not_called()


def test_ready_asserterer_paa_INNHOLD_ikke_bare_paa_200():
    """FDR-065-lærdommen: en monitor mot skallet melder GRØNT i nedetid. En tom cache kan
    ikke besvare et eneste søk, så den er fail — ikke warn, og ikke pass."""
    import api
    from fastapi.testclient import TestClient
    with patch("api.bank._db") as db:
        db.return_value.execute.return_value.fetchone.return_value = (0,)
        r = TestClient(api.app).get("/health/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "fail"


def test_ready_er_503_naar_cachen_ikke_er_lesbar():
    import api
    from fastapi.testclient import TestClient
    with patch("api.bank._db", side_effect=OSError("disk borte")):
        r = TestClient(api.app).get("/health/ready")
    assert r.status_code == 503


def test_helse_lekker_ingen_tall_uten_noekkel():
    """Stien er unntatt auth-gaten i Traefik, så den er OFFENTLIG. Uten nøkkel skal den
    ikke røpe antall papirer, profilnavn eller tjenestenavn — kun status."""
    import api
    from fastapi.testclient import TestClient
    r = TestClient(api.app).get("/health")
    assert set(r.json()) == {"status"}
    assert "papirer" not in r.text and "Fiskehelse" not in r.text


def test_helse_gir_detalj_med_riktig_noekkel():
    import os
    import api
    from fastapi.testclient import TestClient
    with patch.dict(os.environ, {"INTERNAL_API_KEY": "hemmelig"}, clear=False):
        r = TestClient(api.app).get("/health", headers={"X-Internal-Key": "hemmelig"})
    assert "checks" in r.json()
    assert r.json()["checks"]["cache:innhold"][0]["observedValue"]["papirer"] >= 0


def test_nede_kilde_gir_WARN_ikke_FAIL():
    """En nede kilde er ikke VÅR nedetid: cachen svarer, sitatbanken virker, «Lignende»
    virker. Å la Europe PMC-nedetid gjøre /ready rød ville vekket Anders for en annens
    driftsavbrudd — og EBI lå nede i DAGEVIS i september."""
    import api
    from fastapi.testclient import TestClient
    nede = [{"kilde": "europe_pmc", "sist_ok": 1.0, "sist_feil": 2.0,
             "feil_paa_rad": 5, "siste_feilmelding": "503"}]
    with patch("api.bank.kilde_status", return_value=nede):
        r = TestClient(api.app).get("/health/ready")
    assert r.status_code == 200, "warn er ikke fail — tjenesten er oppe"
    assert r.json()["status"] == "warn"


def test_kilde_under_terskel_er_fortsatt_pass():
    """Ett enkelt timeout er vær, ikke nedetid."""
    import api
    from fastapi.testclient import TestClient
    with patch("api.bank.kilde_status", return_value=[
            {"kilde": "europe_pmc", "sist_ok": 1.0, "sist_feil": 2.0,
             "feil_paa_rad": 2, "siste_feilmelding": "timeout"}]):
        r = TestClient(api.app).get("/health/ready")
    assert r.json()["status"] == "pass"


def test_kilde_detalj_navngir_kilden_bak_noekkel():
    import os
    import api
    from fastapi.testclient import TestClient
    with patch("api.bank.kilde_status", return_value=[
            {"kilde": "europe_pmc", "sist_ok": 1.0, "sist_feil": 2.0,
             "feil_paa_rad": 4, "siste_feilmelding": "503 maintenance"}]), \
         patch.dict(os.environ, {"INTERNAL_API_KEY": "h"}, clear=False):
        r = TestClient(api.app).get("/health", headers={"X-Internal-Key": "h"})
    ut = r.json()["checks"]["kilder:naabarhet"][0]["output"]
    assert "europe_pmc" in ut and "4 feil på rad" in ut
