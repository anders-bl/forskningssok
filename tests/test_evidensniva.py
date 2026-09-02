"""Verifiserer evidensniva.py — bevisst enkel mønster-heuristikk, ikke en klassifikator.
Se moduldocstring for hvorfor: signalord forfattere selv bruker, aldri en kvalitetsdom."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evidensniva import evidensniva  # noqa: E402


def test_systematisk_oversikt_gjenkjennes():
    assert evidensniva("A systematic review of X", "") == "Systematisk oversikt/meta-analyse"
    assert evidensniva("", "This meta-analysis pooled 12 studies") == "Systematisk oversikt/meta-analyse"


def test_rct_gjenkjennes():
    assert evidensniva("A randomized controlled trial of Y", "") == "Randomisert kontrollert studie"


def test_kohortstudie_gjenkjennes():
    assert evidensniva("", "A prospective cohort study of salmon health") == "Kohort-/observasjonsstudie"


def test_case_rapport_gjenkjennes():
    assert evidensniva("A case report of Z", "") == "Case-rapport/case-serie"


def test_ingen_treff_gir_ukjent_ikke_lavt_nivaa():
    assert evidensniva("Nephrocalcinosis in Atlantic salmon", "abstract uten designord") == "Ukjent design"


def test_tom_tekst_gir_ukjent_ikke_feil():
    assert evidensniva("", "") == "Ukjent design"
    assert evidensniva(None, None) == "Ukjent design"


def test_hoeyeste_nivaa_vinner_ved_flere_treff():
    """En oversikt som nevner en case-serie den diskuterer skal klassifiseres som
    oversikten — rekkefølgen i NIVAAER avgjør, ikke siste treff."""
    tekst = "A systematic review including several case reports of X"
    assert evidensniva(tekst, "") == "Systematisk oversikt/meta-analyse"
