"""Sitatbanken og «relasjonelle sitater» — det Zotero/EndNote/Mendeley ikke gjør.

De er arkivskap: de aner ikke at to sitater handler om det samme. Vi har embeddingene,
så nabolaget er gratis. Testene her vokter de tre kontraktene flaten hviler på: banken
virker uten embedder, relasjonen holder seg innenfor det du FAKTISK har sitert, og
boilerplaten bærer en fullstendig referanse for hver kilde.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bank  # noqa: E402
import rapport  # noqa: E402
from schemas import PaperDossier  # noqa: E402

DIM = 1024


def _vec(grader: float) -> list[float]:
    r = math.radians(grader)
    v = [0.0] * DIM
    v[0], v[1] = math.cos(r), math.sin(r)
    return v


def _embed(texts):
    vinkler = {"A": 0.0, "B": 4.0, "C": 8.0, "D": 90.0}
    return [_vec(vinkler.get(t[0], 0.0)) for t in texts]


def _p(pid, tittel):
    return PaperDossier(pmid=pid, doi=f"10.1/{pid}", tittel=tittel,
                        forfattere="Klykken C, Dalum AS", tidsskrift="J Fish Dis", aar=2026,
                        abstract=f"{tittel} abstract", siteringstall=0, open_access=False,
                        kilde_url="u", volum="49", sider="e1")


def _oppsett(tmp_path):
    db = tmp_path / "cache.db"
    bank.lagre([_p("1", "Atittel"), _p("2", "Btittel"), _p("3", "Ctittel"), _p("4", "Dtittel")],
               embed_fn=_embed, db_path=db)
    return db


def test_banken_grupperer_paa_papir_og_teller(tmp_path):
    db = _oppsett(tmp_path)
    bank.lagre_sitat("10.1/1", "utdrag en", db_path=db)
    bank.lagre_sitat("10.1/1", "utdrag to", db_path=db)
    bank.lagre_sitat("10.1/2", "utdrag tre", db_path=db)
    banken = bank.sitatbank(db_path=db)
    antall = {r["paper_id"]: r["antall"] for r in banken}
    assert antall == {"10.1/1": 2, "10.1/2": 1}
    assert all(r["forfattere"] for r in banken), "banken må bære forfatter for referansen"


def test_relaterte_holder_seg_til_det_du_faktisk_har_sitert(tmp_path):
    """Et nabolag av USITERTE papirer er et søkeresultat, ikke en sitatbank."""
    db = _oppsett(tmp_path)
    bank.lagre_sitat("10.1/1", "utdrag", db_path=db)
    bank.lagre_sitat("10.1/2", "utdrag", db_path=db)   # nær 1 (4°)
    # 10.1/3 er enda nærmere i vinkel enn mange, men er ALDRI sitert
    rel = bank.relaterte_sitater("10.1/1", db_path=db)
    assert [r["id"] for r in rel] == ["10.1/2"]


def test_relaterte_er_tom_uten_vektor_ikke_en_feil(tmp_path):
    db = tmp_path / "cache.db"
    bank.lagre([_p("1", "Atittel")], embed_fn=lambda t: (_ for _ in ()).throw(RuntimeError()),
               db_path=db) if False else None
    # papir cachet uten abstract → aldri embeddet
    p = _p("9", "Utenabstract")
    p = PaperDossier(**{**p.__dict__, "abstract": ""})
    bank.lagre([p], embed_fn=_embed, db_path=db)
    assert bank.relaterte_sitater("10.1/9", db_path=db) == []


def test_banken_virker_uten_embedder(tmp_path):
    """Grupperingen på papir krever ingen embedding. En nede embedder skal gjøre banken
    tregere å UTFORSKE, aldri utilgjengelig."""
    db = _oppsett(tmp_path)
    bank.lagre_sitat("10.1/1", "utdrag", db_path=db)
    assert len(bank.sitatbank(db_path=db)) == 1     # ingen embed_fn involvert


def test_boilerplaten_baerer_fullstendig_referanse_for_HVER_kilde(tmp_path):
    """Regresjon: _naboer_fra_rader droppet `forfattere`, så hver relatert kilde sto som
    «(2022) Aquaculture.» uten forfatter. En referanse uten forfatter er ikke en referanse."""
    db = _oppsett(tmp_path)
    bank.lagre_sitat("10.1/1", "utdrag en", db_path=db)
    bank.lagre_sitat("10.1/2", "utdrag to", db_path=db)
    rel = bank.relaterte_sitater("10.1/1", db_path=db)
    assert rel and all(r.get("forfattere") for r in rel)
    per = {p: bank.hent_sitater(p, db_path=db) for p in ["10.1/1"] + [r["id"] for r in rel]}
    md = rapport.til_markdown(rapport.boilerplate_blokker(
        bank.hent("10.1/1", db_path=db), rel, per))
    referanser = md.split("## Referanser")[1]
    assert referanser.count("Klykken C et al.") >= 2
    assert "avstand" in md and "utgangspunkt" in md
    assert "Din lesning" in md, "det som skal tenkes må være merket, ikke usynlig"
