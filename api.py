#!/usr/bin/env python3
"""api.py — FastAPI-laget som gjør cli.py/bank.py/citation_gap.py om til JSON-endepunkter
for en ekte nettflate (frontend/index.html). Ingen ny forretningslogikk her — alt tungt
arbeid (Resolve/Rank/TTL-cache/embedding) skjer i de allerede testede modulene; dette
laget serialiserer og feilhåndterer for HTTP.

Kjør: venv/bin/uvicorn api:app --reload --port 8420
"""
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import bank
from citation_gap import gap_kandidater
from cli import sok_og_ranger
from ranking import FAGTIDSSKRIFTER, NORSKE_FAGMILJOER, domene_naer

app = FastAPI(title="nefrokalsinose-sok API")


@app.get("/api/status")
def api_status():
    db = bank._db()
    n = db.execute("SELECT count(*) FROM papers").fetchone()[0]
    db.close()
    return {"papirer_cachet": n}


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


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
