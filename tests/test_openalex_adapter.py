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


def test_verk_for_emne_mapper_ekte_felt(tmp_path):
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
