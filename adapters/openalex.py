"""adapters/openalex.py — OpenAlex: emne-/konsept-tagger + referanse-fallback.

Live-verifisert 2026-09-02 mot et ekte cachet papir (10.1111/jfd.70099): gir treffsikre
emne-tagger («Aquaculture disease management and microbiota» — ordrett relevant) OG
batch-oppløser `referenced_works` til ekte titler/DOI-er i ETT kall (opptil 50 ID-er per
OR-filter). Sistnevnte er en FUNGERENDE fallback for citation_gap.py når Europe PMC sin
`/references` er nede — verifisert live samme kveld som EBIs eget endepunkt var det, hele
kvelden (503 «temporarily unavailable due to maintenance»).

US-hostet non-profit (OurResearch), men åpne bibliografiske metadata uten PII — samme
vurdering som NVD/CVE-oppslagene i `teknisk-enhets-sok`, ikke et unntak fra EU-preferansen
(den gjelder tjenester som PROSESSERER våre data, ikke offentlig metadata vi leser).
"kilde: OpenAlex, CC0" i eksport/UI når dette brukes (lisens-krav, samme disiplin som
Enhetsregisteret-oppslaget i dybdesøk-relasjonsryggrad).

ADR-004-disiplin: spørretid + TTL-cache, ingen crawler, ingen full korpus-indeksering.
"""
import json
import time
from pathlib import Path

import httpx

from paths import DB

BASE = "https://api.openalex.org"
# "Polite pool" — OpenAlex prioriterer/stabiliserer trafikk med e-post i UA, samme
# høflighets-prinsipp som Europe PMC-adapteren og hoster.py sin arXiv-UA.
UA = "lauvasdata-research (mailto:kontakt@lauvasdata.no)"
TTL_SEKUNDER = 24 * 3600


def _db(db_path: Path = DB):
    import sqlite3
    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE IF NOT EXISTS openalex_cache(
        key TEXT PRIMARY KEY, hentet_ved REAL, respons TEXT)""")
    return db


def _hent(key: str, url: str, params: dict | None, *, db_path: Path = DB) -> dict:
    db = _db(db_path)
    rad = db.execute("SELECT hentet_ved, respons FROM openalex_cache WHERE key=?", (key,)).fetchone()
    if rad and (time.time() - rad[0]) < TTL_SEKUNDER:
        db.close()
        return json.loads(rad[1])
    try:
        r = httpx.get(url, params=params, headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        db.close()
        raise RuntimeError(f"OpenAlex utilgjengelig: {e}") from e
    data = r.json()
    db.execute("INSERT OR REPLACE INTO openalex_cache(key, hentet_ved, respons) VALUES (?,?,?)",
               (key, time.time(), json.dumps(data)))
    db.commit()
    db.close()
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


def verk_for_emne(emne_id: str, limit: int = 20, *, db_path: Path = DB) -> list:
    """FDR: søk-doktrinens tredje modus («Utforskning» — vet domenet, ikke termen).
    Alle OpenAlex-verk under ett emne, nyeste/mest siterte først (OpenAlex sin egen
    sortering — vår egen ranking.ranger() domene-vekting påføres i api.py, ikke her,
    siden den regner på PaperDossier-objekter og denne funksjonen returnerer dem).
    Live-verifisert 2026-09-02: emne T10506 («Aquaculture disease management and
    microbiota») → 218 630 treff i OpenAlex — et EMNE er et bredt FELT (kontrollert
    taksonomi, ~4500 emner totalt), ikke et smalt tema. Forventet: eldre, kanoniske,
    høyt siterte artikler dominerer råresultatet uten videre rangering — derfor
    komponeres denne funksjonen alltid med ranking.ranger() i api.py."""
    from schemas import PaperDossier
    data = _hent(f"emne::{emne_id}::{limit}", f"{BASE}/works", {
        "filter": f"topics.id:{emne_id}",
        "sort": "cited_by_count:desc",
        "per_page": limit,
        "select": "id,title,publication_year,doi,cited_by_count,open_access,"
                  "authorships,primary_location,abstract_inverted_index",
    }, db_path=db_path)
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
