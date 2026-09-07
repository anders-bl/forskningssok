"""Verifiserer rapport.konvergens_blokker: at de fem seksjonene flettes, og at hver er
ærlig om fravær (mangler gap-papiret → ingen gap-seksjon; verifisering ikke tilgjengelig →
sies rett ut, ikke utelates stille).

Nettverksfri: konvergens_blokker tar ferdig-beregnede biter inn (api.py gjør søket/gap).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from unittest.mock import patch  # noqa: E402
import rapport  # noqa: E402

_PAPIR = {
    "id": "10.1111/jfd.13815", "doi": "10.1111/jfd.13815",
    "tittel": "Nephrocalcinosis in juvenile farmed Atlantic Salmon",
    "forfattere": "Klykken C, Reed AK", "tidsskrift": "Journal of Fish Diseases",
    "aar": 2023, "volum": "46", "sider": "943-956",
}
_REVISJON = {"treff_per_kilde": {"europe_pmc": 20, "core": 5}, "cache_alder_s": 1800,
             "dubletter_fjernet": 2, "kilder": {"europe_pmc": True, "core": True}, "profil": "Fiskehelse"}


def _tekst(blokker):
    return rapport.til_markdown(blokker)


def test_alle_fem_seksjoner_naar_alt_er_gitt():
    gap = {"siterte_antall": 20, "referanse_kilde": "openalex", "naboer": [],
           "gap": [{"tittel": "En nabo", "aar": 2022, "avstand": 0.7}]}
    b = rapport.konvergens_blokker(
        "nefrokalsinose", [_PAPIR], gap_papir=_PAPIR, gap=gap,
        omfang={"Lever": 0.5, "Nyre": 1.0}, revisjon=_REVISJON,
        verifisering={"tilgjengelig": False})
    md = _tekst(b)
    for seksjon in ("Kilder", "Hva litteraturen mangler", "Omfang", "Verifisering", "Referanser"):
        assert seksjon in md, f"mangler seksjon: {seksjon}"


def test_proveniens_linje_baerer_hard_empiri():
    b = rapport.konvergens_blokker("q", [_PAPIR], revisjon=_REVISJON)
    md = _tekst(b)
    assert "Europe PMC 20" in md and "CORE 5" in md
    assert "Fiskehelse" in md
    assert "av Lauvasdata" in md


def test_uten_gap_ingen_gap_seksjon():
    """Mangler gap-papiret (kilden var nede), står seksjonen ikke — ikke en tom overskrift."""
    b = rapport.konvergens_blokker("q", [_PAPIR], gap=None, gap_papir=None)
    assert "Hva litteraturen mangler" not in _tekst(b)


def test_verifisering_utilgjengelig_sies_rett_ut():
    """Ærlig fravær: kapabiliteten finnes men er gated (Mistral-abonnement). Rapporten sier
    det, den utelater det ikke stille."""
    b = rapport.konvergens_blokker("q", [_PAPIR], verifisering={"tilgjengelig": False})
    md = _tekst(b)
    assert "Verifisering" in md
    assert "ikke aktivert" in md.lower() or "ikke aktivert i dette miljøet" in md


def test_verifisering_tilgjengelig_gir_annen_tekst():
    b = rapport.konvergens_blokker("q", [_PAPIR], verifisering={"tilgjengelig": True})
    assert "Verifiser" in _tekst(b)


def test_referanser_kommer_sist_og_er_formatert():
    b = rapport.konvergens_blokker("q", [_PAPIR], stil="vancouver")
    md = _tekst(b)
    idx_kilder = md.index("## Kilder")
    idx_ref = md.index("## Referanser")
    assert idx_ref > idx_kilder, "referanser skal komme etter kildene"
    assert "Klykken" in md[idx_ref:]


def test_pdf_variant_bygger_uten_krasj():
    """Konvergensen skal kunne rendres til PDF (reportlab), ikke bare Markdown."""
    gap = {"siterte_antall": 5, "referanse_kilde": "openalex", "naboer": [],
           "gap": [{"tittel": "Nabo", "aar": 2022, "avstand": 0.7}]}
    b = rapport.konvergens_blokker("q", [_PAPIR], gap_papir=_PAPIR, gap=gap,
                                   omfang={"Nyre": 1.0}, revisjon=_REVISJON,
                                   verifisering={"tilgjengelig": False})
    pdf = rapport.til_pdf_bytes(b, tittel="Test")
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000


# ---------- Tverrfaglige retninger (smartsyntese-veikart fase 1, 2026-09-07) ----------

def _nabo(tittel, dist, domene, art, aar=2020, ts="J", url="https://x/1"):
    return {"id": tittel, "tittel": tittel, "tidsskrift": ts, "aar": aar, "doi": None,
            "kilde_url": url, "avstand": dist, "forfattere": "Doe J",
            "domene_naer": domene, "arts_naer": art}


def test_tverrfaglig_seksjon_viser_kun_ekte_papirer_med_kilde():
    from rapport import konvergens_blokker, Blokk
    tv = [_nabo("Signal processing in ultrasound arrays", 0.72, False, False)]
    b = konvergens_blokker("q", [_PAPIR], tverrfaglig=tv)
    typer = [(x.type, x.tekst) for x in b]
    assert ("h2", "Tverrfaglige retninger") in typer
    assert any(x.type == "p" and "Signal processing" in x.tekst and "0.720" in x.tekst for x in b)
    assert any(x.type == "lenke" and x.tekst == "https://x/1" for x in b)  # kilde med, mekanisk majoritet
    # ingen LLM-parafrase: seksjonen er rene papir-linjer + meta, ingen syntese-blokk
    assert not any(x.type == "p" and "oppsummer" in x.tekst.lower() for x in b)


def test_tverrfaglig_tomt_sier_fra_aerlig():
    from rapport import konvergens_blokker
    b = konvergens_blokker("q", [_PAPIR], tverrfaglig=[])
    assert any(x.type == "h2" and x.tekst == "Tverrfaglige retninger" for x in b)
    assert any(x.type == "p" and "Ingen kryssfelt-naboer" in x.tekst for x in b)


def test_tverrfaglig_none_gir_ogsaa_aerlig_tomt():
    from rapport import konvergens_blokker
    b = konvergens_blokker("q", [_PAPIR])  # ingen tverrfaglig-arg
    assert any(x.type == "p" and "Ingen kryssfelt-naboer" in x.tekst for x in b)


def test_konvergens_json_format_gir_blokker_for_in_app_rendring():
    """format=json (smartsyntese fase 1: rapporten sydd inn i flaten) gir Blokk-lista som
    typede items — frontend rendrer dem, serveren sender aldri HTML."""
    from fastapi.testclient import TestClient
    import api
    from schemas import PaperDossier
    treff = [PaperDossier(pmid="1", doi="10.1/a", tittel="T", forfattere="Doe J",
                          tidsskrift="J", aar=2024, abstract="x", siteringstall=1,
                          open_access=True, kilde_url="https://x/a")]
    _REV = {"kilder": {"europe_pmc": True, "core": True}, "treff_per_kilde": {"europe_pmc": 1, "core": 0},
            "etter_dedup": 1, "dubletter_fjernet": 0, "cache_alder_s": None, "profil": "test",
            "baand": {"domene_naer": 0, "arts_naer": 0}, "ms": 1}
    with patch("api.sok_og_ranger", return_value=(treff, None, _REV)), \
         patch("api._lagre_bakgrunn"), patch("api.bank.hent", side_effect=lambda i: {
             "id": "10.1/a", "tittel": "T", "forfattere": "Doe J", "tidsskrift": "J", "aar": 2024,
             "abstract": "x", "doi": "10.1/a", "pmid": "1", "kilde_url": "https://x/a", "kilde_kode": "MED"}), \
         patch("api.bank.lignende", return_value=[]), \
         patch("api.verifiser_modul.tilgjengelig", return_value=False):
        r = TestClient(api.app).get("/api/rapport/konvergens?q=test&format=json")
    assert r.status_code == 200
    blokker = r.json()["blokker"]
    assert blokker[0]["type"] == "h1"
    assert any(b["type"] == "h2" and "Tverrfaglige" in b["tekst"] for b in blokker)
    assert all(set(b) == {"type", "tekst"} for b in blokker)  # ren data, ingen HTML
