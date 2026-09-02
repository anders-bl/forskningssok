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

BASE = "https://api.openalex.org"
# "Polite pool" — OpenAlex prioriterer/stabiliserer trafikk med e-post i UA, samme
# høflighets-prinsipp som Europe PMC-adapteren og hoster.py sin arXiv-UA.
UA = "lauvasdata-research (mailto:kontakt@lauvasdata.no)"
DB = Path(__file__).resolve().parent.parent / "cache.db"
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


def konsepter(doi: str, *, db_path: Path = DB) -> list[str]:
    """Emne-tagger for ett papir (OpenAlex sine «topics», ikke de eldre «concepts»)."""
    return [t["display_name"] for t in _verk(doi, db_path=db_path).get("topics", [])]


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
