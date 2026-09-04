"""Verifiserer evidensniva.py — bevisst enkel mønster-heuristikk, ikke en klassifikator.
Se moduldocstring for hvorfor: signalord forfattere selv bruker, aldri en kvalitetsdom."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evidensniva import evidensniva  # noqa: E402


def test_systematisk_oversikt_gjenkjennes():
    assert evidensniva("A systematic review of X", "")[0] == "Systematisk oversikt/meta-analyse"
    assert evidensniva("", "This meta-analysis pooled 12 studies")[0] == "Systematisk oversikt/meta-analyse"


def test_rct_gjenkjennes():
    assert evidensniva("A randomized controlled trial of Y", "")[0] == "Randomisert kontrollert studie"


def test_kohortstudie_gjenkjennes():
    assert evidensniva("", "A prospective cohort study of salmon health")[0] == "Kohort-/observasjonsstudie"


def test_case_rapport_gjenkjennes():
    assert evidensniva("A case report of Z", "")[0] == "Case-rapport/case-serie"


def test_ingen_treff_gir_ukjent_ikke_lavt_nivaa():
    assert evidensniva("Nephrocalcinosis in Atlantic salmon", "abstract uten designord")[0] == "Ukjent design"


def test_tom_tekst_gir_ukjent_ikke_feil():
    assert evidensniva("", "")[0] == "Ukjent design"
    assert evidensniva(None, None)[0] == "Ukjent design"


def test_hoeyeste_nivaa_vinner_ved_flere_treff():
    """En oversikt som nevner en case-serie den diskuterer skal klassifiseres som
    oversikten — rekkefølgen i NIVAAER avgjør, ikke siste treff."""
    tekst = "A systematic review including several case reports of X"
    assert evidensniva(tekst, "")[0] == "Systematisk oversikt/meta-analyse"


# ---------- NLMs autoritative publikasjonstype slår heuristikken (2026-09-04) ----------

def test_nlm_vinner_over_monsteret():
    """Europe PMC har returnert pubTypeList i hvert resultType=core-svar hele tiden — i
    samme kall vi alt gjør. Et menneske hos NLM har lest papiret; en substreng-match i et
    abstract har ikke."""
    niva, kilde = evidensniva("En helt vanlig tittel", "et abstract uten designord",
                              ("Randomized Controlled Trial",))
    assert niva == "Randomisert kontrollert studie"
    assert kilde == "nlm"


def test_monsteret_er_fallback_ikke_erstattet():
    """Preprints (PPR) og CORE-treff har ingen pubTypeList i det hele tatt."""
    niva, kilde = evidensniva("A systematic review of X", "", ())
    assert niva == "Systematisk oversikt/meta-analyse"
    assert kilde == "monster"


def test_journal_article_og_review_loefter_ingenting():
    """«Journal Article» sier ingenting om design — alt er en journal article. Og «Review»
    er NLMs merkelapp for ENHVER oversikt, også narrative; å kartlegge den til
    «Systematisk oversikt» ville løftet en narrativ oversikt til toppen av et
    evidenshierarki på en autoritet den ikke har."""
    assert evidensniva("vanlig", "abstract", ("Journal Article",)) == ("Ukjent design", "")
    assert evidensniva("vanlig", "abstract", ("Review",)) == ("Ukjent design", "")


def test_kilden_returneres_alltid_saa_flaten_kan_skille():
    for args in (("A case report of Z", "", ()), ("x", "y", ("Case Reports",)), ("", "", ())):
        niva, kilde = evidensniva(*args)
        assert kilde in ("nlm", "monster", "")
        assert (kilde == "") == (niva == "Ukjent design")
