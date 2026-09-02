"""Verifiserer akse-dekning: nøkkelord fra flere akser gir riktig fordelt dekning, tom
tekst gir alle akser 0.0 (ærlig, ikke en feil), og terskelen (2+ ord = full stolpe) virker
som dokumentert.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scoping import AKSER, akse_dekning  # noqa: E402


def test_flere_akser_i_samme_tekst_gir_uavhengig_dekning():
    tekst = "Vi så økt CO2 i karet, og ultralydbildene viste fortettet levervev."
    ut = akse_dekning(tekst)
    assert ut["Miljøfaktorer"] > 0  # "co2"
    assert ut["Lever"] > 0  # "lever" (norsk substring i "levervev")
    assert ut["Ultralyd-validering"] > 0  # "ultralyd"
    assert ut["Regenerasjon"] == 0.0  # ingen av regenerasjons-ordene nevnt


def test_tom_tekst_gir_alle_akser_null_ikke_feil():
    ut = akse_dekning("")
    assert all(v == 0.0 for v in ut.values())
    assert set(ut.keys()) == set(AKSER.keys())


def test_to_ord_gir_full_stolpe_ett_ord_gir_halv():
    tekst_ett = "nephrocalcinosis kan ha ulike stadium"  # kun "stadium" = 1 Faser-ord
    tekst_to = "denne fasen viser et stadium av sykdommen"  # "fase"+"stadium" = 2 Faser-ord
    assert 0 < akse_dekning(tekst_ett)["Faser"] < 1.0
    assert akse_dekning(tekst_to)["Faser"] == 1.0
