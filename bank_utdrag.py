#!/usr/bin/env python3
"""bank_utdrag.py — et lite, selvstendig utdrag av bok-banken som prod kan søke i.

Hvorfor det finnes: bank_bakgrunn.py søker helst i hele boker.db (1,5 GB, bge-m3), men den
bor på Anders' Mac. Prod-containeren embedder med mistral-embed via ai-proxy, et ANNET
vektorrom, så bankens vektorer kan ikke gjenbrukes der. Løsningen er å ta med TEKSTEN til
den delen av banken profilen peker på (profiler/*.toml `bank_proveniens`) og embedde den
på nytt med den embedderen som faktisk skal søke. Ingen ny inngående flate, ingen
avhengighet av at Macen er på, og ingen tunnel.

To trinn, bevisst adskilt:
  1. `eksporter` (Mac): boker.db -> JSONL + manifest. Ren tekst + proveniens, ingen vektorer.
     Bare chunks som ALT er ratifisert inn i banken (lisensgaten i fold_op.py er passert).
  2. `bygg` (der søket skal kjøre): standardmodus legger til nye chunks.
     `bygg --speil` avstemmer databasen mot hele JSONL-snapshotet og fjerner gamle ID-er.
     Nye embeddings er idempotente, så en avbrutt kjøring kan tas opp igjen.

Vektorrommet er bokført i `meta.embed_modell`. sok() nekter å søke hvis spørringen ville
blitt embeddet med en annen modell enn utdraget (samme feilklasse embed_renhet.py vokter:
to modeller i samme vektorrom gir stille søppel, ikke en feil).
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import sqlite_vec

sys.path.insert(0, str(Path(__file__).resolve().parent))
import art_niva  # noqa: E402
import domeneprofil  # noqa: E402
import tema  # noqa: E402
from paths import DB  # noqa: E402

HER = Path(__file__).resolve().parent
JSONL = HER / "data" / "bank_utdrag.jsonl"
MANIFEST = HER / "data" / "bank_utdrag.manifest.json"
STANDARD_BOKER = Path.home() / "prosjekter" / "bøker" / "boker.db"
DIM = 1024
BATCH = 32
MANIFEST_FORMAT_VERSION = 1
# ai-proxy/mistral-embed har tak per forespørsel; median chunk er ~1 100 tegn, men lengste er ~8 800.
# Batchen fylles derfor til første av antall eller tegnbudsjett.
MAKS_TEGN_BATCH = 20000


def manifest_sti(jsonl: Path = JSONL) -> Path:
    return MANIFEST if jsonl == JSONL else jsonl.with_suffix(".manifest.json")


def _skriv_midlertidig(mal: Path, innhold: bytes) -> Path:
    modus = mal.stat().st_mode & 0o777 if mal.exists() else 0o644
    sti = None
    try:
        with tempfile.NamedTemporaryFile(prefix=f".{mal.name}.", dir=mal.parent, delete=False) as f:
            sti = Path(f.name)
            f.write(innhold)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(sti, modus)
        return sti
    except BaseException:
        if sti is not None:
            sti.unlink(missing_ok=True)
        raise


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
    for kol in ("art_niva", "tema"):   # lagt til 2026-09-25; eldre utdrag migreres uten re-embedding
        if kol not in {r[1] for r in db.execute("PRAGMA table_info(utdrag)")}:
            db.execute(f"ALTER TABLE utdrag ADD COLUMN {kol} TEXT")
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
    klassifisering = _klassifiser_artikler(rader)
    manifest = manifest_sti(ut)
    digest = hashlib.sha256()
    data_temp = manifest_temp = None
    try:
        with tempfile.NamedTemporaryFile(prefix=f".{ut.name}.", dir=ut.parent, delete=False) as f:
            data_temp = Path(f.name)
            for cid, bok, samling, heading, tekst, prov in rader:
                niva, temaer = klassifisering[bok]
                linje = (json.dumps({"id": cid, "bok": bok, "samling": samling, "heading": heading,
                                     "tekst": tekst, "proveniens": prov, "art_niva": niva,
                                     "tema": temaer}, ensure_ascii=False) + "\n").encode("utf-8")
                f.write(linje)
                digest.update(linje)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(data_temp, ut.stat().st_mode & 0o777 if ut.exists() else 0o644)
        dokument = {"format_version": MANIFEST_FORMAT_VERSION, "row_count": len(rader),
                    "sha256": digest.hexdigest()}
        manifest_bytes = (json.dumps(dokument, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        manifest_temp = _skriv_midlertidig(manifest, manifest_bytes)
        os.replace(data_temp, ut)
        data_temp = None
        os.replace(manifest_temp, manifest)
        manifest_temp = None
    except BaseException:
        for sti in (data_temp, manifest_temp):
            if sti is not None:
                sti.unlink(missing_ok=True)
        raise
    return len(rader)


ARTIKKEL_CHUNKS = 3   # samme grunnlag som fasiten (tittel + de tre første chunkene)


def _klassifiser_artikler(rader: list[tuple]) -> dict[str, tuple[str, list[str]]]:
    """Art og temaer avgjøres per ARTIKKEL, ikke per chunk: en enkelt chunk nevner sjelden
    arten, men tittelen og de første chunkene gjør det. Alle chunks i en artikkel arver svaret."""
    tekster: dict[str, list[str]] = {}
    for _cid, bok, _s, _h, tekst, _p in rader:      # rader er sortert på id
        tekster.setdefault(bok, [])
        if len(tekster[bok]) < ARTIKKEL_CHUNKS:
            tekster[bok].append(tekst)
    ut = {}
    for bok, deler in tekster.items():
        samlet = " ".join(deler)[:3600]
        ut[bok] = (art_niva.klassifiser(bok, samlet).niva, [f.tema for f in tema.klassifiser(bok, samlet)])
    return ut


def _les_snapshot(jsonl: Path, *, speil: bool, tillat_tom: bool
                  ) -> tuple[list[dict], str | None, int | None]:
    """Valider full kilde og manifest foer speilmodus kan slette rader."""
    innhold = jsonl.read_bytes()
    sha256 = hashlib.sha256(innhold).hexdigest()
    manifest = None
    if speil:
        try:
            manifest = json.loads(manifest_sti(jsonl).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"speilmodus krever lesbart manifest: {manifest_sti(jsonl)}") from e
        if not isinstance(manifest, dict):
            raise ValueError("ugyldig snapshot-manifest")
        if type(manifest.get("format_version")) is not int or manifest["format_version"] != MANIFEST_FORMAT_VERSION:
            raise ValueError("ukjent format_version i snapshot-manifest")
        if manifest.get("sha256") != sha256:
            raise ValueError("snapshot-manifestets sha256 stemmer ikke med JSONL")
        if type(manifest.get("row_count")) is not int or manifest["row_count"] < 0:
            raise ValueError("ugyldig row_count i snapshot-manifest")
    rader = []
    sett = set()
    for nr, linje in enumerate(innhold.decode("utf-8").splitlines(), 1):
        rad = json.loads(linje)
        if not isinstance(rad, dict) or type(rad.get("id")) is not int or not isinstance(rad.get("tekst"), str):
            raise ValueError(f"ugyldig bankrad paa linje {nr}: krever heltalls-id og tekst")
        if rad["id"] in sett:
            raise ValueError(f"duplikat chunk-id {rad['id']} paa linje {nr}")
        sett.add(rad["id"])
        rader.append(rad)
    if manifest is not None and manifest["row_count"] != len(rader):
        raise ValueError("snapshot-manifestets row_count stemmer ikke med JSONL")
    if speil and not rader and not tillat_tom:
        raise ValueError("tom JSONL avvises i speilmodus; bruk tillat_tom=True for tilsiktet tomming")
    return rader, sha256 if speil else None, manifest["format_version"] if speil else None


def bygg(jsonl: Path = JSONL, db_path: Path | None = None, *, embed_fn=None,
         modell: str | None = None, batch: int = BATCH, speil: bool = False,
         tillat_tom: bool = False) -> dict:
    """Build from JSONL; speil=True removes obsolete IDs after a successful build."""
    if tillat_tom and not speil:
        raise ValueError("tillat_tom krever speil=True")
    rader, snapshot_sha256, snapshot_format_version = _les_snapshot(
        jsonl, speil=speil, tillat_tom=tillat_tom)
    kilde_ids = {r["id"] for r in rader}
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
        # Invalidate the old proof before any row or vector can change. Batch commits
        # make interrupted builds resumable, but no partial DB may claim snapshot parity.
        db.execute("DELETE FROM meta WHERE key IN ('snapshot_sha256', 'snapshot_rows', "
                   "'snapshot_format_version')")
        db.commit()
        db.execute("INSERT OR REPLACE INTO meta VALUES('embed_modell', ?)", (modell,))
        har = {r[0] for r in db.execute("SELECT chunk_id FROM utdrag_vec")}
        eksisterende = {r[0]: r[1:] for r in db.execute(
            "SELECT chunk_id, bok, samling, heading, tekst, proveniens, art_niva, tema FROM utdrag")}
        ventende = []
        hoppet = 0
        for r in rader:
            cid = r["id"]
            rad = (r.get("bok"), r.get("samling"), r.get("heading"), r["tekst"],
                   r.get("proveniens"), r.get("art_niva"),
                   json.dumps(r.get("tema", []), ensure_ascii=False))
            gammel = eksisterende.get(cid)
            if speil and cid in har and gammel is not None and gammel[3] == r["tekst"]:
                if gammel != rad:
                    db.execute("UPDATE utdrag SET bok=?, samling=?, heading=?, tekst=?, proveniens=?, "
                               "art_niva=?, tema=? WHERE chunk_id=?", (*rad, cid))
                hoppet += 1
            elif not speil and cid in har:
                db.execute("UPDATE utdrag SET art_niva=?, tema=? WHERE chunk_id=?",
                           (r.get("art_niva"), rad[6], cid))
                hoppet += 1
            else:
                ventende.append(r)
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
                db.execute("DELETE FROM utdrag_vec WHERE chunk_id=?", (r["id"],))
                db.execute("INSERT OR REPLACE INTO utdrag(chunk_id, bok, samling, heading, tekst, proveniens,"
                           " art_niva, tema) VALUES (?,?,?,?,?,?,?,?)",
                           (r["id"], r["bok"], r["samling"], r["heading"], r["tekst"], r["proveniens"],
                            r.get("art_niva"), json.dumps(r.get("tema", []), ensure_ascii=False)))
                db.execute("INSERT INTO utdrag_vec(chunk_id, embedding) VALUES (?,?)",
                           (r["id"], sqlite_vec.serialize_float32(v)))
            db.commit()
        fjernet = 0
        if speil:
            tekst_ids = {r[0] for r in db.execute("SELECT chunk_id FROM utdrag")}
            vektor_ids = {r[0] for r in db.execute("SELECT chunk_id FROM utdrag_vec")}
            if tekst_ids != vektor_ids:
                raise RuntimeError("utdrag-databasen har ulike ID-sett mellom tekst og vektorer; avbrot speiling")
            foreldet = tekst_ids - kilde_ids
            for cid in foreldet:
                db.execute("DELETE FROM utdrag_vec WHERE chunk_id=?", (cid,))
                db.execute("DELETE FROM utdrag WHERE chunk_id=?", (cid,))
            fjernet = len(foreldet)
            db.execute("INSERT OR REPLACE INTO meta VALUES('snapshot_sha256', ?)", (snapshot_sha256,))
            db.execute("INSERT OR REPLACE INTO meta VALUES('snapshot_rows', ?)", (str(len(rader)),))
            db.execute("INSERT OR REPLACE INTO meta VALUES('snapshot_format_version', ?)",
                       (str(snapshot_format_version),))
        totalt = db.execute("SELECT count(*) FROM utdrag_vec").fetchone()[0]
        db.execute("INSERT OR REPLACE INTO meta VALUES('bygd', ?)", (time.strftime("%Y-%m-%dT%H:%M:%S"),))
        db.commit()
    finally:
        db.close()
    return {"nye": len(ventende), "hoppet_over": hoppet, "fjernet": fjernet,
            "totalt": totalt, "modell": modell}


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


def verifiser(jsonl: Path = JSONL, db_path: Path | None = None) -> dict:
    """Read-only check that DB rows and vectors match one complete manifested snapshot."""
    try:
        rader, sha256, format_version = _les_snapshot(jsonl, speil=True, tillat_tom=True)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as e:
        return {"ok": False, "checks": {}, "errors": [f"snapshot: {type(e).__name__}: {e}"]}

    sti = db_path or utdrag_db_sti()
    if not sti.is_file():
        return {"ok": False, "checks": {}, "errors": [f"database mangler: {sti}"]}
    db = None
    try:
        db = sqlite3.connect(f"file:{sti}?mode=ro", uri=True)
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        meta = dict(db.execute("SELECT key, value FROM meta"))
        lagrede_rader = {
            rad[0]: rad[1:] for rad in db.execute(
                "SELECT chunk_id, bok, samling, heading, tekst, proveniens, art_niva, tema FROM utdrag")
        }
        vektor_ids = {rad[0] for rad in db.execute("SELECT chunk_id FROM utdrag_vec")}
    except (OSError, sqlite3.Error) as e:
        return {"ok": False, "checks": {}, "errors": [f"database: {type(e).__name__}: {e}"]}
    finally:
        if db is not None:
            db.close()

    kilde_rader = {
        rad["id"]: (rad.get("bok"), rad.get("samling"), rad.get("heading"), rad["tekst"],
                    rad.get("proveniens"), rad.get("art_niva"),
                    json.dumps(rad.get("tema", []), ensure_ascii=False))
        for rad in rader
    }
    tekst_ids = set(lagrede_rader)
    avvikende_rader = sum(1 for cid in tekst_ids & set(kilde_rader)
                          if lagrede_rader[cid] != kilde_rader[cid])
    checks = {
        "embed_modell": bool(meta.get("embed_modell")),
        "snapshot_format_version": meta.get("snapshot_format_version") == str(format_version),
        "snapshot_rows": meta.get("snapshot_rows") == str(len(rader)),
        "snapshot_sha256": meta.get("snapshot_sha256") == sha256,
        "tekst_id-er": tekst_ids == set(kilde_rader),
        "tekstinnhold": avvikende_rader == 0,
        "vektor_id-er": vektor_ids == set(kilde_rader),
    }
    feil = [navn for navn, bestatt in checks.items() if not bestatt]
    return {"ok": not feil, "rows": len(rader), "sha256": sha256,
            "checks": checks, "errors": feil}


def sok(emne: str, k: int, *, db_path: Path | None = None, embed_fn=None,
        modell: str | None = None) -> tuple[list[tuple], str]:
    """Nærmeste utdrag-chunks. Returnerer (rader, arsak); rader har samme form som
    boker.db-spørringen i bank_bakgrunn: (id, bok, samling, heading, tekst, proveniens, avstand,
    art_niva, tema); de to siste er None/None fra boker.db.
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
            """SELECT u.chunk_id, u.bok, u.samling, u.heading, u.tekst, u.proveniens, v.distance,
                      u.art_niva, u.tema
               FROM utdrag_vec v JOIN utdrag u ON u.chunk_id = v.chunk_id
               WHERE v.embedding MATCH ? AND K = ? ORDER BY v.distance""",
            (sqlite_vec.serialize_float32(qvec), k)).fetchall()
        return rader, ""
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(description="Utdrag av bok-banken for forskningssøk-syntesen")
    sub = p.add_subparsers(dest="kommando", required=True)
    e = sub.add_parser("eksporter", help="boker.db -> JSONL + manifest (kjøres på Macen)")
    e.add_argument("--boker", default=str(STANDARD_BOKER))
    e.add_argument("--ut", default=str(JSONL))
    b = sub.add_parser("bygg", help="jsonl -> bank_utdrag.db med gjeldende embedder (kjøres der søket skal gå)")
    b.add_argument("--jsonl", default=str(JSONL))
    b.add_argument("--db", default=None)
    b.add_argument("--speil", action="store_true", help="fjern DB-ID-er som mangler i hele JSONL-kilden")
    b.add_argument("--tillat-tom", action="store_true", help="tillat at speilmodus tømmer databasen")
    v = sub.add_parser("verifiser", help="kontroller DB mot komplett JSONL-snapshot uten å skrive")
    v.add_argument("--jsonl", default=str(JSONL))
    v.add_argument("--db", default=None)
    sub.add_parser("status", help="finnes utdraget, hvilken modell, hvor mange chunks")
    a = p.parse_args()
    if a.kommando == "eksporter":
        ut = Path(a.ut)
        n = eksporter(Path(a.boker), ut)
        print(f"eksporterte {n} chunks til {ut} og manifest {manifest_sti(ut)} "
              f"(prefikser: {domeneprofil.PROFIL.get('bank_proveniens')})")
    elif a.kommando == "bygg":
        if a.tillat_tom and not a.speil:
            p.error("--tillat-tom krever --speil")
        print(bygg(Path(a.jsonl), Path(a.db) if a.db else None,
                   speil=a.speil, tillat_tom=a.tillat_tom))
    elif a.kommando == "verifiser":
        resultat = verifiser(Path(a.jsonl), Path(a.db) if a.db else None)
        print(json.dumps(resultat, ensure_ascii=False, sort_keys=True))
        if not resultat["ok"]:
            raise SystemExit(1)
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
