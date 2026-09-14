"""Verifiserer dossier_innsikt.py — mekaniske M1-M3-visualiseringsdata
(prosjekt/forskningssok-dossier-scivis), ingen AI, ingen nettverk.

Positiv/negativ-kontroll-mønster, samme disiplin som hage_lenkegraf.py sin
selvtest: kjent input skal gi kjent, sjekkbar output; fravær av data skal gi et
ærlig tomt/nøytralt resultat, aldri en feil eller en gjettet verdi.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dossier_innsikt as di  # noqa: E402
import scoping  # noqa: E402


def _p(aar=None, tittel="", abstract=""):
    return {"aar": aar, "tittel": tittel, "abstract": abstract}


def test_tidslinje_bucketer_kronologisk():
    papirer = [_p(aar=2017), _p(aar=2019), _p(aar=2021), _p(aar=2023), _p(aar=2023)]
    t = di.tidslinje(papirer, bucket=5)
    assert t == {2015: 2, 2020: 3}


def test_tidslinje_utelater_papirer_uten_aar_ikke_krasj():
    papirer = [_p(aar=2020), _p(aar=None), {"tittel": "mangler aar-felt helt"}]
    t = di.tidslinje(papirer)
    assert t == {2020: 1}


def test_tidslinje_tomt_korpus_gir_tomt_ikke_feil():
    assert di.tidslinje([]) == {}


def test_akse_fordeling_teller_per_papir_ikke_saturerer():
    """Regresjon mot kveldens feilslåtte første forsøk (aggregert tekst saturerte
    4 av 5 akser til 1.0). Kun ETT av to papirer nevner "liver" — skal telle 1, ikke
    la det andre papirets ordmengde dra Lever til "fullt dekket"."""
    papirer = [
        _p(tittel="Liver histopathology in farmed salmon", abstract=""),
        _p(tittel="Environmental temperature effects", abstract="salinity and co2"),
    ]
    fordeling = di.akse_fordeling(papirer)
    assert fordeling["Lever"] == 1
    assert fordeling["Miljøfaktorer"] == 1


def test_akse_fordeling_inkluderer_alle_akser_med_null():
    fordeling = di.akse_fordeling([_p(tittel="helt urelatert tekst om ingenting")])
    assert set(fordeling.keys()) == set(scoping.AKSER.keys())
    assert all(v == 0 for v in fordeling.values())


def test_akse_fordeling_tomt_korpus_gir_alle_akser_null():
    fordeling = di.akse_fordeling([])
    assert set(fordeling.keys()) == set(scoping.AKSER.keys())
    assert all(v == 0 for v in fordeling.values())


def test_art_konfidens_skiller_bekreftet_fra_usikker():
    papirer = [
        _p(tittel="Nephrocalcinosis in farmed Atlantic salmon (Salmo salar)"),
        _p(tittel="Revisiting Intranasal Salmon Calcitonin for Osteoporosis"),
    ]
    k = di.art_konfidens(papirer)
    assert k == {"bekreftet": 1, "usikker": 1}


def test_art_konfidens_tomt_korpus_gir_aerlig_null_null():
    assert di.art_konfidens([]) == {"bekreftet": 0, "usikker": 0}


def test_innsikt_samler_alt_uten_aa_kalle_hent_kandidater_flere_ganger(monkeypatch):
    kalt = []

    def fake_hent(emne, db_path):
        kalt.append(emne)
        return [_p(aar=2022, tittel="Nephrocalcinosis in Atlantic salmon Salmo salar")]

    monkeypatch.setattr(di, "hent_kandidater", fake_hent)
    ut = di.innsikt("nephrocalcinosis salmon")
    assert kalt == ["nephrocalcinosis salmon"]  # ett kall, ikke ett per M1/M2/M3
    assert ut["antall_kandidater"] == 1
    assert ut["tidslinje"] == {2020: 1}
    assert ut["art_konfidens"]["bekreftet"] == 1


def test_innsikt_tomt_emne_gir_aerlig_tomt_ikke_feil(monkeypatch):
    monkeypatch.setattr(di, "hent_kandidater", lambda emne, db_path: [])
    ut = di.innsikt("et emne uten treff")
    assert ut["antall_kandidater"] == 0
    assert ut["tidslinje"] == {}
    assert ut["art_konfidens"] == {"bekreftet": 0, "usikker": 0}
