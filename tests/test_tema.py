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


def test_kilde_sammensetning_teller_art_og_tema_per_kilde():
    import scoping
    papirer = [
        {"id": "a", "tittel": "Vaccination against IHNV in rainbow trout", "abstract": "Vaccine immune response."},
        {"id": "b", "tittel": "Phage therapy of sea cucumber", "abstract": "Virus infection of the sea cucumber."},
        {"id": "c", "tittel": "Skeletal deformities in fish", "abstract": ""},
    ]
    s = scoping.kilde_sammensetning(papirer)
    assert s["antall"] == 3
    assert s["art"] == {"maal": 1, "naer": 1, "annet": 1, "ingen": 0}
    assert s["temaer"]["immun"]["kilder"] == 1 and s["temaer"]["skjelett"]["andel"] == 0.33
    assert scoping.kilde_sammensetning([]) == {"antall": 0, "art": {n: 0 for n in ("maal", "naer", "annet", "ingen")}, "temaer": {}}


def test_omfang_endepunktet_beholder_akser_og_legger_til_temaer():
    from fastapi.testclient import TestClient
    import api
    r = TestClient(api.app).get("/api/omfang", params={"tekst": "Kidney nephrocalcinosis and calcium in the urine"})
    d = r.json()
    assert r.status_code == 200 and "akser" in d
    assert d["temaer"][0]["tema"] == "nyre" and d["temaer"][0]["bevis"]


def test_konvergensrapporten_har_kildesammensetning_med_ærlig_forbehold():
    import rapport
    sam = {"antall": 4, "art": {"maal": 2, "naer": 1, "annet": 1, "ingen": 0},
           "temaer": {"infeksjon": {"kilder": 3, "andel": 0.75}, "immun": {"kilder": 2, "andel": 0.5}}}
    b = rapport.konvergens_blokker("q", [{"id": 1, "tittel": "T", "abstract": "a", "forfattere": "F", "aar": 2024}],
                                   sammensetning=sam)
    tekst = " ".join(getattr(x, "tekst", "") or "" for x in b)
    assert "Kildesammensetning" in tekst and "2 av 4 kilder" in tekst and "målarten (laksefisk)" in tekst
    assert "infeksjon 3" in tekst and "ikke en dom" in tekst
    uten = rapport.konvergens_blokker("q", [{"id": 1, "tittel": "T", "abstract": "a", "forfattere": "F", "aar": 2024}])
    assert "Kildesammensetning" not in " ".join(getattr(x, "tekst", "") or "" for x in uten)
