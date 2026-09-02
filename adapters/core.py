"""adapters/core.py — CORE: institusjonelle open-access-repositorier (200M+ dok).

Live-verifisert 2026-09-02: virker UTEN nøkkel (rate-limitert, standard sidestørrelse),
og traff en NTNU-mastergrad («Nephrocalcinosis in juvenile farmed Atlantic salmon»,
NTNU Open) MED fullt bilingvalt (norsk+engelsk) abstract — direkte om miljøfaktorer
(karmiljø) og nefrokalsinose hos oppdrettslaks. Dette er nøyaktig den klassen norsk
gråtekst/institusjonsarkiv-materiale Europe PMC aldri indekserer (masteroppgaver/ph.d.-
avhandlinger er sjelden i PubMed/MEDLINE). Retter en feilkonklusjon fra tidligere samme
kveld (`oai_harvest.py`s notat om at CORE er dødt gjaldt kun den gamle OAI-PMH-veien —
v3 REST-søket er en annen, fungerende vei). Se prosjekt/idebank/29-forskningssok-rammeverk.

⚠ Fulltekst er IKKE tilgjengelig via gratis API (`fullText: "Not available for public API
users."` i rå-svaret) — kun abstract + metadata + en browse-lenke (`core.ac.uk/works/{id}`)
der et menneske kan finne selve PDF-en. `open_access=True` er en RIMELIG ANTAKELSE, ikke
et felt CORE selv returnerer her: CORE aggregerer PER DEFINISJON kun open-access-
repositorier (det er hele prosjektets mandat), så et treff HERFRA er strukturelt OA —
men det er en påstand om KILDEN, ikke en verifisert per-dokument-flagg slik Europe PMCs
`isOpenAccess` er. Dokumentert her, ikke skjult.

ADR-004-disiplin: spørretid + TTL-cache, ingen crawler.
"""
import json
import re
import sqlite3
import time
from pathlib import Path

import httpx

from schemas import PaperDossier

BASE = "https://api.core.ac.uk/v3/search/works"
UA = "lauvasdata-research (kontakt@lauvasdata.no)"
DB = Path(__file__).resolve().parent.parent / "cache.db"
TTL_SEKUNDER = 24 * 3600


def _db(db_path: Path = DB) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE IF NOT EXISTS core_cache(
        query TEXT PRIMARY KEY, hentet_ved REAL, respons TEXT)""")
    return db


def _rens(tekst: str) -> str:
    return re.sub(r"\s+", " ", tekst or "").strip()


def sok(query: str, limit: int = 10, *, tving_fersk: bool = False,
        db_path: Path = DB) -> list[PaperDossier]:
    """query → kandidat-papirer fra institusjonelle OA-repositorier, TTL-cachet.
    Samme ærlighets-disiplin som europe_pmc.py: en kilde-feil raiser, blir aldri en
    stille tom liste som kunne forveksles med et ekte fravær av treff."""
    key = f"{query.strip().lower()}::{limit}"
    db = _db(db_path)
    if not tving_fersk:
        rad = db.execute(
            "SELECT hentet_ved, respons FROM core_cache WHERE query=?", (key,)).fetchone()
        if rad and (time.time() - rad[0]) < TTL_SEKUNDER:
            db.close()
            return _parse(json.loads(rad[1]))
    try:
        r = httpx.get(BASE, params={"q": query, "limit": limit},
                       headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
        r.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        db.close()
        raise RuntimeError(f"CORE utilgjengelig: {e}") from e
    data = r.json()
    db.execute("INSERT OR REPLACE INTO core_cache(query, hentet_ved, respons) VALUES (?,?,?)",
               (key, time.time(), json.dumps(data)))
    db.commit()
    db.close()
    return _parse(data)


def _parse(data: dict) -> list[PaperDossier]:
    ut = []
    for r in data.get("results", []):
        forfattere = "; ".join(a.get("name", "") for a in (r.get("authors") or []) if a.get("name"))
        leverandorer = ", ".join(p.get("name", "") for p in (r.get("dataProviders") or []))
        lenke = next((lk["url"] for lk in (r.get("links") or []) if lk.get("type") == "display"), None)
        core_id = r.get("id")
        ut.append(PaperDossier(
            pmid=None,
            doi=r.get("doi"),
            tittel=_rens(r.get("title", "")),
            forfattere=forfattere,
            tidsskrift=leverandorer or (r.get("publisher") or ""),
            aar=r.get("yearPublished"),
            abstract=_rens(r.get("abstract", "")),
            siteringstall=r.get("citationCount"),
            open_access=True,  # strukturell antakelse — se moduldocstring
            kilde_url=lenke or f"https://core.ac.uk/works/{core_id}",
            kilde="core",
            kilde_kode="CORE",
        ))
    return ut
