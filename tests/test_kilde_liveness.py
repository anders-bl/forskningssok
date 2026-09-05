"""Verifiserer kilde_liveness.py: den bærende felle-38-diskrimineringen — at et TOMT svar
på et kjent-referert kontroll-papir meldes MISTENKT_NEDE, ikke som et gyldig «0 referanser».

Nettverksfri (CLAUDE.md): adapter-kallene injiseres.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import kilde_liveness as kl  # noqa: E402


def test_kilde_med_referanser_er_oppe():
    s = kl.sjekk_kilde("x", lambda: [{"doi": "a"}, {"doi": "b"}])
    assert s.status == kl.OPPE and s.antall == 2


def test_kilde_som_kaster_er_nede():
    def kaster():
        raise RuntimeError("503 maintenance")
    s = kl.sjekk_kilde("europe_pmc", kaster)
    assert s.status == kl.NEDE and "503" in s.feil


def test_TOMT_svar_paa_kontrollen_er_mistenkt_nede_ikke_null():
    """Kjernen. Kontroll-papiret HAR referanser, så et tomt svar kan ikke bety «ingen
    referanser» — det betyr at kilden ikke leverer. En detektor uten denne kontrollen
    ville lest tomt som et gyldig 0 og meldt grønt på en stille-nede kilde (felle 38)."""
    s = kl.sjekk_kilde("openalex", lambda: [])
    assert s.status == kl.MISTENKT_NEDE
    assert s.status != kl.OPPE, "et tomt svar er ALDRI oppe for et kjent-referert papir"


def test_None_svar_behandles_som_tomt():
    s = kl.sjekk_kilde("x", lambda: None)
    assert s.status == kl.MISTENKT_NEDE


def test_alle_kilder_sjekker_tre_med_pmid_og_doi():
    svar = kl.alle_kilder(
        doi="10.1/x", pmid="123", kilde_kode="MED",
        epmc_fn=lambda: [{"doi": "a"}],
        openalex_fn=lambda: [{"doi": "b"}, {"doi": "c"}],
        crossref_fn=lambda: [{"doi": "d"}])
    navn = {s.navn: s.status for s in svar}
    assert navn == {"europe_pmc": kl.OPPE, "openalex": kl.OPPE, "crossref": kl.OPPE}


def test_uten_pmid_er_europepmc_ikke_sjekkbar_ikke_nede():
    """«Vi kunne ikke prøve» er ikke «kilden er nede». Å melde NEDE her ville vært en falsk
    alarm på vår egen manglende input, ikke på kilden."""
    svar = kl.alle_kilder(doi="10.1/x", pmid=None, kilde_kode="MED",
                          openalex_fn=lambda: [{"doi": "b"}], crossref_fn=lambda: [{"doi": "d"}])
    epmc = next(s for s in svar if s.navn == "europe_pmc")
    assert epmc.status == "IKKE_SJEKKBAR" and "PMID" in epmc.feil


def test_oppsummer_skiller_nede_fra_mistenkt():
    """De to holdes fra hverandre fordi de betyr ulike ting: NEDE svarte ikke,
    MISTENKT_NEDE svarte tomt (verre — ser ut som et gyldig 0)."""
    svar = kl.alle_kilder(
        doi="10.1/x", pmid="123", kilde_kode="MED",
        epmc_fn=lambda: (_ for _ in ()).throw(RuntimeError("503")),  # kaster
        openalex_fn=lambda: [],       # tomt
        crossref_fn=lambda: [{"doi": "d"}])
    o = kl.oppsummer(svar)
    assert o["nede"] == ["europe_pmc"]
    assert o["mistenkt_nede"] == ["openalex"]
    assert o["alle_oppe"] is False


def test_oppsummer_alle_oppe_ignorerer_ikke_sjekkbar():
    """En IKKE_SJEKKBAR kilde skal ikke gjøre alle_oppe False — vi vet ikke, og «vet ikke»
    er ikke «nede»."""
    svar = kl.alle_kilder(doi="10.1/x", pmid=None, kilde_kode="MED",
                          openalex_fn=lambda: [{"doi": "b"}], crossref_fn=lambda: [{"doi": "d"}])
    assert kl.oppsummer(svar)["alle_oppe"] is True
