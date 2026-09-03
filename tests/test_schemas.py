"""Verifiserer PaperDossier.id sin fallback-prioritet — flagget udekket av Six-Hats-sveipen
2026-09-04. Eneste ikke-trivielle logikk i schemas.py, og nettopp den typen ting en
refaktor stille kan bytte rekkefølge på uten at noe feiler synlig.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schemas import PaperDossier  # noqa: E402


def _p(pmid=None, doi=None, kilde_url="https://example.org/x"):
    return PaperDossier(pmid=pmid, doi=doi, tittel="t", forfattere="", tidsskrift="",
                        aar=2026, abstract="a", siteringstall=0, open_access=False,
                        kilde_url=kilde_url)


def test_doi_foretrekkes_selv_om_pmid_ogsaa_finnes():
    assert _p(pmid="12345", doi="10.1/x").id == "10.1/x"


def test_pmid_faller_tilbake_naar_doi_mangler():
    assert _p(pmid="12345", doi=None).id == "12345"


def test_kilde_url_er_siste_utvei_naar_verken_doi_eller_pmid_finnes():
    assert _p(pmid=None, doi=None, kilde_url="https://example.org/CORE:abc").id == "https://example.org/CORE:abc"


def test_kilde_og_kilde_kode_defaults():
    p = _p()
    assert p.kilde == "europe_pmc"
    assert p.kilde_kode == "MED"
