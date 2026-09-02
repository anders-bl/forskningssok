"""Verifiserer CORE-adapteren: parsing av ekte felt (NTNU Open-treffet, live-verifisert
2026-09-02), TTL-cache, og at en kilde-feil ALDRI ser ut som et ærlig tomt resultat.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from adapters import core  # noqa: E402

EKTE_RESPONS = {
    "totalHits": 101450,
    "results": [{
        "id": 169309659,
        "title": "Nephrocalcinosis in juvenile farmed Atlantic salmon",
        "authors": [{"name": "Klykken, Christine"}],
        "yearPublished": 2023,
        "citationCount": 0,
        "doi": None,
        "abstract": "English summary  Good health and welfare of farmed fish...",
        "dataProviders": [{"name": "NTNU Open (Norwegian University of Science and Technology)"}],
        "publisher": "NTNU",
        "links": [{"type": "display", "url": "https://core.ac.uk/works/169309659"}],
    }]
}


def _mock_get(status=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data or EKTE_RESPONS
    if status != 200:
        import httpx
        resp.raise_for_status.side_effect = httpx.HTTPStatusError("feil", request=None, response=resp)
    return resp


def test_parser_mapper_ekte_felt(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.core.httpx.get", return_value=_mock_get()) as m:
        ut = core.sok("nephrocalcinosis salmon", db_path=db)
    assert m.call_count == 1
    assert len(ut) == 1
    p = ut[0]
    assert p.tittel == "Nephrocalcinosis in juvenile farmed Atlantic salmon"
    assert p.forfattere == "Klykken, Christine"
    assert p.aar == 2023
    assert p.kilde == "core"
    assert "NTNU Open" in p.tidsskrift
    assert p.kilde_url == "https://core.ac.uk/works/169309659"
    assert p.doi is None  # ærlig fravær — theses har sjelden DOI
    assert p.open_access is True  # strukturell antakelse, se moduldocstring


def test_ttl_cache_unngaar_nytt_kall(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.core.httpx.get", return_value=_mock_get()) as m:
        core.sok("nephrocalcinosis salmon", db_path=db)
        core.sok("nephrocalcinosis salmon", db_path=db)
    assert m.call_count == 1


def test_kilde_feil_gir_ikke_stille_tomt_resultat(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.core.httpx.get", return_value=_mock_get(status=503)):
        with pytest.raises(RuntimeError, match="utilgjengelig"):
            core.sok("nephrocalcinosis salmon", db_path=db)


def test_tomt_treffsett_gir_aerlig_tom_liste(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.core.httpx.get", return_value=_mock_get(json_data={"results": []})):
        assert core.sok("et sikkert ubesvarlig søk xyzzy123", db_path=db) == []
