"""Verifiserer Unpaywall-adapteren: felt-mapping (schema live-verifisert 2026-09-07 mot
10.1111/jfd.13815), url_for_pdf->url-fallback, ærlig fravær ved lukket papir, TTL-cache,
og at en feil ALDRI ser ut som et ærlig tomt resultat — samme disiplin som openalex.py.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from adapters import unpaywall  # noqa: E402

# Formen er live-verifisert, ikke gjettet (curl 2026-09-07).
OA_RESPONS = {
    "doi": "10.1111/jfd.13815", "is_oa": True, "oa_status": "hybrid",
    "publisher": "Wiley", "journal_name": "Journal of Fish Diseases",
    "journal_is_in_doaj": False, "has_repository_copy": False,
    "best_oa_location": {
        "url_for_pdf": "https://onlinelibrary.wiley.com/doi/pdfdirect/10.1111/jfd.13815",
        "url": "https://onlinelibrary.wiley.com/doi/pdfdirect/10.1111/jfd.13815",
        "license": "cc-by-nc-nd", "host_type": "publisher", "version": "publishedVersion",
    },
}
# Grønn OA: kun landingsside-url, ingen direkte PDF, i et repositorium (den brede
# dekningen som er Unpaywalls poeng utover OpenAlex).
GROENN_RESPONS = {
    "doi": "10.1/gronn", "is_oa": True, "oa_status": "green",
    "publisher": "Elsevier", "journal_is_in_doaj": True, "has_repository_copy": True,
    "best_oa_location": {
        "url_for_pdf": None, "url": "https://ntnuopen.ntnu.no/handle/11250/12345",
        "license": "cc-by", "host_type": "repository", "version": "acceptedVersion",
    },
}
LUKKET_RESPONS = {
    "doi": "10.1/lukket", "is_oa": False, "oa_status": "closed",
    "publisher": "Springer", "journal_is_in_doaj": False, "has_repository_copy": False,
    "best_oa_location": None,
}


def _mock_get(status=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    if status != 200:
        import httpx
        resp.raise_for_status.side_effect = httpx.HTTPStatusError("feil", request=None, response=resp)
    return resp


def test_tilgang_mapper_fire_kjernefelt_som_openalex(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.unpaywall.httpx.get", return_value=_mock_get(json_data=OA_RESPONS)):
        info = unpaywall.tilgang("10.1111/jfd.13815", db_path=db)
    assert info["lisens"] == "cc-by-nc-nd"
    assert info["fri_pdf_url"] == "https://onlinelibrary.wiley.com/doi/pdfdirect/10.1111/jfd.13815"
    assert info["utgiver"] == "Wiley"
    assert info["oa_status"] == "hybrid"


def test_tilgang_bonus_signaler_openalex_ikke_har(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.unpaywall.httpx.get", return_value=_mock_get(json_data=GROENN_RESPONS)):
        info = unpaywall.tilgang("10.1/gronn", db_path=db)
    assert info["i_doaj"] is True
    assert info["repositorie_kopi"] is True
    assert info["vert_type"] == "repository"


def test_fri_pdf_faller_tilbake_paa_url_naar_pdf_mangler(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.unpaywall.httpx.get", return_value=_mock_get(json_data=GROENN_RESPONS)):
        info = unpaywall.tilgang("10.1/gronn", db_path=db)
    assert info["fri_pdf_url"] == "https://ntnuopen.ntnu.no/handle/11250/12345"  # url, ikke None
    assert info["lisens"] == "cc-by"


def test_lukket_papir_gir_aerlig_fravaer_ikke_feil(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.unpaywall.httpx.get", return_value=_mock_get(json_data=LUKKET_RESPONS)):
        info = unpaywall.tilgang("10.1/lukket", db_path=db)
    assert info["lisens"] is None
    assert info["fri_pdf_url"] is None
    assert info["oa_status"] == "closed"       # statusen finnes selv uten fri kopi
    assert info["utgiver"] == "Springer"


def test_ttl_cache_unngaar_nytt_kall(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.unpaywall.httpx.get", return_value=_mock_get(json_data=OA_RESPONS)) as m:
        unpaywall.tilgang("10.1111/jfd.13815", db_path=db)
        unpaywall.tilgang("10.1111/jfd.13815", db_path=db)
    assert m.call_count == 1


def test_kilde_feil_gir_ikke_stille_tomt_resultat(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.unpaywall.httpx.get", return_value=_mock_get(status=503)):
        with pytest.raises(RuntimeError, match="utilgjengelig"):
            unpaywall.tilgang("10.1111/jfd.13815", db_path=db)
