"""Verifiserer tema.klassifiser (temaer per artikkel fra innholdet). Treffsikkerheten måles av
art_niva_eval.py mot tests/fixtures/art_fasit.json; her testes reglene."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import art_niva_eval  # noqa: E402
import tema  # noqa: E402


def navn(tittel, tekst=""):
    return [f.tema for f in tema.klassifiser(tittel, tekst)]


def test_tittelen_gir_temaet_med_bevis():
    funn = tema.klassifiser("Nephrocalcinosis and magnesium transport in the kidney", "")
    assert funn[0].tema == "nyre" and "kidney" in funn[0].bevis


def test_flere_temaer_per_artikkel():
    t = navn("Vaccination against a virus in farmed fish")
    assert "immun" in t and "infeksjon" in t


def test_to_treff_paa_samme_generelle_ord_er_ikke_et_tema():
    assert "okonomi" not in navn("A study of growth", "The cost was high. The cost fell. Cost again. Cost.")


def test_tekst_med_nok_ulike_treff_gir_tema():
    tekst = "Economic analysis. The price of fish and the cost of feed. Market and profit margins."
    assert "okonomi" in navn("A study", tekst)


def test_ultrasonikering_er_ikke_bildediagnostikk_ord_ved_ordstart():
    # «ultrasound» er termen; «ultrasonication» starter ikke med den og skal ikke treffe
    assert "bildediagn" not in navn("Extraction by ultrasonication of protamine", "ultrasonication was applied")


def test_kort_term_maa_vaere_helt_ord():
    assert "miljo" not in navn("Grasping the rasters", "")   # «ras» i «rasters»


def test_maks_fire_temaer_og_rangert():
    funn = tema.klassifiser("Vaccine virus welfare feed genetic kidney liver economic", "")
    assert len(funn) == 4 and funn == sorted(funn, key=lambda f: -f.score)


def test_innholdsavledet_slaar_samling_som_tema_paa_fasiten():
    r = art_niva_eval.tema_rapport(art_niva_eval.last("utvikling"))
    assert r["presisjon"] > 0.6 and r["gjenfinning"] > 0.75
