"""adapters/semantic_scholar.py — Semantic Scholar Graph API: sitasjonsgraf, ikke
en ny artikkel-kilde (Europe PMC/OpenAlex dekker det alt).

Verdien er IKKE søk — det er `citations`/`references` med KONTEKST (`contexts`,
`intents`, `isInfluential`) som verken Europe PMC eller OpenAlex sin `referenced_works`
gir: OpenAlex sier KUN at A siterer B, Semantic Scholar sier OGSÅ om siteringen var
"background"/"methodology"/"result comparison" og om den var innflytelsesrik for
arbeidet. Det er det [[research-utkast/artikkel-bank-akse]] sitt siteringsgap-spor
faktisk trenger for å skille «nevnt i forbifarten» fra «bygget videre på».

[OBS] Feltskjemaet under er IKKE live-verifisert mot et ekte 200-svar i denne økten
(2026-09-08) — Semantic Scholar sin DELTE anonyme rate-limit-pool var mettet (429 på
gjentatte forsøk). Feltnavnene (paperId, externalIds.DOI, citationCount, isOpenAccess,
openAccessPdf.url, contexts, intents, isInfluential) er hentet fra Semantic Scholar
sin offentlige, stabile API-dokumentasjon — IKKE gjettet, men heller ikke bekreftet mot
et ekte svar herfra ennå. Første reelle live-kall bør kryssjekke denne docstringen.

Retry/backoff-oppførselen ER derimot verifisert mot kilde (semanticscholar.readthedocs.io
+ CASRAI sin målte gjennomgang, begge 2026-09-08): INGEN Retry-After-header på 429 —
eneste signal er statuskoden selv, ulikt CORE (som gir et eksakt reset-tidspunkt vi kan
sove til, se ops/core_lisens_sjekk.py i bøker-repoet). Offisiell Python-klients egen
strategi er 10 forsøk, start 5s, dobler til tak 60s — for tungt for en SYNKRON web-
respons her (forskningssok sitt /api/siteringsgraf-endepunkt kaller dette direkte, ikke
i en bakgrunnsjobb). `_hent()` bruker derfor samme PRINSIPP (eksponentiell backoff på
429, aldri umiddelbar retry) skalert til en akseptabel verst-tenkelig ventetid: 4 forsøk,
2s→4s→8s, gir opp med en tydelig feil fremfor å holde en bruker ventende i minuttvis.

Rate-grensen for den registrerte nøkkelen ER oppgitt eksplisitt (Semantic Scholars
registreringsside, lest av Anders 2026-09-08): «1 request per second, cumulative across
all endpoints.» Det er en HARD, kjent grense — ikke noe vi må gjette oss til reaktivt via
429-er. `_vent_pa_rate_limit()` håndhever den PROAKTIVT (≥1,0s mellom hvert faktiske
HTTP-kall, på tvers av /search og /paper) — 429-backoffen over er belte-og-seler for det
som likevel går galt (samtidige requests fra andre prosesser, kortvarige overskridelser),
ikke hovedforsvaret lenger.

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
import threading
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


# 2s→4s→8s — se moduldocstring for hvorfor dette er skalert NED fra den offisielle
# klientens 5s→60s×10-forsøk: den er bygget for batch-jobber, dette kalles synkront
# fra en HTTP-respons. MAKS_FORSOEK=4 betyr 3 faktiske ventinger (2+4+8=14s verst
# tenkelig) FØR vi gir opp — en bruker skal aldri holdes ventende i minuttvis for ett
# siteringsgraf-oppslag.
MAKS_FORSOEK = 4
BACKOFF_START_SEKUNDER = 2.0

# Proaktiv rate-grense — se moduldocstring: «1 request per second, cumulative across
# all endpoints», oppgitt av Semantic Scholar selv på registreringssiden (2026-09-08),
# ikke gjettet. threading.Lock fordi forskningssok sine FastAPI-handlers er BEVISST
# synkrone (ADR-004) og kjører i en threadpool — flere samtidige requests i SAMME
# prosess skal likevel serialiseres til ≥1,0s mellomrom, ikke race mot hverandre.
_RATE_LOCK = threading.Lock()
_MIN_INTERVALL_SEKUNDER = 1.0
_siste_kall_monotonic = 0.0


def _vent_pa_rate_limit() -> None:
    global _siste_kall_monotonic
    with _RATE_LOCK:
        na = time.monotonic()
        vent = _siste_kall_monotonic + _MIN_INTERVALL_SEKUNDER - na
        if vent > 0:
            time.sleep(vent)
        _siste_kall_monotonic = time.monotonic()


def _hent(url: str, params: dict, *, cache_key: str, db_path: Path = DB) -> dict:
    db = _db(db_path)
    rad = db.execute("SELECT hentet_ved, respons FROM semantic_scholar_cache WHERE key=?",
                     (cache_key,)).fetchone()
    if rad and (time.time() - rad[0]) < TTL_SEKUNDER:
        db.close()
        return json.loads(rad[1])

    ventetid = BACKOFF_START_SEKUNDER
    r = None
    for forsoek in range(MAKS_FORSOEK):
        siste_forsoek = forsoek == MAKS_FORSOEK - 1
        _vent_pa_rate_limit()
        try:
            r = httpx.get(url, params=params, headers=_headers(), timeout=30)
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            if siste_forsoek:
                db.close()
                raise RuntimeError(f"Semantic Scholar utilgjengelig: {e}") from e
            time.sleep(ventetid)
            ventetid *= 2
            continue
        if r.status_code == 429:
            # INGEN Retry-After her (verifisert, se moduldocstring) — ren eksponentiell
            # backoff er eneste vei, uansett hvilken feilklasse (429 ELLER en
            # forbindelsesfeil) — begge betyr "ikke prøv igjen med det samme".
            if siste_forsoek:
                db.close()
                raise RuntimeError(
                    f"Semantic Scholar rate-limitet etter {MAKS_FORSOEK} forsøk (429, "
                    f"ingen Retry-After å vente på — prøv igjen senere eller registrer "
                    f"SEMANTIC_SCHOLAR_API_KEY for en dedikert rate)")
            time.sleep(ventetid)
            ventetid *= 2
            continue
        break  # ekte svar, verken unntak eller 429 — ut av retry-løkka

    try:
        r.raise_for_status()
    except httpx.HTTPError as e:
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
