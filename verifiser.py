"""verifiser.py — «verifiser denne påstanden mot web-kilder» (FDR-028, gjenbrukt).

Ulven krever «hard empiri». Verktøyet viser ellers KUN rå litteratur — aldri en
LLM-parafrase (README §Om, `fag_sok.py`-disiplinen). Denne modulen er det ene stedet det
finnes en LLM-syntese, og den er derfor bygget som et STRENGT AVGRENSET, tydelig merket
lag ved siden av søket — aldri blandet inn i det rå treffet.

Ingenting av dette er nytt i huset. `ai-proxy`s `/research`-endepunkt (FDR-028) gjør
allerede jobben: påstand → EU-direkte Mistral med web_search → verdikt + kilder,
budsjettsporet per `wiki_id`, ingen US-transit-fallback. Portalen kaller det alt fra
`note_verify.py`/`research.py`. Vi arver mønsteret; vi bygger ikke en andre klient.

**Kjernedisiplinen, arvet ordrett fra FDR-028:** et verdikt UTEN kilder er «uverifisert»,
ikke et falskt grønt flagg. Mistral svarer noen ganger fra egen trening uten å faktisk
kalle web_search — da er kildelista tom, og det er RIKTIG å vise fram som «modellen hentet
ingen kilder», ikke som en bekreftelse. `verifisert` i svaret er `bool(kilder)`, aldri en
egen påstand.

Kall-stilen er SYNKRON httpx (`bank._ai_proxy_embed`-mønsteret), ikke portalens async —
forskningssøk sine handlere er bevisst synkrone (CLAUDE.md), og et andre paradigme her
ville vært en avviker uten grunn.
"""
import os

import httpx


def tilgjengelig() -> bool:
    """Er verifiser-veien i det hele tatt konfigurert? Kun sann i Dokploy-miljøet, der
    AI_PROXY_URL peker på ai-proxy over dokploy-network. Lokalt (Anders' Mac) er den av,
    samme bryter som embeddingen — flaten skal da si det, ikke feile stygt."""
    return bool(os.environ.get("AI_PROXY_URL"))


def verifiser(paastand: str, *, post_fn=None) -> dict:
    """Påstand → {verdikt, kilder, verifisert}.

    `verifisert` er bool(kilder) og ikke noe modellen sier: FDR-028 krever at et verdikt
    uten hentede kilder leses som uverifisert. Kaster RuntimeError ved manglende konfig
    eller ai-proxy-feil — aldri et stille tomt svar, som ville sett ut som «ingenting å
    verifisere» der sannheten er «vi klarte ikke å spørre».

    post_fn injiseres i test (suiten er nettverksfri per kontrakt, CLAUDE.md §Testing).
    """
    paastand = (paastand or "").strip()
    if len(paastand) < 8:
        raise RuntimeError("påstanden er for kort til å verifiseres")
    url = os.environ.get("AI_PROXY_URL")
    if not url:
        raise RuntimeError("verifisering krever AI_PROXY_URL (kun satt i Dokploy) — "
                           "utilgjengelig lokalt, samme som embeddingen")
    wiki_id = os.environ.get("AI_PROXY_WIKI_ID", "forskningssok")
    post = post_fn or httpx.post
    try:
        # 180s: web_search-kall er trege. ai-proxy rate-limiter selv til 5/min per wiki_id
        # (FDR-028), så vi trenger ingen egen grense — men en 429 derfra skal forplantes
        # som en ærlig «prøv igjen om litt», ikke svelges.
        r = post(url.rstrip("/") + "/research",
                 json={"wiki_id": wiki_id, "claim": paastand}, timeout=180)
    except httpx.HTTPError as e:
        raise RuntimeError(f"ai-proxy utilgjengelig: {e}") from e
    if r.status_code == 429:
        raise RuntimeError("verifisering er rate-limitert (5/min) — prøv igjen om litt")
    if r.status_code != 200:
        raise RuntimeError(f"ai-proxy /research feilet ({r.status_code}): {r.text[:160]}")
    try:
        data = r.json()
    except ValueError as e:
        raise RuntimeError(f"ai-proxy returnerte ugyldig JSON: {e}") from e

    verdikt = (data.get("verdict") or "").strip()
    kilder = [k for k in (data.get("sources") or []) if k.get("url")]
    return {
        "verdikt": verdikt,
        "kilder": kilder,
        # Den bærende linjen: sann KUN hvis modellen faktisk hentet kilder. Et verdikt
        # uten kilder er en påstand fra treningsdata, ikke en verifisering.
        "verifisert": bool(kilder),
    }
