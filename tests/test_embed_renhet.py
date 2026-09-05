"""Verifiserer embed_renhet.py: at samme-modell gir ~0 (ren), en annen modell gir stort
avvik (blandet fanget), og at en tom cache meldes UMÅLT, ikke «ren».

Nettverksfri: embed_fn injiseres. En ekte bge-m3-kjøring gjøres i CLI-en.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bank  # noqa: E402
import embed_renhet as er  # noqa: E402
from schemas import PaperDossier  # noqa: E402

DIM = 1024


def _modell_a(texts):
    """En deterministisk «modell A»: vektor bestemt av tekstlengden, normalisert."""
    out = []
    for t in texts:
        v = [((len(t) + i) % 7) / 6.0 for i in range(DIM)]
        norm = sum(x * x for x in v) ** 0.5 or 1.0
        out.append([x / norm for x in v])
    return out


def _modell_b(texts):
    """En ANNEN modell: helt annet mønster, samme dim. Skal gi stort avvik mot A."""
    out = []
    for t in texts:
        v = [((len(t) * 3 + i * 2) % 5) / 4.0 for i in range(DIM)]
        norm = sum(x * x for x in v) ** 0.5 or 1.0
        out.append([x / norm for x in v])
    return out


def _cache_med(db, tekster, embed_fn):
    # DOI seedet av tittelen, ikke enumerate — ellers kolliderer id-er på tvers av kall og
    # bank.lagre dedupliserer bort papirer stille (fanget 2026-09-05: «Blandet inn» fikk
    # samme DOI som «Ren en» og ble aldri lagret, så testen så falskt ren ut).
    for tekst in tekster:
        sid = abs(hash(tekst)) % 100000
        p = PaperDossier(pmid=str(sid), doi=f"10.1/{sid}", tittel=tekst, forfattere="", tidsskrift="",
                         aar=2024, abstract="brødtekst her", siteringstall=0, open_access=False,
                         kilde_url="u")
        bank.lagre([p], embed_fn=embed_fn, db_path=db)


def test_ren_cache_gir_naer_null(tmp_path):
    """Samme modell inn og ut: avstanden er ~0 (deterministisk), cachen er ren."""
    db = tmp_path / "cache.db"
    _cache_med(db, ["Papir A", "Papir B", "Papir C"], _modell_a)
    r = er.sjekk_renhet(embed_fn=_modell_a, db_path=db, n=5)
    assert r["ren"] is True
    assert r["maks_avstand"] < er.TERSKEL


def test_blandet_cache_fanges(tmp_path):
    """Kjernen: cachen ble skrevet av modell A, men vi re-embedder med modell B (som om
    embedderen ble byttet). Stort avvik → ikke ren. Uten denne sjekken ville et
    modellbytte vært usynlig fordi dimensjonen er lik."""
    db = tmp_path / "cache.db"
    _cache_med(db, ["Papir A", "Papir B"], _modell_a)  # lagret med A
    r = er.sjekk_renhet(embed_fn=_modell_b, db_path=db, n=5)  # sjekket med B
    assert r["ren"] is False
    assert r["maks_avstand"] > er.TERSKEL
    assert len(r["avvik"]) >= 1


def test_delvis_blandet_ett_avvik_er_nok(tmp_path):
    """Én rad fra feil modell gjør hele cachen blandet. `ren` skal være False selv om de
    fleste radene stemmer."""
    db = tmp_path / "cache.db"
    # to papirer lagret med A, ett med B
    _cache_med(db, ["Ren en", "Ren to"], _modell_a)
    _cache_med(db, ["Blandet inn"], _modell_b)
    r = er.sjekk_renhet(embed_fn=_modell_a, db_path=db, n=10)  # sjekk mot A
    assert r["ren"] is False
    assert any("Blandet inn" in a["tittel"] for a in r["avvik"])


def test_tom_cache_er_UMAALT_ikke_ren(tmp_path):
    """Ingen embeddede papirer kan ikke bevise at embedderen stemmer. `ren` = None
    (umålt), aldri True — samme «0 er ikke en måling»-disiplin som resten av verktøyet."""
    db = tmp_path / "cache.db"
    bank._db(db).close()  # oppretter tomt skjema
    r = er.sjekk_renhet(embed_fn=_modell_a, db_path=db, n=5)
    assert r["ren"] is None and r["sjekket"] == 0


def test_deserialisering_er_riktig_vei():
    """_floats må invertere sqlite-vec sin serialize_float32 eksakt, ellers ville en ren
    cache sett blandet ut (falsk alarm)."""
    import sqlite_vec
    v = [0.1, -0.2, 0.3, 0.0]
    raa = sqlite_vec.serialize_float32(v)
    ut = er._floats(raa)
    assert len(ut) == 4
    assert all(abs(a - b) < 1e-6 for a, b in zip(ut, v))
