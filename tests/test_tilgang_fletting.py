"""Verifiserer _flett_tilgang i api.py: OpenAlex + Unpaywall flettes slik at en funnet
fri PDF foretrekkes, hvem som svarte rapporteres (kilde_tilgang), og uenighet flagges
(nøyaktig én kilde fant åpen tilgang — Unpaywalls egentlige verdi). Én kilde nede skal
degradere synlig via den andre, aldri ta ned svaret."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import _flett_tilgang  # noqa: E402

OA = {"lisens": "cc-by-nc-nd", "fri_pdf_url": "https://wiley/pdf", "utgiver": "Wiley", "oa_status": "hybrid"}
UP = {"lisens": "cc-by", "fri_pdf_url": "https://ntnuopen/handle", "utgiver": "Wiley", "oa_status": "green"}
INGEN = {"lisens": None, "fri_pdf_url": None, "utgiver": "Springer", "oa_status": "closed"}


def test_begge_fant_pdf_foretrekker_openalex_ingen_uenighet():
    r = _flett_tilgang(OA, UP)
    assert r["fri_pdf_url"] == "https://wiley/pdf"   # OpenAlex først når begge har
    assert r["kilde_tilgang"] == "begge"
    assert r["uenighet"] is False


def test_kun_unpaywall_fant_pdf_flagges_som_uenighet():
    r = _flett_tilgang(INGEN, UP)
    assert r["fri_pdf_url"] == "https://ntnuopen/handle"  # Unpaywall fant en OpenAlex ikke hadde
    assert r["kilde_tilgang"] == "unpaywall"
    assert r["uenighet"] is True                          # nettopp verdien wikien flagget


def test_kun_openalex_fant_pdf_flagges_som_uenighet():
    r = _flett_tilgang(OA, INGEN)
    assert r["kilde_tilgang"] == "openalex"
    assert r["uenighet"] is True


def test_ingen_fant_pdf_beholder_status_ingen_uenighet():
    r = _flett_tilgang(INGEN, INGEN)
    assert r["fri_pdf_url"] is None
    assert r["oa_status"] == "closed"     # statusen finnes selv uten fri kopi
    assert r["kilde_tilgang"] == "ingen"
    assert r["uenighet"] is False


def test_unpaywall_nede_gir_fortsatt_openalex_svar():
    r = _flett_tilgang(OA, None)          # up=None simulerer Unpaywall nede
    assert r["fri_pdf_url"] == "https://wiley/pdf"
    assert r["kilde_tilgang"] == "openalex"


def test_openalex_nede_gir_fortsatt_unpaywall_svar():
    r = _flett_tilgang(None, UP)          # oa=None simulerer OpenAlex nede
    assert r["fri_pdf_url"] == "https://ntnuopen/handle"
    assert r["kilde_tilgang"] == "unpaywall"
