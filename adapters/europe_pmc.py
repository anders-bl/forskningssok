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
import html
import json
import re
import sqlite3
import time
from pathlib import Path

import httpx

from paths import DB
from schemas import PaperDossier

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
REST = "https://www.ebi.ac.uk/europepmc/webservices/rest"
UA = "Mozilla/5.0 (research; lauvasdata; kontakt@lauvasdata.no)"
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


def _rens(tekst: str) -> str:
    """Europe PMC sin abstractText/title bærer ofte innebygd XML-markup — enten rå
    (<p>, <italic>, <title>Abstract</title> som forspalte) eller HTML-escaped
    (&lt;i&gt;…&lt;/i&gt;, sett i artstitler). Fanget live 2026-09-02 på to ulike papirer
    som rendret rå/escaped tagger i leseflaten. Escape først (så begge formene blir like
    tagger), strip deretter — aldri vist urenset."""
    t = html.unescape(tekst or "")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)).strip()


# Verdier Europe PMC bruker for «vi vet ikke», som er strenger og ikke fravær.
# Målt 2026-09-04: 3 av 31 berikede papirer fikk `pageInfo: "Not Available"`, som ville
# rendret som «s. Not Available» i en referanse. Et ærlig fravær er None — en plassholder
# som ser ut som data er verre enn ingen data, fordi den ikke kan skilles fra et sidetall
# nedstrøms.
_IKKE_VERDI = {"not available", "n/a", "na", "-", "none", "null", "unknown"}


def _felt(v) -> str | None:
    """Normaliser et metadatafelt: tom streng og kildens plassholdere blir None."""
    if v is None:
        return None
    t = str(v).strip()
    return None if not t or t.lower() in _IKKE_VERDI else t


def _mesh(r: dict) -> list[dict]:
    """meshHeadingList.meshHeading, eller tom liste. Preprints (PPR) og arkivtreff har
    ingen MeSH — de ble aldri indeksert av NLM, og det er et ekte fravær, ikke en feil."""
    return (r.get("meshHeadingList") or {}).get("meshHeading") or []


def _parse(data: dict) -> list[PaperDossier]:
    ut = []
    for r in data.get("resultList", {}).get("result", []):
        pmid = r.get("pmid")
        aar_raw = r.get("pubYear") or ""
        ut.append(PaperDossier(
            pmid=pmid,
            doi=r.get("doi"),
            tittel=_rens(r.get("title", "")),
            forfattere=r.get("authorString", ""),
            tidsskrift=((r.get("journalInfo") or {}).get("journal") or {}).get("title", ""),
            aar=int(aar_raw) if aar_raw.isdigit() else None,
            abstract=_rens(r.get("abstractText", "")),
            siteringstall=r.get("citedByCount"),
            open_access=(r.get("isOpenAccess") == "Y"),
            kilde_url=f"https://europepmc.org/article/{r.get('source', 'MED')}/{pmid or r.get('id', '')}",
            kilde_kode=r.get("source", "MED"),
            # journalInfo ligger ETT nivå over journal: volume/issue er søsken av
            # `journal`-objektet, mens issn bor inni det. pageInfo står på rot-nivå,
            # ikke i journalInfo — verifisert mot ekte svar 2026-09-04 (10.1111/jfd.70099
            # gir volume=49, issue=5, pageInfo=e70099, issn=0140-7775).
            volum=_felt((r.get("journalInfo") or {}).get("volume")),
            hefte=_felt((r.get("journalInfo") or {}).get("issue")),
            sider=_felt(r.get("pageInfo")),
            issn=_felt(((r.get("journalInfo") or {}).get("journal") or {}).get("issn")),
            pubtyper=tuple((r.get("pubTypeList") or {}).get("pubType") or ()),
            mesh=tuple(m.get("descriptorName") for m in _mesh(r) if m.get("descriptorName")),
            mesh_major=tuple(m.get("descriptorName") for m in _mesh(r)
                             if m.get("majorTopic_YN") == "Y" and m.get("descriptorName")),
        ))
    return ut


def referanser(kilde_kode: str, ekte_id: str, page_size: int = 200, *,
                tving_fersk: bool = False, db_path: Path = DB) -> list[dict]:
    """Hva ETT papir selv siterer (Europe PMC /references) — grunnlaget for
    citation_gap.py. IKKE live-verifisert mot ekte respons ennå: EBIs `/references`-
    delressurs var i vedlikeholdsvindu («temporarily unavailable due to maintenance»,
    503, målt 2026-09-02 14:34 UTC) mens dette ble bygget — kun `/search` var oppe
    samtidig. Parsingen under følger EBIs DOKUMENTERTE reference-schema (id/source/
    title/authorString/pubYear/doi — doi er ofte FRAVÆRENDE i referanselister, derfor
    matcher citation_gap.py primært på tittel), men er en gjetning om FELTENE til det
    er kjørt live én gang. RuntimeError på feil, samme disiplin som `sok()` — en 503
    her skal ALDRI se ut som «dette papiret siterer ingenting»."""
    key = f"refs::{kilde_kode}::{ekte_id}::{page_size}"
    db = _db(db_path)
    if not tving_fersk:
        rad = db.execute(
            "SELECT hentet_ved, respons FROM query_cache WHERE query=?", (key,)).fetchone()
        if rad and (time.time() - rad[0]) < TTL_SEKUNDER:
            db.close()
            return json.loads(rad[1])
    try:
        r = httpx.get(f"{REST}/{kilde_kode}/{ekte_id}/references",
                       params={"format": "json", "pageSize": page_size},
                       headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        db.close()
        raise RuntimeError(f"Europe PMC /references utilgjengelig: {e}") from e
    data = r.json()
    rader = (data.get("referenceList") or {}).get("reference", [])
    db.execute("INSERT OR REPLACE INTO query_cache(query, hentet_ved, respons) VALUES (?,?,?)",
               (key, time.time(), json.dumps(rader)))
    db.commit()
    db.close()
    return rader
