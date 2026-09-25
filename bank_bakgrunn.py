#!/usr/bin/env python3
"""bank_bakgrunn.py — bok-banken (bøker/boker.db) som BAKGRUNN-lag i syntese_fortelling.

Rollen er den biologibank-siden beskriver (prosjekt/forskningssok-smartsyntese-for-ulven,
research-utkast/biologibank-marinebiologi): cachen er FORGRUNN (de spesifikke papirene for
dette søket), banken er kuratert, varig BAKGRUNN. Syntesen kan da hente bredere kontekst
uten at bakgrunnen får se ut som direkte evidens: hver bankpost bærer id `bank:<chunk_id>`
og går gjennom samme verifiser_kilder()-gate som cachede papirer.

TO KILDER, samme utdata:
  · boker.db (1,5 GB, bge-m3) på Anders' Mac. Embedder ALLTID med bge-m3 (ikke
    bank._hus_embed(), som bytter til mistral-embed når AI_PROXY_URL er satt, et annet
    vektorrom: stille søppel, samme feilklasse som embed_renhet.py vokter). Kalibrerte bånd.
  · bank_utdrag.db (se bank_utdrag.py): et lite utdrag embeddet på nytt med den embedderen
    som søker, så prod kan bruke det. Ingen kalibrerte bånd for mistral-embed, så bare
    rangering + per-bok-tak, ingen MØRKT-terskel.
I prod (AI_PROXY_URL satt) brukes bare utdraget. Lokalt foretrekkes hele banken.
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


def _rader_boker(sti: Path, emne: str, k: int, embed_fn) -> list[tuple]:
    import sqlite_vec  # noqa: PLC0415
    embed = embed_fn or _bge_m3_embed()
    db = sqlite3.connect(f"file:{sti}?mode=ro", uri=True)
    try:
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        qvec = embed([emne])[0]
        return db.execute(
            """SELECT bc.id, bc.bok, bc.samling, bc.heading, bc.chunk_text,
                      bc.proveniens, be.distance
               FROM book_embeddings_v2 be JOIN book_chunks bc ON bc.id = be.chunk_id
               WHERE be.embedding MATCH ? AND K = ? ORDER BY be.distance""",
            (sqlite_vec.serialize_float32(qvec), k * 6)).fetchall()
    finally:
        db.close()


def hent_bakgrunn(emne: str, k: int = MAKS_BAKGRUNN, *, db_path: Path | str | None = None,
                  embed_fn=None, utdrag_db: Path | None = None) -> tuple[list[dict], dict]:
    """Returnerer (poster, status). `status` er alltid fylt ut:
    {"tilgjengelig": bool, "kilde": "boker.db"|"utdrag"|None, "arsak": str, "antall": int,
     "beste_avstand": float | None, "forkastet_morkt": int}. Poster har samme nøkler som
    cachede papirer, pluss kilde='bok-bank', samling, bank_avstand og bank_band
    (None for utdraget: ingen kalibrerte bånd for mistral-embed)."""
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
        kal = None if bruk_utdrag else _kalibrering()
        if bruk_utdrag:
            rader, arsak = bank_utdrag.sok(emne, k * 6, db_path=utdrag_db, embed_fn=embed_fn)
            if arsak:
                status["arsak"] = arsak
                return [], status
        else:
            rader = _rader_boker(boker, emne, k, embed_fn)
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
