#!/usr/bin/env python3
"""bank_bakgrunn.py — bok-banken (bøker/boker.db) som BAKGRUNN-lag i syntese_fortelling.

Rollen er den biologibank-siden beskriver (prosjekt/forskningssok-smartsyntese-for-ulven,
research-utkast/biologibank-marinebiologi): cachen er FORGRUNN (de spesifikke papirene for
dette søket), banken er kuratert, varig BAKGRUNN. Syntesen kan da hente bredere kontekst
uten at bakgrunnen får se ut som direkte evidens: hver bankpost bærer id `bank:<chunk_id>`
og går gjennom samme verifiser_kilder()-gate som cachede papirer.

TO KILDER, samme utdata:
  · boker.db (1,5 GB, bge-m3) på Anders' Mac. Hele banken filtreres mot profilens
    bank_proveniens-allowlist og embeddes med bge-m3 (ikke bank._hus_embed(), som bytter til
    mistral-embed når AI_PROXY_URL er satt, et annet vektorrom). Kalibrerte bånd.
  · bank_utdrag.db (se bank_utdrag.py): et lite utdrag embeddet på nytt med den embedderen
    som søker, så prod kan bruke det. bge-m3-utdraget bruker samme bånd; mistral-embed
    failes lukket inntil en relevansterskel er målt.
I prod (AI_PROXY_URL satt) brukes bare utdraget. Lokalt foretrekkes den allowlistede banken.
Modulen sier «ikke tilgjengelig» med en årsak når ingen av dem kan brukes. Aldri en stille
tom liste.

Avstanden er sqlite-vec L2 mot bge-m3 (LAVERE = bedre dekket). Bånd og terskler importeres
fra bøker/bok_kalibrering.py — ikke kopiert (tallene drev fire kopier før 2026-07-17).
Poster i MØRKT-båndet slippes ikke inn (boker.db-veien): en bakgrunn som ikke dekker emnet
er støy.
"""
import os
import re
import sqlite3
import sys
from pathlib import Path

HJEM = Path.home() / "prosjekter"
BOKER_DB_ENV = "BOKBANK_DB"
STANDARD_DB = HJEM / "bøker" / "boker.db"
MAKS_BAKGRUNN = 8
# Ett bakgrunns-chunk er en fagtekstbit, ikke et abstract. Kappet så 8 stykker ikke
# sprenger konteksten (samme hensyn som MAKS_KILDER i syntese_fortelling.py).
MAKS_TEGN = 700
# Live-måling 2026-09-25: de fem nærmeste chunkene for nefrokalsinose var alle fra ÉN artikkel.
# Bakgrunn skal være bredde, så samme bok teller maks to ganger.
MAKS_PER_BOK = 2

_PMC = re.compile(r"^epmc:[^:]+:(PMC\d+)")


def _kalibrering():
    sys.path.insert(0, str(HJEM / "bøker"))
    import bok_kalibrering  # noqa: PLC0415
    return bok_kalibrering


def _bge_m3_embed():
    """bge-m3 via husets Ollama-vei. Bevisst IKKE bank._hus_embed(): den bytter til
    mistral-embed når AI_PROXY_URL er satt, og det er feil vektorrom for boker.db."""
    sys.path.insert(0, str(HJEM / "silverbullet" / "ops"))
    from semantisk_sok import embed  # noqa: PLC0415
    return embed


def boker_db_sti(db_path: Path | str | None = None) -> Path | None:
    kandidat = db_path or os.environ.get(BOKER_DB_ENV) or STANDARD_DB
    p = Path(kandidat)
    return p if p.is_file() else None


def _kilde_url(proveniens: str | None) -> str | None:
    """Ekte lenke der proveniensen bærer en id vi kan gjøre om til en; ellers ingen.
    Aldri en påstått URL for en kilde vi ikke kan adressere."""
    m = _PMC.match(proveniens or "")
    return f"https://pmc.ncbi.nlm.nih.gov/articles/{m.group(1)}/" if m else None


def utdrag_finnes() -> bool:
    import bank_utdrag
    return bank_utdrag.finnes()


def _bank_proveniens_prefikser() -> tuple[str, ...]:
    """Banken er større enn det denne profilen har lov til å sitere. Bruk samme
    proveniens-allowlist som eksportveien; manglende allowlist er fail-closed."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import domeneprofil  # noqa: PLC0415
    prefikser = tuple(domeneprofil.PROFIL.get("bank_proveniens", ()))
    if not prefikser:
        raise ValueError("domeneprofilen mangler bank_proveniens; bakgrunnsbanken er stengt")
    return prefikser


def _rader_boker(sti: Path, emne: str, k: int, embed_fn, kal, prefikser) -> list[tuple]:
    import sqlite_vec  # noqa: PLC0415
    embed = embed_fn or _bge_m3_embed()
    db = sqlite3.connect(f"file:{sti}?mode=ro", uri=True)
    try:
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        qvec = embed([emne])[0]
        filter_sql = " OR ".join(
            "substr(bc.proveniens, 1, length(?)) = ?" for _ in prefikser)
        filter_args = tuple(arg for p in prefikser for arg in (p, p))
        total_count = db.execute(
            "SELECT count(*) FROM book_embeddings_v2"
        ).fetchone()[0]
        tillat_count = db.execute(
            f"""SELECT count(*) FROM book_embeddings_v2 be
                JOIN book_chunks bc ON bc.id = be.chunk_id WHERE {filter_sql}""",
            filter_args,
        ).fetchone()[0]
        if not tillat_count or not total_count:
            return []

        # Etter terskel, proveniens-filter og per-bok-tak kan topp-k*6 fortsatt bestå
        # av én bok eller MØRKT-treff. sqlite-vec bruker K før JOIN-filteret, så taket
        # må være hele vektorindeksen, ikke bare antallet tillatte provenienser.
        # Øk K til vi faktisk har k brukbare treff eller har sett hele indeksen.
        limit = min(total_count, max(k * 6, k))
        qblob = sqlite_vec.serialize_float32(qvec)
        while True:
            rader = db.execute(
                f"""SELECT bc.id, bc.bok, bc.samling, bc.heading, bc.chunk_text,
                          bc.proveniens, be.distance
                   FROM book_embeddings_v2 be JOIN book_chunks bc ON bc.id = be.chunk_id
                   WHERE be.embedding MATCH ? AND K = ? AND ({filter_sql})
                   ORDER BY be.distance""",
                (qblob, limit, *filter_args),
            ).fetchall()
            antall_brukbare = 0
            per_bok: dict[str, int] = {}
            for row in rader:
                _cid, bok, _samling, _heading, _tekst, _prov, avstand = row
                if avstand >= kal.MORKT or per_bok.get(bok, 0) >= MAKS_PER_BOK:
                    continue
                per_bok[bok] = per_bok.get(bok, 0) + 1
                antall_brukbare += 1
                if antall_brukbare >= k:
                    break
            if antall_brukbare >= k or limit >= total_count:
                return rader
            limit = min(total_count, limit * 2)
    finally:
        db.close()


def hent_bakgrunn(emne: str, k: int = MAKS_BAKGRUNN, *, db_path: Path | str | None = None,
                  embed_fn=None, utdrag_db: Path | None = None) -> tuple[list[dict], dict]:
    """Returnerer (poster, status). `status` er alltid fylt ut:
    {"tilgjengelig": bool, "kilde": "boker.db"|"utdrag"|None, "arsak": str, "antall": int,
     "beste_avstand": float | None, "forkastet_morkt": int}. Poster har samme nøkler som
     cachede papirer, pluss kilde='bok-bank', samling, bank_avstand og bank_band."""
    status = {"tilgjengelig": False, "kilde": None, "arsak": "", "antall": 0,
              "beste_avstand": None, "forkastet_morkt": 0}
    prod = bool(os.environ.get("AI_PROXY_URL"))
    boker = None if prod and db_path is None else boker_db_sti(db_path)
    bruk_utdrag = boker is None
    if bruk_utdrag:
        import bank_utdrag  # noqa: PLC0415
        if not bank_utdrag.finnes(utdrag_db):
            status["arsak"] = (f"ingen bank tilgjengelig: fant ikke boker.db (sett {BOKER_DB_ENV})"
                               " og utdraget er ikke bygget (python bank_utdrag.py bygg)")
            return [], status
    try:
        # bge-m3-utdraget deler boker.db sitt vektorrom og kan bruke samme kalibrering.
        # mistral-embed har ingen validert mørketerskel: ikke la vilkårlig nærmeste treff
        # fremstå som faglig bakgrunn før en slik terskel er målt.
        kal = (_kalibrering() if not bruk_utdrag or bank_utdrag.embed_modell() == "bge-m3"
               else None)
        if bruk_utdrag:
            if kal is None:
                status["kilde"] = "utdrag"
                status["tilgjengelig"] = True
                status["arsak"] = (
                    "bakgrunnsutdraget mangler kalibrert relevansterskel for mistral-embed; "
                    "syntesen fortsetter uten bankbakgrunn")
                return [], status
            rader, arsak = bank_utdrag.sok(emne, k * 6, db_path=utdrag_db, embed_fn=embed_fn)
            if arsak:
                status["arsak"] = arsak
                return [], status
            prefikser = ()
        else:
            prefikser = _bank_proveniens_prefikser()
            rader = _rader_boker(boker, emne, k, embed_fn, kal, prefikser)
    except ImportError as e:
        status["arsak"] = f"mangler bge-m3-embedder eller kalibrering: {e.name or e}"
        return [], status
    except Exception as e:  # noqa: BLE001 — en bank som svikter skal synes, ikke stoppe syntesen
        status["arsak"] = f"banken kunne ikke søkes: {type(e).__name__}: {e}"
        return [], status

    status["tilgjengelig"] = True
    status["kilde"] = "utdrag" if bruk_utdrag else "boker.db"
    poster: list[dict] = []
    per_bok: dict[str, int] = {}
    for cid, bok, samling, heading, tekst, prov, avstand in rader:
        if kal is not None and avstand >= kal.MORKT:
            status["forkastet_morkt"] += 1
            continue
        if len(poster) >= k:
            break
        if per_bok.get(bok, 0) >= MAKS_PER_BOK:
            continue
        per_bok[bok] = per_bok.get(bok, 0) + 1
        poster.append({
            "id": f"bank:{cid}",
            "tittel": f"{bok}" + (f" › {heading}" if heading else ""),
            "forfattere": f"bok-bank/{samling}",
            "aar": "u.å.",
            "tidsskrift": "",
            "abstract": (tekst or "")[:MAKS_TEGN],
            "doi": None,
            "kilde_url": _kilde_url(prov),
            "kilde": "bok-bank",
            "samling": samling,
            "bank_avstand": round(float(avstand), 4),
            "bank_band": kal.band(avstand) if kal else None,
        })
    status["antall"] = len(poster)
    status["beste_avstand"] = round(float(rader[0][6]), 4) if rader else None
    if not poster:
        status["arsak"] = "banken dekker ikke emnet (alle treff i MØRKT-båndet)" if kal else "ingen treff i utdraget"
    return poster, status
