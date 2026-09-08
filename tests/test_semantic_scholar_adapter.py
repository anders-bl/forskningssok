"""Verifiserer Semantic Scholar-adapteren: felt-mapping, TTL-cache, ærlig feil ved
nedetid — samme disiplin som test_unpaywall_adapter.py. Skjemaet er IKKE live-
verifisert i denne økten (se adapters/semantic_scholar.py sin docstring for hvorfor)
— disse testene låser koden mot DOKUMENTASJONENS skjema, ikke et bekreftet ekte svar.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from adapters import semantic_scholar  # noqa: E402

SOK_RESPONS = {
    "data": [
        {
            "paperId": "abc123",
            "title": "Nephrocalcinosis in farmed Atlantic salmon",
            "abstract": "A study of kidney disease in salmon.",
            "year": 2023,
            "externalIds": {"DOI": "10.1111/jfd.99999"},
            "citationCount": 7,
            "isOpenAccess": True,
            "openAccessPdf": {"url": "https://example.org/paper.pdf"},
            "venue": "Journal of Fish Diseases",
            "publicationTypes": ["JournalArticle"],
        }
    ]
}
GRAF_RESPONS = {
    "citations": [
        {"title": "A follow-up study", "year": 2024, "contexts": ["We build on [1]"],
         "intents": ["methodology"], "isInfluential": True},
        {"title": "A passing mention", "year": 2024, "contexts": [], "intents": ["background"],
         "isInfluential": False},
    ],
    "references": [
        {"title": "Earlier foundational work", "year": 2019, "contexts": [], "intents": ["background"],
         "isInfluential": False},
    ],
}


def _mock_get(status=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    if status != 200:
        import httpx
        resp.raise_for_status.side_effect = httpx.HTTPStatusError("feil", request=None, response=resp)
    return resp


def test_sok_mapper_felter_til_husets_navn(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.semantic_scholar.httpx.get", return_value=_mock_get(json_data=SOK_RESPONS)):
        treff = semantic_scholar.sok("nephrocalcinosis salmon", db_path=db)
    assert len(treff) == 1
    p = treff[0]
    assert p["doi"] == "10.1111/jfd.99999"
    assert p["tittel"] == "Nephrocalcinosis in farmed Atlantic salmon"
    assert p["siteringstall"] == 7
    assert p["open_access"] is True
    assert p["fri_pdf_url"] == "https://example.org/paper.pdf"


def test_sok_uten_treff_gir_tom_liste_ikke_feil(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.semantic_scholar.httpx.get", return_value=_mock_get(json_data={"data": []})):
        treff = semantic_scholar.sok("noe uten treff", db_path=db)
    assert treff == []


def test_siteringsgraf_skiller_innflytelsesrik_fra_forbifarten(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.semantic_scholar.httpx.get", return_value=_mock_get(json_data=GRAF_RESPONS)):
        graf = semantic_scholar.siteringsgraf("10.1111/jfd.99999", db_path=db)
    assert len(graf["siteringer"]) == 2
    assert graf["siteringer"][0]["innflytelsesrik"] is True
    assert graf["siteringer"][0]["intents"] == ("methodology",)
    assert graf["siteringer"][1]["innflytelsesrik"] is False
    assert len(graf["referanser"]) == 1
    assert graf["referanser"][0]["tittel"] == "Earlier foundational work"


def test_ttl_cache_unngaar_nytt_kall(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.semantic_scholar.httpx.get", return_value=_mock_get(json_data=SOK_RESPONS)) as m:
        semantic_scholar.sok("nephrocalcinosis salmon", db_path=db)
        semantic_scholar.sok("nephrocalcinosis salmon", db_path=db)
    assert m.call_count == 1


def test_kilde_feil_gir_ikke_stille_tomt_resultat(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.semantic_scholar.httpx.get", return_value=_mock_get(status=429)):
        with pytest.raises(RuntimeError, match="utilgjengelig"):
            semantic_scholar.sok("noe", db_path=db)


def test_nokkel_sendes_som_header_naar_satt(tmp_path, monkeypatch):
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "hemmelig-test-nokkel")
    db = tmp_path / "cache.db"
    with patch("adapters.semantic_scholar.httpx.get", return_value=_mock_get(json_data=SOK_RESPONS)) as m:
        semantic_scholar.sok("noe", db_path=db)
    assert m.call_args.kwargs["headers"]["x-api-key"] == "hemmelig-test-nokkel"


def test_ingen_nokkel_gir_ingen_api_key_header(tmp_path, monkeypatch):
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    db = tmp_path / "cache.db"
    with patch("adapters.semantic_scholar.httpx.get", return_value=_mock_get(json_data=SOK_RESPONS)) as m:
        semantic_scholar.sok("noe", db_path=db)
    assert "x-api-key" not in m.call_args.kwargs["headers"]
