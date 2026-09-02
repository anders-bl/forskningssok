"""adapters/europe_pmc.py — Europe PMC (EU/EMBL-EBI) spørretid-søk, TTL-cachet.

Primær kilde for prosjekt/idebank/28-nefrokalsinose-litteratursok (v1). Ingen nøkkel
nødvendig. Live-verifisert 2026-09-02: «nephrocalcinosis salmon» → 201 treff, og
`citedByCount` + `isOpenAccess` ligger DIREKTE i core-resultatet — den planlagte
OpenAlex-berikelsen («andreklipp» i spec'en) er dermed IKKE nødvendig for siteringstall
i v1, Europe PMC gir det gratis i samme kall.

ADR-004-disiplin: spørretid + TTL-cache, ingen crawler, ingen full korpus-indeksering.
En feil fra kilden skal ALDRI se ut som «ingen forskning finnes» — samme lærdom som
bøker/hoster.py sin `_arxiv_get` (struping så ut som lisensgate; her ville en feil se ut
som et ekte, ærlig fravær). Derfor: RuntimeError på feil, aldri en stille tom liste.
"""
import json
import re
import sqlite3
import time
from pathlib import Path

import httpx

from schemas import PaperDossier

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
UA = "Mozilla/5.0 (research; lauvasdata; kontakt@lauvasdata.no)"
DB = Path(__file__).resolve().parent.parent / "cache.db"
TTL_SEKUNDER = 24 * 3600  # papirmetadata endrer seg sjelden — 1 dags TTL er rikelig


def _db(db_path: Path = DB) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE IF NOT EXISTS query_cache(
        query TEXT PRIMARY KEY, hentet_ved REAL, respons TEXT)""")
    return db


def _normaliser(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


def sok(query: str, page_size: int = 20, *, tving_fersk: bool = False,
        db_path: Path = DB) -> list[PaperDossier]:
    """query → kandidat-papirer, TTL-cachet på normalisert spørring+sidestørrelse."""
    key = f"{_normaliser(query)}::{page_size}"
    db = _db(db_path)
    if not tving_fersk:
        rad = db.execute(
            "SELECT hentet_ved, respons FROM query_cache WHERE query=?", (key,)).fetchone()
        if rad and (time.time() - rad[0]) < TTL_SEKUNDER:
            db.close()
            return _parse(json.loads(rad[1]))
    try:
        r = httpx.get(BASE, params={
            "query": query, "format": "json", "resultType": "core", "pageSize": page_size,
        }, headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        db.close()
        raise RuntimeError(f"Europe PMC utilgjengelig: {e}") from e
    data = r.json()
    db.execute("INSERT OR REPLACE INTO query_cache(query, hentet_ved, respons) VALUES (?,?,?)",
               (key, time.time(), json.dumps(data)))
    db.commit()
    db.close()
    return _parse(data)


def _parse(data: dict) -> list[PaperDossier]:
    ut = []
    for r in data.get("resultList", {}).get("result", []):
        pmid = r.get("pmid")
        aar_raw = r.get("pubYear") or ""
        ut.append(PaperDossier(
            pmid=pmid,
            doi=r.get("doi"),
            tittel=re.sub(r"\s+", " ", r.get("title", "")).strip(),
            forfattere=r.get("authorString", ""),
            tidsskrift=((r.get("journalInfo") or {}).get("journal") or {}).get("title", ""),
            aar=int(aar_raw) if aar_raw.isdigit() else None,
            abstract=r.get("abstractText", ""),
            siteringstall=r.get("citedByCount"),
            open_access=(r.get("isOpenAccess") == "Y"),
            kilde_url=f"https://europepmc.org/article/{r.get('source', 'MED')}/{pmid or r.get('id', '')}",
        ))
    return ut
