"""Verifiserer ai_assistent.py sin mønstergjenkjenning — spesielt at den faktisk finner
noe i et korpus som overveiende er ENGELSK. De opprinnelige mønstrene var rene bokmåls-ord
("signifikant", "korrelerer" …) og traff kun 7 % av 191 ekte cachede abstracts (målt
2026-09-10) — nesten alt via en tilfeldig delstreng-krasj ("identifi*"), ikke ved design.
Nå brukt fra to steder (ai_assistent.py sin CLI OG api.py sin /api/rapport/konvergens),
så regresjon her rammer begge.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ai_assistent  # noqa: E402


def _p(tittel, abstract):
    return {"id": tittel, "tittel": tittel, "abstract": abstract, "forfattere": "A. Forfatter",
            "aar": 2024, "doi": None}


def test_engelsk_abstract_med_signifikant_resultat():
    p = _p("Et engelsk funn", "The treatment group showed a significant improvement (p<0.05).")
    funn = ai_assistent.detekter_hovedfunn([p])
    assert any(f["type"] == "signifikant" for f in funn)


def test_engelsk_abstract_med_deteksjon():
    p = _p("En engelsk metode", "This method can detect early-stage lesions reliably.")
    funn = ai_assistent.detekter_hovedfunn([p])
    assert any(f["type"] == "deteksjon" for f in funn)


def test_engelsk_abstract_med_korrelasjon():
    p = _p("En engelsk sammenheng", "Elevated CO2 was associated with reduced growth rates.")
    funn = ai_assistent.detekter_hovedfunn([p])
    assert any(f["type"] == "korrelasjon" for f in funn)


def test_norsk_abstract_fungerer_fortsatt():
    """Regresjonsvakt: de opprinnelige bokmåls-mønstrene skal ikke ha forsvunnet i
    utvidelsen til engelsk."""
    p = _p("Et norsk funn", "Studien fant at stress signifikant påvirker veksten hos fisken.")
    funn = ai_assistent.detekter_hovedfunn([p])
    typer = {f["type"] for f in funn}
    assert "signifikant" in typer and "korrelasjon" in typer


def test_ett_papir_kan_treffe_flere_moenstre():
    p = _p("Alt på en gang", "This significant, correlated finding helped detect the cause.")
    funn = ai_assistent.detekter_hovedfunn([p])
    typer = {f["type"] for f in funn}
    assert typer == {"signifikant", "deteksjon", "korrelasjon"}


def test_hvert_funn_baerer_kildepapiret():
    """detekter_hovedfunn skal ALDRI returnere en løsrevet påstand — samme prinsipp
    som resten av huset (rapport.py bygger kilde-lenken fra nettopp dette feltet)."""
    p = _p("Kildesporbarhet", "This is a significant result.")
    funn = ai_assistent.detekter_hovedfunn([p])
    assert funn[0]["papir"] is p


def test_ingen_moenstre_gir_aerlig_tom_liste():
    p = _p("Ingenting å hente", "Salmon were fed a standard commercial diet for twelve weeks.")
    assert ai_assistent.detekter_hovedfunn([p]) == []


def test_tomt_eller_manglende_abstract_krasjer_ikke():
    ut = ai_assistent.detekter_hovedfunn([_p("Uten abstract", ""), {"id": "x", "tittel": "Uten felt"}])
    assert ut == []
