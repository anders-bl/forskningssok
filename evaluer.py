"""evaluer.py — setter rangeringen riktig papir øverst? Et LOKALT måleinstrument.

Fase-2-hullet i veikartet: 336 tester bekrefter at mekanismene OPPFØRER SEG, og null måler
om `ranking.py` faktisk er GOD. Dette er instrumentet, bygget etter husets dommer-disiplin
(`dommer_kort`, `positiv-kontroll-per-detektor`, gjerdets-akse): en UAVHENGIG dommer, ikke
mitt eget skjønn, med en positiv kontroll som VOIDER målingen hvis dommeren svikter.

**Lokalt, aldri deployert.** Dommeren er husets lokale Ollama (`_ollama_port.kall_dommer`,
gjenbrukt for num_ctx-disiplinen — default 4096 trunkerer stille). Ollama bor på
hjemme-flåtenoden, ikke på Netcup, så dette kjører kun på Anders' Mac — samme grunn som
`bank._hus_embed`s lokale gren. Gratis, ingen abonnement, ingen per-kall-kost.

**Tre disipliner bakt inn, alle dyrekjøpt i huset:**

1. **Dommeren er BLIND for rangeringen.** Prompten får kun spørring + tittel + abstract,
   aldri `ranking.py`s plassering eller score. Ellers måler vi om dommeren kan gjenta
   rangeringen, ikke om rangeringen er god.
2. **Positiv kontroll som gate.** Dommeren må skille et ekte fiskehelse-papir fra
   species-trap-fella (menneske-nefrokalsinose, samme ord, feil art) FØR hovedmålingen
   telles. Feiler den den, er den lurt av nøyaktig fella `ranking.py` bander mot, og
   konkordans-tallet er verdiløst — samme rolle som «salmon calcitonin» i citation-gap.
3. **Forhåndsregistrert terskel.** Bestått-grensen står som konstant med begrunnelse,
   valgt FØR første kjøring. Ikke iterert til tallet ser bra ut (felle 47/50).
"""
import re
from pathlib import Path

# Firetrinns relevansskala, TREC-inspirert. Bevisst grov: en dommer som må velge mellom
# fire nivåer er mer pålitelig enn en som gir en kontinuerlig score den ikke kan forsvare.
SKALA = {0: "irrelevant", 1: "perifer", 2: "relevant", 3: "sentral"}

# Forhåndsregistrert 2026-09-05, FØR første kjøring: rangeringen «består» konkordans-armen
# hvis ≥ 0.70 av de ordnede parene er enige med dommeren. 0.70 er ikke 1.0 fordi to naboer
# ofte er like relevante (dommeren gir dem samme grad → teller som enig via ≥), og ikke
# 0.50 fordi det er ren tilfeldighet. Tallet skal IKKE justeres etter å ha sett resultatet.
KONKORDANS_TERSKEL = 0.70

DEFAULT_MODELL = "gpt-oss:20b"  # samme dommer-modell huset bruker (firkant-kalibreringen)

_PROMPT = """Du vurderer hvor relevant et vitenskapelig papir er for et litteratursøk.

Søket gjelder: «{query}»

Papir:
Tittel: {tittel}
Sammendrag: {abstract}

Gi ÉN karakter for hvor relevant papiret er for søket:
0 = irrelevant (helt annet tema, eller feil art/organisme)
1 = perifer (så vidt berører temaet)
2 = relevant (klart på tema)
3 = sentral (direkte om kjernen i søket)

Svar med KUN ett siffer (0, 1, 2 eller 3). Ingen forklaring."""


def _hus_dommer(model: str = DEFAULT_MODELL):
    """Lokal Ollama via husets delte port. Importeres lat, samme sys.path-mønster som
    bank._hus_embed — porten bor i silverbullet/ops, nåbar KUN på Anders' Mac."""
    import sys
    sys.path.insert(0, str(Path.home() / "prosjekter" / "silverbullet" / "ops"))
    import _ollama_port

    def doem(prompt: str) -> str:
        # temperature 0: en relevansdom skal være reproduserbar, ikke kreativ.
        svar = _ollama_port.kall_dommer(model, prompt, temperature=0.0, num_predict=600)
        return svar["message"]["content"]

    return doem


def _parse_grad(tekst: str) -> int | None:
    """Første siffer 0-3 i svaret, eller None. gpt-oss legger noen ganger tenkning foran
    (se reference gpt-oss-tomt-svar) — vi tar første gyldige siffer, ikke hele strengen."""
    m = re.search(r"[0-3]", tekst or "")
    return int(m.group()) if m else None


def doem_relevans(query: str, tittel: str, abstract: str, *, dommer_fn=None) -> int | None:
    """Uavhengig relevansgrad 0-3 for ETT papir, blind for rangeringen. None hvis dommeren
    ikke ga et tolkbart svar (skal telles som «ikke målt», aldri som 0)."""
    dommer_fn = dommer_fn or _hus_dommer()
    svar = dommer_fn(_PROMPT.format(query=query, tittel=tittel or "",
                                    abstract=(abstract or "(intet sammendrag)")[:2000]))
    return _parse_grad(svar)


# Kontrollen har sin EGEN spørring, uavhengig av eval-spørringen: den tester om DOMMEREN
# kan skille art (fisk vs. menneske) på et tema der svaret er utvetydig, ikke om
# domene-kjerne-papiret er relevant for en tilgrensende spørring. Hardkodet til
# eval-spørringen ville voidet enhver tilgrensende kjøring falskt (funnet 2026-09-05).
# `query` er en ren parameter — den fagfelt-spesifikke verdien bor i profilen
# (domeneprofil.EVAL_KONTROLL), ikke i denne modulen.
def positiv_kontroll(relevant: dict, felle: dict, *, query: str, dommer_fn=None) -> dict:
    """Dommeren MÅ gi det ekte fiskehelse-papiret høyere grad enn species-trap-fella på
    kontroll-spørringen. Består ikke den, er dommeren lurt av samme ordoverlapp rangeringen
    bander mot, og hovedmålingen skal ikke leses. {bestått, grad_relevant, grad_felle}."""
    gr = doem_relevans(query, relevant["tittel"], relevant.get("abstract", ""), dommer_fn=dommer_fn)
    gf = doem_relevans(query, felle["tittel"], felle.get("abstract", ""), dommer_fn=dommer_fn)
    bestått = gr is not None and gf is not None and gr > gf
    return {"bestått": bestått, "grad_relevant": gr, "grad_felle": gf,
            "relevant_tittel": relevant["tittel"][:70], "felle_tittel": felle["tittel"][:70]}


def _konkordans(rekkefolge: list[int]) -> tuple[float, int, int]:
    """Andel ordnede par (i før j i rangeringen) der grad[i] >= grad[j].

    `rekkefolge` er dommer-gradene I RANGERINGENS REKKEFØLGE. En perfekt rangering har
    ikke-økende grader nedover → alle par konkordante → 1.0. Like grader teller som enige
    (≥), fordi to like relevante naboer ikke er en feil i rangeringen."""
    enige = total = 0
    for i in range(len(rekkefolge)):
        for j in range(i + 1, len(rekkefolge)):
            total += 1
            if rekkefolge[i] >= rekkefolge[j]:
                enige += 1
    return (enige / total if total else 0.0), enige, total


def evaluer_rangering(query: str, papirer: list, *, dommer_fn=None, kontroll: dict | None = None) -> dict:
    """papirer = ranking.py-ordnet liste av dicts/PaperDossier (tittel, abstract). Grader
    hvert papir uavhengig (blind for plassering), mål konkordans med rangeringens rekkefølge.

    `kontroll` = {relevant, felle} kjører positiv-kontroll-gaten. Uten den er `kontroll_ok`
    None, og resultatet skal leses med forbehold: en umålt dommer er ikke en godkjent dommer.
    """
    def felt(p, navn):
        return p.get(navn) if isinstance(p, dict) else getattr(p, navn, "")

    grader, umålte = [], 0
    detaljer = []
    for p in papirer:
        g = doem_relevans(query, felt(p, "tittel"), felt(p, "abstract"), dommer_fn=dommer_fn)
        if g is None:
            umålte += 1
        else:
            grader.append(g)
        detaljer.append({"tittel": (felt(p, "tittel") or "")[:70], "grad": g})

    konk, enige, total = _konkordans(grader)
    kontroll_res = positiv_kontroll(kontroll["relevant"], kontroll["felle"],
                                    query=kontroll["query"], dommer_fn=dommer_fn) if kontroll else None
    kontroll_ok = kontroll_res["bestått"] if kontroll_res else None

    return {
        "query": query,
        "n": len(papirer),
        "umålte": umålte,  # dommer-svar uten tolkbar grad; talt, aldri som 0
        "konkordans": round(konk, 3),
        "enige_par": enige, "totale_par": total,
        "bestått": (konk >= KONKORDANS_TERSKEL) if grader else None,
        "terskel": KONKORDANS_TERSKEL,
        "kontroll": kontroll_res,
        # Den bærende linjen: konkordansen betyr INGENTING hvis kontrollen ikke besto.
        "gyldig": bool(kontroll_ok) if kontroll_ok is not None else None,
        "detaljer": detaljer,
    }
