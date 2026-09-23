"""adapters/openalex.py — OpenAlex: fritekst-søk + emne-/konsept-tagger + referanse-fallback.

Live-verifisert 2026-09-02 mot et ekte cachet papir (10.1111/jfd.70099): gir treffsikre
emne-tagger («Aquaculture disease management and microbiota» — ordrett relevant) OG
batch-oppløser `referenced_works` til ekte titler/DOI-er i ETT kall (opptil 50 ID-er per
OR-filter). Sistnevnte er en FUNGERENDE fallback for citation_gap.py når Europe PMC sin
`/references` er nede — verifisert live samme kveld som EBIs eget endepunkt var det, hele
kvelden (503 «temporarily unavailable due to maintenance»).

`sok()` lagt til 2026-09-10 som det billige, nøkkel-frie alternativet til Google Scholar
(adapters/google_scholar.py via SerpAPI — kodet ferdig, men aldri koblet inn: krever
betalt nøkkel og en skrape-mellomtjeneste for noe OpenAlex alt dekker gratis). Samme
`search`-parameter/relevans-rangering, samme `_parse()` som `verk_for_emne()` under —
IKKE en ny kilde-klasse, kun en ny inngang til samme API.

US-hostet non-profit (OurResearch), men åpne bibliografiske metadata uten PII — samme
vurdering som NVD/CVE-oppslagene i `teknisk-enhets-sok`, ikke et unntak fra EU-preferansen
(den gjelder tjenester som PROSESSERER våre data, ikke offentlig metadata vi leser).
"kilde: OpenAlex, CC0" i eksport/UI når dette brukes (lisens-krav, samme disiplin som
Enhetsregisteret-oppslaget i dybdesøk-relasjonsryggrad).

ADR-004-disiplin: spørretid + TTL-cache, ingen crawler, ingen full korpus-indeksering.
"""
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from paths import DB
from schemas import PaperDossier

BASE = "https://api.openalex.org"
# "Polite pool" — OpenAlex prioriterer/stabiliserer trafikk med e-post i UA, samme
# høflighets-prinsipp som Europe PMC-adapteren og hoster.py sin arXiv-UA.
UA = "lauvasdata-research (mailto:kontakt@lauvasdata.no)"
TTL_SEKUNDER = 24 * 3600
# Delt av verk_for_emne() og sok() — begge bygger PaperDossier via samme _parse().
_SELECT_FELTER = ("id,title,publication_year,doi,cited_by_count,open_access,"
                   "authorships,primary_location,abstract_inverted_index")


def _db(db_path: Path = DB) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE IF NOT EXISTS openalex_cache(
        key TEXT PRIMARY KEY, hentet_ved REAL, respons TEXT)""")
    return db


def _hent_med_tid(key: str, url: str, params: dict | None, *, tving_fersk: bool = False,
                  db_path: Path = DB) -> tuple[dict, str]:
    db = _db(db_path)
    if not tving_fersk:
        rad = db.execute("SELECT hentet_ved, respons FROM openalex_cache WHERE key=?", (key,)).fetchone()
        if rad and (time.time() - rad[0]) < TTL_SEKUNDER:
            db.close()
            return json.loads(rad[1]), datetime.fromtimestamp(rad[0], timezone.utc).isoformat()
    try:
        r = httpx.get(url, params=params, headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        db.close()
        raise RuntimeError(f"OpenAlex utilgjengelig: {e}") from e
    data = r.json()
    hentet_ved = time.time()
    db.execute("INSERT OR REPLACE INTO openalex_cache(key, hentet_ved, respons) VALUES (?,?,?)",
               (key, hentet_ved, json.dumps(data)))
    db.commit()
    db.close()
    return data, datetime.fromtimestamp(hentet_ved, timezone.utc).isoformat()


def _hent(key: str, url: str, params: dict | None, *, tving_fersk: bool = False,
          db_path: Path = DB) -> dict:
    data, _ = _hent_med_tid(key, url, params, tving_fersk=tving_fersk, db_path=db_path)
    return data


def _verk(doi: str, *, db_path: Path = DB) -> dict:
    return _hent(f"verk::{doi}", f"{BASE}/works/https://doi.org/{doi}", None, db_path=db_path)


def konsepter(doi: str, *, db_path: Path = DB) -> list[dict]:
    """Emne-tagger for ett papir (OpenAlex sine «topics», ikke de eldre «concepts») —
    {id, navn} per emne. Id-en er den korte formen («T10506», ikke full URL) — det er
    formen `verk_for_emne()`s filter og frontendens lenke bruker."""
    return [{"id": t["id"].rsplit("/", 1)[-1], "navn": t["display_name"]}
            for t in _verk(doi, db_path=db_path).get("topics", [])]


def tilgang(doi: str, *, db_path: Path = DB) -> dict:
    """Lisens/tilgang-info — SAMME _verk()-kall som konsepter() (TTL-cachet, ingen ekstra
    HTTP-kall hvis papiret alt er slått opp). Erstatter det opprinnelig foreslåtte
    "koble til bruktsøk"-sporet (idébank #28) — undersøkt 2026-09-02: bruktsøk/bruktmarked
    er ISBN-baserte fysiske varer (Speider/FDR-029), journalartikler har DOI, ikke ISBN,
    strukturelt feil domene. Dette er hva OpenAlex FAKTISK har, i kallet vi alt gjør:
    ekte lisens-streng (SPDX-aktig, f.eks. "cc-by-nc-nd"), direkte fri-PDF-lenke når den
    finnes, utgiver, og oa_status (gold/green/hybrid/closed/diamond). INGEN prisdata
    finnes noe sted i OpenAlex — `pris` er derfor ALDRI et felt her, kun fravær av
    fri tilgang (ærlighets-prinsippet: aldri gjettet, aldri en oppdiktet pris)."""
    data = _verk(doi, db_path=db_path)
    oa_loc = data.get("best_oa_location") or {}
    return {
        "lisens": oa_loc.get("license"),
        "fri_pdf_url": oa_loc.get("pdf_url"),
        "utgiver": (oa_loc.get("source") or {}).get("host_organization_name"),
        "oa_status": (data.get("open_access") or {}).get("oa_status"),
    }


def _rekonstruer_abstract(inv_idx: dict | None) -> str:
    """OpenAlex leverer abstract som en invertert indeks (ord → posisjonsliste), ikke
    løpende tekst — juridisk/lisens-motivert format fra deres side, ikke noe å gjette
    seg rundt. Rekonstruerer ordrett rekkefølge fra posisjonene."""
    if not inv_idx:
        return ""
    posisjoner: dict[int, str] = {}
    for ord, idxer in inv_idx.items():
        for i in idxer:
            posisjoner[i] = ord
    return " ".join(posisjoner[i] for i in sorted(posisjoner))


def _parse(data: dict) -> list[PaperDossier]:
    ut = []
    for w in data.get("results", []):
        forfattere = "; ".join(
            a.get("author", {}).get("display_name", "") for a in (w.get("authorships") or []))
        kilde = ((w.get("primary_location") or {}).get("source") or {}).get("display_name", "")
        doi_raw = (w.get("doi") or "").replace("https://doi.org/", "") or None
        ut.append(PaperDossier(
            pmid=None,
            doi=doi_raw,
            tittel=(w.get("title") or "").strip(),
            forfattere=forfattere,
            tidsskrift=kilde,
            aar=w.get("publication_year"),
            abstract=_rekonstruer_abstract(w.get("abstract_inverted_index")),
            siteringstall=w.get("cited_by_count"),
            open_access=bool((w.get("open_access") or {}).get("is_oa")),
            kilde_url=w.get("id", ""),
            kilde="openalex",
            kilde_kode="OpenAlex",
        ))
    return ut


def sok(query: str, limit: int = 10, *, tving_fersk: bool = False,
        db_path: Path = DB) -> list[PaperDossier]:
    """Fritekst-søk (OpenAlex sin egen relevans-rangerte `search`-parameter — matcher
    tittel+abstract+fulltekst der fulltekst finnes) → kandidat-papirer, TTL-cachet.
    Samme ærlighets-disiplin som core.py/europe_pmc.py: en kilde-feil raiser via
    _hent(), blir aldri en stille tom liste som kunne forveksles med et ekte fravær
    av treff. Gratis, ingen nøkkel — se moduldocstring for hvorfor dette er valgt
    fremfor SerpAPI/Google Scholar."""
    key = f"sok::{query.strip().lower()}::{limit}"
    data = _hent(key, f"{BASE}/works", {
        "search": query,
        "per_page": limit,
        "select": _SELECT_FELTER,
    }, tving_fersk=tving_fersk, db_path=db_path)
    return _parse(data)


def verk_for_emne(emne_id: str, limit: int = 20, *, db_path: Path = DB) -> list[PaperDossier]:
    """FDR: søk-doktrinens tredje modus («Utforskning» — vet domenet, ikke termen).
    Alle OpenAlex-verk under ett emne, nyeste/mest siterte først (OpenAlex sin egen
    sortering — vår egen ranking.ranger() domene-vekting påføres i api.py, ikke her,
    siden den regner på PaperDossier-objekter og denne funksjonen returnerer dem).
    Live-verifisert 2026-09-02: emne T10506 («Aquaculture disease management and
    microbiota») → 218 630 treff i OpenAlex — et EMNE er et bredt FELT (kontrollert
    taksonomi, ~4500 emner totalt), ikke et smalt tema. Forventet: eldre, kanoniske,
    høyt siterte artikler dominerer råresultatet uten videre rangering — derfor
    komponeres denne funksjonen alltid med ranking.ranger() i api.py."""
    data = _hent(f"emne::{emne_id}::{limit}", f"{BASE}/works", {
        "filter": f"topics.id:{emne_id}",
        "sort": "cited_by_count:desc",
        "per_page": limit,
        "select": _SELECT_FELTER,
    }, db_path=db_path)
    return _parse(data)


def siterende_verk(doi: str, limit: int = 20, cursor: str = "*",
                   *, db_path: Path = DB) -> dict:
    """Fetch works that cite this DOI and return explicit, directional graph edges.

    `cites:<OpenAlex Work ID>` is OpenAlex's incoming-citation filter. Results are
    capped to one page; `next_cursor` and `complete` let clients continue without
    mistaking a truncated neighborhood for the full citation history.
    """
    doi = doi.strip().removeprefix("https://doi.org/").lower()
    if not doi:
        raise ValueError("DOI mangler")
    if not 1 <= limit <= 100:
        raise ValueError("limit må være mellom 1 og 100")

    seed = _verk(doi, db_path=db_path)
    seed_id = seed.get("id")
    if not seed_id:
        return {
            "status": "not_found",
            "provider": "openalex",
            "seed_doi": doi,
            "seed_openalex_id": None,
            "works": [],
            "edges": [],
            "total_available": None,
            "retrieved": 0,
            "next_cursor": None,
            "complete": None,
        }

    openalex_short_id = seed_id.rsplit("/", 1)[-1]
    data, retrieved_at = _hent_med_tid(
        f"cites::{doi}::{limit}::{cursor}",
        f"{BASE}/works",
        {
            "filter": f"cites:{openalex_short_id}",
            "sort": "-publication_date",
            "per_page": limit,
            "cursor": cursor,
            "select": _SELECT_FELTER,
        },
        db_path=db_path,
    )
    works = _parse(data)
    meta = data.get("meta") or {}
    next_cursor = meta.get("next_cursor")
    source_coverage = {
        "provider": "openalex",
        "retrieved_at": retrieved_at,
        "retrieved": len(works),
        "total_available": meta.get("count"),
        "complete": next_cursor is None,
        "cursor": cursor,
    }
    edges = [
        {
            "id": f"openalex:cites:{work.kilde_url.rsplit('/', 1)[-1]}:{openalex_short_id}",
            "from_id": work.doi or work.kilde_url,
            "to_id": doi,
            "relation": "cites",
            "provider": "openalex",
            "match_method": "openalex.cites",
            "retrieved_at": retrieved_at,
            "source_coverage": source_coverage,
        }
        for work in works
    ]
    return {
        "status": "ok",
        "provider": "openalex",
        "seed_doi": doi,
        "seed_openalex_id": seed_id,
        "works": [
            {
                "id": work.id,
                "doi": work.doi,
                "openalex_id": work.kilde_url,
                "title": work.tittel,
                "authors": work.forfattere,
                "year": work.aar,
                "venue": work.tidsskrift,
                "cited_by_count": work.siteringstall,
                "url": work.kilde_url,
            }
            for work in works
        ],
        "edges": edges,
        "total_available": meta.get("count"),
        "retrieved": len(works),
        "next_cursor": next_cursor,
        "complete": next_cursor is None,
    }


def referanser(doi: str, *, db_path: Path = DB) -> list[dict]:
    """Fallback for citation_gap.py: OpenAlex sin referenced_works, batch-oppløst til
    {doi, title} — SAMME feltnavn-kontrakt som adapters/europe_pmc.py:referanser(), slik
    at citation_gap.py sin DOI-/tittel-matching virker identisk uansett hvilken kilde
    som faktisk svarte. Ærlig tom liste hvis papiret ikke er i OpenAlex eller mangler
    referanser der — aldri en feil for et gyldig, bare tomt, svar."""
    ider = [i.rsplit("/", 1)[-1] for i in _verk(doi, db_path=db_path).get("referenced_works", [])]
    ut = []
    for i in range(0, len(ider), 50):  # OpenAlex sitt OR-filter tar ~50 id-er per kall
        batch = ider[i:i + 50]
        filt = "|".join(batch)
        data = _hent(f"refs::{doi}::{i}", f"{BASE}/works", {
            "filter": f"ids.openalex:{filt}", "select": "id,title,publication_year,doi",
            "per_page": 50,
        }, db_path=db_path)
        for w in data.get("results", []):
            doi_raw = (w.get("doi") or "").replace("https://doi.org/", "") or None
            ut.append({"doi": doi_raw, "title": w.get("title", "")})
    return ut
