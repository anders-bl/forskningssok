#!/usr/bin/env python3
"""bank_bakgrunn.py — bok-banken (bøker/boker.db) som BAKGRUNN-lag i syntese_fortelling.

Rollen er den biologibank-siden beskriver (prosjekt/forskningssok-smartsyntese-for-ulven,
research-utkast/biologibank-marinebiologi): cachen er FORGRUNN (de spesifikke papirene for
dette søket), banken er kuratert, varig BAKGRUNN. Syntesen kan da hente bredere kontekst
uten at bakgrunnen får se ut som direkte evidens: hver bankpost bærer id `bank:<chunk_id>`
og går gjennom samme verifiser_kilder()-gate som cachede papirer.

VALGFRITT OG LOKALT. boker.db (1,5 GB, bge-m3-vektorer) bor på Anders' Mac, ikke i
prod-containeren. Prod-embedding (bank._hus_embed med AI_PROXY_URL) er mistral-embed, et
ANNET vektorrom enn bankens bge-m3 — å søke banken med det ville gitt stille søppel
(samme feilklasse som embed_renhet.py vokter). Denne modulen embedder derfor ALLTID med
bge-m3 via husets Ollama-vei, og sier «ikke tilgjengelig» med en årsak når banken eller den
embedderen mangler. Aldri en stille tom liste.

Avstanden er sqlite-vec L2 mot bge-m3 (LAVERE = bedre dekket). Bånd og terskler importeres
fra bøker/bok_kalibrering.py — ikke kopiert (tallene drev fire kopier før 2026-07-17).
Poster i MØRKT-båndet slippes ikke inn: en bakgrunn som ikke dekker emnet er støy.
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


def hent_bakgrunn(emne: str, k: int = MAKS_BAKGRUNN, *, db_path: Path | str | None = None,
                  embed_fn=None) -> tuple[list[dict], dict]:
    """Returnerer (poster, status). `status` er alltid fylt ut:
    {"tilgjengelig": bool, "arsak": str, "antall": int, "beste_avstand": float | None,
     "forkastet_morkt": int}. Poster har samme nøkler som cachede papirer, pluss
    kilde='bok-bank', samling, bank_avstand og bank_band."""
    status = {"tilgjengelig": False, "arsak": "", "antall": 0,
              "beste_avstand": None, "forkastet_morkt": 0}
    sti = boker_db_sti(db_path)
    if sti is None:
        status["arsak"] = f"fant ikke boker.db (sett {BOKER_DB_ENV})"
        return [], status
    try:
        kal = _kalibrering()
        embed = embed_fn or _bge_m3_embed()
    except ImportError as e:
        status["arsak"] = f"mangler bge-m3-embedder eller kalibrering: {e.name or e}"
        return [], status

    import sqlite_vec  # noqa: PLC0415
    db = sqlite3.connect(f"file:{sti}?mode=ro", uri=True)
    try:
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        qvec = embed([emne])[0]
        rader = db.execute(
            """SELECT bc.id, bc.bok, bc.samling, bc.heading, bc.chunk_text, bc.chunk_index,
                      bc.proveniens, be.distance
               FROM book_embeddings_v2 be JOIN book_chunks bc ON bc.id = be.chunk_id
               WHERE be.embedding MATCH ? AND K = ? ORDER BY be.distance""",
            (sqlite_vec.serialize_float32(qvec), k * 6)).fetchall()
    except Exception as e:  # noqa: BLE001 — en bank som svikter skal synes, ikke stoppe syntesen
        status["arsak"] = f"banken kunne ikke søkes: {type(e).__name__}: {e}"
        return [], status
    finally:
        db.close()

    status["tilgjengelig"] = True
    poster: list[dict] = []
    per_bok: dict[str, int] = {}
    for cid, bok, samling, heading, tekst, idx, prov, avstand in rader:
        if avstand >= kal.MORKT:
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
            "bank_band": kal.band(avstand),
        })
    status["antall"] = len(poster)
    status["beste_avstand"] = round(float(rader[0][7]), 4) if rader else None
    if not poster:
        status["arsak"] = "banken dekker ikke emnet (alle treff i MØRKT-båndet)"
    return poster, status
