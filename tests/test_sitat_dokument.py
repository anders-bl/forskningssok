"""Verifiserer hybriden sitat↔dokument (Anders' valg 2026-09-04): ETT lager, valgfritt
medlemskap. Et sitat hører alltid til papiret; det hører I TILLEGG til ett dokument hvis
ett var åpent da du siterte. De tre linsene (papir / dokument / løse) er tre spørringer
mot samme rad — ingen av dem kopierer noe, og «løsne» må aldri kunne bli «slett».
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bank import (  # noqa: E402
    hent_sitater, knytt_sitat, lagre, lagre_sitat, lagre_utkast, slett_sitat,
)
from schemas import PaperDossier  # noqa: E402

DIM = 1024


def _fake_embed(texts: list[str]) -> list[list[float]]:
    v = [0.0] * DIM
    v[0] = 1.0
    return [list(v) for _ in texts]


def _p(pid, tittel):
    return PaperDossier(pmid=pid, doi=f"10.1/{pid}", tittel=tittel, forfattere="Ulven, N, Kolstad, A",
                        tidsskrift="J Fish Dis", aar=2026, abstract="noe abstract-tekst",
                        siteringstall=0, open_access=False,
                        kilde_url=f"https://example.org/{pid}")


def _oppsett(tmp_path):
    db = tmp_path / "cache.db"
    lagre([_p("1", "Atittel"), _p("2", "Btittel")], embed_fn=_fake_embed, db_path=db)
    utkast = lagre_utkast("Notat", "brødtekst", db_path=db)
    return db, utkast["id"]


def test_sitat_uten_dokument_blir_lost_ikke_avvist(tmp_path):
    db, _ = _oppsett(tmp_path)
    s = lagre_sitat("10.1/1", "et utdrag", db_path=db)
    assert s["utkast_id"] is None
    assert [x["id"] for x in hent_sitater(kun_lose=True, db_path=db)] == [s["id"]]


def test_sitat_med_apent_dokument_lander_i_dokumentet(tmp_path):
    db, uid = _oppsett(tmp_path)
    s = lagre_sitat("10.1/1", "et utdrag", "", uid, db_path=db)
    assert s["utkast_id"] == uid
    assert [x["id"] for x in hent_sitater(utkast_id=uid, db_path=db)] == [s["id"]]
    assert hent_sitater(kun_lose=True, db_path=db) == []


def test_de_tre_linsene_ser_samme_rad(tmp_path):
    db, uid = _oppsett(tmp_path)
    s = lagre_sitat("10.1/1", "et utdrag", "", uid, db_path=db)
    via_papir = hent_sitater("10.1/1", db_path=db)
    via_dok = hent_sitater(utkast_id=uid, db_path=db)
    via_alle = hent_sitater(db_path=db)
    assert {r[0]["id"] for r in (via_papir, via_dok, via_alle)} == {s["id"]}
    assert len(via_alle) == 1  # ingen linse duplisererer raden


def test_feste_og_losne_er_reversibelt_og_sletter_aldri(tmp_path):
    db, uid = _oppsett(tmp_path)
    s = lagre_sitat("10.1/1", "et utdrag", db_path=db)
    assert knytt_sitat(s["id"], uid, db_path=db) is True
    assert len(hent_sitater(utkast_id=uid, db_path=db)) == 1
    assert knytt_sitat(s["id"], None, db_path=db) is True
    assert hent_sitater(utkast_id=uid, db_path=db) == []
    assert len(hent_sitater(kun_lose=True, db_path=db)) == 1  # fortsatt der, bare løs


def test_knytt_ukjent_sitat_er_usant_ikke_en_krasj(tmp_path):
    db, uid = _oppsett(tmp_path)
    assert knytt_sitat(9999, uid, db_path=db) is False


def test_slett_er_den_eneste_veien_til_tap(tmp_path):
    db, uid = _oppsett(tmp_path)
    s = lagre_sitat("10.1/1", "et utdrag", "", uid, db_path=db)
    slett_sitat(s["id"], db_path=db)
    assert hent_sitater(db_path=db) == []


def test_papir_linsen_baerer_kildefeltene_rapporten_trenger(tmp_path):
    """rapport._kildelinje bygger henvisningen av nettopp disse feltene — mangler de,
    blir en delt PDF stående med «Ukjent kilde» under et ekte sitat."""
    db, uid = _oppsett(tmp_path)
    lagre_sitat("10.1/1", "et utdrag", "", uid, db_path=db)
    s = hent_sitater(utkast_id=uid, db_path=db)[0]
    assert s["paper_forfattere"].startswith("Ulven")
    assert s["paper_tidsskrift"] == "J Fish Dis"
    assert s["paper_aar"] == 2026
    assert s["paper_doi"] == "10.1/1"


def test_to_dokumenter_deler_ikke_sitater(tmp_path):
    db, uid = _oppsett(tmp_path)
    annet = lagre_utkast("Annet", "", db_path=db)["id"]
    lagre_sitat("10.1/1", "til det første", "", uid, db_path=db)
    lagre_sitat("10.1/2", "til det andre", "", annet, db_path=db)
    assert [s["tekst"] for s in hent_sitater(utkast_id=uid, db_path=db)] == ["til det første"]
    assert [s["tekst"] for s in hent_sitater(utkast_id=annet, db_path=db)] == ["til det andre"]
