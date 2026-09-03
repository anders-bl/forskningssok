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

**To embed-veier, aldri blandet i samme cache.db** (lagt til 2026-09-04, Dokploy-
deploy-forberedelse): lokalt (Anders' Mac) deler dette fortsatt husets bge-m3-embedder
(silverbullet/ops/semantisk_sok.py:embed) read-only, samme kontrakt multisok bruker.
Men den modulen kaller til slutt en Ollama-instans på `localhost`/hjemme-flåtenoden —
nåbar på din Mac, IKKE fra en Dokploy-container på Netcup (ingen VPN/mesh dit funnet).
`AI_PROXY_URL` (satt kun i Dokploy-miljøet) bytter derfor til `ai-proxy`s `/embed`
(mistral-embed, EU-direkte, `dokploy-network`-internt — samme mønster smartsok/wiki
alt bruker, se `integrasjoner/dokploy`-wikisiden). Begge er 1024-dim (ingen
skjema-endring), men er IKKE samme vektor-rom — bge-m3 og mistral-embed er MÅLT ulike
fordelinger (se lauvasdatas `app/config.py`s kalibreringsnotater). Derfor: cache.db må
være embed-modell-REN. Lokal utvikling og prod-volumet er allerede strukturelt atskilt
(cache.db er gitignored, prod starter med et tomt volum) — ALDRI kopier en lokal
cache.db inn i prod-volumet, det ville blandet to inkompatible rom stille.
"""
import os
import sqlite3
import sys
import time
from pathlib import Path

import httpx
import sqlite_vec

from domeneprofil import arts_naer_tekst, domene_naer_tekst
from paths import DB
from schemas import PaperDossier

HJEM = Path.home() / "prosjekter"


def _ai_proxy_embed(texts: list[str]) -> list[list[float]]:
    """mistral-embed via ai-proxy /embed — se moduldocstring for hvorfor dette KUN
    brukes når AI_PROXY_URL er satt (Dokploy), aldri som stille lokal fallback."""
    url = os.environ["AI_PROXY_URL"].rstrip("/") + "/embed"
    wiki_id = os.environ.get("AI_PROXY_WIKI_ID", "forskningssok")
    r = httpx.post(url, json={"wiki_id": wiki_id, "input": texts}, timeout=120)
    r.raise_for_status()
    return r.json()["embeddings"]


def _hus_embed():
    if os.environ.get("AI_PROXY_URL"):
        return _ai_proxy_embed
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
    db.execute("""CREATE TABLE IF NOT EXISTS sitater(
        id INTEGER PRIMARY KEY, paper_id TEXT NOT NULL, tekst TEXT NOT NULL,
        kommentar TEXT, opprettet REAL NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS utkast(
        id INTEGER PRIMARY KEY, tittel TEXT NOT NULL, innhold TEXT NOT NULL,
        opprettet REAL NOT NULL, oppdatert REAL NOT NULL)""")
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
    lagret = 0
    for p, emb in zip(nye, embeddinger):
        # OR IGNORE, ikke ren INSERT: SELECT-sjekken over og denne INSERT-en er IKKE én
        # atomisk operasjon — to overlappende søk på samme uncachede spørring (f.eks. en
        # bruker som reloader mens embed_fn (opptil 120s, se _ai_proxy_embed) fortsatt
        # kjører server-side) kan begge se raden som fraværende og begge forsøke å skrive
        # den. Rein INSERT ga da sqlite3.IntegrityError: UNIQUE constraint failed —
        # ufanget i api.py (kun RuntimeError fanges), altså et rått 500 til klienten.
        # Reprodusert live 2026-09-04 (8 samtidige identiske /api/sok-kall).
        cur = db.execute(
            """INSERT OR IGNORE INTO papers(id,tittel,forfattere,tidsskrift,aar,doi,pmid,abstract,
               siteringstall,open_access,kilde_url,kilde_kode) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p.id, p.tittel, p.forfattere, p.tidsskrift, p.aar, p.doi, p.pmid, p.abstract,
             p.siteringstall, int(p.open_access), p.kilde_url, p.kilde_kode))
        if cur.rowcount == 0:
            continue  # en samtidig lagre() vant kappløpet — dens paper_vec-rad dekker oss
        db.execute("INSERT INTO paper_vec(chunk_id, embedding) VALUES (?,?)",
                   (cur.lastrowid, sqlite_vec.serialize_float32(emb)))
        lagret += 1
    db.commit()
    db.close()
    return lagret


_PAPER_KOLONNER = ("id", "tittel", "forfattere", "tidsskrift", "aar", "doi", "pmid",
                   "abstract", "siteringstall", "open_access", "kilde_url", "kilde_kode")


def hent(paper_id: str, *, db_path: Path = DB) -> dict | None:
    """Fullt cachet papir (alle felt) — ærlig None hvis ikke cachet, ikke en feil."""
    db = _db(db_path)
    rad = db.execute(
        f"SELECT {','.join(_PAPER_KOLONNER)} FROM papers WHERE id=?", (paper_id,)).fetchone()
    db.close()
    if not rad:
        return None
    d = dict(zip(_PAPER_KOLONNER, rad))
    d["open_access"] = bool(d["open_access"])
    return d


def lagre_sitat(paper_id: str, tekst: str, kommentar: str = "", *, db_path: Path = DB) -> dict:
    """Lagrer en sitert seksjon (+ valgfri kommentar) direkte fra leseflaten. Krever at
    papiret alt er cachet (paper_id må finnes i `papers`) — sitering av noe verktøyet
    ikke selv har hentet ville vært en gjettet kildehenvisning."""
    if not hent(paper_id, db_path=db_path):
        raise ValueError(f"{paper_id} er ikke cachet — søk det opp først")
    db = _db(db_path)
    ts = time.time()
    cur = db.execute(
        "INSERT INTO sitater(paper_id, tekst, kommentar, opprettet) VALUES (?,?,?,?)",
        (paper_id, tekst, kommentar, ts))
    db.commit()
    sid = cur.lastrowid
    db.close()
    return {"id": sid, "paper_id": paper_id, "tekst": tekst, "kommentar": kommentar, "opprettet": ts}


def oppdater_sitat(sitat_id: int, kommentar: str, *, db_path: Path = DB) -> bool:
    db = _db(db_path)
    cur = db.execute("UPDATE sitater SET kommentar=? WHERE id=?", (kommentar, sitat_id))
    db.commit()
    endret = cur.rowcount > 0
    db.close()
    return endret


def slett_sitat(sitat_id: int, *, db_path: Path = DB) -> bool:
    db = _db(db_path)
    cur = db.execute("DELETE FROM sitater WHERE id=?", (sitat_id,))
    db.commit()
    slettet = cur.rowcount > 0
    db.close()
    return slettet


def hent_sitater(paper_id: str | None = None, *, db_path: Path = DB) -> list[dict]:
    """Alle lagrede sitater, nyeste først — filtrert på ett papir hvis oppgitt, ellers
    hele notat-loggen (Notater-fanen på tvers av alt som er lest)."""
    db = _db(db_path)
    if paper_id:
        rows = db.execute(
            """SELECT s.id, s.paper_id, s.tekst, s.kommentar, s.opprettet, p.tittel, p.doi
               FROM sitater s JOIN papers p ON p.id = s.paper_id
               WHERE s.paper_id=? ORDER BY s.opprettet DESC""", (paper_id,)).fetchall()
    else:
        rows = db.execute(
            """SELECT s.id, s.paper_id, s.tekst, s.kommentar, s.opprettet, p.tittel, p.doi
               FROM sitater s JOIN papers p ON p.id = s.paper_id
               ORDER BY s.opprettet DESC""").fetchall()
    db.close()
    return [{"id": r[0], "paper_id": r[1], "tekst": r[2], "kommentar": r[3],
             "opprettet": r[4], "paper_tittel": r[5], "paper_doi": r[6]} for r in rows]


def _naboer_fra_rader(rows, k: int) -> list[dict]:
    """Bygger nabo-dicts og BÅNDER dem som ranking.py:_band gjør for hovedsøket
    (domene_naer, arts_naer FØR avstand) — samme species-trap-motvekt Svart hatt-
    gjennomgangen 2026-09-02 bygde for hovedsøket, tidligere kun FLAGGET (aldri sortert
    om) her. Det ærlige gapet («Relevans-panelet filtrerer IKKE på domene_naer/art ennå»,
    idébank #30) var at et menneske-CYP24A1-treff kunne ligge ØVERST i akkurat dette
    panelet på ren embedding-avstand med bare et advarselsikon ved siden av — synlig,
    men ikke mindre fremtredende. Banding fjerner INGEN kandidat (samme kontrakt som før,
    kun rekkefølgen endres), og kandidatSETTET (de k/k+1 nærmeste i embedding-rommet) er
    uendret — kun presentasjonsrekkefølgen innenfor det settet."""
    naboer = [{"id": r[0], "tittel": r[1], "tidsskrift": r[2], "aar": r[3], "doi": r[4],
               "kilde_url": r[5], "avstand": r[6],
               "domene_naer": domene_naer_tekst(f"{r[7]} {r[2]}"),
               "arts_naer": arts_naer_tekst(f"{r[1]} {r[8]}")}
              for r in rows]
    naboer.sort(key=lambda n: (not n["domene_naer"], not n["arts_naer"], n["avstand"]))
    return naboer[:k]


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
        SELECT p.id, p.tittel, p.tidsskrift, p.aar, p.doi, p.kilde_url, v.distance, p.forfattere, p.abstract
        FROM paper_vec v JOIN papers p ON p.rowid = v.chunk_id
        WHERE v.embedding MATCH ? AND K = ? AND v.chunk_id != ?
        ORDER BY v.distance""", (qvec[0], k + 1, rad[0])).fetchall()
    db.close()
    return _naboer_fra_rader(rows, k)


def lignende_tekst(tekst: str, k: int = 5, *, embed_fn=None, db_path: Path = DB) -> list[dict]:
    """FDR-038 ambient-modus: vilkårlig tekst (det Ulven SKRIVER, ikke et cachet papirs id)
    → nærmeste papirer i cachen. Samme sqlite-vec-spørring som lignende(), men søkevektoren
    beregnes on-the-fly fra teksten selv. Ærlig tom liste for for kort tekst (< 20 tegn —
    et par ord embedder til støy, ikke en meningsfull retning) eller tom cache, ALDRI en
    feil — «tomt korpus → stille, ærlig negativ» er FDR-038s eget suksesskriterium."""
    tekst = (tekst or "").strip()
    if len(tekst) < 20:
        return []
    db = _db(db_path)
    if db.execute("SELECT count(*) FROM papers").fetchone()[0] == 0:
        db.close()
        return []
    embed_fn = embed_fn or _hus_embed()
    qvec = embed_fn([tekst])[0]
    rows = db.execute("""
        SELECT p.id, p.tittel, p.tidsskrift, p.aar, p.doi, p.kilde_url, v.distance, p.forfattere, p.abstract
        FROM paper_vec v JOIN papers p ON p.rowid = v.chunk_id
        WHERE v.embedding MATCH ? AND K = ?
        ORDER BY v.distance""", (sqlite_vec.serialize_float32(qvec), k)).fetchall()
    db.close()
    return _naboer_fra_rader(rows, k)


def lagre_utkast(tittel: str, innhold: str, utkast_id: int | None = None,
                  *, db_path: Path = DB) -> dict:
    """Oppretter eller oppdaterer ett utkast (Skriv-modus). Idempotent på utkast_id — samme
    id oppdaterer i stedet for å duplisere, slik en autolagring skal virke."""
    db = _db(db_path)
    ts = time.time()
    if utkast_id is not None and db.execute(
            "SELECT 1 FROM utkast WHERE id=?", (utkast_id,)).fetchone():
        db.execute("UPDATE utkast SET tittel=?, innhold=?, oppdatert=? WHERE id=?",
                   (tittel, innhold, ts, utkast_id))
    else:
        cur = db.execute(
            "INSERT INTO utkast(tittel, innhold, opprettet, oppdatert) VALUES (?,?,?,?)",
            (tittel, innhold, ts, ts))
        utkast_id = cur.lastrowid
    db.commit()
    db.close()
    return {"id": utkast_id, "tittel": tittel, "innhold": innhold, "oppdatert": ts}


def hent_utkast(utkast_id: int, *, db_path: Path = DB) -> dict | None:
    db = _db(db_path)
    rad = db.execute(
        "SELECT id, tittel, innhold, opprettet, oppdatert FROM utkast WHERE id=?",
        (utkast_id,)).fetchone()
    db.close()
    if not rad:
        return None
    return {"id": rad[0], "tittel": rad[1], "innhold": rad[2], "opprettet": rad[3], "oppdatert": rad[4]}


def slett_utkast(utkast_id: int, *, db_path: Path = DB) -> bool:
    db = _db(db_path)
    cur = db.execute("DELETE FROM utkast WHERE id=?", (utkast_id,))
    db.commit()
    slettet = cur.rowcount > 0
    db.close()
    return slettet


def liste_utkast(*, db_path: Path = DB) -> list[dict]:
    """Sist oppdatert først — samme rekkefølge som en «nylig brukt»-liste bør ha."""
    db = _db(db_path)
    rows = db.execute(
        "SELECT id, tittel, opprettet, oppdatert FROM utkast ORDER BY oppdatert DESC").fetchall()
    db.close()
    return [{"id": r[0], "tittel": r[1], "opprettet": r[2], "oppdatert": r[3]} for r in rows]
