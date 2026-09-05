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
import json
import logging
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

logger = logging.getLogger(__name__)

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
    # Rørseparert tekst, ikke JSON: feltene er korte flate lister, og «|» er trygt i
    # MeSH-termer og NLM-publikasjonstyper (verifisert mot NLMs vokabular — ingen av dem
    # inneholder rør). rapport.py splitter allerede på «|».
    for kolonne in ("kilde_kode TEXT", "volum TEXT", "hefte TEXT", "sider TEXT", "issn TEXT",
                    "pubtyper TEXT", "mesh TEXT", "mesh_major TEXT"):
        try:  # migrasjon for cache.db skrevet før feltet fantes — idempotent
            db.execute(f"ALTER TABLE papers ADD COLUMN {kolonne}")
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
    try:  # migrasjon: sitater fantes før dokumentskuffen — idempotent, samme mønster
        db.execute("ALTER TABLE sitater ADD COLUMN utkast_id INTEGER")
        db.commit()
    except sqlite3.OperationalError:
        pass  # kolonnen finnes alt
    db.execute("""CREATE TABLE IF NOT EXISTS kilde_status(
        kilde TEXT PRIMARY KEY, sist_ok REAL, sist_feil REAL,
        feil_paa_rad INTEGER NOT NULL DEFAULT 0, siste_feilmelding TEXT)""")
    # Revisjonssporet: hva som FAKTISK kjørte per spørring. Idébank #29 §Kritikk punkt
    # C/D — bibliotekar-fagmiljøet ber om dokumentasjon av hvert filtreringslag per søk,
    # og «Om»-panelet svarer kun på metodikken generelt, ikke på hva som skjedde i DETTE
    # søket. Revisjonen lagres som JSON fordi den er et lesbart spor, ikke noe vi spør på.
    db.execute("""CREATE TABLE IF NOT EXISTS sok_logg(
        id INTEGER PRIMARY KEY, query TEXT NOT NULL, tid REAL NOT NULL,
        treff INTEGER NOT NULL, revisjon TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS varme(
        paper_id TEXT PRIMARY KEY, poeng REAL NOT NULL, sist_rort REAL NOT NULL,
        sterkeste_hendelse TEXT)""")
    try:  # migrasjon: kolonnen het «siste_hendelse» før den lagret det sterkeste
        db.execute("ALTER TABLE varme RENAME COLUMN siste_hendelse TO sterkeste_hendelse")
        db.commit()
    except sqlite3.OperationalError:
        pass  # alt omdøpt, eller tabellen er ny
    return db


# ---------- Varme: det VARIGE laget (se varm_opp for hvorfor to lag, ikke ett) ----------

VARME_VEKT = {
    "apnet": 1.0,      # du leste det
    "sitert": 6.0,     # du tok noe ut av det
    "dokument": 4.0,   # du festet det til et dokument
    "nabo": 0.0,       # settes av spredningen selv, aldri direkte utenfra
}
# Hvilken handling som får NAVNGI et papir i panelet. Ikke den siste, men den sterkeste:
# målt live 2026-09-04 sa kortet «du har lest det» om et papir jeg nettopp hadde SITERT,
# fordi en sidelast rakk å skrive «apnet» oppå. Et papir du har sitert er et papir du har
# sitert, uansett hvor mange ganger du åpner det etterpå.
HENDELSE_RANG = {"sitert": 4, "dokument": 3, "apnet": 2, "nabo": 1}
NABO_SPREDNING = 0.30   # brøkdel av kildens delta som treffer hver semantiske nabo
NABO_VIDDE = 5          # hvor mange naboer spredningen når


def varm_opp(paper_id: str, hendelse: str, *, spre: bool = True, db_path: Path = DB) -> float:
    """Legger varme på ETT papir og (for «sitert»/«dokument») en brøkdel på dets
    semantiske naboer. Returnerer papirets nye totalpoeng.

    Hvorfor akkumulert og persistert, ikke utledet på nytt hver gang: det andre laget
    (avstand mot teksten du skriver NÅ, se lignende_tekst) er allerede momentant og
    glemmer alt mellom dokumenter. Dette laget er hukommelsen — «du har rørt dette 11
    ganger over to uker» er et signal ingen avstandsmåling kan gjenskape. De to holdes
    bevisst atskilt hele veien opp i UI-et, slik at et papir som er varmt aldri skjuler
    HVORFOR det er varmt.

    Ingen forfall: varmen synker aldri av seg selv. Et papir du sluttet å bruke blir
    kaldt RELATIVT (visningen normaliserer mot maks), ikke absolutt — verktøyet skal
    ikke stille glemme noe du faktisk brukte.

    Spredningen er grunnen til at panelet kan løfte fram noe du ALDRI har åpnet: siterer
    du A, arver A-s nærmeste naboer 30 % av det. Ukjent, men i selskap med noe du brukte.
    """
    vekt = VARME_VEKT.get(hendelse)
    if not vekt:
        return 0.0
    poeng = _legg_varme(paper_id, vekt, hendelse, db_path=db_path)
    if spre and hendelse in ("sitert", "dokument"):
        for n in lignende(paper_id, k=NABO_VIDDE, db_path=db_path):
            _legg_varme(n["id"], vekt * NABO_SPREDNING, "nabo", db_path=db_path)
    return poeng


def _legg_varme(paper_id: str, delta: float, hendelse: str, *, db_path: Path = DB) -> float:
    """BEGIN IMMEDIATE, ikke en ren UPSERT: navnevalget må lese den lagrede hendelsen
    før det skriver, og rangeringen bor i HENDELSE_RANG — å speile den i et SQL
    CASE-uttrykk ville gitt to kopier av samme regel som kan drive fra hverandre.
    IMMEDIATE tar skrivelåsen med én gang, så to samtidige varm_opp serialiseres i stedet
    for å lese samme utgangstilstand og skrive navnet nedover igjen."""
    db = _db(db_path)
    ts = time.time()
    try:
        db.execute("BEGIN IMMEDIATE")
        rad = db.execute(
            "SELECT poeng, sterkeste_hendelse FROM varme WHERE paper_id=?", (paper_id,)).fetchone()
        if rad is None:
            db.execute("INSERT INTO varme(paper_id, poeng, sist_rort, sterkeste_hendelse) VALUES (?,?,?,?)",
                       (paper_id, delta, ts, hendelse))
            poeng = delta
        else:
            poeng = rad[0] + delta
            navn = hendelse if HENDELSE_RANG.get(hendelse, 0) > HENDELSE_RANG.get(rad[1], 0) else rad[1]
            db.execute("UPDATE varme SET poeng=?, sist_rort=?, sterkeste_hendelse=? WHERE paper_id=?",
                       (poeng, ts, navn, paper_id))
        db.commit()
    finally:
        db.close()
    return poeng


def varmeliste(k: int = 12, *, db_path: Path = DB) -> list[dict]:
    """Varmeste papirer først. JOIN mot papers, ikke LEFT JOIN: varme på en id som ikke
    (lenger) er cachet er ikke et papir vi kan vise — den blir stille liggende i
    varme-tabellen til papiret eventuelt caches igjen, i stedet for å bli en rad uten
    tittel i panelet."""
    db = _db(db_path)
    rows = db.execute("""
        SELECT p.id, p.tittel, p.tidsskrift, p.aar, p.doi, p.kilde_url,
               v.poeng, v.sist_rort, v.sterkeste_hendelse, p.forfattere, p.abstract
        FROM varme v JOIN papers p ON p.id = v.paper_id
        ORDER BY v.poeng DESC LIMIT ?""", (k,)).fetchall()
    db.close()
    return [{"id": r[0], "tittel": r[1], "tidsskrift": r[2], "aar": r[3], "doi": r[4],
             "kilde_url": r[5], "poeng": round(r[6], 2), "sist_rort": r[7],
             "sterkeste_hendelse": r[8],
             "domene_naer": domene_naer_tekst(f"{r[9]} {r[2]}"),
             "arts_naer": arts_naer_tekst(f"{r[1]} {r[10]}")} for r in rows]


def registrer_kildekall(kilde: str, ok: bool, melding: str = "", *, db_path: Path = DB) -> int:
    """Bokfør utfallet av et EKTE kall til en ekstern kilde. Returnerer feil-på-rad etterpå.

    PASSIV observasjon, ikke aktiv sondering. Alternativet — å pinge Europe PMC, OpenAlex,
    CORE og Crossref på timer for å vite om de lever — betyr fire tredjepartskall per
    runde for å svare på et spørsmål om VÅR tjeneste, og det måler dessuten en syntetisk
    sti ingen bruker går. Her måles den ekte: hvert søk et menneske gjør er allerede en
    prøve, og den er gratis.

    `feil_paa_rad` er nøkkelen til å skille to tilstander som ser like ut i et
    tidsstempel: «sist_ok er tre dager gammel» kan bety at kilden er nede ELLER at ingen
    har søkt på tre dager. En teller på rad kan bare vokse når noen faktisk prøvde."""
    db = _db(db_path)
    naa = time.time()
    if ok:
        db.execute("""INSERT INTO kilde_status(kilde, sist_ok, feil_paa_rad) VALUES (?,?,0)
                      ON CONFLICT(kilde) DO UPDATE SET sist_ok=excluded.sist_ok,
                      feil_paa_rad=0, siste_feilmelding=NULL""", (kilde, naa))
        paa_rad = 0
    else:
        db.execute("""INSERT INTO kilde_status(kilde, sist_feil, feil_paa_rad, siste_feilmelding)
                      VALUES (?,?,1,?)
                      ON CONFLICT(kilde) DO UPDATE SET sist_feil=excluded.sist_feil,
                      feil_paa_rad=kilde_status.feil_paa_rad+1,
                      siste_feilmelding=excluded.siste_feilmelding""", (kilde, naa, melding[:200]))
        paa_rad = db.execute("SELECT feil_paa_rad FROM kilde_status WHERE kilde=?",
                             (kilde,)).fetchone()[0]
    db.commit()
    db.close()
    return paa_rad


def kilde_status(*, db_path: Path = DB) -> list[dict]:
    """Sist kjente utfall per kilde. Tom liste = ingen søk er kjørt ennå, som er en ærlig
    tredje tilstand og ikke «alt er bra»."""
    db = _db(db_path)
    rows = db.execute("""SELECT kilde, sist_ok, sist_feil, feil_paa_rad, siste_feilmelding
                         FROM kilde_status ORDER BY kilde""").fetchall()
    db.close()
    return [{"kilde": r[0], "sist_ok": r[1], "sist_feil": r[2],
             "feil_paa_rad": r[3], "siste_feilmelding": r[4]} for r in rows]


def lagre(papirer: list[PaperDossier], *, embed_fn=None, db_path: Path = DB) -> int:
    """Cacher papirer + embedder abstracts. Kun de MED abstract embeddes — et tomt
    abstract gir ingen embedding, aldri en oppdiktet en (ærlighets-prinsippet fra
    Lag-3-spec'en). Idempotent på id (doi foretrukket, pmid fallback)."""
    embed_fn = embed_fn or _hus_embed()
    db = _db(db_path)
    nye = [p for p in papirer if not db.execute(
        "SELECT 1 FROM papers WHERE id=?", (p.id,)).fetchone()]
    if not nye:
        db.close()
        return 0

    # RADENE FØRST, EMBEDDINGEN ETTERPÅ. Rekkefølgen er ikke kosmetisk — den var en ekte
    # brukerfeil, rapportert av Anders 2026-09-04 mot prod: «Kunne ikke lagre:
    # 10.1111/jfd.70099 er ikke cachet — søk det opp først».
    #
    # Før dette embedde lagre() FØR den satte inn noe. To veier til samme melding:
    #   A) embed_fn feiler eller timer ut (i prod er det ai-proxy over dokploy-network,
    #      opptil 120 s) → unntaket kastes før første INSERT → NULL papirer cachet, og
    #      sitering er umulig. Rådet «søk det opp først» er da nytteløst: et nytt søk
    #      kjører samme bakgrunnsjobb mot samme nedetid.
    #   B) papirer uten abstract ble filtrert bort HELT, ikke bare fra embeddingen. De
    #      kunne dermed aldri siteres, permanent.
    #
    # Å sitere er en kjernehandling som koster én rad; å embedde er en VALGFRI berikelse
    # som gir `--lignende` og varme-panelet. En feilende berikelse skal aldri kunne blokkere
    # kjernehandlingen. Papirer uten vektor er allerede håndtert overalt: lignende() slår opp
    # paper_vec separat og returnerer ærlig tom liste, varmeliste() joiner kun papers.
    lagret = 0
    for p in nye:
        # OR IGNORE, ikke ren INSERT: SELECT-sjekken over og denne INSERT-en er IKKE én
        # atomisk operasjon — to overlappende søk på samme uncachede spørring (f.eks. en
        # bruker som reloader mens embeddingen fortsatt kjører server-side) kan begge se
        # raden som fraværende og begge forsøke å skrive den. Rein INSERT ga da
        # sqlite3.IntegrityError: UNIQUE constraint failed — ufanget i api.py (kun
        # RuntimeError fanges), altså et rått 500 til klienten.
        # Reprodusert live 2026-09-04 (8 samtidige identiske /api/sok-kall).
        cur = db.execute(
            """INSERT OR IGNORE INTO papers(id,tittel,forfattere,tidsskrift,aar,doi,pmid,abstract,
               siteringstall,open_access,kilde_url,kilde_kode,volum,hefte,sider,issn,
               pubtyper,mesh,mesh_major)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p.id, p.tittel, p.forfattere, p.tidsskrift, p.aar, p.doi, p.pmid, p.abstract,
             p.siteringstall, int(p.open_access), p.kilde_url, p.kilde_kode,
             p.volum, p.hefte, p.sider, p.issn,
             "|".join(p.pubtyper), "|".join(p.mesh), "|".join(p.mesh_major)))
        if cur.rowcount:
            lagret += 1
    db.commit()
    db.close()

    # Embeddingen er nå et eget, feilbart steg. Feiler den, står radene igjen og
    # embed_manglende() tar dem ved neste søk — selvhelbredende i stedet for tapt.
    embed_manglende(embed_fn=embed_fn, db_path=db_path)
    return lagret


def embed_manglende(*, embed_fn=None, db_path: Path = DB) -> int:
    """Embedder cachede papirer som har abstract men mangler vektor. Idempotent.

    Finnes fordi lagre() ikke lenger lar en feilende embedder velte hele cachingen: da
    trengs en vei tilbake for radene som ble stående uten vektor. Kalles fra lagre() selv,
    så et hvilket som helst senere søk tar igjen etterslepet uten at noen husker det."""
    db = _db(db_path)
    rader = db.execute("""
        SELECT p.rowid, p.tittel, p.abstract FROM papers p
        LEFT JOIN paper_vec v ON v.chunk_id = p.rowid
        WHERE v.chunk_id IS NULL AND p.abstract IS NOT NULL AND p.abstract != ''""").fetchall()
    if not rader:
        db.close()
        return 0
    embed_fn = embed_fn or _hus_embed()
    try:
        embeddinger = embed_fn([f"{t}. {a}" for _, t, a in rader])
    except Exception:
        db.close()
        raise
    n = 0
    for (rowid, _, _), emb in zip(rader, embeddinger):
        db.execute("INSERT OR IGNORE INTO paper_vec(chunk_id, embedding) VALUES (?,?)",
                   (rowid, sqlite_vec.serialize_float32(emb)))
        n += 1
    db.commit()
    db.close()
    return n


_PAPER_KOLONNER = ("id", "tittel", "forfattere", "tidsskrift", "aar", "doi", "pmid",
                   "abstract", "siteringstall", "open_access", "kilde_url", "kilde_kode",
                   "volum", "hefte", "sider", "issn", "pubtyper", "mesh", "mesh_major")


def berik_sitasjonsfelt(*, db_path: Path = DB, batch: int = 20, sok_fn=None) -> int:
    """Fyller volum/hefte/sider/issn på papirer som ble cachet FØR feltene fantes.

    Nødvendig fordi migrasjonen bare legger til kolonner — den kan ikke finne opp verdier.
    Alle 55 papirer i Anders' cache manglet dem 2026-09-04.

    Batcher DOI-ene i ÉN Europe PMC-spørring per gruppe (`DOI:"a" OR DOI:"b" …`) i stedet
    for ett kall per papir: 55 papirer blir 3 kall, ikke 55. Samme høflighets-disiplin som
    adapternes polite-pool-UA.

    Oppdaterer KUN felter som er NULL, aldri felter som alt har verdi — en berikelse skal
    ikke kunne overskrive noe et ferskere søk har hentet. Papirer uten DOI hoppes over og
    telles ikke som beriket; de har ingen nøkkel å slå opp på."""
    from adapters.europe_pmc import sok as _sok
    sok_fn = sok_fn or _sok
    db = _db(db_path)
    doier = [r[0] for r in db.execute(
        """SELECT doi FROM papers WHERE doi IS NOT NULL AND doi != ''
           AND (volum IS NULL OR mesh IS NULL)""")]
    db.close()
    if not doier:
        return 0

    beriket = 0
    for i in range(0, len(doier), batch):
        gruppe = doier[i:i + batch]
        query = " OR ".join(f'DOI:"{d}"' for d in gruppe)
        try:
            treff = sok_fn(query, page_size=len(gruppe))
        except RuntimeError:
            continue  # kilden nede for DENNE gruppen — de andre gruppene skal ikke falle med
        db = _db(db_path)
        for p in treff:
            if not (p.volum or p.hefte or p.sider or p.issn):
                continue
            cur = db.execute(
                """UPDATE papers SET volum = COALESCE(volum, ?), hefte = COALESCE(hefte, ?),
                   sider = COALESCE(sider, ?), issn = COALESCE(issn, ?),
                   pubtyper = COALESCE(NULLIF(pubtyper,''), ?),
                   mesh = COALESCE(NULLIF(mesh,''), ?),
                   mesh_major = COALESCE(NULLIF(mesh_major,''), ?)
                   WHERE doi = ?""",
                (p.volum, p.hefte, p.sider, p.issn,
                 "|".join(p.pubtyper), "|".join(p.mesh), "|".join(p.mesh_major), p.doi))
            beriket += cur.rowcount
        db.commit()
        db.close()
    return beriket


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


def lagre_sitat(paper_id: str, tekst: str, kommentar: str = "",
                 utkast_id: int | None = None, *, db_path: Path = DB) -> dict:
    """Lagrer en sitert seksjon (+ valgfri kommentar) direkte fra leseflaten. Krever at
    papiret alt er cachet (paper_id må finnes i `papers`) — sitering av noe verktøyet
    ikke selv har hentet ville vært en gjettet kildehenvisning.

    `utkast_id` er NULLBAR med vilje (hybriden Anders valgte 2026-09-04): sitatet hører
    alltid til papiret, og hører I TILLEGG til ett dokument hvis ett var åpent da du
    siterte. Er det ingen, blir det et løst sitat du kan feste senere — det havner aldri
    i et dokument du ikke ba om, og går aldri tapt fordi du ikke hadde ett åpent."""
    if not hent(paper_id, db_path=db_path):
        raise ValueError(f"{paper_id} er ikke cachet — søk det opp først")
    db = _db(db_path)
    ts = time.time()
    cur = db.execute(
        "INSERT INTO sitater(paper_id, tekst, kommentar, opprettet, utkast_id) VALUES (?,?,?,?,?)",
        (paper_id, tekst, kommentar, ts, utkast_id))
    db.commit()
    sid = cur.lastrowid
    db.close()
    return {"id": sid, "paper_id": paper_id, "tekst": tekst, "kommentar": kommentar,
            "opprettet": ts, "utkast_id": utkast_id}


def knytt_sitat(sitat_id: int, utkast_id: int | None, *, db_path: Path = DB) -> bool:
    """Fester et løst sitat til et dokument, eller løsner det igjen (utkast_id=None).
    Å fjerne et sitat fra dokumentet SKAL ikke slette det — slett_sitat er den eneste
    veien til faktisk tap, og den må velges eksplisitt."""
    db = _db(db_path)
    cur = db.execute("UPDATE sitater SET utkast_id=? WHERE id=?", (utkast_id, sitat_id))
    db.commit()
    endret = cur.rowcount > 0
    db.close()
    return endret


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


_SITAT_FELT = """SELECT s.id, s.paper_id, s.tekst, s.kommentar, s.opprettet,
                        p.tittel, p.doi, s.utkast_id, p.forfattere, p.tidsskrift, p.aar
                 FROM sitater s JOIN papers p ON p.id = s.paper_id"""


def hent_sitater(paper_id: str | None = None, *, utkast_id: int | None = None,
                  kun_lose: bool = False, db_path: Path = DB) -> list[dict]:
    """Alle lagrede sitater, nyeste først. Tre uavhengige linser på SAMME lager (hybriden):
    ett papir (`paper_id`), ett dokument (`utkast_id`), eller de som ennå ikke er festet
    til noe dokument (`kun_lose`). Ingen av dem kopierer en rad — et sitat har én identitet
    uansett hvilken linse du ser det gjennom."""
    db = _db(db_path)
    hvor, args = [], []
    if paper_id:
        hvor.append("s.paper_id=?")
        args.append(paper_id)
    if utkast_id is not None:
        hvor.append("s.utkast_id=?")
        args.append(utkast_id)
    if kun_lose:
        hvor.append("s.utkast_id IS NULL")
    sql = _SITAT_FELT + (" WHERE " + " AND ".join(hvor) if hvor else "") + " ORDER BY s.opprettet DESC"
    rows = db.execute(sql, args).fetchall()
    db.close()
    return [{"id": r[0], "paper_id": r[1], "tekst": r[2], "kommentar": r[3],
             "opprettet": r[4], "paper_tittel": r[5], "paper_doi": r[6],
             "utkast_id": r[7], "paper_forfattere": r[8], "paper_tidsskrift": r[9],
             "paper_aar": r[10]} for r in rows]


def sitatbank(*, db_path: Path = DB) -> list[dict]:
    """Alle sitater gruppert på papiret de kom fra, nyeste papir først.

    Banken er lageret; grupperingen på papir er den ene som ALLTID er sann og aldri krever
    en embedding. Den semantiske relasjonen ligger i relaterte_sitater() ved siden av — de
    er bevisst atskilt, så en nede embedder gjør banken tregere å utforske, aldri utilgjengelig."""
    db = _db(db_path)
    rows = db.execute("""
        SELECT s.paper_id, p.tittel, p.forfattere, p.tidsskrift, p.aar, p.doi,
               count(*), max(s.opprettet)
        FROM sitater s JOIN papers p ON p.id = s.paper_id
        GROUP BY s.paper_id ORDER BY max(s.opprettet) DESC""").fetchall()
    db.close()
    return [{"paper_id": r[0], "tittel": r[1], "forfattere": r[2], "tidsskrift": r[3],
             "aar": r[4], "doi": r[5], "antall": r[6], "sist": r[7]} for r in rows]


def relaterte_sitater(paper_id: str, k: int = 5, *, db_path: Path = DB) -> list[dict]:
    """Papirer du har SITERT som ligger semantisk nær `paper_id` — «relasjonelle sitater».

    Dette er det ingen referansehåndterer gjør: Zotero, EndNote og Mendeley er arkivskap
    som ikke aner at to sitater handler om det samme. Vi har embeddingene, så nabolaget
    er gratis.

    Ingen avstandsTERSKEL, med vilje. En global klynging ville krevd en grense jeg måtte
    ha gjettet, og en ukalibrert terskel er nøyaktig felleklassen huset jakter på
    (konsepter/detektorfelle). k-nærmeste trenger ingen: den svarer alltid «de k nærmeste
    du faktisk har sitert», og avstanden følger med så DU kan se hvor nært det er.

    Filtrerer til papirer som HAR sitater — et nabolag av usiterte papirer er et
    søkeresultat, ikke en sitatbank."""
    db = _db(db_path)
    rad = db.execute("SELECT rowid FROM papers WHERE id=?", (paper_id,)).fetchone()
    if not rad:
        db.close()
        return []
    qvec = db.execute("SELECT embedding FROM paper_vec WHERE chunk_id=?", (rad[0],)).fetchone()
    if not qvec:
        db.close()
        return []   # papiret mangler vektor (ingen abstract, eller embedderen var nede)
    # Hentes bredt og filtreres på «har sitat» etterpå: vec0 kan ikke JOIN-e i MATCH-en,
    # og et smalt K ville gitt tomt svar så snart de nærmeste naboene er usiterte.
    rows = db.execute("""
        SELECT p.id, p.tittel, p.tidsskrift, p.aar, p.doi, p.kilde_url, v.distance,
               p.forfattere, p.abstract
        FROM paper_vec v JOIN papers p ON p.rowid = v.chunk_id
        WHERE v.embedding MATCH ? AND K = ? AND v.chunk_id != ?
        ORDER BY v.distance""", (qvec[0], 60, rad[0])).fetchall()
    siterte = {r[0] for r in db.execute("SELECT DISTINCT paper_id FROM sitater")}
    db.close()
    return _naboer_fra_rader([r for r in rows if r[0] in siterte], k)


def _naboer_fra_rader(rows, k: int, band: bool = True) -> list[dict]:
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
               # forfattere BÆRES videre (lagt til 2026-09-04). Den ble hentet hele tiden
               # — r[7] brukes til domene_naer-sjekken rett under — men falt ut av dicten.
               # Boilerplaten bygger referanselisten sin av nabo-dictene, og uten dette
               # sto hver relatert kilde som «(2022) Aquaculture.» uten forfatter. En
               # referanse uten forfatter er ikke en referanse.
               "forfattere": r[7],
               "domene_naer": domene_naer_tekst(f"{r[7]} {r[2]}"),
               "arts_naer": arts_naer_tekst(f"{r[1]} {r[8]}")}
              for r in rows]
    # band=False finnes for sti.py: banding sorterer FØR kuttet til k, så den kan skyve
    # den aller nærmeste naboen ut av settet når den er bånd-svak. For et menneske som
    # leser en liste er det riktig (domene-nære først). For en graf-traversering er det
    # en forvrengt kant-mengde — stien ville hoppet over den korteste kanten fordi
    # tidsskriftet ikke var norsk. Presentasjon og topologi er to ulike spørsmål.
    if band:
        naboer.sort(key=lambda n: (not n["domene_naer"], not n["arts_naer"], n["avstand"]))
    else:
        naboer.sort(key=lambda n: n["avstand"])
    return naboer[:k]


def lignende(paper_id: str, k: int = 5, *, band: bool = True, db_path: Path = DB) -> list[dict]:
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
    return _naboer_fra_rader(rows, k, band=band)


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


def logg_sok(query: str, treff: int, revisjon: dict, *, db_path: Path = DB) -> int:
    """Bokfører ett søk. Feiler ALDRI oppover: et revisjonsspor som kan velte selve søket
    ville vært en verre feil enn det manglende sporet det skulle forhindre."""
    try:
        db = _db(db_path)
        cur = db.execute(
            "INSERT INTO sok_logg(query, tid, treff, revisjon) VALUES (?,?,?,?)",
            (query, time.time(), treff, json.dumps(revisjon, ensure_ascii=False)))
        db.commit()
        db.close()
        return cur.lastrowid
    except Exception:
        logger.warning("kunne ikke bokføre søkerevisjon for «%s» — søket selv er upåvirket",
                       query, exc_info=True)
        return 0


def sok_historikk(k: int = 50, *, db_path: Path = DB) -> list[dict]:
    """Nyeste søk først, med hele revisjonen. Reproduserbarhetskravet (idébank #29
    §Kritikk punkt D) er at en litteraturgjennomgang MÅ kunne dokumentere eksakte
    spørringer og databaser i ettertid — det krever at sporet overlever økten."""
    db = _db(db_path)
    rader = db.execute("""SELECT id, query, tid, treff, revisjon FROM sok_logg
                          ORDER BY tid DESC LIMIT ?""", (k,)).fetchall()
    db.close()
    ut = []
    for r in rader:
        try:
            rev = json.loads(r[4])
        except json.JSONDecodeError:
            rev = {}  # en ødelagt rad skal ikke felle hele historikken
        ut.append({"id": r[0], "query": r[1], "tid": r[2], "treff": r[3], "revisjon": rev})
    return ut


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
    """Løsner sitatene FØR dokumentet slettes. Uten det ble de foreldreløse: utkast_id
    pekte på en rad som ikke fantes, så de forsvant fra «Løse» (som spør på IS NULL) OG
    fra «I dokumentet» (som spør på en id ingen kan velge) — synlige bare under «Alle».
    UI-ets egen slettedialog lover «sitatene blir liggende som løse», og det løftet må
    holdes her, i laget som eier invarianten, ikke av at frontend husker å rydde."""
    db = _db(db_path)
    db.execute("UPDATE sitater SET utkast_id=NULL WHERE utkast_id=?", (utkast_id,))
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
