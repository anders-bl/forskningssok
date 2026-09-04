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


def test_slett_dokument_loser_sitatene_i_stedet_for_a_foreldreloese_dem(tmp_path):
    """Reprodusert 2026-09-04: uten løsningen pekte utkast_id på en rad som ikke fantes,
    og sitatet forsvant fra BEGGE arbeidslinsene — «Løse» spør på IS NULL, «I dokumentet»
    på en id ingen kan velge. Slettedialogen lover det motsatte."""
    db, uid = _oppsett(tmp_path)
    lagre_sitat("10.1/1", "overlever dokumentet", "", uid, db_path=db)
    from bank import slett_utkast
    assert slett_utkast(uid, db_path=db) is True
    lose = hent_sitater(kun_lose=True, db_path=db)
    assert [s["tekst"] for s in lose] == ["overlever dokumentet"]
    assert lose[0]["utkast_id"] is None


def test_sletting_rorer_ikke_andre_dokumenters_sitater(tmp_path):
    db, uid = _oppsett(tmp_path)
    from bank import lagre_utkast as nytt, slett_utkast
    annet = nytt("Annet", "", db_path=db)["id"]
    lagre_sitat("10.1/1", "mitt", "", uid, db_path=db)
    lagre_sitat("10.1/2", "det andres", "", annet, db_path=db)
    slett_utkast(uid, db_path=db)
    assert [s["tekst"] for s in hent_sitater(utkast_id=annet, db_path=db)] == ["det andres"]


def test_migrasjon_fra_cache_uten_utkast_id(tmp_path):
    """En cache.db skrevet FØR dokumentskuffen fantes har hverken utkast_id eller
    varme-tabell. ALTER-migrasjonen i _db() må gjøre gamle sitater til løse sitater —
    ikke til usynlige rader, og ikke til en krasj ved første oppslag."""
    import sqlite3
    db = tmp_path / "gammel.db"
    c = sqlite3.connect(db)
    c.execute("""CREATE TABLE papers(id TEXT PRIMARY KEY, tittel TEXT, forfattere TEXT,
                 tidsskrift TEXT, aar INTEGER, doi TEXT, pmid TEXT, abstract TEXT,
                 siteringstall INTEGER, open_access INTEGER, kilde_url TEXT)""")
    c.execute("""CREATE TABLE sitater(id INTEGER PRIMARY KEY, paper_id TEXT NOT NULL,
                 tekst TEXT NOT NULL, kommentar TEXT, opprettet REAL NOT NULL)""")
    c.execute("INSERT INTO papers VALUES ('10.1/x','T','A','J',2020,'10.1/x',NULL,'abs',0,0,'u')")
    c.execute("INSERT INTO sitater VALUES (1,'10.1/x','gammelt sitat','',1.0)")
    c.commit()
    c.close()

    alle = hent_sitater(db_path=db)
    assert [s["tekst"] for s in alle] == ["gammelt sitat"]
    assert alle[0]["utkast_id"] is None
    assert [s["id"] for s in hent_sitater(kun_lose=True, db_path=db)] == [1]

    from bank import varm_opp, varmeliste
    varm_opp("10.1/x", "apnet", db_path=db)
    assert [r["id"] for r in varmeliste(db_path=db)] == ["10.1/x"]


def test_fersk_installasjon_svarer_tomt_ikke_krasj(tmp_path):
    """Tom fil, ingen tabeller. Alle lese-veiene må svare ærlig tomt — nøyaktig når
    verktøyet har minst data og en krasj ville vært mest forvirrende."""
    from bank import varmeliste
    db = tmp_path / "fersk.db"
    assert varmeliste(db_path=db) == []
    assert hent_sitater(db_path=db) == []
    assert hent_sitater(kun_lose=True, db_path=db) == []
    assert hent_sitater(utkast_id=1, db_path=db) == []
