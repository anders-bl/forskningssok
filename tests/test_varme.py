"""Verifiserer varme-laget (bank.varm_opp/varmeliste) mot en ekte sqlite-fil, samme
disiplin som test_bank.py: injisert fake-embedder, ingen Ollama/AI-proxy involvert.

Det som testes er kontraktene UI-et faktisk hviler på, ikke at «funksjonen returnerer
noe»: at en sitering veier tyngre enn et åpning, at spredningen når naboene (og bare
dem), at varme på et ikke-cachet papir ikke blir en rad uten tittel i panelet, og at
akkumuleringen faktisk akkumulerer over flere kall.
"""
import math
import sys

import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bank  # noqa: E402
from bank import lagre, varm_opp, varmeliste  # noqa: E402
from schemas import PaperDossier  # noqa: E402

DIM = 1024


def _vec(vinkel_grader: float) -> list[float]:
    r = math.radians(vinkel_grader)
    v = [0.0] * DIM
    v[0], v[1] = math.cos(r), math.sin(r)
    return v


def _fake_embed(texts: list[str]) -> list[list[float]]:
    vinkler = {"A": 0.0, "B": 5.0, "C": 90.0}
    return [_vec(vinkler.get(t[0], 0.0)) for t in texts]


def _p(pid, tittel):
    return PaperDossier(pmid=pid, doi=None, tittel=tittel, forfattere="Ulven, N",
                        tidsskrift="J Fish Dis", aar=2026, abstract="noe abstract-tekst",
                        siteringstall=0, open_access=False,
                        kilde_url=f"https://example.org/{pid}")


def _db_med_tre(tmp_path) -> Path:
    db = tmp_path / "cache.db"
    lagre([_p("1", "Atittel"), _p("2", "Btittel"), _p("3", "Ctittel")],
          embed_fn=_fake_embed, db_path=db)
    return db


def test_sitering_veier_tyngre_enn_apning(tmp_path):
    db = _db_med_tre(tmp_path)
    varm_opp("1", "apnet", db_path=db)
    varm_opp("2", "sitert", spre=False, db_path=db)
    rader = {r["id"]: r["poeng"] for r in varmeliste(db_path=db)}
    assert rader["2"] > rader["1"]


def test_varme_akkumulerer_over_flere_kall(tmp_path):
    db = _db_med_tre(tmp_path)
    forste = varm_opp("1", "apnet", db_path=db)
    andre = varm_opp("1", "apnet", db_path=db)
    assert andre == forste * 2


def test_sitering_sprer_varme_til_naboer_men_svakere(tmp_path):
    """Kjernen i «panelet kan løfte fram noe du aldri har åpnet»: 1 og 2 er nære
    (0° og 5°), 3 er fjern (90°). Siterer du 1, skal 2 bli varm uten at noen rørte den —
    men aldri like varm som kilden selv."""
    db = _db_med_tre(tmp_path)
    varm_opp("1", "sitert", db_path=db)
    rader = {r["id"]: r["poeng"] for r in varmeliste(db_path=db)}
    assert rader["1"] > rader["2"] > 0
    # approx, ikke ==: varmeliste runder poeng til to desimaler for visning, og
    # 6.0*0.3 er ikke representerbart eksakt i float.
    assert rader["2"] == pytest.approx(bank.VARME_VEKT["sitert"] * bank.NABO_SPREDNING, abs=0.01)


def test_apning_sprer_ikke(tmp_path):
    """Bare de sterke handlingene smitter. Ellers ville ren navigasjon i trefflista
    varmet opp halve cachen, og panelet målt klikking i stedet for interesse."""
    db = _db_med_tre(tmp_path)
    varm_opp("1", "apnet", db_path=db)
    assert [r["id"] for r in varmeliste(db_path=db)] == ["1"]


def test_ukjent_hendelse_gir_null_og_skriver_ingenting(tmp_path):
    db = _db_med_tre(tmp_path)
    assert varm_opp("1", "tulle-hendelse", db_path=db) == 0.0
    assert varmeliste(db_path=db) == []


def test_varme_paa_ikke_cachet_papir_vises_ikke(tmp_path):
    """Raden blir liggende i varme-tabellen (den kan bli relevant igjen når papiret
    caches), men den skal ALDRI dukke opp i panelet som en tittelløs rad."""
    db = _db_med_tre(tmp_path)
    varm_opp("finnes-ikke", "sitert", spre=False, db_path=db)
    assert varmeliste(db_path=db) == []


def test_varmeliste_sorterer_varmest_forst_og_respekterer_k(tmp_path):
    db = _db_med_tre(tmp_path)
    varm_opp("3", "apnet", db_path=db)
    varm_opp("2", "dokument", spre=False, db_path=db)
    varm_opp("1", "sitert", spre=False, db_path=db)
    liste = varmeliste(db_path=db)
    assert [r["id"] for r in liste] == ["1", "2", "3"]
    assert [r["id"] for r in varmeliste(k=1, db_path=db)] == ["1"]


def test_varmeliste_baerer_banding_signalene(tmp_path):
    """Panelet tegner ★/⚠ fra de samme feltene som resten av huset — de må komme med
    herfra også, ellers ville varme-fanen vært den ene flaten der art-fellen er usynlig."""
    db = _db_med_tre(tmp_path)
    varm_opp("1", "apnet", db_path=db)
    rad = varmeliste(db_path=db)[0]
    assert "domene_naer" in rad and "arts_naer" in rad
    assert rad["sterkeste_hendelse"] == "apnet"


def test_navnet_er_den_sterkeste_handlingen_ikke_den_siste(tmp_path):
    """Målt live 2026-09-04: kortet sa «du har lest det» om et papir jeg nettopp hadde
    SITERT, fordi en sidelast rakk å skrive «apnet» oppå. Poengene skal akkumulere begge
    veier, men navnet skal bare kunne flytte seg oppover."""
    db = _db_med_tre(tmp_path)
    varm_opp("1", "sitert", spre=False, db_path=db)
    varm_opp("1", "apnet", db_path=db)
    rad = varmeliste(db_path=db)[0]
    assert rad["sterkeste_hendelse"] == "sitert"
    assert rad["poeng"] == pytest.approx(bank.VARME_VEKT["sitert"] + bank.VARME_VEKT["apnet"])


def test_navnet_flytter_seg_oppover(tmp_path):
    db = _db_med_tre(tmp_path)
    varm_opp("1", "apnet", db_path=db)
    varm_opp("1", "dokument", spre=False, db_path=db)
    assert varmeliste(db_path=db)[0]["sterkeste_hendelse"] == "dokument"
