"""Sikrer at ufullstendige Semantic Scholar-lister ikke blir kalt siteringsgap."""

from __future__ import annotations

import json
import sqlite3

import scivis_siteringsgap as gap


def _db(sti, *, paginert: bool, mangler_doi: bool):
    with sqlite3.connect(sti) as db:
        db.execute("CREATE TABLE semantic_scholar_cache (key TEXT, respons TEXT)")
        db.execute(
            "CREATE TABLE papers (doi TEXT, tittel TEXT, aar INTEGER, tidsskrift TEXT)"
        )
        papers = (
            ("10.1234/focus", 2020),
            ("10.1234/cited", 2020),
            ("10.1234/near", 2020),
            ("10.1234/far", 2019),
            ("10.1234/newer", 2021),
        )
        db.executemany(
            "INSERT INTO papers (doi, tittel, aar, tidsskrift) VALUES (?, ?, ?, ?)",
            [(doi, doi, aar, "Test") for doi, aar in papers],
        )
        data = [
            {"citedPaper": {"externalIds": {"DOI": "10.1234/cited"}}}
        ]
        if mangler_doi:
            data.append({"citedPaper": {"externalIds": {}}})
        payload = {"offset": 0, "data": data}
        if paginert:
            payload["next"] = 100
        db.execute(
            "INSERT INTO semantic_scholar_cache (key, respons) VALUES (?, ?)",
            ("graf-ref::DOI:10.1234/focus", json.dumps(payload)),
        )


def _naboer(_fokus, _k, _db):
    return [
        {"id": "10.1234/cited", "tittel": "Cited", "aar": 2020, "avstand": 0.1},
        {"id": "10.1234/near", "tittel": "Near", "aar": 2020, "avstand": 0.2},
        {"id": "10.1234/far", "tittel": "Far", "aar": 2019, "avstand": 0.3},
        {"id": "10.1234/newer", "tittel": "Newer", "aar": 2021, "avstand": 0.4},
    ]


def test_paginerte_sider_og_referanser_uten_doi_blir_uavklarte(tmp_path, monkeypatch):
    db = tmp_path / "cache.db"
    _db(db, paginert=True, mangler_doi=True)
    monkeypatch.setattr(gap, "_naboer", _naboer)

    refs = gap.referanse_sett(db)
    nett = gap.bygg_egonett("10.1234/focus", refs, db)
    side = gap.bygg_html(nett, "Test")

    assert refs["10.1234/focus"].komplett is False
    assert nett["n_sitert"] == 1
    assert nett["n_gap"] == 0
    assert nett["n_ukjent"] == 2
    assert nett["n_nyere"] == 1
    assert all(n["status"] != "gap" for n in nett["naboer"] if n["doi"] != "10.1234/cited")
    assert "flere sider fra offset 100 er ikke cachet" in side
    assert "1 cachede oppforinger mangler DOI" in side
    assert "Ukjent -- referansedekning eller tidsrekkefolge er ufullstendig" in side
    same_year = next(n for n in nett["naboer"] if n["doi"] == "10.1234/near")
    assert "samme publikasjonsaar" in same_year["ukjent_grunn"]
    assert "Publisert etter fokuspapiret" in side


def test_fravaer_fra_full_doi_dekket_liste_blir_gap_kandidat(tmp_path, monkeypatch):
    db = tmp_path / "cache.db"
    _db(db, paginert=False, mangler_doi=False)
    monkeypatch.setattr(gap, "_naboer", _naboer)

    refs = gap.referanse_sett(db)
    nett = gap.bygg_egonett("10.1234/focus", refs, db)

    assert refs["10.1234/focus"].komplett is True
    assert nett["n_sitert"] == 1
    assert nett["n_gap"] == 1
    assert nett["n_ukjent"] == 1
    assert nett["n_nyere"] == 1
    assert "gap-kandidat" in gap._gap_liste(nett)
