"""EPO Open Patent Services adapter for bounded, on-demand bibliographic search.

OPS publishes XML bibliographic records and exposes title/abstract CQL search.
This first connector intentionally stops at search results: a keyword match is
not a citation to a paper, and it must never be presented as a legal or scientific
conclusion. OPS requires registered OAuth credentials; no anonymous fallback exists.
"""
import json
import os
import re
import sqlite3
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from paths import DB

TOKEN_URL = "https://ops.epo.org/3.2/auth/accesstoken"
BASE = "https://ops.epo.org/rest-services"
UA = "lauvasdata-research (mailto:kontakt@lauvasdata.no)"
TTL_SEKUNDER = 24 * 3600
MAKS_RESULTATER = 20
_TOKEN_LOCK = threading.Lock()
_token: str | None = None
_token_utloper = 0.0
_SEARCH_LOCK = threading.Lock()
_siste_sok = 0.0


def tilgjengelig() -> dict:
    """Report local configuration without reading or returning credential values."""
    konfigurert = bool(os.environ.get("EPO_OPS_KEY") and os.environ.get("EPO_OPS_SECRET"))
    return {"provider": "epo_ops", "configured": konfigurert,
            "status": "ready" if konfigurert else "unconfigured"}


def _db(db_path: Path = DB) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE IF NOT EXISTS epo_ops_cache(
        key TEXT PRIMARY KEY, hentet_ved REAL, respons TEXT)""")
    return db


def _cql(query: str) -> str:
    ordliste = re.findall(r"[^\W_]+", query, flags=re.UNICODE)[:8]
    if not ordliste:
        raise ValueError("Søket må inneholde minst ett ord")
    return 'ta all "' + " ".join(ordliste) + '"'


def _tilgangstoken() -> str:
    global _token, _token_utloper
    with _TOKEN_LOCK:
        if _token and time.monotonic() < _token_utloper:
            return _token
        key = os.environ.get("EPO_OPS_KEY", "")
        secret = os.environ.get("EPO_OPS_SECRET", "")
        if not key or not secret:
            raise RuntimeError("EPO OPS er ikke konfigurert")
        try:
            response = httpx.post(
                TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=(key, secret),
                headers={"User-Agent": UA},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            raise RuntimeError(f"EPO OPS OAuth utilgjengelig: {exc}") from exc
        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("EPO OPS ga ikke en tilgangstoken")
        try:
            levetid = max(60, int(data.get("expires_in", 1200)))
        except (TypeError, ValueError):
            levetid = 1200
        _token = token
        _token_utloper = time.monotonic() + levetid - 30
        return token


def _vent_pa_sokerate() -> None:
    global _siste_sok
    with _SEARCH_LOCK:
        vent = 6.0 - (time.monotonic() - _siste_sok)
        if vent > 0:
            time.sleep(vent)
        _siste_sok = time.monotonic()


def _tekst(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    tekst = " ".join(part.strip() for part in element.itertext() if part.strip())
    return tekst or None


def _lokalnavn(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse(xml_text: str) -> tuple[list[dict], int | None]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RuntimeError("EPO OPS returnerte ugyldig XML") from exc
    total_raw = next((el.attrib.get("total-result-count") for el in root.iter()
                      if _lokalnavn(el.tag) == "biblio-search"), None)
    try:
        total = int(total_raw) if total_raw is not None else None
    except ValueError:
        total = None
    records: list[dict] = []
    for record in root.iter():
        if _lokalnavn(record.tag) != "exchange-document":
            continue
        country = record.attrib.get("country")
        number = record.attrib.get("doc-number")
        kind = record.attrib.get("kind")
        if not country or not number:
            continue
        biblio = next((el for el in record if _lokalnavn(el.tag) == "bibliographic-data"), None)
        if biblio is None:
            continue
        title_nodes = [el for el in biblio.iter() if _lokalnavn(el.tag) == "invention-title"]
        title = next((_tekst(el) for el in title_nodes if el.attrib.get("lang") == "en"), None)
        title = title or (_tekst(title_nodes[0]) if title_nodes else None)
        pubref = next((el for el in biblio.iter() if _lokalnavn(el.tag) == "publication-reference"), None)
        date = None
        if pubref is not None:
            for el in pubref.iter():
                if _lokalnavn(el.tag) == "date" and el.text:
                    date = el.text.strip()
                    break
        family_id = record.attrib.get("family-id")
        publication = f"{country}{number}{kind or ''}"
        records.append({
            "id": f"epo:{publication}",
            "provider": "epo_ops",
            "publication_number": publication,
            "country": country,
            "kind": kind,
            "family_id": family_id,
            "title": title,
            "publication_date": date,
            "url": f"https://worldwide.espacenet.com/patent/search?q=pn%3D{publication}",
            "relation": "keyword_match",
        })
    return records, total


def sok(query: str, limit: int = 10, *, db_path: Path = DB) -> dict:
    query = query.strip()
    if not query:
        raise ValueError("Søketekst mangler")
    if not 1 <= limit <= MAKS_RESULTATER:
        raise ValueError(f"limit må være mellom 1 og {MAKS_RESULTATER}")
    cql = _cql(query)
    readiness = tilgjengelig()
    if not readiness["configured"]:
        return {**readiness, "query": query, "cql": cql, "records": [],
                "total_available": None, "retrieved": 0, "truncated": None}

    cache_key = f"search::{cql}::{limit}"
    db = _db(db_path)
    row = db.execute("SELECT hentet_ved, respons FROM epo_ops_cache WHERE key=?", (cache_key,)).fetchone()
    if row and time.time() - row[0] < TTL_SEKUNDER:
        db.close()
        return json.loads(row[1])
    try:
        _vent_pa_sokerate()
        response = httpx.get(
            f"{BASE}/published-data/search/biblio",
            params={"q": cql},
            headers={"Authorization": f"Bearer {_tilgangstoken()}",
                     "Accept": "application/exchange+xml",
                     "X-OPS-Range": f"1-{limit}", "User-Agent": UA},
            timeout=30,
        )
        response.raise_for_status()
        records, total = _parse(response.text)
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        db.close()
        raise RuntimeError(f"EPO OPS-søk utilgjengelig: {exc}") from exc
    except RuntimeError:
        db.close()
        raise
    result = {
        "provider": "epo_ops", "status": "ok", "query": query, "cql": cql,
        "records": records, "total_available": total, "retrieved": len(records),
        "truncated": total is None or total > len(records),
        "coverage": "EPO OPS bibliografisk tittel/abstract-søk; ikke fulltekst",
    }
    db.execute("INSERT OR REPLACE INTO epo_ops_cache(key, hentet_ved, respons) VALUES (?,?,?)",
               (cache_key, time.time(), json.dumps(result)))
    db.commit()
    db.close()
    return result
