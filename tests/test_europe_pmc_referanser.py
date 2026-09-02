"""Verifiserer TTL-cache og feilhåndtering for /references — SAMME disiplin som
test_europe_pmc_adapter.py sin sok()-test. Mock-formen følger EBIs dokumenterte
reference-schema, IKKE live-verifisert ennå (EBIs /references-delressurs var i
vedlikeholdsvindu, 503, da dette ble bygget 2026-09-02 — se docstring i
adapters/europe_pmc.py:referanser). Re-kjør en live smoke-test når vinduet er over.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from adapters.europe_pmc import referanser  # noqa: E402

DOKUMENTERT_SKJEMA = {
    "hitCount": 2,
    "referenceList": {"reference": [
        {"id": "1", "source": "MED", "title": "Et papir med DOI", "pubYear": 2015,
         "doi": "10.1000/eksempel.1"},
        {"id": "2", "source": "MED", "title": "Et papir uten DOI (vanlig case)", "pubYear": 2010},
    ]}
}


def _mock_get(status=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data or DOKUMENTERT_SKJEMA
    if status != 200:
        import httpx
        resp.raise_for_status.side_effect = httpx.HTTPStatusError("feil", request=None, response=resp)
    return resp


def test_parser_returnerer_referanselisten(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.europe_pmc.httpx.get", return_value=_mock_get()) as m:
        ut = referanser("MED", "41363532", db_path=db)
    assert m.call_count == 1
    assert len(ut) == 2
    assert ut[0]["doi"] == "10.1000/eksempel.1"
    assert "doi" not in ut[1]  # dokumentert vanlig case — doi kan mangle


def test_ttl_cache_unngaar_nytt_kall(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.europe_pmc.httpx.get", return_value=_mock_get()) as m:
        referanser("MED", "41363532", db_path=db)
        referanser("MED", "41363532", db_path=db)
    assert m.call_count == 1


def test_vedlikeholdsvindu_gir_ikke_stille_tomt(tmp_path):
    """Den EKTE feilen vi målte live 2026-09-02 (503 «temporarily unavailable due to
    maintenance») skal aldri se ut som «dette papiret siterer ingenting»."""
    db = tmp_path / "cache.db"
    with patch("adapters.europe_pmc.httpx.get", return_value=_mock_get(status=503)):
        with pytest.raises(RuntimeError, match="utilgjengelig"):
            referanser("MED", "41363532", db_path=db)
