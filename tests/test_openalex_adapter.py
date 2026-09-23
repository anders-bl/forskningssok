"""Verifiserer OpenAlex-adapteren: konsept-tagger, batch-oppløsning av referenced_works,
TTL-cache og at en feil ALDRI ser ut som et ærlig tomt resultat — samme disiplin som
Europe PMC-adapteren. Mock-formen følger felt live-verifisert 2026-09-02 (se README),
ikke gjettet.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from adapters import openalex  # noqa: E402

VERK_RESPONS = {
    "title": "Characterisation of Urocystolithiasis…",
    "topics": [{"id": "https://openalex.org/T10506", "display_name": "Aquaculture disease management and microbiota"},
               {"id": "https://openalex.org/T13350", "display_name": "Myxozoan Parasites in Aquatic Species"}],
    "referenced_works": [f"https://openalex.org/W{i}" for i in range(3)],
    "open_access": {"is_oa": True, "oa_status": "hybrid"},
    "best_oa_location": {
        "license": "cc-by-nc-nd",
        "pdf_url": "https://onlinelibrary.wiley.com/doi/pdfdirect/10.1111/jfd.13815",
        "source": {"host_organization_name": "Wiley"},
    },
}
EMNE_RESPONS = {"results": [{
    "id": "https://openalex.org/W999", "title": "Et emne-utforsket funn",
    "publication_year": 2021, "doi": "https://doi.org/10.1/emne", "cited_by_count": 12,
    "open_access": {"is_oa": True},
    "authorships": [{"author": {"display_name": "A. Forfatter"}}, {"author": {"display_name": "B. Medforfatter"}}],
    "primary_location": {"source": {"display_name": "Et Tidsskrift"}},
    "abstract_inverted_index": {"Dette": [0], "er": [1], "et": [2], "sammendrag": [3]},
}]}
REFS_RESPONS = {"results": [
    {"id": "https://openalex.org/W0", "title": "Transport physiology of the urinary bladder",
     "publication_year": 2002, "doi": "https://doi.org/10.1002/jez.10080"},
    {"id": "https://openalex.org/W1", "title": "Uten DOI registrert", "publication_year": 1999, "doi": None},
]}


def _mock_get(status=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    if status != 200:
        import httpx
        resp.raise_for_status.side_effect = httpx.HTTPStatusError("feil", request=None, response=resp)
    return resp


def test_konsepter_returnerer_emnetagger_med_id(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.openalex.httpx.get", return_value=_mock_get(json_data=VERK_RESPONS)):
        tagger = openalex.konsepter("10.1111/jfd.70099", db_path=db)
    navn = [t["navn"] for t in tagger]
    assert "Aquaculture disease management and microbiota" in navn
    assert tagger[0]["id"] == "T10506"  # kort form, ikke full URL — det filteret trenger


def test_tilgang_mapper_lisens_og_fri_pdf(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.openalex.httpx.get", return_value=_mock_get(json_data=VERK_RESPONS)):
        info = openalex.tilgang("10.1111/jfd.13815", db_path=db)
    assert info["lisens"] == "cc-by-nc-nd"
    assert info["fri_pdf_url"] == "https://onlinelibrary.wiley.com/doi/pdfdirect/10.1111/jfd.13815"
    assert info["utgiver"] == "Wiley"
    assert info["oa_status"] == "hybrid"


def test_tilgang_deler_ttl_cache_med_konsepter_ingen_ekstra_kall(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.openalex.httpx.get", return_value=_mock_get(json_data=VERK_RESPONS)) as m:
        openalex.konsepter("10.1111/jfd.13815", db_path=db)
        openalex.tilgang("10.1111/jfd.13815", db_path=db)
    assert m.call_count == 1  # samme _verk()::doi cache-nøkkel


def test_tilgang_ingen_oa_lokasjon_gir_aerlig_fravaer_ikke_feil(tmp_path):
    db = tmp_path / "cache.db"
    ingen_oa = {"title": "x", "open_access": {"is_oa": False, "oa_status": "closed"}}
    with patch("adapters.openalex.httpx.get", return_value=_mock_get(json_data=ingen_oa)):
        info = openalex.tilgang("10.1111/lukket", db_path=db)
    assert info["lisens"] is None
    assert info["fri_pdf_url"] is None
    assert info["oa_status"] == "closed"


def test_siterende_verk_returnerer_retningskant_og_paginering(tmp_path):
    db = tmp_path / "cache.db"
    seed = {"id": "https://openalex.org/WSEED", "title": "Seed", "doi": "https://doi.org/10.1/seed"}
    citing = {"results": [{
        "id": "https://openalex.org/WLATER", "title": "Later work", "publication_year": 2024,
        "doi": "https://doi.org/10.1/later", "cited_by_count": 3,
        "open_access": {"is_oa": True}, "authorships": [],
        "primary_location": {"source": {"display_name": "Journal"}},
        "abstract_inverted_index": None,
    }], "meta": {"count": 2, "next_cursor": "cursor-2"}}
    with patch("adapters.openalex.httpx.get", side_effect=[
        _mock_get(json_data=seed), _mock_get(json_data=citing),
    ]) as get:
        result = openalex.siterende_verk("10.1/seed", limit=1, db_path=db)
        cached = openalex.siterende_verk("10.1/seed", limit=1, db_path=db)

    assert result["status"] == "ok"
    assert result["complete"] is False
    assert result["total_available"] == 2
    assert result["retrieved"] == 1
    assert result["next_cursor"] == "cursor-2"
    assert result["edges"][0]["retrieved_at"]
    assert result["edges"][0]["source_coverage"] == {
        "provider": "openalex", "retrieved_at": result["edges"][0]["retrieved_at"],
        "retrieved": 1, "total_available": 2, "complete": False, "cursor": "*",
    }
    assert cached["edges"][0]["retrieved_at"] == result["edges"][0]["retrieved_at"]
    assert get.call_count == 2
    assert result["edges"] == [{
        "id": "openalex:cites:WLATER:WSEED",
        "from_id": "10.1/later",
        "to_id": "10.1/seed",
        "relation": "cites",
        "provider": "openalex",
        "match_method": "openalex.cites",
        "retrieved_at": result["edges"][0]["retrieved_at"],
        "source_coverage": result["edges"][0]["source_coverage"],
    }]
    assert get.call_args.kwargs["params"]["filter"] == "cites:WSEED"
    assert get.call_args.kwargs["params"]["cursor"] == "*"


def test_siterende_verk_ukjent_seed_er_skilt_fra_tom_graf(tmp_path):
    with patch("adapters.openalex.httpx.get", return_value=_mock_get(json_data={})):
        result = openalex.siterende_verk("10.1/missing", db_path=tmp_path / "cache.db")
    assert result["status"] == "not_found"
    assert result["complete"] is None
    assert result["total_available"] is None


def test_siterende_verk_avviser_for_stor_side(tmp_path):
    with pytest.raises(ValueError, match="limit"):
        openalex.siterende_verk("10.1/seed", limit=101, db_path=tmp_path / "cache.db")
    db = tmp_path / "cache.db"
    with patch("adapters.openalex.httpx.get", return_value=_mock_get(json_data=EMNE_RESPONS)) as m:
        papirer = openalex.verk_for_emne("T10506", limit=20, db_path=db)
    assert m.call_args.kwargs["params"]["filter"] == "topics.id:T10506"
    assert len(papirer) == 1
    p = papirer[0]
    assert p.tittel == "Et emne-utforsket funn"
    assert p.forfattere == "A. Forfatter; B. Medforfatter"
    assert p.tidsskrift == "Et Tidsskrift"
    assert p.aar == 2021
    assert p.siteringstall == 12
    assert p.open_access is True
    assert p.abstract == "Dette er et sammendrag"  # rekonstruert fra invertert indeks
    assert p.kilde == "openalex"


def test_verk_for_emne_tomt_treffsett_gir_aerlig_tom_liste(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.openalex.httpx.get", return_value=_mock_get(json_data={"results": []})):
        assert openalex.verk_for_emne("T99999", db_path=db) == []


def test_referanser_batch_opploeser_til_doi_og_tittel(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.openalex.httpx.get") as m:
        m.side_effect = [_mock_get(json_data=VERK_RESPONS), _mock_get(json_data=REFS_RESPONS)]
        refs = openalex.referanser("10.1111/jfd.70099", db_path=db)
    assert len(refs) == 2
    assert refs[0]["doi"] == "10.1002/jez.10080"
    assert refs[1]["doi"] is None  # ærlig fravær, ikke oppdiktet
    assert refs[1]["title"] == "Uten DOI registrert"


def test_ttl_cache_unngaar_nytt_kall(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.openalex.httpx.get", return_value=_mock_get(json_data=VERK_RESPONS)) as m:
        openalex.konsepter("10.1111/jfd.70099", db_path=db)
        openalex.konsepter("10.1111/jfd.70099", db_path=db)
    assert m.call_count == 1


def test_kilde_feil_gir_ikke_stille_tomt_resultat(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.openalex.httpx.get", return_value=_mock_get(status=503)):
        with pytest.raises(RuntimeError, match="utilgjengelig"):
            openalex.konsepter("10.1111/jfd.70099", db_path=db)


def test_verk_uten_referenced_works_gir_aerlig_tom_liste(tmp_path):
    db = tmp_path / "cache.db"
    with patch("adapters.openalex.httpx.get", return_value=_mock_get(json_data={"title": "x"})):
        assert openalex.referanser("10.1111/jfd.70099", db_path=db) == []
