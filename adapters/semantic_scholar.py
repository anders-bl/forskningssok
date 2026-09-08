"""adapters/semantic_scholar.py — Semantic Scholar Graph API: sitasjonsgraf, ikke
en ny artikkel-kilde (Europe PMC/OpenAlex dekker det alt).

Verdien er IKKE søk — det er `citations`/`references` med KONTEKST (`contexts`,
`intents`, `isInfluential`) som verken Europe PMC eller OpenAlex sin `referenced_works`
gir: OpenAlex sier KUN at A siterer B, Semantic Scholar sier OGSÅ om siteringen var
"background"/"methodology"/"result comparison" og om den var innflytelsesrik for
arbeidet. Det er det [[research-utkast/artikkel-bank-akse]] sitt siteringsgap-spor
faktisk trenger for å skille «nevnt i forbifarten» fra «bygget videre på».

[OBS] Skjemaet under er IKKE live-verifisert i denne økten (2026-09-08) — Semantic Scholar
sin DELTE anonyme rate-limit-pool var mettet (429 på alle forsøk, flere ganger, med
høflig ventetid mellom). Feltnavnene (paperId, externalIds.DOI, citationCount,
isOpenAccess, openAccessPdf.url, contexts, intents, isInfluential) er hentet fra
Semantic Scholar sin offentlige, stabile API-dokumentasjon (uendret i flere år per
egne endringslogger) — IKKE gjettet fra løse minner, men heller ikke bekreftet mot et
ekte svar herfra. Første reelle live-kall (helst med registrert nøkkel, se under) bør
kryssjekke denne docstringen mot faktisk respons og rette den om noe avviker — samme
disiplin som resten av adapters/ (unpaywall.py, openalex.py) allerede følger.

INGEN nøkkel kreves for grunnleggende bruk, men den DELTE poolen (alle anonyme
brukere i verden) er tydeligvis lett å mette. En gratis registrert nøkkel gir en
DEDIKERT rate i stedet for den delte — https://www.semanticscholar.org/product/api#api-key-form
(samme mønster som CORE-registreringen 2026-09-08: gratis, selvbetjent, ikke en faktura).

Ingen PII i spørringene (DOI/paper-ID/fritekst-søk er offentlige identifikatorer) —
samme EU-vurdering som openalex.py: tjenesten prosesserer ikke våre data, vi leser
dens offentlige graf.

ADR-004-disiplin: spørretid + TTL-cache, ingen crawler.
"""
import json
import os
import sqlite3
import time
from pathlib import Path

import httpx

from paths import DB

BASE = "https://api.semanticscholar.org/graph/v1"
UA = "lauvasdata-research (mailto:kontakt@lauvasdata.no)"
TTL_SEKUNDER = 24 * 3600
FELTER = "title,abstract,year,externalIds,citationCount,isOpenAccess,openAccessPdf,venue,publicationTypes"


def _headers() -> dict:
    # Nøkkel er valgfri — se moduldocstring. Satt via env, ALDRI hardkodet/committet
    # (samme hemmelighets-disiplin som resten av huset: instans-scopet, ikke i kode).
    nokkel = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    h = {"User-Agent": UA}
    if nokkel:
        h["x-api-key"] = nokkel
    return h


def _db(db_path: Path = DB) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE IF NOT EXISTS semantic_scholar_cache(
        key TEXT PRIMARY KEY, hentet_ved REAL, respons TEXT)""")
    return db


def _hent(url: str, params: dict, *, cache_key: str, db_path: Path = DB) -> dict:
    db = _db(db_path)
    rad = db.execute("SELECT hentet_ved, respons FROM semantic_scholar_cache WHERE key=?",
                     (cache_key,)).fetchone()
    if rad and (time.time() - rad[0]) < TTL_SEKUNDER:
        db.close()
        return json.loads(rad[1])
    try:
        r = httpx.get(url, params=params, headers=_headers(), timeout=30)
        r.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        db.close()
        raise RuntimeError(f"Semantic Scholar utilgjengelig: {e}") from e
    data = r.json()
    db.execute("INSERT OR REPLACE INTO semantic_scholar_cache(key, hentet_ved, respons) VALUES (?,?,?)",
               (cache_key, time.time(), json.dumps(data)))
    db.commit()
    db.close()
    return data


def _paper_dict(p: dict) -> dict:
    """Rått Semantic Scholar-paper-objekt → husets felt-navn. Ærlig fravær (None/tom
    streng) der feltet mangler, ALDRI en gjettet verdi — samme prinsipp som resten
    av adapters/."""
    ext = p.get("externalIds") or {}
    oa_pdf = p.get("openAccessPdf") or {}
    return {
        "ss_id": p.get("paperId"),
        "doi": ext.get("DOI"),
        "tittel": p.get("title") or "",
        "abstract": p.get("abstract") or "",
        "aar": p.get("year"),
        "tidsskrift": p.get("venue") or "",
        "siteringstall": p.get("citationCount"),
        "open_access": bool(p.get("isOpenAccess")),
        "fri_pdf_url": oa_pdf.get("url"),
        "pubtyper": tuple(p.get("publicationTypes") or ()),
    }


def sok(query: str, limit: int = 10, *, db_path: Path = DB) -> list[dict]:
    """Fritekst-søk. Se moduldocstring — verdien her er sekundær til siteringsgrafen,
    denne finnes for å FÅ et paperId/DOI å slå opp siteringer for, ikke som primær
    artikkel-kilde (Europe PMC/OpenAlex/CORE dekker det bedre for vårt korpus)."""
    key = f"sok::{query.strip().lower()}::{limit}"
    data = _hent(f"{BASE}/paper/search",
                {"query": query, "limit": limit, "fields": FELTER},
                cache_key=key, db_path=db_path)
    return [_paper_dict(p) for p in (data.get("data") or [])]


def siteringsgraf(doi_eller_id: str, *, db_path: Path = DB) -> dict:
    """Siteringer MED KONTEKST (contexts/intents/isInfluential) — det Europe PMC/
    OpenAlex sin referanseliste ikke har. `doi_eller_id` kan være et DOI (prefikset
    med DOI: internt, Semantic Scholar sin egen konvensjon for paper-ID-lookup på
    tvers av identifikator-typer) eller et rått Semantic Scholar paperId.

    Returnerer {"siteringer": [...], "referanser": [...]} — hver oppføring har
    {tittel, aar, intents, innflytelsesrik} slik at api.py kan vise «denne artikkelen
    ble sitert som METODOLOGI av 4 senere arbeider, hvorav 1 innflytelsesrikt» i
    stedet for et rått tall."""
    pid = doi_eller_id if doi_eller_id.upper().startswith("DOI:") else f"DOI:{doi_eller_id}"
    if not doi_eller_id.startswith("10."):
        pid = doi_eller_id  # allerede et rått Semantic Scholar paperId
    felter = "citations.title,citations.year,citations.contexts,citations.intents,citations.isInfluential," \
             "references.title,references.year,references.contexts,references.intents,references.isInfluential"
    key = f"graf::{pid}"
    data = _hent(f"{BASE}/paper/{pid}", {"fields": felter}, cache_key=key, db_path=db_path)

    def _rens(rader):
        ut = []
        for r in rader or []:
            ut.append({
                "tittel": r.get("title") or "",
                "aar": r.get("year"),
                "intents": tuple(r.get("intents") or ()),
                "innflytelsesrik": bool(r.get("isInfluential")),
            })
        return ut
    return {
        "siteringer": _rens(data.get("citations")),
        "referanser": _rens(data.get("references")),
    }
