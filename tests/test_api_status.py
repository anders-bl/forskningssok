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


def test_helse_er_billig_og_gjor_ingen_utgaaende_kall():
    """En monitor hvert 60. sekund ville gjort 7 200 kall til fire tredjeparter i døgnet
    om den traff /api/status. Husets høflighets-disiplin gjelder også vår egen overvåking."""
    import api
    with patch("api._kilde_naabar") as naabar:
        from fastapi.testclient import TestClient
        r = TestClient(api.app).get("/api/helse")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    naabar.assert_not_called()


def test_helse_er_503_naar_cachen_ikke_er_lesbar():
    """En død database er ekte nedetid for denne appen — søk, sitatbank og varme hviler
    alle på den. En monitor som bare måler at prosessen lever ville vært grønn da."""
    import api
    with patch("api.bank._db", side_effect=OSError("disk borte")):
        from fastapi.testclient import TestClient
        r = TestClient(api.app).get("/api/helse")
    assert r.status_code == 503
