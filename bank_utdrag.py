#!/usr/bin/env python3
"""bank_utdrag.py — et lite, selvstendig utdrag av bok-banken som prod kan søke i.

Hvorfor det finnes: bank_bakgrunn.py søker helst i hele boker.db (1,5 GB, bge-m3), men den
bor på Anders' Mac. Prod-containeren embedder med mistral-embed via ai-proxy, et ANNET
vektorrom, så bankens vektorer kan ikke gjenbrukes der. Løsningen er å ta med TEKSTEN til
den delen av banken profilen peker på (profiler/*.toml `bank_proveniens`) og embedde den
på nytt med den embedderen som faktisk skal søke. Ingen ny inngående flate, ingen
avhengighet av at Macen er på, og ingen tunnel.

To trinn, bevisst adskilt:
  1. `eksporter` (Mac): boker.db -> data/bank_utdrag.jsonl. Ren tekst + proveniens, ingen
     vektorer. Bare chunks som ALT er ratifisert inn i banken (lisensgaten i fold_op.py er
     passert); ingenting nytt slippes inn her.
  2. `bygg` (der søket skal kjøre, f.eks. `docker exec ... python bank_utdrag.py bygg`):
     jsonl -> bank_utdrag.db med embeddings fra GJELDENDE embedder. Idempotent: allerede
     embeddede chunk-id-er hoppes over, så en avbrutt kjøring kan tas opp igjen.

Vektorrommet er bokført i `meta.embed_modell`. sok() nekter å søke hvis spørringen ville
blitt embeddet med en annen modell enn utdraget (samme feilklasse embed_renhet.py vokter:
to modeller i samme vektorrom gir stille søppel, ikke en feil).
"""
import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import sqlite_vec

sys.path.insert(0, str(Path(__file__).resolve().parent))
import domeneprofil  # noqa: E402
from paths import DB  # noqa: E402

HER = Path(__file__).resolve().parent
JSONL = HER / "data" / "bank_utdrag.jsonl"
STANDARD_BOKER = Path.home() / "prosjekter" / "bøker" / "boker.db"
DIM = 1024
BATCH = 32
# ai-proxy/mistral-embed har tak per forespørsel; median chunk er ~1 100 tegn, men lengste er ~8 800.
# Batchen fylles derfor til første av antall eller tegnbudsjett.
MAKS_TEGN_BATCH = 20000


def utdrag_db_sti() -> Path:
    """Ved siden av cache.db (i prod: det monterte volumet), så utdraget overlever redeploy
    på samme måte som cachen. FORSKNINGSSOK_BANK_UTDRAG overstyrer."""
    ov = os.environ.get("FORSKNINGSSOK_BANK_UTDRAG")
    return Path(ov) if ov else DB.parent / "bank_utdrag.db"


def embed_modell() -> str:
    """Hvilken modell bank._hus_embed() faktisk bruker akkurat nå."""
    return "mistral-embed" if os.environ.get("AI_PROXY_URL") else "bge-m3"


def _db(sti: Path) -> sqlite3.Connection:
    db = sqlite3.connect(sti)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.execute("CREATE TABLE IF NOT EXISTS utdrag(chunk_id INTEGER PRIMARY KEY, bok TEXT, samling TEXT,"
               " heading TEXT, tekst TEXT, proveniens TEXT)")
    db.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS utdrag_vec USING vec0(chunk_id INTEGER PRIMARY KEY,"
               f" embedding float[{DIM}])")
    db.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")
    return db


def eksporter(boker_db: Path = STANDARD_BOKER, ut: Path = JSONL,
              prefikser: list[str] | None = None) -> int:
    """boker.db -> jsonl for chunks vars proveniens starter med et av prefiksene. Sortert på
    chunk-id, så to eksporter av samme bank gir samme fil (diffbar i git)."""
    prefikser = prefikser if prefikser is not None else list(domeneprofil.PROFIL.get("bank_proveniens", []))
    if not prefikser:
        raise RuntimeError("profilen har ingen `bank_proveniens` — ingenting å eksportere")
    db = sqlite3.connect(f"file:{boker_db}?mode=ro", uri=True)
    try:
        hvor = " OR ".join("proveniens LIKE ?" for _ in prefikser)
        rader = db.execute(
            f"SELECT id, bok, samling, heading, chunk_text, proveniens FROM book_chunks WHERE {hvor} ORDER BY id",
            [p + "%" for p in prefikser]).fetchall()
    finally:
        db.close()
    ut.parent.mkdir(parents=True, exist_ok=True)
    with ut.open("w", encoding="utf-8") as f:
        for cid, bok, samling, heading, tekst, prov in rader:
            f.write(json.dumps({"id": cid, "bok": bok, "samling": samling, "heading": heading,
                                "tekst": tekst, "proveniens": prov}, ensure_ascii=False) + "\n")
    return len(rader)


def bygg(jsonl: Path = JSONL, db_path: Path | None = None, *, embed_fn=None,
         modell: str | None = None, batch: int = BATCH) -> dict:
    """jsonl -> bank_utdrag.db. Returnerer {"nye", "hoppet_over", "totalt", "modell"}."""
    db_path = db_path or utdrag_db_sti()
    modell = modell or embed_modell()
    if embed_fn is None:
        import bank
        embed_fn = bank._hus_embed()
    db = _db(db_path)
    try:
        eksisterende_modell = db.execute("SELECT value FROM meta WHERE key='embed_modell'").fetchone()
        if eksisterende_modell and eksisterende_modell[0] != modell:
            raise RuntimeError(
                f"utdraget er embeddet med {eksisterende_modell[0]}, men denne kjøringen bruker {modell}. "
                "Slett bank_utdrag.db og bygg på nytt; to modeller kan ikke blandes i ett vektorrom.")
        db.execute("INSERT OR REPLACE INTO meta VALUES('embed_modell', ?)", (modell,))
        har = {r[0] for r in db.execute("SELECT chunk_id FROM utdrag_vec")}
        ventende = []
        for linje in jsonl.read_text(encoding="utf-8").splitlines():
            r = json.loads(linje)
            if r["id"] not in har:
                ventende.append(r)
        hoppet = sum(1 for _ in har)
        for del_ in _batcher(ventende, batch):
            for forsok in range(4):
                try:
                    vektorer = embed_fn([r["tekst"] for r in del_])
                    break
                except Exception:  # noqa: BLE001 — nettverk/rate-limit: prøv igjen, så gi opp høyt
                    if forsok == 3:
                        raise
                    time.sleep(2 ** forsok)
            for r, v in zip(del_, vektorer, strict=True):
                db.execute("INSERT OR REPLACE INTO utdrag VALUES (?,?,?,?,?,?)",
                           (r["id"], r["bok"], r["samling"], r["heading"], r["tekst"], r["proveniens"]))
                db.execute("INSERT INTO utdrag_vec(chunk_id, embedding) VALUES (?,?)",
                           (r["id"], sqlite_vec.serialize_float32(v)))
            db.commit()
        totalt = db.execute("SELECT count(*) FROM utdrag_vec").fetchone()[0]
        db.execute("INSERT OR REPLACE INTO meta VALUES('bygd', ?)", (time.strftime("%Y-%m-%dT%H:%M:%S"),))
        db.commit()
    finally:
        db.close()
    return {"nye": len(ventende), "hoppet_over": hoppet, "totalt": totalt, "modell": modell}


def _batcher(rader: list[dict], maks_antall: int):
    del_, tegn = [], 0
    for r in rader:
        if del_ and (len(del_) >= maks_antall or tegn + len(r["tekst"]) > MAKS_TEGN_BATCH):
            yield del_
            del_, tegn = [], 0
        del_.append(r)
        tegn += len(r["tekst"])
    if del_:
        yield del_


def finnes(db_path: Path | None = None) -> bool:
    sti = db_path or utdrag_db_sti()
    if not sti.is_file():
        return False
    db = sqlite3.connect(f"file:{sti}?mode=ro", uri=True)
    try:
        return db.execute("SELECT count(*) FROM utdrag").fetchone()[0] > 0
    except sqlite3.DatabaseError:
        return False
    finally:
        db.close()


def sok(emne: str, k: int, *, db_path: Path | None = None, embed_fn=None,
        modell: str | None = None) -> tuple[list[tuple], str]:
    """Nærmeste utdrag-chunks. Returnerer (rader, arsak); rader har samme form som
    boker.db-spørringen i bank_bakgrunn: (id, bok, samling, heading, tekst, proveniens, avstand).
    Tom liste + årsak hvis modellene ikke stemmer."""
    db_path = db_path or utdrag_db_sti()
    modell = modell or embed_modell()
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        lagret = db.execute("SELECT value FROM meta WHERE key='embed_modell'").fetchone()
        if not lagret or lagret[0] != modell:
            return [], (f"utdraget er embeddet med {lagret[0] if lagret else 'ukjent modell'}, "
                        f"søket ville brukt {modell}: feil vektorrom")
        if embed_fn is None:
            import bank
            embed_fn = bank._hus_embed()
        qvec = embed_fn([emne])[0]
        rader = db.execute(
            """SELECT u.chunk_id, u.bok, u.samling, u.heading, u.tekst, u.proveniens, v.distance
               FROM utdrag_vec v JOIN utdrag u ON u.chunk_id = v.chunk_id
               WHERE v.embedding MATCH ? AND K = ? ORDER BY v.distance""",
            (sqlite_vec.serialize_float32(qvec), k)).fetchall()
        return rader, ""
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(description="Utdrag av bok-banken for forskningssøk-syntesen")
    sub = p.add_subparsers(dest="kommando", required=True)
    e = sub.add_parser("eksporter", help="boker.db -> data/bank_utdrag.jsonl (kjøres på Macen)")
    e.add_argument("--boker", default=str(STANDARD_BOKER))
    e.add_argument("--ut", default=str(JSONL))
    b = sub.add_parser("bygg", help="jsonl -> bank_utdrag.db med gjeldende embedder (kjøres der søket skal gå)")
    b.add_argument("--jsonl", default=str(JSONL))
    b.add_argument("--db", default=None)
    sub.add_parser("status", help="finnes utdraget, hvilken modell, hvor mange chunks")
    a = p.parse_args()
    if a.kommando == "eksporter":
        n = eksporter(Path(a.boker), Path(a.ut))
        print(f"eksporterte {n} chunks til {a.ut} (prefikser: {domeneprofil.PROFIL.get('bank_proveniens')})")
    elif a.kommando == "bygg":
        print(bygg(Path(a.jsonl), Path(a.db) if a.db else None))
    else:
        sti = utdrag_db_sti()
        if not finnes(sti):
            print(f"{sti}: finnes ikke eller er tomt")
            return
        db = sqlite3.connect(f"file:{sti}?mode=ro", uri=True)
        print(sti, dict(db.execute("SELECT key, value FROM meta").fetchall()),
              "chunks:", db.execute("SELECT count(*) FROM utdrag").fetchone()[0])


if __name__ == "__main__":
    main()
