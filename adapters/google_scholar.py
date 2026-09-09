"""google_scholar.py — Google Scholar via SerpAPI (offisielt API).

Google Scholar har INTET offisielt API — kun scraping (brudd på ToS) eller
betalte tjenester. SerpAPI er den mest pålitelige:
  - https://serpapi.com/ (gratis: 100 søk/mnd, betalt: $50/mnd for 5000)
  - Returnerer: tittel, forfattere, år, sitert_av, pdf_lenke, abstract
  - Samme format som andre adapters (PaperDossier)

Bruk:
  from adapters.google_scholar import sok
  resultat = sok("salmon liver ultrasound", limit=10)

Miljøvariabel:
  SERPAPI_KEY=hent fra https://serpapi.com/manage-api-key
"""
import os
import time
from pathlib import Path
from datetime import datetime, timezone

import httpx
import sqlite3

from paths import DB
from schemas import PaperDossier

BASE = "https://serpapi.com/search"
TTL_SEKUNDER = 7 * 24 * 3600  # 1 uke cache for Scholar


def _db(db_path: Path = DB) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE IF NOT EXISTS scholar_cache(
        query TEXT PRIMARY KEY, hentet_ved REAL, respons TEXT)""")
    return db


def _headers() -> dict:
    """SerpAPI bruker query-param `api_key`, ikke header."""
    return {"User-Agent": "lauvasdata-research (kontakt@lauvasdata.no)"}


def sok(query: str, limit: int = 10, *, tving_fersk: bool = False,
        db_path: Path = DB) -> list[dict]:
    """Google Scholar søk via SerpAPI → PaperDossier format.
    
    Returnerer papirer med:
      - tittel, forfattere, aar, abstract (hvis tilgjengelig)
      - doi (hvis funnet), kilde_url (SerpAPI lenke)
      - kilde="Google Scholar"
      - embedding=None (må hentes separat)
    
    Rate limits:
      - Gratis: 100 søk/mnd (~3/dag)
      - Betalt: 5000/mnd (~160/dag)
      - Ingen per-time limit (ulikt Semantic Scholar)
    """
    key = f"{query.strip().lower()}::{limit}"
    db = _db(db_path)
    
    # Sjekk cache
    if not tving_fersk:
        rad = db.execute(
            "SELECT hentet_ved, respons FROM scholar_cache WHERE query=?", (key,)).fetchone()
        if rad and (time.time() - rad[0]) < TTL_SEKUNDER:
            db.close()
            return _parse(__import__('json').loads(rad[1]))
    
    # Hent fra SerpAPI
    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        db.close()
        raise RuntimeError(
            "SERPAPI_KEY mangler. Hent fra https://serpapi.com/manage-api-key\n"
            "Gratis: 100 søk/mnd · Betalt: $50/mnd for 5000")
    
    params = {
        "engine": "google_scholar",
        "q": query,
        "api_key": api_key,
        "num": limit,
        "hl": "en",  # Engelsk grensesnitt
    }
    
    try:
        r = httpx.get(BASE, params=params, headers=_headers(), timeout=30)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise RuntimeError("Ugyldig SERPAPI_KEY") from e
        elif e.response.status_code == 429:
            raise RuntimeError("SerpAPI rate-limitet (gratis: 100/mnd)") from e
        raise
    except httpx.TimeoutException:
        raise RuntimeError("SerpAPI timeout")
    
    # Cache svaret
    papirer = _parse(data)
    db.execute(
        "INSERT OR REPLACE INTO scholar_cache(query, hentet_ved, respons) VALUES (?,?,?)",
        (key, time.time(), __import__('json').dumps(data)))
    db.commit()
    db.close()
    
    return papirer


def _parse(data: dict) -> list[dict]:
    """SerpAPI JSON → liste av PaperDossier (som dict)."""
    papirer = []
    
    for item in data.get("organic_results", []):
        # Ekstraher metadata
        tittel = item.get("title", "")
        resultat_snippet = item.get("snippet", "")
        
        # Forfattere
        forfattere = []
        if "authors" in item:
            forfattere = [a.get("name", "") for a in item["authors"]]
        elif "publication_info" in item:
            pub_info = item["publication_info"]
            if "summary" in pub_info:
                # "J Hansen et al. · 2024" → ekstraher navn
                tekst = pub_info["summary"]
                if "·" in tekst:
                    forfatter_del = tekst.split("·")[0].strip()
                    forfattere = [f.strip() for f in forfatter_del.replace("et al.", "").split(",")]
        
        # År
        aar = None
        if "publication_info" in item:
            pub_info = item["publication_info"]
            if "year" in pub_info:
                aar = pub_info["year"]
            elif "summary" in pub_info:
                import re
                match = re.search(r'\b(19|20)\d{2}\b', pub_info.get("summary", ""))
                if match:
                    aar = int(match.group())
        
        # DOI (hvis tilgjengelig)
        doi = None
        if "link" in item:
            link = item["link"]
            if "doi.org" in link:
                doi = link.split("doi.org/")[-1].split("/")[0] if "/" in link.split("doi.org/")[-1] else link.split("doi.org/")[-1]
        
        # Kilde-lenke
        kilde_url = item.get("link", "")
        
        # Abstract (hvis "snippet" er lang nok, eller hvis "inline_links" har abstract)
        abstract = resultat_snippet if len(resultat_snippet) > 50 else ""
        if "inline_links" in item and "serpapi_cite_link" in item["inline_links"]:
            # Kunne hentet full abstract via ekstra kall, men det koster ekstra søk
            pass
        
        papirer.append({
            "id": doi or f"scholar_{abs(hash(tittel))}",
            "tittel": tittel,
            "forfattere": forfattere,
            "aar": aar,
            "kilde_url": kilde_url,
            "abstract": abstract,
            "doi": doi,
            "kilde": "Google Scholar",
            "embedding": None,
        })
    
    return papirer
