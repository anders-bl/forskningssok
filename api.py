#!/usr/bin/env python3
"""api.py — FastAPI-laget som gjør cli.py/bank.py/citation_gap.py om til JSON-endepunkter
for en ekte nettflate (frontend/index.html). Ingen ny forretningslogikk her — alt tungt
arbeid (Resolve/Rank/TTL-cache/embedding) skjer i de allerede testede modulene; dette
laget serialiserer og feilhåndterer for HTTP.

Kjør: venv/bin/uvicorn api:app --reload --port 8420
"""
import logging
import hmac
import os
import re
import time
from dataclasses import asdict
from datetime import datetime, timezone

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

import bank
import rapport
import scoping
from adapters import openalex
from adapters.europe_pmc import DB as CACHE_DB
from citation_gap import gap_kandidater
from cli import sok_og_ranger
import domeneprofil
from domeneprofil import arts_naer_tekst, domene_naer_tekst
from evidensniva import evidensniva
from ranking import arts_naer, domene_naer, ranger

# Tom DSN = av, uten sentry_sdk.init — samme graceful mønster som rollesok/app/main.py.
# Lokalt er variabelen aldri satt, så utvikling er upåvirket; i Dokploy settes den i
# compose. traces_sample_rate=0: vi vil ha FEIL, ikke ytelsessporing — det siste ville
# sendt hver eneste request til en tredjepart uten at noen ba om det.
# Hvor mange kall på rad som må feile før en kilde regnes som nede. 3, ikke 1: et enkelt
# timeout er vær. Tallet er UKALIBRERT og dokumentert som det — det er valgt for å være
# tydelig lavt nok til å fange en ekte nedetid innen få søk, ikke målt mot en fordeling.
_KILDE_TERSKEL = 3

_GLITCHTIP_DSN = os.environ.get("GLITCHTIP_DSN", "")


def _skal_rapporteres(hendelse, hint):
    """Scoping-porten. Uten den fanger feilsporing enten for LITE eller for MYE.

    Taksonomien er bokbankens (`modernnetworkobservability` §The art of alerts):
    event → notification → alert → incident. Ikke alt som skjer er en alarm, og en kanal
    som roper på alt er like taus som en som aldri roper — målt i huset som 1851 uleste
    varsler hvorav ETT fra et menneske (konsepter/feil-synlighet §Den motsatte feilmodusen).

    Tre klasser, tre svar:

    1. VÆR — kilden er nede. Europe PMC 503, CORE timeout, ai-proxy uten svar. Vi reiser
       502/504 for dem, og det er RIKTIG oppførsel, ikke en defekt hos oss. Slippes ikke
       gjennom: EBI lå nede i dagevis i september, og hver eneste brukers søk ville blitt
       en hendelse.
    2. FORVENTET AVVISNING — 400/404/422. «Papiret er ikke cachet», «tom spørring».
       Brukerinput, ikke en bug. Slippes ikke gjennom.
    3. VÅR FEIL — alt annet: ufangede unntak, 500. Slippes gjennom.

    Den fjerde, som porten IKKE ser og som derfor rapporteres eksplisitt der den skjer:
    fanget svikt som degraderer noe brukeren merker. Embedderen som feiler gjør at
    varme-panelet og «Lignende» stille blir tomme — appen svarer 200 hele veien. Det er
    nøyaktig hullet Anders falt i, og en `except` uten rapportering er hvordan det ble
    usynlig."""
    for verdi in (hint or {}).values():
        if isinstance(verdi, HTTPException):
            return None if verdi.status_code < 500 or verdi.status_code in (502, 503, 504) else hendelse
    return hendelse


if _GLITCHTIP_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=_GLITCHTIP_DSN,
                    environment=os.environ.get("ENVIRONMENT", "production"),
                    traces_sample_rate=0,
                    before_send=_skal_rapporteres)

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
        # Etter 2026-09-04 er dette IKKE lenger «papirene gikk tapt». lagre() setter inn
        # radene FØR den embedder, så et unntak her betyr at embeddingen falt mens
        # cachingen — og dermed siteringen — står. Neste søk tar etterslepet via
        # embed_manglende(). Se bank.lagre for feilrapporten som drev fram delingen.
        logger.warning("bakgrunns-embedding feilet (papirene ER cachet og kan siteres; "
                       "etterslepet tas ved neste søk)", exc_info=True)
        # Rapporteres EKSPLISITT, fordi den er fanget og dermed usynlig for
        # before_send-porten: appen svarer 200 hele veien mens varme-panelet og
        # «Lignende» stille blir tomme. En `except` uten rapportering er nøyaktig
        # hvordan dette ble usynlig sist.
        _rapporter_degradering("bakgrunns-embedding")


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


def _rapporter_degradering(hva: str) -> None:
    """Send en FANGET svikt videre, med kontekst om hva brukeren mister.

    Stille no-op uten DSN, og den skal aldri kunne kaste — en feil i feilsporingen som
    velter forespørselen ville vært verre enn den opprinnelige feilen."""
    if not _GLITCHTIP_DSN:
        return
    try:
        import sentry_sdk
        with sentry_sdk.new_scope() as scope:
            scope.set_tag("degradering", hva)
            scope.set_level("warning")
            sentry_sdk.capture_exception()
    except Exception:
        logger.debug("kunne ikke rapportere degradering «%s»", hva, exc_info=True)


def _varm_stille(paper_id: str, hendelse: str) -> None:
    """Varme er et BIPRODUKT av at du bruker verktøyet — den skal aldri kunne velte
    handlingen som utløste den. En feilet varme-skriving (låst db, papir ikke cachet)
    logges og svelges; et sitat som ble lagret skal ikke bli et 500 fordi et
    relevanssignal ikke lot seg oppdatere."""
    try:
        bank.varm_opp(paper_id, hendelse)
    except Exception:
        logger.warning("varm_opp(%s, %s) feilet — handlingen selv er upåvirket",
                       paper_id, hendelse, exc_info=True)


def _evidens(tittel: str, abstract: str, pubtyper) -> dict:
    """Nivå OG kilde ut til flaten. Kilden er ikke pynt: «indeksert av NLM» er en påstand
    noen har stått inne for, «mønstergjenkjent» er vår heuristikk. Å sende bare nivået
    ville latt UI-et låne NLMs autoritet til vår egen gjetning."""
    niva, kilde = evidensniva(tittel, abstract, tuple(pubtyper or ()))
    return {"evidensniva": niva, "evidensniva_kilde": kilde}


# ---------- Helsesjekk etter HUSSTANDARDEN (konsepter/helsesjekk, ny-tjeneste-mal) ----------
# Jeg skrev først et eget /api/helse her. Det var `reimplementer-i-stedet-for-gjenbruk`
# (misc/feilantagelser 2026-08-29): standarden fantes i rollesok/app/health.py, arvet fra
# ny-tjeneste-mal, og var bedre enn min på tre punkter jeg ikke hadde tenkt på — tre nivåer
# i stedet for ett, application/health+json som medietype, og at /ready asserterer på
# INNHOLD og ikke bare på 200. Det siste er FDR-065-lærdommen: en monitor mot skallet
# melder GRØNT i nedetid.
#
# /health/live   lever prosessen? Aldri eksterne kall, aldri disk. Docker HEALTHCHECK.
# /health/ready  kan vi ta trafikk? Cachen må finnes OG ha papirer — en tom cache kan ikke
#                besvare et eneste søk, så det er fail, ikke warn.
# /health        full detalj. Uten nøkkel: kun status, ingen tall.
#
# Offentlig eksponering: Anders valgte å unnta helse-stien fra auth-gaten i Traefik, så
# Kuma slipper en hemmelighet. Derfor lekker /live og /ready NULL — ikke profilnavn, ikke
# antall papirer, ikke tjenestenavn. Tallene bor bak X-Internal-Key.
_HELSE_MEDIA = "application/health+json"


def _helse_sjekk() -> dict:
    """Cachen ER tjenesten: mangler fila eller er papers tom, kan ingen spørring besvares."""
    tid = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        db = bank._db(CACHE_DB)
        try:
            antall = db.execute("SELECT count(*) FROM papers").fetchone()[0]
        finally:
            db.close()
        if not antall:
            return {"componentType": "datastore", "status": "fail", "time": tid,
                    "output": "cachen er tom — ingen søk kan besvares ennå"}
        return {"componentType": "datastore", "status": "pass", "time": tid,
                "observedValue": {"papirer": antall, "profil": domeneprofil.NAVN}}
    except Exception as e:
        return {"componentType": "datastore", "status": "fail", "time": tid,
                "output": f"{type(e).__name__}: {e}"}


def _helse_svar(payload: dict):
    return JSONResponse(payload, status_code=503 if payload["status"] == "fail" else 200,
                        media_type=_HELSE_MEDIA)


def _helse_kilder() -> dict:
    """Kilde-nåbarhet fra PASSIV observasjon — ingen utgående kall.

    WARN, aldri FAIL. En nede kilde er ikke vår nedetid: cachen svarer fortsatt, sitatbanken
    virker, «Lignende» virker. Å la Europe PMC-nedetid gjøre /ready rød ville vekket Anders
    for en annens driftsavbrudd — og EBI lå nede i DAGEVIS i september.

    Tom tabell gir «pass», ikke «warn»: ingen søk kjørt ennå er ikke et tegn på at noe er
    galt. Det er den tredje tilstanden, og den skal ikke leses som en av de to andre."""
    tid = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        status = bank.kilde_status()
    except Exception:
        # Kilde-leddet leser samme database som cache-leddet. Er den død, har cache-sjekken
        # ALT meldt fail — dette leddet skal da si «kunne ikke måle», ikke kaste og gjøre
        # en 503 om til en 500. Fanget av test_ready_er_503_naar_cachen_ikke_er_lesbar.
        return {"componentType": "system", "status": "warn", "time": tid,
                "output": "kunne ikke lese kilde-status (samme db som cachen)"}
    nede = [k for k in status if k["feil_paa_rad"] >= _KILDE_TERSKEL]
    if not nede:
        return {"componentType": "system", "status": "pass", "time": tid}
    return {"componentType": "system", "status": "warn", "time": tid,
            "output": "; ".join(f"{k['kilde']}: {k['feil_paa_rad']} feil på rad "
                                f"({(k['siste_feilmelding'] or '')[:60]})" for k in nede)}


def _helse_bygg() -> dict:
    sjekk = _helse_sjekk()
    kilder = _helse_kilder()
    statuser = {sjekk["status"], kilder["status"]}
    samlet = "fail" if "fail" in statuser else ("warn" if "warn" in statuser else "pass")
    return {"status": samlet,
            "checks": {"cache:innhold": [sjekk], "kilder:naabarhet": [kilder]}}


@app.get("/health/live")
def health_live():
    """Lever prosessen? Ingen disk, ingen nettverk — svarer så lenge uvicorn kjører."""
    return JSONResponse({"status": "pass"}, media_type=_HELSE_MEDIA)


@app.get("/health/ready")
def health_ready():
    """Kan vi ta trafikk? Asserterer på INNHOLD, ikke bare at endepunktet svarer.
    Dette er stien en oppetidsmonitor skal peke på."""
    return _helse_svar({"status": _helse_bygg()["status"]})


@app.get("/health")
def health_detail(x_internal_key: str = Header(None)):
    """Full detalj bak portalens delte INTERNAL_API_KEY. Uten nøkkel: kun status —
    samme svar som /ready, så et offentlig kall aldri lekker tall."""
    payload = _helse_bygg()
    nokkel = os.environ.get("INTERNAL_API_KEY", "")
    if nokkel and x_internal_key and hmac.compare_digest(x_internal_key, nokkel):
        return _helse_svar(payload)
    return _helse_svar({"status": payload["status"]})


@app.get("/api/profil")
def api_profil():
    """Fagfeltet flaten skal beskrive seg selv med. Uten dette endepunktet sto ni steder
    i frontend/index.html med ordet «laks» hardkodet — altså de stedene en profilbytte
    garantert ville glemt, og som ville fortsatt påstå fiskehelse for en bruker i et
    annet fagfelt uten at noe feilet."""
    return domeneprofil.for_frontend()


@app.get("/api/status")
def api_status():
    """Helse-flate for mennesker og for et eventuelt overvåkingskall.

    Kartlagt 2026-09-04 hva som FAKTISK dekker denne tjenesten, i stedet for å bygge en
    fjerde sjekk oppå tre eksisterende:
      - crash-loop:  silverbullet/ops/container_helse.py, cron på noden hvert 10. min,
                     leser `docker ps -a` og dekker dermed enhver container — også denne.
      - HTTP oppe:   Uptime Kuma (se container_helse sin egen docstring om arbeidsdelingen).
      - feil INNE i appen: var udekket til GlitchTip ble koblet inn samme dag. Det var
                     hullet Anders falt i: containeren frisk, forsiden 200, og siteringen
                     feilet likevel. Verken restart-telling eller en HTTP-sjekk kan se det.

    Docstringen sa «tenkt som pluggbar sjekk for kommandosenter.py, koblet ikke inn» fra
    2026-09-02 til 09-04. Den koblingen er IKKE bygget, og bør trolig ikke bygges:
    kommandosenteret diagnostiserer Anders' Mac, mens denne tjenesten kjører på Netcup.
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
            # /references er en EGEN delressurs med eget oppetid, og den har vært 503
            # sammenhengende siden 2026-09-02. Uten denne linjen sa panelet «Europe PMC —
            # nåbar nå» mens gap-rapportene samtidig skrev «kilde: openalex + crossref»,
            # og de to utsagnene motsa hverandre uten at noen av dem var direkte usanne.
            # Én kilde kan være halvveis oppe, og da skal flaten vise nettopp det.
            "europe_pmc_referanser": _kilde_naabar(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/MED/41363532/references?format=json&pageSize=1"),
            "openalex": _kilde_naabar("https://api.openalex.org/works/W2151543183"),
            "core": _kilde_naabar("https://api.core.ac.uk/v3/search/works"),
            "crossref": _kilde_naabar("https://api.crossref.org/works/10.1111/jfd.70099"),
        },
    }


@app.get("/api/sok")
def api_sok(q: str, background_tasks: BackgroundTasks, n: int = 20):
    if not q.strip():
        raise HTTPException(400, "tom spørring")
    try:
        papirer, eksakt_id, kilder = sok_og_ranger(q, page_size=max(n, 20))
    except RuntimeError as e:
        # Bokfør at det EKTE kallet feilet, før vi svarer. Passiv observasjon: hvert søk
        # et menneske gjør er allerede en prøve på om kilden lever, og den er gratis.
        paa_rad = bank.registrer_kildekall("europe_pmc", False, str(e))
        if paa_rad == _KILDE_TERSKEL:
            # KANT, ikke nivå: rapporter når terskelen KRYSSES, ikke hver gang den
            # vedvarer. En kilde som er nede i tre dager skal gi én hendelse, ikke tusen.
            _rapporter_degradering(f"kilde europe_pmc nede ({paa_rad} feil på rad)")
        raise HTTPException(502, f"Europe PMC utilgjengelig: {e}") from e
    bank.registrer_kildekall("europe_pmc", True)
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
            "papirer": [{**asdict(p), "id": p.id, "domene_naer": domene_naer(p), "arts_naer": arts_naer(p), **_evidens(p.tittel, p.abstract, p.pubtyper)} for p in papirer[:n]]}


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
    papir.update(_evidens(papir["tittel"], papir["abstract"], ()))
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
def api_emne_utforsk(emne_id: str, background_tasks: BackgroundTasks, navn: str = "", n: int = 20):
    """Søk-doktrinens tredje modus («Utforskning» — vet domenet, ikke termen). Alle
    OpenAlex-verk under ETT emne, rangert med samme ADR-013-logikk (domene-nærhet FØR
    rå siteringstall) som resten av appen — ikke OpenAlex sin egen citation-sortering
    urørt, som ville gitt de samme gamle kanoniske artiklene uansett emne."""
    try:
        papirer = openalex.verk_for_emne(emne_id, limit=n)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    rangert = ranger(papirer)
    # BackgroundTask, ikke synkront — SAMME 2026-09-04-fiks som /api/sok (se _lagre_bakgrunn):
    # bank.lagre() sitt embed_fn kan ta opptil 120s, og emne-funnene trenger den ALDRI for å
    # vises. Denne ruta ble oversett da fiksen først landet på /api/sok — funnet ved en
    # Six-Hats-sveip av hele filen etter samme mønster, ikke ved gjentatt symptom.
    background_tasks.add_task(_lagre_bakgrunn, rangert)
    return {"emne_id": emne_id, "emne_navn": navn,
            "papirer": [{**asdict(p), "id": p.id, "domene_naer": domene_naer(p), "arts_naer": arts_naer(p), **_evidens(p.tittel, p.abstract, p.pubtyper)} for p in rangert[:n]]}


@app.get("/api/sitater")
def api_sitater_liste(paper_id: str | None = None, utkast_id: int | None = None,
                       kun_lose: bool = False):
    return bank.hent_sitater(paper_id, utkast_id=utkast_id, kun_lose=kun_lose)


@app.post("/api/sitater")
def api_sitater_lagre(body: dict):
    """`utkast_id` er valgfri — er dokumentskuffen åpen sender frontend den med, og
    sitatet lander i dokumentet med én gang. Uten den blir det et løst sitat (se
    bank.lagre_sitat sin docstring for hvorfor det ikke er en degradering)."""
    paper_id = body.get("paper_id", "")
    tekst = (body.get("tekst") or "").strip()
    if not paper_id or not tekst:
        raise HTTPException(400, "paper_id og tekst er påkrevd")
    try:
        sitat = bank.lagre_sitat(paper_id, tekst, body.get("kommentar", ""), body.get("utkast_id"))
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    # Varmen legges HER, ikke i frontend: en sitering er den sterkeste handlingen i
    # verktøyet, og den skal telle likt uansett hvilken flate som utløste den.
    _varm_stille(paper_id, "sitert")
    return sitat


@app.patch("/api/sitater/{sitat_id}")
def api_sitater_oppdater(sitat_id: int, body: dict):
    """To uavhengige felt på samme rad: «kommentar» (redigering) og «utkast_id»
    (feste/løsne mot et dokument). utkast_id=null er en GYLDIG verdi — «løsne» — så
    tilstedeværelsen av nøkkelen, ikke sannhetsverdien, avgjør om den skrives."""
    endret = False
    if "kommentar" in body:
        endret = bank.oppdater_sitat(sitat_id, body.get("kommentar", "")) or endret
    if "utkast_id" in body:
        endret = bank.knytt_sitat(sitat_id, body["utkast_id"]) or endret
        if endret and body["utkast_id"] is not None:
            traff = [s for s in bank.hent_sitater() if s["id"] == sitat_id]
            if traff:
                _varm_stille(traff[0]["paper_id"], "dokument")
    if not endret:
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


@app.post("/api/varme")
def api_varme_legg(body: dict):
    """Frontend melder inn de svake signalene (åpnet et papir). De sterke («sitert»,
    «dokument») legges server-side der handlingen skjer, ikke herfra."""
    paper_id = (body.get("paper_id") or "").strip()
    hendelse = body.get("hendelse", "apnet")
    if not paper_id:
        raise HTTPException(400, "paper_id er påkrevd")
    if hendelse not in ("apnet",):
        raise HTTPException(400, f"«{hendelse}» settes ikke utenfra")
    _varm_stille(paper_id, hendelse)
    return {"ok": True}


@app.get("/api/varme")
def api_varme(tekst: str = "", k: int = 12):
    """Relevanspanelet, TO LAG SLÅTT SAMMEN MEN ALDRI BLANDET (Anders' valg 2026-09-04).

    - `varig`: akkumulert bruk over tid (bank.varmeliste) — hukommelse, overlever
      dokumentbytte og omstart.
    - `naa`: semantisk avstand mot SITATENE dine samlet (bank.lignende_tekst). Fram til
      2026-09-04 var kilden dokumenteditorens tekst; da sitatbanken erstattet skuffen ble
      den sitatene, som er en bedre kilde uansett — et sitat er noe du aktivt plukket ut,
      mens et utkast også bærer tenking som ikke er en påstand om litteraturen.

    Hvert kort bærer BEGGE tallene, og `aarsaker` sier hvilke av dem som faktisk
    løftet det. Et papir som er varmt av gammel bruk, men fjernt fra det du skriver nå,
    skal se annerledes ut enn ett som er nær nå men aldri rørt — å slå dem sammen til
    ett tall ville skjult nettopp forskjellen som gjør panelet lesbart.

    De to stolpene har BEVISST ULIK skala, fordi de to tallene er ulike slags tall:

    - `varig_andel` er relativ (mot listas egen maks). Varmepoeng har ingen enhet — «7,3»
      betyr ingenting alene, «varmest av det du har» betyr noe.
    - `naa_andel` er ABSOLUTT (1 - avstand/2, over L2-rommets 0..2). Den var først
      normalisert mot maks som varig-laget, og det var målbart en løgn: live 2026-09-04
      lå de tolv kandidatene på avstand 0.955–1.002, altså ~5 % spredning, og
      maks-normaliseringen tegnet dem ALLE som nesten fulle stolper. Panelet påstod
      «alt er brennhett» der sannheten var «alt ligger middels nær, og omtrent like
      nær». Med absolutt skala står de nå på ~halv stolpe, og et faktisk nært treff
      (avstand 0.2 → 0.9) skiller seg ut fordi det ER annerledes, ikke fordi det tilfeldig
      var best i en flat gruppe."""
    varig = bank.varmeliste(k=k)
    naa = bank.lignende_tekst(tekst, k=k) if (tekst or "").strip() else []

    maks_poeng = max((v["poeng"] for v in varig), default=0.0)
    # Nærheten snus fra avstand: L2 er lavere=bedre, og et panel der den lengste stolpen
    # betyr «fjernest» ville løyet visuelt uansett hvilken skala den ellers hadde.
    naerhet = {n["id"]: max(0.0, 1.0 - n["avstand"] / 2.0) for n in naa}

    samlet: dict[str, dict] = {}
    for v in varig:
        samlet[v["id"]] = {**v, "avstand": None, "varig": v["poeng"], "naa": 0.0,
                            "aarsaker": [_varme_aarsak(v["sterkeste_hendelse"])]}
    for n in naa:
        rad = samlet.setdefault(n["id"], {**n, "poeng": 0.0, "sterkeste_hendelse": None,
                                          "varig": 0.0, "aarsaker": []})
        rad["avstand"] = n["avstand"]
        rad["naa"] = naerhet[n["id"]]
        # «det du har sitert», ikke «det du skriver nå». Teksten laget måles mot kom fra
        # dokumenteditoren til 2026-09-04; da sitatbanken erstattet skuffen ble kilden
        # sitatene dine, og årsaksstrengen ville ellers påstått noe om en flate som ikke
        # finnes lenger. Et kort som navngir feil kilde er verre enn et uten årsak.
        rad["aarsaker"] = rad["aarsaker"] + ["nær det du har sitert"]

    for rad in samlet.values():
        rad["varig_andel"] = round(rad["varig"] / maks_poeng, 3) if maks_poeng else 0.0
        rad["naa_andel"] = round(rad["naa"], 3)

    rader = sorted(samlet.values(),
                   key=lambda r: (not r["domene_naer"], not r["arts_naer"],
                                  -(r["varig_andel"] + r["naa_andel"])))
    return {"papirer": rader[:k], "har_naa_lag": bool(naa)}


_VARME_AARSAK = {
    "sitert": "du siterte det",
    "dokument": "du festet det til et dokument",
    "apnet": "du har lest det",
    "nabo": "nabo av noe du siterte",
}


def _varme_aarsak(hendelse: str | None) -> str:
    return _VARME_AARSAK.get(hendelse or "", "brukt tidligere")


@app.get("/api/rapport/dokument")
def api_rapport_dokument(utkast_id: int, format: str = "md"):
    """Dokumentet slik det står — brødteksten din PLUSS sitatene som er festet til det,
    med full kildehenvisning. Dette er filen Ulven faktisk deler videre, og den er derfor
    den eneste rapporten som blander egen tekst med sitert tekst; blokk-typene holder de
    to fra hverandre visuelt i begge formater (se rapport.dokument_blokker)."""
    utkast = bank.hent_utkast(utkast_id)
    if not utkast:
        raise HTTPException(404, "utkast finnes ikke")
    sitater = bank.hent_sitater(utkast_id=utkast_id)
    blokker = rapport.dokument_blokker(utkast, sitater)
    return _rapport_svar(blokker, format, utkast["tittel"], utkast["tittel"])


@app.get("/api/sitatbank")
def api_sitatbank():
    """Sitatbanken: alle sitater gruppert på papir. Grupperingen på papir krever ingen
    embedding og er alltid sann — den semantiske relasjonen ligger i /api/relaterte ved
    siden av, så en nede embedder gjør banken tregere å utforske, aldri utilgjengelig."""
    return {"papirer": bank.sitatbank()}


@app.get("/api/relaterte/{paper_id:path}")
def api_relaterte(paper_id: str, k: int = 5):
    """«Relasjonelle sitater» — papirer DU HAR SITERT som ligger semantisk nær dette.
    Det er det ingen referansehåndterer gjør: Zotero og EndNote er arkivskap som ikke aner
    at to sitater handler om det samme. Ærlig tom liste hvis papiret mangler vektor."""
    return {"relaterte": bank.relaterte_sitater(paper_id, k=k)}


@app.get("/api/rapport/boilerplate/{paper_id:path}")
def api_rapport_boilerplate(paper_id: str, format: str = "md", k: int = 5):
    """Åpner et papir og dets semantiske naboer i sitatbanken SAMLET som ett
    arbeidsdokument — alt som kan utledes er utledet, og bare tenkingen står tom."""
    kilde = bank.hent(paper_id)
    if not kilde:
        raise HTTPException(404, f"{paper_id} er ikke cachet")
    relaterte = bank.relaterte_sitater(paper_id, k=k)
    per_papir: dict[str, list] = {}
    for pid in [paper_id] + [r["id"] for r in relaterte]:
        per_papir[pid] = bank.hent_sitater(pid)
    tittel = f"Arbeidsnotat — {kilde.get('tittel') or paper_id}"
    blokker = rapport.boilerplate_blokker(kilde, relaterte, per_papir, tittel=tittel)
    return _rapport_svar(blokker, format, tittel, tittel)


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
    if format in ("bib", "ris", "csl"):
        # csl = CSL-JSON, inngangen til Citation Style Language og dermed til 10 000+
        # ferdige tidsskriftstiler via en hvilken som helst citeproc (Zotero, Pandoc,
        # citeproc-js). Lagt til 2026-09-04 ved siden av BibTeX/RIS, som er
        # UTVEKSLINGSformater — CSL-JSON er RENDRINGSformatet.
        tekst = {"bib": rapport.til_bibtex, "ris": rapport.til_ris,
                 "csl": rapport.til_csl_json}[format](papirer)
        media = {"bib": "application/x-bibtex",
                 "ris": "application/x-research-info-systems",
                 "csl": "application/vnd.citationstyles.csl+json"}[format]
        filending = "json" if format == "csl" else format
        return Response(tekst.encode("utf-8"), media_type=f"{media}; charset=utf-8",
                         headers={"Content-Disposition": f'attachment; filename="{_slug(tittel)}.{filending}"'})
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
