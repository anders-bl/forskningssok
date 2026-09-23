"""Nettverksfrie kontraktstester for EPO OPS-token, CQL, XML og TTL-cache."""
from unittest.mock import patch

import httpx
import pytest

from adapters import epo_ops

XML = """<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns="http://www.epo.org/exchange">
  <ops:biblio-search total-result-count="31">
    <ops:search-result><exchange-documents>
      <exchange-document country="EP" doc-number="1234567" kind="A1" family-id="999">
        <bibliographic-data><publication-reference><document-id><date>20240201</date></document-id></publication-reference>
          <invention-title lang="de">Titel auf Deutsch</invention-title>
          <invention-title lang="en">A test patent</invention-title>
        </bibliographic-data>
      </exchange-document>
    </exchange-documents></ops:search-result>
  </ops:biblio-search>
</ops:world-patent-data>"""


@pytest.fixture(autouse=True)
def clear_token_cache():
    epo_ops._token = None
    epo_ops._token_utloper = 0
    epo_ops._siste_sok = 0
    yield
    epo_ops._token = None
    epo_ops._token_utloper = 0
    epo_ops._siste_sok = 0


def test_unconfigured_reports_state_without_network_or_empty_claim(monkeypatch, tmp_path):
    monkeypatch.delenv("EPO_OPS_KEY", raising=False)
    monkeypatch.delenv("EPO_OPS_SECRET", raising=False)
    with patch("adapters.epo_ops.httpx.post") as post, patch("adapters.epo_ops.httpx.get") as get:
        result = epo_ops.sok("microfluidic sensor", db_path=tmp_path / "cache.db")
    assert result["status"] == "unconfigured"
    assert result["total_available"] is None
    assert post.call_count == get.call_count == 0


def test_search_oauth_cql_xml_provenance_and_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("EPO_OPS_KEY", "test-key")
    monkeypatch.setenv("EPO_OPS_SECRET", "test-secret")
    token_response = httpx.Response(
        200, request=httpx.Request("POST", epo_ops.TOKEN_URL),
        json={"access_token": "test-token", "expires_in": 1200},
    )
    search_response = httpx.Response(
        200, request=httpx.Request("GET", f"{epo_ops.BASE}/published-data/search/biblio"),
        text=XML,
    )
    with patch("adapters.epo_ops.httpx.post", return_value=token_response) as post, \
            patch("adapters.epo_ops.httpx.get", return_value=search_response) as get:
        result = epo_ops.sok('microfluidic sensor "quoted"', limit=1, db_path=tmp_path / "cache.db")
        cached = epo_ops.sok('microfluidic sensor "quoted"', limit=1, db_path=tmp_path / "cache.db")

    assert post.call_args.kwargs["auth"] == ("test-key", "test-secret")
    assert result["cql"] == 'ta all "microfluidic sensor quoted"'
    assert result["total_available"] == 31
    assert result["truncated"] is True
    assert result["records"] == [{
        "id": "epo:EP1234567A1", "provider": "epo_ops", "publication_number": "EP1234567A1",
        "country": "EP", "kind": "A1", "family_id": "999", "title": "A test patent",
        "publication_date": "20240201",
        "url": "https://worldwide.espacenet.com/patent/search?q=pn%3DEP1234567A1",
        "relation": "keyword_match",
    }]
    assert cached == result
    assert get.call_count == 1
    assert get.call_args.kwargs["headers"]["X-OPS-Range"] == "1-1"


def test_invalid_query_and_limit_rejected_before_network(tmp_path):
    with pytest.raises(ValueError, match="minst ett ord"):
        epo_ops.sok("---", db_path=tmp_path / "cache.db")
    with pytest.raises(ValueError, match="limit"):
        epo_ops.sok("sensor", limit=21, db_path=tmp_path / "cache.db")


def test_malformed_provider_xml_is_not_a_empty_result(monkeypatch, tmp_path):
    monkeypatch.setenv("EPO_OPS_KEY", "test-key")
    monkeypatch.setenv("EPO_OPS_SECRET", "test-secret")
    token_response = httpx.Response(
        200, request=httpx.Request("POST", epo_ops.TOKEN_URL), json={"access_token": "t"},
    )
    search_response = httpx.Response(
        200, request=httpx.Request("GET", f"{epo_ops.BASE}/published-data/search/biblio"),
        text="<broken>",
    )
    with patch("adapters.epo_ops.httpx.post", return_value=token_response), \
            patch("adapters.epo_ops.httpx.get", return_value=search_response):
        with pytest.raises(RuntimeError, match="ugyldig XML"):
            epo_ops.sok("sensor", db_path=tmp_path / "cache.db")
