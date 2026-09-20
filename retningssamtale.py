#!/usr/bin/env python3
"""retningssamtale.py — fase 2b fra prosjekt/forskningssok-smartsyntese-for-ulven:
fritekst inn (Ulvens tanker/funderinger/ønsker), retningsrapport ut (aktuell/glemt/hull).

Arkitekturen er MÅLT, ikke antatt (samme roadmap-side, kveldens eksperiment 1-7):
rå fritekst rett i et søkefelt gir 0 treff i Europe PMC/OpenAlex uansett språk — det
er SETNINGSLENGDE/-struktur som knekker dem, ikke språket. Løsningen er to mekaniske
lag, ingen AI nødvendig for selve søket:

  Lag 1 (mekanisk, alltid tilgjengelig, feiler aldri):
    fritekst → stoppord-strippede innholdsord → språk-segregert (norsk/engelsk,
    egen ordliste under, IKKE en LLM-tagger — se roadmapens "veivalg"-avsnitt for
    hvorfor: et feilklassifisert ord koster kun RECALL i feil språk-bøtte, aldri
    grunnings-disiplinen) → to separate spørringer kjørt mot sok_og_ranger()
    (samme, allerede artsforankrede, live multi-kilde-søk som selve søkefeltet bruker).

  Lag 2 (AI, valgfritt, degraderer ærlig): ETT kall, til SLUTT, for narrativ
  kontekstualisering over de allerede-hentede, ekte kildene — gjenbruker
  syntese_fortelling.py sin kall_llm()/verifiser_kilder()/lag_referanseliste()
  UENDRET, kun bygg_prompt() er nytt (retningsframing, ikke sammenheng-fortelling).

Tre linser, alle mekaniske (ingen av dem trenger AI for å EKSISTERE — kun narrativet
som vever dem sammen gjør):
  - AKTUELL: mekanisk årssortering (siste AKTUELL_TERSKEL_AR år)
  - GLEMT: mekanisk års-TERSKEL-heuristikk (eldre enn GLEMT_TERSKEL_AR år, men
    fortsatt i treffmengden) — en grov proxy for "oversett", IKKE en påstand om
    faktisk glemsel (det ville kreve sitasjonsdata huset ikke har for disse kildene)
  - HULL: gjenbruk av samme per-papir akse-tellemønster som dossier_innsikt.py
    (2026-09-14) — IKKE aggregert tekst, som saturerer (se den modulens docstring)

v1 er brukerinitiert ETT-SKUDD (fritekst → ett rapport-svar), ikke ekte flertrinns-
samtale — samme FDR-026-begrunnelse ("samle tanke, ikke delegere den") som resten
av forskningssøks AI-flater.

Bruk:
  python3 retningssamtale.py --tekst "Har lurt litt på om nefrokalsinose henger sammen med..."
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import domeneprofil  # noqa: E402
import scoping  # noqa: E402
import syntese_fortelling  # noqa: E402
from cli import sok_og_ranger  # noqa: E402
from dedup import dedupliser  # noqa: E402

# Kappet likt dossier.py/syntese_fortelling.py sin egen MAKS_KILDER — samme grunn
# (et ukappet LLM-kall over et helt kombinert to-språks resultatsett sprenger
# konteksten stille, målt der 2026-09-11).
MAKS_KILDER = 25

# v1-heuristikk-terskler, bevisst grove — se moduldocstring og roadmapens "glemt er
# en grov proxy, ikke en sannhet"-advarsel. Ikke en fasit, en startverdi.
AKTUELL_TERSKEL_AR = 5
GLEMT_TERSKEL_AR = 10

# ---------------------------------------------------------------------------------
# Lag 1a: mekanisk stoppord-stripping (språkuavhengig av HVA som strippes bort --
# dette er ordene som ALDRI bærer nok mening til å være en søketerm, uansett språk
# fritekstet ellers er på).
# ---------------------------------------------------------------------------------
STOPPORD_NO: frozenset[str] = frozenset({
    "jeg", "du", "han", "hun", "den", "det", "vi", "dere", "de", "meg", "deg",
    "ham", "henne", "oss", "dem", "min", "din", "sin", "vår", "deres", "hans",
    "hennes", "denne", "dette", "disse", "hvem", "hva", "hvilken", "hvilke",
    "er", "var", "vært", "blir", "ble", "blitt", "har", "hadde", "kan", "kunne",
    "vil", "ville", "skal", "skulle", "må", "måtte", "bør", "burde", "får", "fikk",
    "gjør", "gjorde", "gjort", "sier", "sa", "sagt", "tror", "tenker", "tenkt",
    "tenke", "lurer", "lurt", "relatert", "angående",
    "litt", "mer", "mest", "mye", "mange", "noe", "noen", "ingen", "ingenting",
    "alle", "alt", "hver", "hvert", "bare", "også", "enda", "ennå", "fortsatt",
    "nå", "her", "der", "dit", "hit", "opp", "ned", "inn", "ut", "inne", "ute",
    "før", "etter", "mot", "over", "under", "gjennom", "uten", "hos", "ved", "fra",
    "til", "på", "av", "om", "med", "for", "i", "og", "eller", "men", "at", "som",
    "en", "et", "den", "de", "ikke", "aldri", "alltid", "kanskje", "gjerne",
    "veldig", "ganske", "egentlig", "faktisk", "sannsynligvis", "muligens",
    "hvordan", "hvorfor", "når", "hvor", "hvorvidt", "enten", "både", "både",
    "så", "da", "altså", "derfor", "dermed", "likevel", "selv", "samme", "annen",
    "andre", "annet", "første", "siste", "neste", "forrige", "noen gang",
    "ting", "sak", "greie", "greia", "del", "deler", "måte", "måten", "grunn",
    "grunnen", "forhold", "forholdet", "tanker", "tanke", "funderinger",
    "funderer", "spørsmål", "spørsmålet", "svar", "svaret",
})

# ---------------------------------------------------------------------------------
# Lag 1b: en LITEN, HÅNDVEDLIKEHOLDT norsk ordbank for språk-segregering — bevisst
# IKKE en LLM-tagger eller en ekstern ordbok-avhengighet (se roadmapens "veivalg"-
# avsnitt: sjekket hunspell/aspell/macOS-stavekontroll, ingen tilgjengelig, og et
# Mac-spesifikt oppslag ville uansett vært en blindvei — prod kjører i
# python:3.14-slim-Docker). Et ord IKKE i denne lista (og uten æøå) behandles som
# en engelsk/fremmed søke-kandidat. Feilklassifisering koster kun RECALL i feil
# språk-bøtte — grunnings-disiplinen (verifiser_kilder) er upåvirket uansett, siden
# hver siterte påstand uansett kommer fra et ekte, mekanisk hentet kildeobjekt.
#
# GENERISK språk-vokabular her, INGEN fagfelt-ord — domene-nære norske ord (laks,
# oppdrett, smolt, ...) bor i profiler/fiskehelse.toml §sprak og hentes inn via
# domeneprofil.NORSKE_DOMENEORD nedenfor, samme regel som AKSER/ARTSTERMER (fagfeltet
# er DATA i en fil, ikke Python-konstanter). Flyttet dit 2026-09-15 etter at
# test_domeneprofil_generisk.py sin AST-detektor korrekt felte "laks"/"oppdrett"/
# "smolt" som strengliteraler her.
NORSKE_ORD_GENERISK: frozenset[str] = frozenset({
    # Forskning/vitenskap — alminnelige norske forskningsord.
    "forskning", "forskningen", "forsker", "forskere", "forsket", "studie",
    "studien", "studier", "undersøkelse", "undersøkelsen", "resultat",
    "resultatet", "resultater", "funn", "funnet", "funnene", "data", "dataene",
    "metode", "metoden", "metoder", "forsøk", "forsøket", "eksperiment",
    "analyse", "analysen", "årsak", "årsaken", "årsaker", "effekt", "effekten",
    "effekter", "sammenheng", "sammenhengen", "behandling", "behandlingen",
    "forebygging", "forebygge", "litteratur", "litteraturen", "kilde", "kilder",
    "kildene", "referanse", "referanser", "faktor", "faktoren", "faktorer",
    "betydning", "betydningen", "forklaring", "forklaringen", "hypotese",
    "hypotesen", "teori", "teorien", "modell", "modellen", "konklusjon",
    "konklusjonen",
    # Vanlige norske substantiv/verb/adjektiv (allmenn ordbank, ikke fagspesifikk).
    "tid", "tiden", "periode", "perioden", "endring", "endringen", "endringer",
    "prosess", "prosessen", "system", "systemet", "nivå", "nivået", "grad",
    "graden", "mengde", "mengden", "andel", "andelen", "antall", "gruppe",
    "gruppen", "grupper", "type", "typen", "typer", "form", "formen", "former",
    "kvalitet", "kvaliteten", "tilstand", "tilstanden", "problem", "problemet",
    "problemer", "utfordring", "utfordringen", "utfordringer", "løsning",
    "løsningen", "risiko", "risikoen", "fare", "faren", "skade", "skaden",
    "høy", "høyt", "høye", "lav", "lavt", "lave", "stor", "stort", "store",
    "liten", "lite", "lille", "små", "god", "godt", "gode", "dårlig", "dårlige",
    "ny", "nytt", "nye", "gammel", "gammelt", "gamle", "vanlig", "vanlige",
    "spesiell", "spesielle", "viktig", "viktige", "relevant", "relevante",
    "tydelig", "tydelige", "mulig", "mulige", "sannsynlig", "sannsynlige",
    "fint", "fine", "bra", "greit", "grei", "riktig", "riktige", "feil",
    "finne", "finner", "fant", "funnet", "se", "ser", "så", "sett", "vise",
    "viser", "viste", "vist", "påvirke", "påvirker", "påvirket", "øke", "øker",
    "økte", "økt", "redusere", "reduserer", "redusert", "endre", "endrer",
    "endret", "bidra", "bidrar", "bidro", "bidratt", "skyldes", "skyldtes",
    "henge", "henger", "hengt", "knytte", "knytter", "knyttet",
})

# Slått sammen med profilens domeneord ÉN gang ved import — segreger_sprak() bruker
# denne, ikke NORSKE_ORD_GENERISK direkte, så modulen forblir korrekt selv om
# NORSKE_DOMENEORD er tom (en annen domeneprofil uten §sprak-seksjon).
NORSKE_ORD: frozenset[str] = NORSKE_ORD_GENERISK | frozenset(domeneprofil.NORSKE_DOMENEORD)


def ekstraher_innholdsord(tekst: str) -> list[str]:
    """fritekst → innholdsord, stoppord fjernet, ORIGINAL rekkefølge bevart, ingen
    duplikater. Kort ord (<=2 tegn) droppes samtidig — de er nesten alltid støy
    eller reststoppord uansett språk.

    Splitter PÅ bindestrek (ikke bevarer den inni ord) — målt live 2026-09-15:
    kodevekslede sammensetninger som "metabolism-greie"/"stress-relatert" ble ETT
    ord med bindestrek bevart, og siden de er LANGE (bindestreken teller med) vant
    de over rene ord som "temperature" i prioriter_spesifikke()s lengde-sortering —
    søppel fortrengte signal. Splitting mister ekte sammensatte fagtermer som
    "post-smolt" som én enhet, men hver halvdel bærer fortsatt mening alene
    ("smolt" er uansett en egen ARTSTERMER-oppføring) — akseptabelt tap, samme
    "koster kun recall"-prinsipp som resten av denne modulens språk-heuristikk."""
    ord = re.findall(r"[\wøæåØÆÅ]+", (tekst or "").lower())
    sett: list[str] = []
    for o in ord:
        if len(o) > 2 and o not in STOPPORD_NO and o not in sett:
            sett.append(o)
    return sett


def segreger_sprak(innholdsord: list[str]) -> tuple[list[str], list[str]]:
    """innholdsord → (norske, andre). Et ord regnes norsk hvis det står i NORSKE_ORD
    ELLER inneholder æøå (et sterkt, billig signal — engelske/latinske fagtermer har
    det så godt som aldri). Resten er engelsk/fremmed-kandidat, default, ikke unntak
    — se moduldocstring for hvorfor lav presisjon her er akseptabelt."""
    norske, andre = [], []
    for o in innholdsord:
        if o in NORSKE_ORD or any(c in o for c in "æøå"):
            norske.append(o)
        else:
            andre.append(o)
    return norske, andre


def prioriter_spesifikke(ord: list[str], maks: int = 5) -> list[str]:
    """Prioriter LENGRE (antatt mer spesifikke) ord fremfor korte/generiske —
    "nefrokalsinose" diskriminerer et søk langt bedre enn "stress" (se roadmapens
    egen "stress forekommer i enorme mengder litteratur"-observasjon). Ordlengde er
    en billig, ærlig proxy — ingen ekstern frekvensdatabase, ingen ny avhengighet.
    Stabil sortering: bevarer original rekkefølge blant like lange ord."""
    return sorted(ord, key=len, reverse=True)[:maks]


def bygg_sokefraser(tekst: str) -> dict[str, str]:
    """fritekst → {"norsk": "...", "engelsk": "..."}. Tom streng for et tomt
    bucket — ÆRLIG fravær (ingen søk kjøres for den siden), ikke et tomt/meningsløst
    søk kjørt likevel. SPRÅKSEGREGERT, ikke oversatt eller blandet (se roadmapens
    eksperiment 7 — blanding "forgifter" Europe PMC/OpenAlex sin matching selv når
    de riktige ordene er til stede)."""
    innholdsord = ekstraher_innholdsord(tekst)
    norske, andre = segreger_sprak(innholdsord)
    return {
        "norsk": " ".join(prioriter_spesifikke(norske)),
        "engelsk": " ".join(prioriter_spesifikke(andre)),
    }


# ---------------------------------------------------------------------------------
# Lag 1c: LIVE, artsforankret henting (sok_og_ranger() er allerede artsforankret,
# 2026-09-14 samme kveld, commit 21b3033 — retningssamtalen arver den fiksen gratis).
# ---------------------------------------------------------------------------------

def hent_kilder(fritekst: str, page_size: int = 20):
    """Kjører sok_og_ranger() for hver ikke-tomme språk-segregerte søkefrase, slår
    sammen og dedupliserer. LIVE multi-kilde-søk, IKKE hent_fra_cache() (den er
    cache-only LIKE-søk — se roadmapens egen begrunnelse for hvorfor det er feil
    verktøy for en fritekst-drevet retningssamtale)."""
    fraser = bygg_sokefraser(fritekst)
    alle = []
    sok_detaljer: dict[str, dict] = {}
    for sprak, frase in fraser.items():
        if not frase:
            sok_detaljer[sprak] = {"sokefrase": "", "kjort": False}
            continue
        rangert, _, revisjon = sok_og_ranger(frase, page_size=page_size)
        alle.extend(rangert)
        sok_detaljer[sprak] = {"sokefrase": frase, "kjort": True, "treff": len(rangert),
                                "revisjon": revisjon}
    return dedupliser(alle), fraser, sok_detaljer


# ---------------------------------------------------------------------------------
# Tre linser — alle mekaniske, ingen AI.
# ---------------------------------------------------------------------------------

def linse_aktuell(papirer: list, i_ar: int | None = None) -> list:
    """Nyeste først, siste AKTUELL_TERSKEL_AR år. Ren årssortering, ingen AI-dom."""
    i_ar = i_ar or datetime.now().year
    return sorted((p for p in papirer if p.aar and p.aar >= i_ar - AKTUELL_TERSKEL_AR),
                  key=lambda p: -(p.aar or 0))


def linse_glemt(papirer: list, i_ar: int | None = None) -> list:
    """Eldre enn GLEMT_TERSKEL_AR år, men fortsatt i treffmengden (dvs. fortsatt
    relevant nok til å treffe et av søkene). Grov ALDERS-heuristikk — IKKE en
    påstand om faktisk glemsel, se moduldocstring."""
    i_ar = i_ar or datetime.now().year
    return sorted((p for p in papirer if p.aar and p.aar < i_ar - GLEMT_TERSKEL_AR),
                  key=lambda p: (p.aar or 0))


def linse_hull(papirer: list) -> dict[str, int]:
    """{akse: antall papirer som nevner den} — PER PAPIR, samme mønster som
    dossier_innsikt.akse_fordeling() (2026-09-14, samme kveld) — IKKE aggregert
    tekst, som saturerer til 1.0 på alle akser (se den modulens egen docstring for
    det målte, feilslåtte første forsøket). Alle akser er alltid med, også med 0."""
    c: Counter[str] = Counter()
    for p in papirer:
        tekst = f"{p.tittel or ''} {p.abstract or ''}"
        dekning = scoping.akse_dekning(tekst)
        for akse, d in dekning.items():
            if d > 0:
                c[akse] += 1
    for akse in scoping.AKSER:
        c.setdefault(akse, 0)
    return dict(c)


def _til_dict(p) -> dict:
    """PaperDossier → dict-shapen syntese_fortelling.py sine gjenbrukte funksjoner
    (verifiser_kilder/lag_referanseliste) forventer."""
    return {"id": p.id, "tittel": p.tittel, "forfattere": p.forfattere, "aar": p.aar,
            "doi": p.doi, "abstract": p.abstract, "kilde": p.kilde_kode}


# ---------------------------------------------------------------------------------
# Lag 2: ETT AI-kall, til slutt, for narrativ kontekstualisering. Gjenbruker
# syntese_fortelling.py sin kall_llm()/verifiser_kilder()/lag_referanseliste()
# UENDRET — kun denne prompten er ny.
# ---------------------------------------------------------------------------------

def bygg_prompt(fritekst: str, aktuelle: list[dict], glemte: list[dict],
                 hull: dict[str, int], antall_kilder: int) -> str:
    """Instruksen i punktene under er en avtale med modellen, ikke en garanti —
    syntese_fortelling.verifiser_kilder() er garantien, samme jernregel som resten
    av forskningssøks AI-flater."""
    def _kildeliste(papirer: list[dict]) -> str:
        return "\n\n".join(
            f"[#{p['id']}] {p.get('tittel', '(uten tittel)')} — "
            f"{p.get('forfattere', 'Ukjent forfatter')} ({p.get('aar', 'u.å.')}), "
            f"kilde={p.get('kilde', '?')}\n"
            f"Abstract: {p.get('abstract') or '(ingen abstract tilgjengelig)'}"
            for p in papirer
        ) or "(ingen kilder i denne kategorien)"

    hull_tekst = "\n".join(f"- {akse}: {n} av {antall_kilder} hentede kilder nevner dette"
                            for akse, n in hull.items()) or "(ingen akser definert for dette fagfeltet)"

    return f"""Du er en forskningsassistent som skal peke ut RETNINGER verdt å
undersøke videre, basert på en forskers egne tanker/funderinger og de faktiske
kildene som ble hentet på bakgrunn av dem.

FORSKERENS TANKER: "{fritekst}"

STRENGE REGLER (brudd gjør outputen ubrukelig og blir fjernet mekanisk etterpå):
1. Bruk KUN fakta fra kildelistene under. Aldri fra egen forhåndskunnskap.
2. HVER setning som hevder noe faktisk MÅ avsluttes med kildereferansen i formatet
   [#<id>], hentet ORDRETT fra listene under (flere kilder: [#12][#47]).
3. Mangler god kildedekning for et poeng, skriv det ærlig
   ("Ingen kilder i utvalget dekker dette") — ikke fyll ut med antakelser.
4. Dikt ALDRI opp en [#id] som ikke står i listene. Den blir oppdaget og fjernet.

RELEVANT OG AKTUELL FORSKNING (siste {AKTUELL_TERSKEL_AR} år):
{_kildeliste(aktuelle)}

RELEVANT MEN ELDRE FORSKNING (eldre enn {GLEMT_TERSKEL_AR} år, men fortsatt relevant
nok til å ha truffet søket — dette er en grov ALDERS-heuristikk for "kan være
oversett", IKKE en påstand om at noen faktisk har glemt disse):
{_kildeliste(glemte)}

DEKNING PÅ TVERS AV FORSKNINGSAKSER (mekanisk telling av de {antall_kilder} hentede
kildene, ikke en AI-vurdering):
{hull_tekst}

FORM: Skriv en sammenhengende tekst i tre deler:
- Hva er relevant og AKTUELT nå, basert på kildene over?
- Hva er relevant men muligens OVERSETT — vær ærlig om at dette er en alders-
  heuristikk (kilder som er eldre, ikke bevist glemt)?
- Hvor er HULLENE — hvilke akser/vinklinger er tynt dekket av de hentede kildene,
  og hva kunne vært verdt å undersøke der?
"""


def _mekanisk_sammendrag(aktuelle: list[dict], glemte: list[dict], hull: dict[str, int],
                          antall_kilder: int) -> str:
    """Ren mekanisk fallback — INGEN AI — brukt når lag 2 (kall_llm) feiler. Speiler
    prosjekt/forskningssok-smartsyntese-for-ulven sin eksplisitte fase 2b-kravslinje:
    "Faller lag 2 (Ollama wedget/ai-proxy nede), skal retningssamtalen fortsatt gi
    kildespråk-treff via lag 1 alene, ikke feile helt — ærlig degradering, ikke
    alt-eller-ingenting." Ingen syntese/prosa her, kun rå kildelister — akkurat den
    mekaniske majoriteten invariant 1 uansett krever."""
    def _rader(papirer: list[dict]) -> str:
        return "\n".join(
            f"- [#{p['id']}] {p.get('tittel', '(uten tittel)')} "
            f"({p.get('aar', 'u.å.')}) — {p.get('forfattere', 'Ukjent forfatter')}"
            for p in papirer
        ) or "(ingen kilder i denne kategorien)"

    hull_tekst = "\n".join(f"- {akse}: {n} av {antall_kilder} hentede kilder nevner dette"
                            for akse, n in hull.items()) or "(ingen akser definert)"

    return (
        "## Aktuell forskning (mekanisk, siste år)\n"
        f"{_rader(aktuelle)}\n\n"
        "## Relevant, muligens oversett (mekanisk, eldre kilder)\n"
        f"{_rader(glemte)}\n\n"
        "## Dekning på tvers av forskningsakser (mekanisk telling)\n"
        f"{hull_tekst}\n\n"
        "[ADVARSEL: AI-narrativet er IKKE tilgjengelig akkurat nå (Ollama/ai-proxy "
        "nede eller ikke konfigurert) — dette er de rå, mekanisk sorterte kildene "
        "uten en sammenhengende fortelling rundt dem. Prøv igjen senere for narrativet.]"
    )


def lag_retningsrapport(fritekst: str) -> str:
    """Hovedfunksjon: fritekst → mekanisk to-språks henting → tre mekaniske linser
    → ETT AI-kall for narrativ kontekstualisering → mekanisk kilde-etterkontroll →
    ferdig rapport. Speiler dossier.lag_dossier()/syntese_fortelling.lag_syntese_
    fortelling() sin egen struktur, ikke funnet opp på nytt her.

    AI-steget (lag 2) degraderer ÆRLIG til _mekanisk_sammendrag() hvis kall_llm()
    feiler (Ollama wedget/ai-proxy nede) — mekanisk henting + de tre linsene er
    UAVHENGIGE av lag 2 og skal aldri utebli fordi AI-et er nede, se
    _mekanisk_sammendrag() sin egen docstring for roadmap-kravet dette oppfyller."""
    return lag_review(fritekst)["rapport"]


def lag_review(fritekst: str) -> dict:
    """Lag den delbare Review-kontrakten for både arbeidsflaten og Smartsøk.

    Kontrakten holder søkeproveniens, mekaniske linser og eventuell AI-kontekst i
    samme objekt. Det gjør at en konsument kan vise eller lagre Review uten å
    tolke markdown, og at en senere scout kan legge til forslag uten å blande dem
    inn i sannhetslaget.
    """
    fritekst = (fritekst or "").strip()
    if not fritekst:
        return {
            "kontrakt": "review.v1",
            "status": "tomt_input",
            "input": {"fritekst": ""},
            "sok": {"fraser": {}, "detaljer": {}},
            "kilder": [],
            "linser": {"aktuell": [], "glemt": [], "hull": {}},
            "ai": {"brukt": False, "avvist": []},
            "rapport": "Ingen tekst å jobbe med.",
        }

    papirer_obj, fraser, sok_detaljer = hent_kilder(fritekst)
    papirer_obj = papirer_obj[:MAKS_KILDER]
    sok_meta = {"fraser": fraser, "detaljer": sok_detaljer}
    if not papirer_obj:
        sokt = ", ".join(f'{s}="{d["sokefrase"]}"' for s, d in sok_detaljer.items() if d["kjort"])
        if not sokt:
            sokt = "(ingen — fritekstet ga ingen innholdsord etter stoppord-stripping)"
        return {
            "kontrakt": "review.v1",
            "status": "ingen_kilder",
            "input": {"fritekst": fritekst},
            "sok": sok_meta,
            "kilder": [],
            "linser": {"aktuell": [], "glemt": [], "hull": {}},
            "ai": {"brukt": False, "avvist": []},
            "rapport": (f"Ingen kilder funnet for dine tanker rundt dette — verken norsk eller "
                         f"engelsk søk ga treff.\nSøkefraser prøvd: {sokt}"),
        }

    papirer = [_til_dict(p) for p in papirer_obj]
    aktuelle = [_til_dict(p) for p in linse_aktuell(papirer_obj)]
    glemte = [_til_dict(p) for p in linse_glemt(papirer_obj)]
    hull = linse_hull(papirer_obj)
    ai_brukt = False
    avvist: list[str] = []

    try:
        prompt = bygg_prompt(fritekst, aktuelle, glemte, hull, len(papirer))
        rått_svar = syntese_fortelling.kall_llm(prompt)
        renset, avvist = syntese_fortelling.verifiser_kilder(rått_svar, papirer)
        ai_brukt = True
        ut = [renset]
        if avvist:
            ut.append(f"\n---\n[ADVARSEL: {len(avvist)} kildehenvisning(er) fantes ikke i "
                       f"kildesettet og ble fjernet: {', '.join(avvist)}]")
    except RuntimeError:
        ut = [_mekanisk_sammendrag(aktuelle, glemte, hull, len(papirer))]

    ut.append(f"\n---\n## Kildeliste ({len(papirer)} kilder)\n"
              f"{syntese_fortelling.lag_referanseliste(papirer)}")
    return {
        "kontrakt": "review.v1",
        "status": "fullfort" if ai_brukt else "mekanisk_fallback",
        "input": {"fritekst": fritekst},
        "sok": sok_meta,
        "kilder": papirer,
        "linser": {"aktuell": aktuelle, "glemt": glemte, "hull": hull},
        "ai": {"brukt": ai_brukt, "avvist": avvist},
        "rapport": "\n".join(ut),
    }


def tilgjengelig() -> bool:
    """Samme spørsmål som syntese_fortelling.tilgjengelig() — gjenbrukt uendret,
    ikke duplisert (AI_PROXY_URL-tilstedeværelse er signalet, samme sted definert)."""
    return syntese_fortelling.tilgjengelig()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tekst", required=True, help="Fritekst — tanker/funderinger/ønsker")
    a = p.parse_args()
    print(lag_retningsrapport(a.tekst))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
