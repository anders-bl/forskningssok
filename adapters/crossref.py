"""adapters/crossref.py — utgiverens EGEN deponerte referanseliste, som tredje kilde til
citation_gap.py.

Hvorfor den finnes (målt 2026-09-04, ikke antatt): Europe PMC sin `/references` svarte
fortsatt 503 «temporarily unavailable due to maintenance» to dager etter at README kalte
det et vedlikeholdsvindu — det er ikke et vindu lenger, og OpenAlex-fallbacken er i praksis
den eneste armen som kjører. Men den er UFULLSTENDIG: for 10.1111/jfd.70099 kjenner
OpenAlex 13 referanser mens Crossref (Wileys egen deposit) har 20. En for kort
referanseliste gjør gap-testen SYSTEMATISK FOR SNILL MOT SEG SELV — hver referanse kilden
ikke kjenner blir en nabo som feilaktig framstår som «ikke sitert», altså et falskt gap.
Nøyaktig den feilen probe-en er bygget for å avsløre hos andre verktøy.

Crossref er ingen erstatning, men et supplement: mange utgivere deponerer ikke
referanselister offentlig i det hele tatt (historisk bl.a. Elsevier), så et tomt svar her
er vanlig og helt normalt — derfor foreneS listene i citation_gap.py i stedet for at én
kilde velges. Union kan bare gjøre gap-listen KORTERE og mer sann, aldri lengre.

Referansene kommer med DOI når utgiveren deponerte den, og med `article-title`/
`unstructured` som tittel ellers. `unstructured` er hele den ustrukturerte
sitasjonsstrengen («Smith J. et al. Title. Journal 2020;12:3-4»), ikke en tittel — den
sendes likevel med, fordi citation_gap.py matcher normalisert tittel som fallback etter
DOI, og en delstreng-match er bedre enn ingen match. Den brukes ALDRI til å vise en
referanse for et menneske.

US-hostet non-profit (Crossref/PILA), åpne bibliografiske metadata uten PII — samme
vurdering som OpenAlex-adapteren dokumenterer, ikke et unntak fra EU-preferansen.
ADR-004-disiplin: spørretid + 24t TTL-cache, ingen crawler.
"""
import json
import sqlite3
import time
from pathlib import Path

import httpx

from paths import DB

BASE = "https://api.crossref.org"
# Crossrefs «polite pool» — samme høflighets-prinsipp som OpenAlex-adapteren.
UA = "lauvasdata-research (mailto:kontakt@lauvasdata.no)"
TTL_SEKUNDER = 24 * 3600


def _db(db_path: Path = DB) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE IF NOT EXISTS crossref_cache(
        key TEXT PRIMARY KEY, hentet_ved REAL, respons TEXT)""")
    return db


def _hent(key: str, url: str, *, db_path: Path = DB) -> dict:
    db = _db(db_path)
    rad = db.execute("SELECT hentet_ved, respons FROM crossref_cache WHERE key=?", (key,)).fetchone()
    if rad and (time.time() - rad[0]) < TTL_SEKUNDER:
        db.close()
        return json.loads(rad[1])
    try:
        r = httpx.get(url, headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        db.close()
        raise RuntimeError(f"Crossref utilgjengelig: {e}") from e
    data = r.json()
    db.execute("INSERT OR REPLACE INTO crossref_cache(key, hentet_ved, respons) VALUES (?,?,?)",
               (key, time.time(), json.dumps(data)))
    db.commit()
    db.close()
    return data


def referanser(doi: str, *, db_path: Path = DB) -> list[dict]:
    """Samme feltnavn-kontrakt som europe_pmc.referanser/openalex.referanser
    ({doi, title}), slik at citation_gap.py sin matching virker identisk uansett kilde.

    Ærlig tom liste når utgiveren ikke har deponert referanser — det er et VANLIG og
    gyldig svar, ikke en feil, og må aldri forveksles med «papiret siterer ingenting»."""
    data = _hent(f"refs::{doi}", f"{BASE}/works/{doi}", db_path=db_path)
    ut = []
    for r in (data.get("message", {}).get("reference") or []):
        tittel = r.get("article-title") or r.get("volume-title") or r.get("unstructured") or ""
        ut.append({"doi": (r.get("DOI") or None), "title": tittel})
    return ut


def referanse_antall(doi: str, *, db_path: Path = DB) -> int | None:
    """Utgiverens EGET tall på hvor mange referanser papiret har — deponert selv når
    selve listen ikke er det. Det gjør den til en uavhengig fasit å måle en hentet
    referanseliste MOT: er den kortere, vet vi at gap-listen er for lang, og kan si det
    i stedet for å presentere et ufullstendig tall som et faktum.

    None betyr «Crossref vet ikke», aldri 0 — et 0 her ville lest som «papiret siterer
    ingenting» og gjort hele nabolisten til falske gap."""
    try:
        m = _hent(f"refs::{doi}", f"{BASE}/works/{doi}", db_path=db_path).get("message", {})
    except RuntimeError:
        return None
    antall = m.get("reference-count", m.get("references-count"))
    return antall if isinstance(antall, int) and antall > 0 else None
