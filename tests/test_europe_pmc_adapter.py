"""Verifiserer parsing, TTL-cache (ingen ekstra HTTP-kall innenfor TTL) og at en
kilde-feil ALDRI ser ut som et ærlig tomt resultat (samme lærdom som bøker/hoster.py:
struping så ut som lisensgate — her ville en feil sett ut som «ingen forskning finnes»).
Alt mocket — ingen live-kall i test-suiten (live-verifisert separat, se README).
"""
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from adapters.europe_pmc import sok  # noqa: E402

EKTE_RESPONS = {
    "resultList": {"result": [{
        "pmid": "41363532", "doi": "10.1111/jfd.70099",
        "title": "Characterisation of Urocystolithiasis  in  Farmed Atlantic Salmon.",
        "authorString": "Dalum AS, Alarcon M.",
        "journalInfo": {"journal": {"title": "Journal of fish diseases"}},
        "pubYear": "2026", "abstractText": "While nephrocalcinosis has received attention…",
        "citedByCount": 0, "isOpenAccess": "N", "source": "MED",
    }]}
}


def _mock_httpx_get(status=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data or EKTE_RESPONS
    if status != 200:
        import httpx
        resp.raise_for_status.side_effect = httpx.HTTPStatusError("feil", request=None, response=resp)
    return resp


def test_parser_mapper_ekte_felt(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.europe_pmc.httpx.get", return_value=_mock_httpx_get()) as m:
        ut = sok("nephrocalcinosis salmon", db_path=db)
    assert m.call_count == 1
    assert len(ut) == 1
    p = ut[0]
    assert p.pmid == "41363532"
    assert p.doi == "10.1111/jfd.70099"
    assert p.tidsskrift == "Journal of fish diseases"
    assert p.aar == 2026
    assert p.siteringstall == 0
    assert p.open_access is False
    assert "urocystolithiasis" in p.tittel.lower()


def test_markup_strippes_fra_tittel_og_abstract(tmp_path):
    """Ekte bug fanget live 2026-09-02: to former av markup så i faktiske Europe PMC-svar
    — rå XML (<title>Abstract</title> som forspalte + <italic>) og HTML-escaped
    (&lt;i&gt;…&lt;/i&gt;, sett i en artstittel) — rendret som rå tagger i leseflaten
    før dette var fikset."""
    db = tmp_path / "cache.db"
    data = {"resultList": {"result": [{
        "pmid": "1", "doi": "10.1/x",
        "title": "Review of Pathogens (&lt;i&gt;Oncorhynchus&lt;/i&gt; spp.)",
        "authorString": "A B", "journalInfo": {"journal": {"title": "X"}}, "pubYear": "2024",
        "abstractText": "<title>Abstract</title> <p>Four <italic>CYP24A1</italic> variants.</p>",
        "citedByCount": 0, "isOpenAccess": "N", "source": "MED",
    }]}}
    with patch("adapters.europe_pmc.httpx.get", return_value=_mock_httpx_get(json_data=data)):
        ut = sok("x", db_path=db)
    assert "<" not in ut[0].tittel and "&lt;" not in ut[0].tittel
    assert ut[0].tittel == "Review of Pathogens ( Oncorhynchus spp.)"  # tagger -> mellomrom, ikke perfekt sammenslått
    assert "<" not in ut[0].abstract
    assert ut[0].abstract == "Abstract Four CYP24A1 variants."


def test_ttl_cache_unngaar_nytt_http_kall(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.europe_pmc.httpx.get", return_value=_mock_httpx_get()) as m:
        sok("nephrocalcinosis salmon", db_path=db)
        sok("nephrocalcinosis salmon", db_path=db)  # innenfor TTL — skal IKKE kalle igjen
    assert m.call_count == 1


def test_tving_fersk_omgaar_cache(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.europe_pmc.httpx.get", return_value=_mock_httpx_get()) as m:
        sok("nephrocalcinosis salmon", db_path=db)
        sok("nephrocalcinosis salmon", db_path=db, tving_fersk=True)
    assert m.call_count == 2


def test_kilde_feil_gir_ikke_stille_tomt_resultat(tmp_path):
    """Kritisk vakt: en 503/timeout skal ALDRI se ut som et ærlig «ingen forskning
    finnes» — det ville vært den eksakte klassen feil hoster.py-lærdommen advarer mot."""
    db = tmp_path / "cache.db"
    with patch("adapters.europe_pmc.httpx.get", side_effect=TimeoutError_stub()):
        with pytest.raises(RuntimeError, match="utilgjengelig"):
            sok("nephrocalcinosis salmon", db_path=db)


def TimeoutError_stub():
    import httpx
    return httpx.TimeoutException("timeout")
