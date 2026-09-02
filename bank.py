"""bank.py — lokal sqlite-vec-cache av papir-abstracts, for relasjonelt «lignende
papir»-søk. Dette er DEN faktiske gjenbruken av kunnskapsbank-logikken Anders pekte på
(bøker/fag_bank.py + fag_sok.py: embed → sqlite-vec → avstand-rangert søk) — IKKE
bøker/hoster.py sin CC-lisens-gate, som løser et annet problem (permanent
redistribuerbar korpus). Dette er en PRIVAT spørretid-cache av API-returnert metadata
(abstract-tekst, ikke fulltekst) for ETT verktøys søk — samme juridiske klasse som
ADR-004s TTL-cache, ikke bøker/-prosjektets bok-bank.

Se prosjekt/idebank/28-nefrokalsinose-litteratursok §CopyMetaDiscoCat for hvorfor det
kompositoriske sitasjons-graf-laget (typede morfismer: støtter/motsier/bygger-på)
bevisst IKKE er bygget her ennå — samme datamangel-felle (få eksempler mot 1024 dim)
som DisCoCat-operatoren selv fant på wiki-grafen. Dette laget er ren distribusjonell
likhet (embeddings), første søyle, ikke tredje.

Deler husets bge-m3-embedder (silverbullet/ops/semantisk_sok.py:embed) read-only, samme
kontrakt multisok bruker — ingen ny modell, ingen nytt embedding-rom.
"""
import sqlite3
import sys
from pathlib import Path

import sqlite_vec

from schemas import PaperDossier

HJEM = Path.home() / "prosjekter"
DB = Path(__file__).resolve().parent / "cache.db"


def _hus_embed():
    sys.path.insert(0, str(HJEM / "silverbullet" / "ops"))
    try:
        from semantisk_sok import embed as hus_embed  # offentlig alias (samme som multisok bruker)
    except ImportError:
        from semantisk_sok import _embed as hus_embed
    return hus_embed


def _db(db_path: Path = DB) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.execute("""CREATE TABLE IF NOT EXISTS papers(
        id TEXT PRIMARY KEY, tittel TEXT, forfattere TEXT, tidsskrift TEXT, aar INTEGER,
        doi TEXT, pmid TEXT, abstract TEXT, siteringstall INTEGER, open_access INTEGER,
        kilde_url TEXT, kilde_kode TEXT)""")
    try:  # migrasjon for cache.db skrevet før dette feltet fantes — idempotent
        db.execute("ALTER TABLE papers ADD COLUMN kilde_kode TEXT")
        db.commit()
    except sqlite3.OperationalError:
        pass  # kolonnen finnes alt (ny db, eller migrasjonen alt kjørt)
    db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS paper_vec
        USING vec0(chunk_id INTEGER PRIMARY KEY, embedding float[1024])""")
    return db


def lagre(papirer: list[PaperDossier], *, embed_fn=None, db_path: Path = DB) -> int:
    """Cacher papirer + embedder abstracts. Kun de MED abstract embeddes — et tomt
    abstract gir ingen embedding, aldri en oppdiktet en (ærlighets-prinsippet fra
    Lag-3-spec'en). Idempotent på id (doi foretrukket, pmid fallback)."""
    embed_fn = embed_fn or _hus_embed()
    db = _db(db_path)
    nye = [p for p in papirer if p.abstract and not db.execute(
        "SELECT 1 FROM papers WHERE id=?", (p.id,)).fetchone()]
    if not nye:
        db.close()
        return 0
    embeddinger = embed_fn([f"{p.tittel}. {p.abstract}" for p in nye])
    for p, emb in zip(nye, embeddinger):
        cur = db.execute(
            """INSERT INTO papers(id,tittel,forfattere,tidsskrift,aar,doi,pmid,abstract,
               siteringstall,open_access,kilde_url,kilde_kode) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p.id, p.tittel, p.forfattere, p.tidsskrift, p.aar, p.doi, p.pmid, p.abstract,
             p.siteringstall, int(p.open_access), p.kilde_url, p.kilde_kode))
        db.execute("INSERT INTO paper_vec(chunk_id, embedding) VALUES (?,?)",
                   (cur.lastrowid, sqlite_vec.serialize_float32(emb)))
    db.commit()
    db.close()
    return len(nye)


def hent(paper_id: str, *, db_path: Path = DB) -> dict | None:
    """Slår opp et cachet papirs pmid+kilde_kode — det citation_gap.py trenger for å
    kalle Europe PMC /references. Ærlig None hvis ikke cachet, ikke en feil."""
    db = _db(db_path)
    rad = db.execute(
        "SELECT id, tittel, pmid, kilde_kode FROM papers WHERE id=?", (paper_id,)).fetchone()
    db.close()
    if not rad:
        return None
    return {"id": rad[0], "tittel": rad[1], "pmid": rad[2], "kilde_kode": rad[3]}


def lignende(paper_id: str, k: int = 5, *, db_path: Path = DB) -> list[dict]:
    """Papirer i CACHEN (ikke hele Europe PMC) semantisk nærmest et gitt papir — den
    relasjonelle aksen Ulven ba om, innenfor det som faktisk er søkt/cachet så langt.
    Vokser organisk med bruk, akkurat som fag.db vokser når Speider mater den — ærlig
    tom liste hvis papiret ikke er cachet eller manglet abstract, ikke en feil."""
    db = _db(db_path)
    rad = db.execute("SELECT rowid FROM papers WHERE id=?", (paper_id,)).fetchone()
    if not rad:
        db.close()
        return []
    qvec = db.execute("SELECT embedding FROM paper_vec WHERE chunk_id=?", (rad[0],)).fetchone()
    if not qvec:
        db.close()
        return []
    rows = db.execute("""
        SELECT p.id, p.tittel, p.tidsskrift, p.aar, p.doi, p.kilde_url, v.distance
        FROM paper_vec v JOIN papers p ON p.rowid = v.chunk_id
        WHERE v.embedding MATCH ? AND K = ? AND v.chunk_id != ?
        ORDER BY v.distance""", (qvec[0], k + 1, rad[0])).fetchall()
    db.close()
    return [{"id": r[0], "tittel": r[1], "tidsskrift": r[2], "aar": r[3], "doi": r[4],
             "kilde_url": r[5], "avstand": r[6]} for r in rows][:k]
