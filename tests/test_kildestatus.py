"""Passiv kilde-observasjon: registrer utfallet av EKTE søk i stedet for å polle kildene.

Anders 2026-09-04: «Kildene er usynlig? Det liker jeg ikke.» Han hadde rett, og den første
innvendingen min — at overvåking av kilder betyr fire tredjepartskall per runde — var en
falsk motsetning. Hvert søk et menneske gjør ER allerede en prøve på om kilden lever.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bank import kilde_status, registrer_kildekall  # noqa: E402


def test_feil_paa_rad_teller_opp_og_nullstilles_av_suksess(tmp_path):
    db = tmp_path / "c.db"
    assert registrer_kildekall("europe_pmc", False, "503", db_path=db) == 1
    assert registrer_kildekall("europe_pmc", False, "503", db_path=db) == 2
    assert registrer_kildekall("europe_pmc", False, "503", db_path=db) == 3
    assert registrer_kildekall("europe_pmc", True, db_path=db) == 0
    r = kilde_status(db_path=db)[0]
    assert r["feil_paa_rad"] == 0
    assert r["siste_feilmelding"] is None, "en suksess skal fjerne den gamle feilmeldingen"


def test_paa_rad_skiller_nede_kilde_fra_ingen_soek(tmp_path):
    """«sist_ok er tre dager gammel» kan bety at kilden er nede ELLER at ingen har søkt.
    En teller på rad kan bare vokse når noen faktisk PRØVDE — det er hele grunnen til at
    den finnes ved siden av tidsstemplene."""
    db = tmp_path / "c.db"
    registrer_kildekall("europe_pmc", True, db_path=db)
    gammel = kilde_status(db_path=db)[0]
    assert gammel["feil_paa_rad"] == 0 and gammel["sist_ok"] <= time.time()
    # ingen nye kall: telleren står stille, uansett hvor gammel sist_ok blir
    assert kilde_status(db_path=db)[0]["feil_paa_rad"] == 0


def test_tom_tabell_er_en_tredje_tilstand(tmp_path):
    """Ingen søk kjørt ennå er ikke «alt er bra» og ikke «noe er galt»."""
    assert kilde_status(db_path=tmp_path / "c.db") == []


def test_flere_kilder_holdes_fra_hverandre(tmp_path):
    db = tmp_path / "c.db"
    registrer_kildekall("europe_pmc", False, "503", db_path=db)
    registrer_kildekall("core", True, db_path=db)
    s = {r["kilde"]: r["feil_paa_rad"] for r in kilde_status(db_path=db)}
    assert s == {"europe_pmc": 1, "core": 0}


def test_feilmelding_avkortes_og_lekker_ikke_hele_stacken(tmp_path):
    db = tmp_path / "c.db"
    registrer_kildekall("europe_pmc", False, "x" * 5000, db_path=db)
    assert len(kilde_status(db_path=db)[0]["siste_feilmelding"]) <= 200
