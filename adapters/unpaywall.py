"""adapters/unpaywall.py — Unpaywall: DOI -> beste lovlige OA-lokasjon.

Wiret inn 2026-09-07 (Anders: «La oss wire inn!»). OpenAlex-adapteren har alt en
tilgang()-funksjon; Unpaywalls verdi er IKKE å gjenta den, men tilfellene der de er
UENIGE — Unpaywall har bredere repositorie-dekning (grønn OA i institusjonsarkiv) enn
OpenAlex/Europe PMC sin OA-flagg fanger. Derfor fletter api.py de to og rapporterer
hvem som svarte + om de er uenige, i stedet for å bytte ut den ene med den andre.

Schema live-verifisert 2026-09-07 mot 10.1111/jfd.13815 (ekte felt, ikke gjettet):
best_oa_location.{url_for_pdf,url,license,host_type,version}, topp-nivå
{is_oa,oa_status,publisher,journal_name,journal_is_in_doaj,has_repository_copy}.
De tre siste er signaler OpenAlex IKKE gir — tatt med fordi de mater lisens-gaten i
[[research-utkast/artikkel-bank-akse]] (DOAJ = ren CC-per-artikkel-kilde, grønn kopi =
lovlig fulltekst utenom forlaget).

Samme organisasjon som OpenAlex (OurResearch), åpne bibliografiske metadata uten PII —
samme EU-preferanse-vurdering som openalex.py sin docstring (gjelder tjenester som
PROSESSERER våre data, ikke offentlig metadata vi leser). Krever en e-post-param
(høflighet + kontaktpunkt), INGEN nøkkel — kontakt@lauvasdata.no er offentlig, ikke en
hemmelighet (samme som mailto-en i openalex-UA-en).

ADR-004-disiplin: spørretid + TTL-cache, ingen crawler, ingen full korpus-indeksering.
"""
import json
import time
from pathlib import Path

import httpx

from paths import DB

BASE = "https://api.unpaywall.org/v2"
EPOST = "kontakt@lauvasdata.no"  # påkrevd param, offentlig kontakt — ikke en hemmelighet
UA = "lauvasdata-research (mailto:kontakt@lauvasdata.no)"
TTL_SEKUNDER = 24 * 3600


def _db(db_path: Path = DB):
    import sqlite3
    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE IF NOT EXISTS unpaywall_cache(
        key TEXT PRIMARY KEY, hentet_ved REAL, respons TEXT)""")
    return db


def _hent(doi: str, *, db_path: Path = DB) -> dict:
    db = _db(db_path)
    rad = db.execute("SELECT hentet_ved, respons FROM unpaywall_cache WHERE key=?", (doi,)).fetchone()
    if rad and (time.time() - rad[0]) < TTL_SEKUNDER:
        db.close()
        return json.loads(rad[1])
    try:
        r = httpx.get(f"{BASE}/{doi}", params={"email": EPOST},
                      headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        db.close()
        raise RuntimeError(f"Unpaywall utilgjengelig: {e}") from e
    data = r.json()
    db.execute("INSERT OR REPLACE INTO unpaywall_cache(key, hentet_ved, respons) VALUES (?,?,?)",
               (doi, time.time(), json.dumps(data)))
    db.commit()
    db.close()
    return data


def tilgang(doi: str, *, db_path: Path = DB) -> dict:
    """Lisens/tilgang for ett DOI — SAMME fire kjernefelt som openalex.tilgang()
    (lisens/fri_pdf_url/utgiver/oa_status) slik at api.py kan flette de to uten
    feltnavn-oversettelse, PLUSS tre Unpaywall-eksklusive signaler (i_doaj,
    repositorie_kopi, vert_type). fri_pdf_url foretrekker den ekte PDF-en
    (url_for_pdf), faller tilbake på lokasjonens url. Ærlig fravær (None) når det
    ikke finnes en åpen lokasjon — aldri gjettet, aldri en oppdiktet pris."""
    data = _hent(doi, db_path=db_path)
    b = data.get("best_oa_location") or {}
    return {
        "lisens": b.get("license"),
        "fri_pdf_url": b.get("url_for_pdf") or b.get("url"),
        "utgiver": data.get("publisher"),
        "oa_status": data.get("oa_status"),
        # Unpaywall-eksklusive signaler (mater lisens-gaten senere, ikke i openalex):
        "i_doaj": data.get("journal_is_in_doaj"),
        "repositorie_kopi": data.get("has_repository_copy"),
        "vert_type": b.get("host_type"),  # "publisher" (gull) vs "repository" (grønn)
    }
