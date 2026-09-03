#!/usr/bin/env python3
"""api.py — FastAPI-laget som gjør cli.py/bank.py/citation_gap.py om til JSON-endepunkter
for en ekte nettflate (frontend/index.html). Ingen ny forretningslogikk her — alt tungt
arbeid (Resolve/Rank/TTL-cache/embedding) skjer i de allerede testede modulene; dette
laget serialiserer og feilhåndterer for HTTP.

Kjør: venv/bin/uvicorn api:app --reload --port 8420
"""
import logging
import re
import time
from dataclasses import asdict

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

import bank
import rapport
import scoping
from adapters import openalex
from adapters.europe_pmc import DB as CACHE_DB
from citation_gap import gap_kandidater
from cli import sok_og_ranger
from domeneprofil import arts_naer_tekst, domene_naer_tekst
from evidensniva import evidensniva
from ranking import arts_naer, domene_naer, ranger

app = FastAPI(title="forskningssok API")
logger = logging.getLogger("forskningssok")


def _lagre_bakgrunn(papirer: list) -> None:
    """Wrapper rundt bank.lagre for BackgroundTasks — fanger ALT. lagre() sin egen
    docstring lover «feiler stille aldri kritisk», men en ufanget exception i en
    BackgroundTask propagerer likevel opp til ASGI-serveren (uvicorn logger den som en
    krasjet request, selv om klienten alt har fått sitt 200-svar) — dette gjør løftet
    ekte, ikke bare en kommentar."""
    try:
        bank.lagre(papirer)
    except Exception:
        logger.warning("bakgrunns-lagre() feilet (søkeresultatet er alt levert)", exc_info=True)


def _slug(tekst: str) -> str:
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9æøå]+", "-", tekst.lower()))


def _rapport_svar(blokker: list[rapport.Blokk], format: str, filnavn_stem: str, tittel: str = ""):
    """Delt av alle fire rapport-endepunktene — se rapport.py sin moduldocstring for
    hvorfor Blokk-listen er det eneste malene bygger, og hvorfor formatvalget bor HER
    (ett sted som vet om HTTP/nedlasting) og ikke i rapport.py (som forblir ren)."""
    if format == "pdf":
        pdf = rapport.til_pdf_bytes(blokker, tittel=tittel)
        return Response(pdf, media_type="application/pdf",
                         headers={"Content-Disposition": f'attachment; filename="{_slug(filnavn_stem)}.pdf"'})
    return PlainTextResponse(rapport.til_markdown(blokker), media_type="text/markdown; charset=utf-8")


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
            "core": _kilde_naabar("https://api.core.ac.uk/v3/search/works"),
        },
    }


@app.get("/api/sok")
def api_sok(q: str, background_tasks: BackgroundTasks, n: int = 20):
    if not q.strip():
        raise HTTPException(400, "tom spørring")
    try:
        papirer, eksakt_id, kilder = sok_og_ranger(q, page_size=max(n, 20))
    except RuntimeError as e:
        raise HTTPException(502, f"Europe PMC utilgjengelig: {e}") from e
    # lagre() (cache/embed for fremtidig --lignende-søk) kjører ETTER at responsen er
    # sendt, ikke før — embed_fn kan ta opptil 120s (ekte AI-proxy-kall), og brukeren
    # trenger ALDRI den bivirkningen for å se søkeresultatet sitt. Å blokkere responsen
    # på den var reell årsak til at ferske søk så ut som de hang (målt live 2026-09-04),
    # og til at et utålmodig reload rakk å starte et kappløpende, dupliserende søk mot
    # samme cache-rader (se bank.py sin lagre()-fiks samme kveld).
    background_tasks.add_task(_lagre_bakgrunn, papirer)
    # asdict() dropper .id — det er en @property (utledet doi/pmid-fallback), ikke et
    # dataclass-felt. Fanget som ekte bug live 2026-09-02: uten dette fikk hvert papir
    # id:undefined i frontend, og «siste skrevet vinner»-kollisjonen åpnet alltid det
    # SISTE søkeresultatet uansett hvilket man klikket på.
    return {"query": q, "eksakt_id": eksakt_id, "kilder": kilder,
            "papirer": [{**asdict(p), "id": p.id, "domene_naer": domene_naer(p), "arts_naer": arts_naer(p), "evidensniva": evidensniva(p.tittel, p.abstract)} for p in papirer[:n]]}


@app.get("/api/papir/{paper_id:path}")
def api_papir(paper_id: str):
    papir = bank.hent(paper_id)
    if not papir:
        raise HTTPException(404, f"{paper_id} er ikke cachet — søk det opp først")
    # Kaller de DELTE funksjonene direkte (ikke en egen inline-reimplementasjon) — en
    # tidligere duplisert versjon her IKKE fikk med seg salmon-calcitonin-fiksen i
    # domeneprofil.py:arts_naer_tekst (funnet live 2026-09-02, samme kveld den ble lagt
    # til) fordi den regnet på ARTSTERMER selv i stedet for å kalle funksjonen.
    papir["domene_naer"] = domene_naer_tekst(f"{papir['forfattere']} {papir['tidsskrift']}")
    papir["arts_naer"] = arts_naer_tekst(f"{papir['tittel']} {papir['abstract']}")
    papir["evidensniva"] = evidensniva(papir["tittel"], papir["abstract"])
    return papir


@app.get("/api/lignende/{paper_id:path}")
def api_lignende(paper_id: str, k: int = 6):
    return {"paper_id": paper_id, "naboer": bank.lignende(paper_id, k=k)}


@app.get("/api/gap/{paper_id:path}")
def api_gap(paper_id: str, k: int = 10):
    papir = bank.hent(paper_id)
    if not papir:
        raise HTTPException(404, f"{paper_id} er ikke cachet — søk det opp først")
    if not papir["pmid"] and not papir["doi"]:
        raise HTTPException(422, "papiret mangler både PMID og DOI — ingen referanse-kilde tilgjengelig")
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


@app.get("/api/tilgang/{paper_id:path}")
def api_tilgang(paper_id: str):
    """Lisens/fri-PDF/utgiver — erstatter det opprinnelig foreslåtte "koble til
    bruktsøk"-sporet, se adapters/openalex.py:tilgang sin docstring for hvorfor. Kun for
    papirer med DOI (OpenAlex slår opp på DOI) — ærlig tomt objekt for resten, ALDRI en
    404/feil for noe som bare mangler forutsetningen."""
    tomt = {"lisens": None, "fri_pdf_url": None, "utgiver": None, "oa_status": None}
    if not paper_id.startswith("10."):
        return tomt
    try:
        return openalex.tilgang(paper_id)
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
            "papirer": [{**asdict(p), "id": p.id, "domene_naer": domene_naer(p), "arts_naer": arts_naer(p), "evidensniva": evidensniva(p.tittel, p.abstract)} for p in rangert[:n]]}


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


@app.delete("/api/sitater/{sitat_id}")
def api_sitater_slett(sitat_id: int):
    if not bank.slett_sitat(sitat_id):
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


@app.delete("/api/utkast/{utkast_id}")
def api_utkast_slett(utkast_id: int):
    if not bank.slett_utkast(utkast_id):
        raise HTTPException(404, "utkast finnes ikke")
    return {"ok": True}


@app.get("/api/relevans")
def api_relevans(tekst: str, k: int = 4):
    """FDR-038 ambient-modus: teksten Ulven skriver akkurat nå → nærmeste papirer i
    cachen. For kort tekst eller tom cache → ærlig tom liste (bank.lignende_tekst()
    sitt eget kontraktsvar), ALDRI en feil — en «gir ingenting»-respons her SKAL se ut
    som stillhet, ikke en 4xx/5xx."""
    return {"naboer": bank.lignende_tekst(tekst, k=k)}


@app.get("/api/rapport/kildesamling")
def api_rapport_kildesamling(ids: str, tittel: str = "Kildesamling", format: str = "md"):
    """Eksport av et papirutvalg (Markdown/PDF/BibTeX/RIS, se rapport.py). `ids` =
    kommaseparerte cache-id-er (typisk et helt søkeresultat, sendt fra frontend).
    Ukjente/ikke-cachede id-er droppes ærlig (samme prinsipp som ellers), ALDRI en feil
    for én manglende blant mange gyldige — kun tom hvis INGEN av dem var cachet.

    format=bib/ris svarer på «sitasjonsformatering er fortsatt uløst» (Anders 2026-09-02):
    ikke pen tekst til manuell liming, men en fil Zotero/EndNote leser NATIVT — se
    rapport.py:til_bibtex/til_ris sin docstring."""
    id_liste = [i.strip() for i in ids.split(",") if i.strip()]
    if not id_liste:
        raise HTTPException(400, "ingen id-er oppgitt")
    papirer = [p for p in (bank.hent(i) for i in id_liste) if p]
    if not papirer:
        raise HTTPException(404, "ingen av de oppgitte id-ene er cachet")
    if format in ("bib", "ris"):
        tekst = rapport.til_bibtex(papirer) if format == "bib" else rapport.til_ris(papirer)
        media = "application/x-bibtex" if format == "bib" else "application/x-research-info-systems"
        return Response(tekst.encode("utf-8"), media_type=f"{media}; charset=utf-8",
                         headers={"Content-Disposition": f'attachment; filename="{_slug(tittel)}.{format}"'})
    blokker = rapport.kildesamling_blokker(papirer, tittel=tittel)
    return _rapport_svar(blokker, format, tittel, tittel)


@app.get("/api/rapport/sitatnotater")
def api_rapport_sitatnotater(tittel: str = "Sitatnotater", format: str = "md"):
    """Hele leseloggen (ALLE lagrede sitater, ikke filtrert på ett papir) som ett
    dokument — se rapport.py:sitatnotater_blokker."""
    sitater = bank.hent_sitater()
    blokker = rapport.sitatnotater_blokker(sitater, tittel=tittel)
    return _rapport_svar(blokker, format, tittel, tittel)


@app.get("/api/rapport/gap/{paper_id:path}")
def api_rapport_gap(paper_id: str, format: str = "md", k: int = 10):
    """Delbar versjon av citation-gap-testen (Aaron Tay-proben) for ett papir — samme
    422/502-disiplin som /api/gap, se den for hvorfor PMID ikke lenger er påkrevd."""
    papir = bank.hent(paper_id)
    if not papir:
        raise HTTPException(404, f"{paper_id} er ikke cachet — søk det opp først")
    if not papir["pmid"] and not papir["doi"]:
        raise HTTPException(422, "papiret mangler både PMID og DOI — ingen referanse-kilde tilgjengelig")
    try:
        resultat = gap_kandidater(paper_id, papir["kilde_kode"] or "MED", papir["pmid"], k=k)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    tittel = f"Citation-gap: {papir['tittel']}"
    blokker = rapport.gap_rapport_blokker(papir, resultat, tittel=tittel)
    return _rapport_svar(blokker, format, tittel, tittel)


@app.get("/api/rapport/omfang")
def api_rapport_omfang(tekst: str, tittel: str = "Omfang-rapport", format: str = "md"):
    """Akse-dekning + kandidater FRA EGEN CACHE for tynt dekkede akser (ingen nye
    eksterne kall — samme ADR-004-disiplin, gjenbruker bank.lignende_tekst() på et
    syntetisk søk bygget av aksens eget nøkkelordsett)."""
    akser = scoping.akse_dekning(tekst)
    forslag = {}
    for akse, dekning in akser.items():
        if dekning >= 1.0:
            continue
        synonym_tekst = akse + " " + " ".join(scoping.AKSER[akse])
        kandidater = bank.lignende_tekst(synonym_tekst, k=3)
        if kandidater:
            forslag[akse] = kandidater
    blokker = rapport.omfang_rapport_blokker(akser, forslag, tittel=tittel)
    return _rapport_svar(blokker, format, tittel, tittel)


@app.get("/api/omfang")
def api_omfang(tekst: str):
    """Akse-dekning for Omfang-fanen — se scoping.py for hvorfor dette er en bevisst
    enkel nøkkelord-heuristikk, ikke en semantisk klassifikator."""
    return {"akser": scoping.akse_dekning(tekst)}


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
