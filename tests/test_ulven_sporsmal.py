"""Kristian Ulvens egne forskerspørsmål (samtalen 21.09 + to oppfølginger) som regresjonsvern
for søkefrasene i retningssamtale. Kjører uten nett: bare frasebyggingen testes.

Bakgrunn 2026-09-28: på disse spørsmålene ga søket 0 relevante av topp 10, fordi den
«engelske» frasen besto av norske restord («detektere eventuelt ultralyd hvilket»). Testen
låser EGENSKAPENE som fikset det, ikke eksakte strenger, så forbedringer ikke knekker den.
Spørsmålene leses fra ops/fagterm_eval.py (én kilde for måling og vern).
"""
import importlib.util
import re
from pathlib import Path

import pytest

import domeneprofil
import retningssamtale as rs

_spec = importlib.util.spec_from_file_location(
    "fagterm_eval", Path(__file__).resolve().parents[1] / "ops" / "fagterm_eval.py")
_ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ev)
SPORSMAL = _ev.SPORSMAL

# Norske restord som faktisk lekket inn i den engelske frasen før rettingen (målt).
LEKKET_FOER = {"dersom", "hvilket", "detektere", "eventuelt", "sammenligner", "gradere", "finnes",
               "foregår", "forklare", "akummuleres", "utvikler", "tidlig", "videre", "nefrokalsinonse",
               "nerfokalsinose", "nefrokalsinose", "ultralyd", "utfelling", "mineraler", "radiologi",
               "hodenyren", "ultralydscreening", "trene", "mellom"}
NEFRO = re.compile(r"ne[rf]{1,2}okalsino", re.IGNORECASE)


def _med_kontekst(i: int) -> tuple[str, str]:
    return SPORSMAL[i], " ".join(SPORSMAL[max(0, i - 3):i])


@pytest.mark.parametrize("i", range(len(SPORSMAL)))
def test_engelsk_frase_har_ingen_norske_restord(i):
    q, k = _med_kontekst(i)
    eng = set(rs.bygg_sokefraser(q, k)["engelsk"].split())
    assert not eng & LEKKET_FOER, f"norsk i engelsk frase: {eng & LEKKET_FOER} <- {q}"
    assert not any(ch in o for o in eng for ch in "æøå")
    assert not eng & set(domeneprofil.NORSKE_DOMENEORD)


@pytest.mark.parametrize("i", range(len(SPORSMAL)))
def test_engelsk_frase_har_hoeyst_tre_ledd(i):
    q, k = _med_kontekst(i)
    # Tallet står her, ikke som rs.MAKS_ENGELSK_TERMER: testen skal vokte konstanten, ikke
    # lese den. Målt 2026-09-28: tre ledd ga 0 i Europe PMC, derfor tilbakefallet; flere
    # ledd enn tre i utgangspunktet ga ikke bedre treff på noen av spørsmålene.
    assert len(rs.bygg_sokeledd(q, k)["engelsk"]) <= 3


@pytest.mark.parametrize("i", [i for i, q in enumerate(SPORSMAL) if NEFRO.search(q)])
def test_nefrokalsinose_ogsaa_med_skrivefeil_gir_nephrocalcinosis_foerst(i):
    q, k = _med_kontekst(i)
    assert rs.bygg_sokeledd(q, k)["engelsk"][0] == "nephrocalcinosis", q


def test_hvorfor_radiologi_faar_emnet_fra_samtalen():
    i = SPORSMAL.index("hvorfor radiologi")
    q, k = _med_kontekst(i)
    assert rs.bygg_sokeledd(q, "")["engelsk"] == ["radiology"]
    assert rs.bygg_sokeledd(q, k)["engelsk"] == ["nephrocalcinosis", "radiology"]


def test_hvert_sporsmaal_faar_en_ikke_tom_engelsk_frase():
    tomme = [q for i, q in enumerate(SPORSMAL) if not rs.bygg_sokefraser(*_med_kontekst(i))["engelsk"]]
    assert tomme == []
