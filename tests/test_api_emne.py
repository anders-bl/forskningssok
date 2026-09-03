"""Verifiserer /api/emne/{id} — søk-doktrinens tredje modus (Utforskning). Mocker
openalex.verk_for_emne() og bank.lagre() på funksjonsnivå (samme disiplin som
test_api_skriv.py — unngår db_path-default-bindings-fellen)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from schemas import PaperDossier  # noqa: E402

client = TestClient(api.app)


def _p(tittel, aar, sit):
    return PaperDossier(pmid=None, doi=f"10.1/{tittel}", tittel=tittel, forfattere="",
                        tidsskrift="X", aar=aar, abstract="a", siteringstall=sit,
                        open_access=True, kilde_url="u", kilde="openalex")


def test_emne_utforsk_rangerer_med_husets_egen_logikk_ikke_raa_openalex_rekkefolge():
    """OpenAlex sorterer på rå siteringstall — appen skal ALLTID re-rangere med
    ranking.ranger() (domene-nærhet/ferskhet FØR siteringstall), aldri servere
    OpenAlex sin egen rekkefølge urørt."""
    gammelt_hoeyt_sitert = _p("gammelt", 2005, 500)
    ferskt_lite_sitert = _p("ferskt", 2026, 0)
    with patch("api.openalex.verk_for_emne", return_value=[gammelt_hoeyt_sitert, ferskt_lite_sitert]), \
         patch("api.bank.lagre", return_value=2):
        r = client.get("/api/emne/T10506", params={"navn": "Test-emne"})
    assert r.status_code == 200
    data = r.json()
    assert data["emne_navn"] == "Test-emne"
    titler = [p["tittel"] for p in data["papirer"]]
    assert titler == ["ferskt", "gammelt"]  # samme ADR-013-logikk som resten av appen


def test_emne_utforsk_kilde_feil_gir_502_ikke_krasj():
    with patch("api.openalex.verk_for_emne", side_effect=RuntimeError("OpenAlex utilgjengelig: x")):
        r = client.get("/api/emne/T10506")
    assert r.status_code == 502


def test_emne_utforsk_tomt_treffsett_er_200_med_tom_liste():
    with patch("api.openalex.verk_for_emne", return_value=[]), patch("api.bank.lagre", return_value=0):
        r = client.get("/api/emne/T99999")
    assert r.status_code == 200
    assert r.json()["papirer"] == []


def test_emne_utforsk_svarer_selv_om_lagre_feiler():
    """Samme klasse bug som /api/sok (2026-09-04): bank.lagre() må kjøre som BackgroundTask,
    ikke synkront — en treg/feilende cache-skriving skal ALDRI forsinke eller velte selve
    emne-responsen. Funnet ved Six-Hats-sveip av api.py etter /api/sok-fiksen, ikke ved
    gjentatt symptom — denne ruta ble oversett i den første fiksen."""
    treff = [_p("Emne-funn", 2026, 0)]

    def lagre_som_krasjer(papirer, **kw):
        raise RuntimeError("simulert feilende cache-skriving")

    with patch("api.openalex.verk_for_emne", return_value=treff), \
         patch("api.bank.lagre", side_effect=lagre_som_krasjer):
        r = client.get("/api/emne/T10506", params={"navn": "Test-emne"})
    assert r.status_code == 200
    assert r.json()["papirer"][0]["tittel"] == "Emne-funn"
