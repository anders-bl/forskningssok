"""Verifiserer dedup.py — normalisering og fler-kilde-dedup, delt av citation_gap.py
(referanse-matching) og cli.py (Europe PMC + CORE-sammenslåing)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dedup import dedupliser, norm_tittel  # noqa: E402
from schemas import PaperDossier  # noqa: E402


def _p(tittel, doi=None):
    return PaperDossier(pmid=None, doi=doi, tittel=tittel, forfattere="", tidsskrift="X",
                        aar=2026, abstract="", siteringstall=0, open_access=False, kilde_url="u")


def test_norm_tittel_ignorerer_tegnsetting_og_store_bokstaver():
    assert norm_tittel("Tittel — Undertittel!") == norm_tittel("tittel undertittel")


def test_dedupliser_fjerner_match_paa_doi():
    a = _p("Tittel A", doi="10.1/x")
    b = _p("Helt annen tittel", doi="10.1/x")  # samme DOI, ulik tittel-streng
    assert dedupliser([a, b]) == [a]


def test_dedupliser_fjerner_match_paa_tittel_naar_doi_mangler():
    a = _p("Nephrocalcinosis in juvenile farmed Atlantic salmon", doi="10.1/x")
    b = _p("Nephrocalcinosis in juvenile farmed Atlantic salmon")  # ingen DOI, samme tittel
    assert dedupliser([a, b]) == [a]


def test_dedupliser_beholder_ulike_papirer():
    a = _p("Papir A", doi="10.1/a")
    b = _p("Papir B", doi="10.1/b")
    assert dedupliser([a, b]) == [a, b]


def test_dedupliser_tom_liste():
    assert dedupliser([]) == []
