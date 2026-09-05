"""Verifiserer rapport.konvergens_blokker: at de fem seksjonene flettes, og at hver er
ærlig om fravær (mangler gap-papiret → ingen gap-seksjon; verifisering ikke tilgjengelig →
sies rett ut, ikke utelates stille).

Nettverksfri: konvergens_blokker tar ferdig-beregnede biter inn (api.py gjør søket/gap).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
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
