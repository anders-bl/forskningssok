"""Verifiserer HTTP-laget for varme, sitat-hybriden og dokument-eksporten. Mocker på
bank.X-funksjonsnivå, ikke DB-sti — se test_api_skriv.py sin moduldocstring for hvorfor
(db_path-defaults bindes ved import).
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(api.app)


def _varm(pid, poeng, hendelse="apnet", **rest):
    return {"id": pid, "tittel": f"T{pid}", "tidsskrift": "J", "aar": 2026, "doi": None,
            "kilde_url": "", "poeng": poeng, "sist_rort": 1.0, "sterkeste_hendelse": hendelse,
            "domene_naer": False, "arts_naer": True, **rest}


def _nabo(pid, avstand, **rest):
    return {"id": pid, "tittel": f"T{pid}", "tidsskrift": "J", "aar": 2026, "doi": None,
            "kilde_url": "", "avstand": avstand, "domene_naer": False, "arts_naer": True, **rest}


# ---------- POST /api/varme: bare de svake signalene slipper inn utenfra ----------

def test_apnet_slipper_gjennom():
    with patch("api.bank.varm_opp") as m:
        r = client.post("/api/varme", json={"paper_id": "10.1/x", "hendelse": "apnet"})
    assert r.status_code == 200
    m.assert_called_once_with("10.1/x", "apnet")


def test_sitert_kan_ikke_settes_utenfra():
    """De sterke vektene legges server-side der handlingen faktisk skjer. Uten denne
    porten kunne en klient blåst opp varmen uten å ha sitert noe."""
    with patch("api.bank.varm_opp") as m:
        r = client.post("/api/varme", json={"paper_id": "10.1/x", "hendelse": "sitert"})
    assert r.status_code == 400
    m.assert_not_called()


def test_varme_uten_paper_id_er_400():
    assert client.post("/api/varme", json={"hendelse": "apnet"}).status_code == 400


def test_feilet_varme_velter_aldri_handlingen():
    """Varme er et biprodukt. En låst db skal aldri gjøre et lagret sitat om til 500."""
    with patch("api.bank.varm_opp", side_effect=RuntimeError("db låst")):
        r = client.post("/api/varme", json={"paper_id": "10.1/x", "hendelse": "apnet"})
    assert r.status_code == 200


# ---------- GET /api/varme: to lag, slått sammen men aldri blandet ----------

def test_to_lag_holdes_adskilt_paa_samme_kort():
    with patch("api.bank.varmeliste", return_value=[_varm("A", 8.0, "sitert")]), \
         patch("api.bank.lignende_tekst", return_value=[_nabo("A", 0.25)]):
        d = client.get("/api/varme", params={"tekst": "x" * 40}).json()
    rad = d["papirer"][0]
    assert rad["varig_andel"] == 1.0            # varig: relativt til listas maks
    assert rad["naa_andel"] == 0.875            # nå: absolutt, 1 - 0.25/2
    assert rad["aarsaker"] == ["du siterte det", "nær det du har sitert"]
    assert rad["avstand"] == 0.25


def test_papir_kun_i_naa_laget_har_null_varig():
    with patch("api.bank.varmeliste", return_value=[_varm("A", 8.0)]), \
         patch("api.bank.lignende_tekst", return_value=[_nabo("B", 0.1)]):
        d = client.get("/api/varme", params={"tekst": "x" * 40}).json()
    rader = {r["id"]: r for r in d["papirer"]}
    assert rader["B"]["varig_andel"] == 0.0 and rader["B"]["naa_andel"] == 0.95
    assert rader["A"]["naa_andel"] == 0.0
    assert rader["B"]["aarsaker"] == ["nær det du har sitert"]


def test_naa_laget_er_absolutt_ikke_normalisert_mot_gruppen():
    """Reprodusert live 2026-09-04: tolv kandidater med 5 % spredning i avstand ble
    ALLE tegnet som nesten fulle stolper under maks-normalisering. En flat gruppe skal
    se flat ut, ikke brennhet — og snuingen (lavere avstand = lengre stolpe) må stå."""
    with patch("api.bank.varmeliste", return_value=[]), \
         patch("api.bank.lignende_tekst", return_value=[_nabo("naer", 0.1), _nabo("fjern", 0.9)]):
        d = client.get("/api/varme", params={"tekst": "x" * 40}).json()
    rader = {r["id"]: r for r in d["papirer"]}
    assert rader["naer"]["naa_andel"] > rader["fjern"]["naa_andel"]
    assert rader["naer"]["naa_andel"] == 0.95 and rader["fjern"]["naa_andel"] == 0.55


def test_tom_tekst_gir_kun_varig_lag_og_sier_fra():
    with patch("api.bank.varmeliste", return_value=[_varm("A", 3.0)]), \
         patch("api.bank.lignende_tekst") as m:
        d = client.get("/api/varme").json()
    m.assert_not_called()  # ingen embedding-kall på tom tekst
    assert d["har_naa_lag"] is False
    assert d["papirer"][0]["naa_andel"] == 0.0


def test_tomt_paa_begge_lag_er_tom_liste_ikke_feil():
    with patch("api.bank.varmeliste", return_value=[]), \
         patch("api.bank.lignende_tekst", return_value=[]):
        r = client.get("/api/varme", params={"tekst": "x" * 40})
    assert r.status_code == 200 and r.json()["papirer"] == []


def test_banding_gaar_foran_varme():
    """Samme kontrakt som resten av huset: domene-/artsnærhet sorteres FØR styrken.
    Et humanmedisinsk treff skal ikke ligge øverst bare fordi det er varmt."""
    with patch("api.bank.varmeliste", return_value=[
            _varm("varm-men-feil-art", 9.0, arts_naer=False),
            _varm("kald-men-riktig", 1.0, arts_naer=True)]), \
         patch("api.bank.lignende_tekst", return_value=[]):
        d = client.get("/api/varme").json()
    assert d["papirer"][0]["id"] == "kald-men-riktig"


# ---------- Sitater: utkast_id inn, varme ut ----------

def test_sitat_sender_utkast_id_videre_og_varmer():
    with patch("api.bank.lagre_sitat", return_value={"id": 1}) as m, \
         patch("api.bank.varm_opp") as v:
        r = client.post("/api/sitater", json={"paper_id": "10.1/x", "tekst": "t", "utkast_id": 7})
    assert r.status_code == 200
    m.assert_called_once_with("10.1/x", "t", "", 7)
    v.assert_called_once_with("10.1/x", "sitert")


def test_sitat_uten_utkast_id_lagres_lost():
    with patch("api.bank.lagre_sitat", return_value={"id": 1}) as m, patch("api.bank.varm_opp"):
        client.post("/api/sitater", json={"paper_id": "10.1/x", "tekst": "t"})
    assert m.call_args.args[3] is None


def test_losne_bruker_nokkelens_tilstedevaerelse_ikke_sannhetsverdien():
    """utkast_id=null ER en gyldig verdi («løsne»). Ble den lest som falsy, ville
    løsne-knappen stille ikke gjort noe."""
    with patch("api.bank.knytt_sitat", return_value=True) as m:
        r = client.patch("/api/sitater/5", json={"utkast_id": None})
    assert r.status_code == 200
    m.assert_called_once_with(5, None)


def test_feste_varmer_papiret_bak_sitatet():
    with patch("api.bank.knytt_sitat", return_value=True), \
         patch("api.bank.hent_sitater", return_value=[{"id": 5, "paper_id": "10.1/x"}]), \
         patch("api.bank.varm_opp") as v:
        client.patch("/api/sitater/5", json={"utkast_id": 7})
    v.assert_called_once_with("10.1/x", "dokument")


def test_patch_uten_treff_er_404():
    with patch("api.bank.oppdater_sitat", return_value=False):
        assert client.patch("/api/sitater/5", json={"kommentar": "k"}).status_code == 404


def test_sitatliste_sender_linsene_videre():
    with patch("api.bank.hent_sitater", return_value=[]) as m:
        client.get("/api/sitater", params={"kun_lose": "true"})
    assert m.call_args.kwargs["kun_lose"] is True


# ---------- Dokument-eksporten ----------

def test_dokument_markdown_skiller_egen_tekst_fra_sitert():
    utkast = {"id": 1, "tittel": "Mitt notat", "innhold": "Egen setning.", "oppdatert": 1.0}
    sitater = [{"id": 1, "tekst": "sitert setning", "kommentar": "", "opprettet": 1.0,
                "paper_tittel": "Kilden", "paper_doi": "10.1/x", "paper_forfattere": "Ulven, N",
                "paper_tidsskrift": "J Fish Dis", "paper_aar": 2026}]
    with patch("api.bank.hent_utkast", return_value=utkast), \
         patch("api.bank.hent_sitater", return_value=sitater):
        r = client.get("/api/rapport/dokument", params={"utkast_id": 1})
    md = r.text
    assert "# Mitt notat" in md
    assert "Egen setning." in md
    assert "> sitert setning" in md          # sitert tekst er markert som sitat
    assert "Egen setning." not in md.split("> sitert setning")[1]
    assert "doi:10.1/x" in md


def test_dokument_ukjent_utkast_er_404():
    with patch("api.bank.hent_utkast", return_value=None):
        assert client.get("/api/rapport/dokument", params={"utkast_id": 9}).status_code == 404


def test_dokument_pdf_er_ekte_pdf():
    with patch("api.bank.hent_utkast", return_value={"id": 1, "tittel": "T", "innhold": "tekst"}), \
         patch("api.bank.hent_sitater", return_value=[]):
        r = client.get("/api/rapport/dokument", params={"utkast_id": 1, "format": "pdf"})
    assert r.content.startswith(b"%PDF")


def test_kildelinje_dobler_ikke_punktum_i_tittelen():
    """Europe PMC leverer mange titler med punktum bakt inn. «… Considerations..» så ut
    som en feil i den delte PDF-en (målt live 2026-09-04)."""
    from rapport import _kildelinje
    assert _kildelinje({"paper_tittel": "En tittel."}).endswith("En tittel.")
    assert _kildelinje({"paper_tittel": "En tittel"}).endswith("En tittel.")
