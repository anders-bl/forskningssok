"""Verifiserer domeneprofil.py isolert — ranking.py/scoping.py sine egne tester
(test_ranking.py, test_scoping.py) dekker allerede at de re-eksporterer riktig, dette
dekker kun selve substreng-matchen som nå bor her."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from domeneprofil import AKSER, domene_naer_tekst  # noqa: E402


def test_domene_naer_tekst_matcher_norsk_fagmiljoe():
    assert domene_naer_tekst("Ola Nordmann, Havforskningsinstituttet")


def test_domene_naer_tekst_matcher_fagtidsskrift():
    assert domene_naer_tekst("Jane Doe, Journal of Fish Diseases")


def test_domene_naer_tekst_urelatert_gir_false():
    assert not domene_naer_tekst("Jane Doe, MIT, Nature")


def test_domene_naer_tekst_tom_streng_gir_false_ikke_feil():
    assert not domene_naer_tekst("")
    assert not domene_naer_tekst(None)


def test_akser_har_forventede_navn():
    assert set(AKSER.keys()) == {"Faser", "Miljøfaktorer", "Regenerasjon", "Lever", "Ultralyd-validering"}
