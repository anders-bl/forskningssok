#!/usr/bin/env python3
"""api.py — FastAPI-laget som gjør cli.py/bank.py/citation_gap.py om til JSON-endepunkter
for en ekte nettflate (frontend/index.html). Ingen ny forretningslogikk her — alt tungt
arbeid (Resolve/Rank/TTL-cache/embedding) skjer i de allerede testede modulene; dette
laget serialiserer og feilhåndterer for HTTP.

Kjør: venv/bin/uvicorn api:app --reload --port 8420
"""
import time
from dataclasses import asdict

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import bank
import scoping
from adapters import openalex
from adapters.europe_pmc import DB as CACHE_DB
from citation_gap import gap_kandidater
from cli import sok_og_ranger
from ranking import FAGTIDSSKRIFTER, NORSKE_FAGMILJOER, domene_naer, ranger

app = FastAPI(title="forskningssok API")


def _kilde_naabar(url: str, *, timeout: float = 4.0) -> bool:
    """Rask nåbarhets-sjekk, IKKE et søk — HEAD først (billigst), GET som fallback
    for verter som ikke svarer på HEAD. Aldri en 500 herfra: en nede kilde er data,
    ikke en feil i statusendepunktet selv."""
    try:
        r = httpx.head(url, timeout=timeout, follow_redirects=True)
        if r.status_code < 500:
            return True
    except httpx.HTTPError:
        pass
    try:
        r = httpx.get(url, timeout=timeout)
        return r.status_code < 500
    except httpx.HTTPError:
        return False


@app.get("/api/status")
def api_status():
    """Helse-/kommandosenter-flate: tenkt som en pluggbar sjekk for
    silverbullet/ops/kommandosenter.py (koblet ikke inn selv i kveld — den filen
    hadde ucommittede endringer hos en søsterinstans, se wiki/log 2026-09-02).
    Kilde-nåbarhet er en fersk PING (millisekunder), ikke resultatet av siste søk —
    en nede-kilde her betyr «akkurat nå», ikke «var nede sist noen søkte»."""
    # CACHE_DB gis eksplisitt (ikke bank._db()s modul-default) — default-argumentet der
    # bindes ved import, så en monkeypatch av bank.DB i tester ville aldri truffet det.
    db = bank._db(CACHE_DB)
    n_papirer = db.execute("SELECT count(*) FROM papers").fetchone()[0]
    n_sitater = db.execute("SELECT count(*) FROM sitater").fetchone()[0]
    # query_cache eies av adapters/europe_pmc.py sin _db(), ikke bank.py sin — på en
    # HELT fersk cache.db (aldri søkt i) finnes tabellen ikke ennå. Fanget ved
    # testskriving: uten dette hadde /api/status krasjet med "no such table" på et
    # blankt oppsett, nøyaktig når status-sjekken hadde mest verdi (rett etter install).
    db.execute("CREATE TABLE IF NOT EXISTS query_cache(query TEXT PRIMARY KEY, hentet_ved REAL, respons TEXT)")
    siste_sok = db.execute(
        "SELECT query, hentet_ved FROM query_cache ORDER BY hentet_ved DESC LIMIT 1").fetchone()
    db.close()

    return {
        "papirer_cachet": n_papirer,
        "sitater_lagret": n_sitater,
        "cache_db": str(CACHE_DB),
        "cache_db_kb": round(CACHE_DB.stat().st_size / 1024, 1) if CACHE_DB.exists() else 0,
        "siste_sok": {"query": siste_sok[0], "for_sekunder_siden": round(time.time() - siste_sok[1])}
        if siste_sok else None,
        "kilder": {
            "europe_pmc": _kilde_naabar("https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=test&pageSize=1"),
            "openalex": _kilde_naabar("https://api.openalex.org/works/W2151543183"),
        },
    }


@app.get("/api/sok")
def api_sok(q: str, n: int = 20):
    if not q.strip():
        raise HTTPException(400, "tom spørring")
    try:
        papirer, eksakt_id = sok_og_ranger(q, page_size=max(n, 20))
    except RuntimeError as e:
        raise HTTPException(502, f"Europe PMC utilgjengelig: {e}") from e
    # asdict() dropper .id — det er en @property (utledet doi/pmid-fallback), ikke et
    # dataclass-felt. Fanget som ekte bug live 2026-09-02: uten dette fikk hvert papir
    # id:undefined i frontend, og «siste skrevet vinner»-kollisjonen åpnet alltid det
    # SISTE søkeresultatet uansett hvilket man klikket på.
    return {"query": q, "eksakt_id": eksakt_id,
            "papirer": [{**asdict(p), "id": p.id, "domene_naer": domene_naer(p)} for p in papirer[:n]]}


@app.get("/api/papir/{paper_id:path}")
def api_papir(paper_id: str):
    papir = bank.hent(paper_id)
    if not papir:
        raise HTTPException(404, f"{paper_id} er ikke cachet — søk det opp først")
    tekst = f"{papir['forfattere']} {papir['tidsskrift']}".lower()
    papir["domene_naer"] = any(m in tekst for m in NORSKE_FAGMILJOER + FAGTIDSSKRIFTER)
    return papir


@app.get("/api/lignende/{paper_id:path}")
def api_lignende(paper_id: str, k: int = 6):
    return {"paper_id": paper_id, "naboer": bank.lignende(paper_id, k=k)}


@app.get("/api/gap/{paper_id:path}")
def api_gap(paper_id: str, k: int = 10):
    papir = bank.hent(paper_id)
    if not papir:
        raise HTTPException(404, f"{paper_id} er ikke cachet — søk det opp først")
    if not papir["pmid"]:
        raise HTTPException(422, "papiret mangler PMID — /references krever det")
    try:
        return gap_kandidater(paper_id, papir["kilde_kode"] or "MED", papir["pmid"], k=k)
    except RuntimeError as e:
        # e er allerede "Europe PMC /references utilgjengelig: …" fra citation_gap.py —
        # ikke pakk inn på nytt (ekte dobbelt/trippel-prefiks-bug fanget live 2026-09-02).
        raise HTTPException(502, str(e)) from e


@app.get("/api/emner/{paper_id:path}")
def api_emner(paper_id: str):
    """OpenAlex-emnetagger — kun for papirer med DOI (OpenAlex slår opp på DOI)."""
    if not paper_id.startswith("10."):
        return {"emner": []}
    try:
        return {"emner": openalex.konsepter(paper_id)}
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e


@app.get("/api/emne/{emne_id}")
def api_emne_utforsk(emne_id: str, navn: str = "", n: int = 20):
    """Søk-doktrinens tredje modus («Utforskning» — vet domenet, ikke termen). Alle
    OpenAlex-verk under ETT emne, rangert med samme ADR-013-logikk (domene-nærhet FØR
    rå siteringstall) som resten av appen — ikke OpenAlex sin egen citation-sortering
    urørt, som ville gitt de samme gamle kanoniske artiklene uansett emne."""
    try:
        papirer = openalex.verk_for_emne(emne_id, limit=n)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    rangert = ranger(papirer)
    bank.lagre(rangert)  # samme cache/embed-sti som vanlig søk — emne-funn blir del av korpuset
    return {"emne_id": emne_id, "emne_navn": navn,
            "papirer": [{**asdict(p), "id": p.id, "domene_naer": domene_naer(p)} for p in rangert[:n]]}


@app.get("/api/sitater")
def api_sitater_liste(paper_id: str | None = None):
    return bank.hent_sitater(paper_id)


@app.post("/api/sitater")
def api_sitater_lagre(body: dict):
    paper_id = body.get("paper_id", "")
    tekst = (body.get("tekst") or "").strip()
    if not paper_id or not tekst:
        raise HTTPException(400, "paper_id og tekst er påkrevd")
    try:
        return bank.lagre_sitat(paper_id, tekst, body.get("kommentar", ""))
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.patch("/api/sitater/{sitat_id}")
def api_sitater_oppdater(sitat_id: int, body: dict):
    if not bank.oppdater_sitat(sitat_id, body.get("kommentar", "")):
        raise HTTPException(404, "sitat finnes ikke")
    return {"ok": True}


@app.get("/api/utkast")
def api_utkast_liste():
    return bank.liste_utkast()


@app.get("/api/utkast/{utkast_id}")
def api_utkast_hent(utkast_id: int):
    u = bank.hent_utkast(utkast_id)
    if not u:
        raise HTTPException(404, "utkast finnes ikke")
    return u


@app.post("/api/utkast")
def api_utkast_lagre(body: dict):
    """Oppretter (uten «id») eller oppdaterer (med «id») — samme endepunkt, samme
    autolagre-mønster som sitater. Tom tittel degraderer til «Uten tittel», aldri en feil
    for en gyldig, bare unavngitt, tekst."""
    innhold = body.get("innhold", "")
    tittel = (body.get("tittel") or "").strip() or "Uten tittel"
    return bank.lagre_utkast(tittel, innhold, body.get("id"))


@app.get("/api/relevans")
def api_relevans(tekst: str, k: int = 4):
    """FDR-038 ambient-modus: teksten Ulven skriver akkurat nå → nærmeste papirer i
    cachen. For kort tekst eller tom cache → ærlig tom liste (bank.lignende_tekst()
    sitt eget kontraktsvar), ALDRI en feil — en «gir ingenting»-respons her SKAL se ut
    som stillhet, ikke en 4xx/5xx."""
    return {"naboer": bank.lignende_tekst(tekst, k=k)}


@app.get("/api/omfang")
def api_omfang(tekst: str):
    """Akse-dekning for Omfang-fanen — se scoping.py for hvorfor dette er en bevisst
    enkel nøkkelord-heuristikk, ikke en semantisk klassifikator."""
    return {"akser": scoping.akse_dekning(tekst)}


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
