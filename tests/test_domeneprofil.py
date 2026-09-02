"""Verifiserer domeneprofil.py isolert — ranking.py/scoping.py sine egne tester
(test_ranking.py, test_scoping.py) dekker allerede at de re-eksporterer riktig, dette
dekker kun selve substreng-matchen som nå bor her."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from domeneprofil import AKSER, arts_naer_tekst, domene_naer_tekst  # noqa: E402


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


def test_arts_naer_tekst_finner_maalart():
    assert arts_naer_tekst("Nephrocalcinosis in farmed Atlantic salmon")
    assert arts_naer_tekst("En norsk tekst om laks i oppdrett")


def test_arts_naer_tekst_ekte_species_trap_caset_gir_false():
    """Den faktiske tittelen som trigget funnet 2026-09-02 — ingen fisketerm i det hele
    tatt, kun delt nøkkelord (nephrocalcinosis) med fiskedomenet."""
    tittel = "Late onset presentation of nephrocalcinosis and nephrolithiasis in association with a heterozygous CYP24A1 pathogenic variant"
    assert not arts_naer_tekst(tittel)


def test_arts_naer_tekst_salmon_calcitonin_er_ikke_en_fisketreff():
    """Ekte falsk-positiv fanget live 2026-09-02: «salmon calcitonin» er et legemiddel-
    navn i kalsium-/nyrestein-litteraturen (kalsitonin isolert fra laks opprinnelig),
    ikke et signal om at teksten faktisk handler om fisk."""
    tekst = ("CYP24A1 and SLC34A1 mutations in five cases with idiopathic infantile "
             "hypercalcemia. Patients were treated with salmon calcitonin injection.")
    assert not arts_naer_tekst(tekst)


def test_arts_naer_tekst_ekte_salmon_term_fortsatt_matcher_ved_siden_av_calcitonin():
    """Fjerningen av «salmon calcitonin» skal ikke skjule et EKTE fiskefunn som også
    nevner legemidlet et annet sted i teksten."""
    tekst = "Nephrocalcinosis in Atlantic salmon treated experimentally with salmon calcitonin"
    assert arts_naer_tekst(tekst)


def test_arts_naer_tekst_tom_streng_gir_false_ikke_feil():
    assert not arts_naer_tekst("")
    assert not arts_naer_tekst(None)
