"""evidensniva.py — grovt evidensnivå fra tittel/abstract-mønstre.

README har sagt siden v1 at ekte evidensnivå-klassifisering (systematisk oversikt >
kontrollert studie > case-rapport) «krever NLP over fulltekst, ikke bygget» — fortsatt
sant, vi har kun abstract (se README §Ikke gjort). Dette er IKKE den klassifikatoren.
Det er samme bevisst-kjedelige mønster som scoping.py sin akse-dekning («tenk kjedelig +
enkelt», Anders 2026-07-26): signalord i tittel/abstract som forfattere selv bruker for å
beskrive studiedesignet sitt (»systematic review«, »case report«, »randomized controlled
trial« …) — IKKE en vurdering av kvalitet eller en påstand om at klassifiseringen er
korrekt. Et papir uten treff er «ukjent design», ALDRI «lavt evidensnivå» — samme
ærlighets-distinksjon som resten av verktøyet.

Rekkefølgen under ER en evidenshierarki-ANTAKELSE (Oxford CEBM-aktig), men BRUKES kun til
å VISE et badge — aldri til å filtrere eller re-rangere søkeresultater. Et menneske
avgjør fortsatt hva som er relevant.
"""

NIVAAER: list[tuple[str, tuple[str, ...]]] = [
    ("Systematisk oversikt/meta-analyse", ("systematic review", "meta-analysis", "meta analysis",
                                            "systematisk oversikt", "scoping review")),
    ("Randomisert kontrollert studie", ("randomized controlled", "randomised controlled",
                                         "randomized trial", "randomised trial", " rct ")),
    ("Kohort-/observasjonsstudie", ("cohort study", "observational study", "longitudinal study",
                                     "prevalence study", "cross-sectional study", "survey of")),
    ("Case-rapport/case-serie", ("case report", "case series", "case study")),
]


# NLMs autoritative publikasjonstyper, kartlagt til samme nivånavn. Kilden INDEKSERER
# dette; vi gjettet det. Europe PMC har returnert pubTypeList i hvert `resultType=core`-svar
# hele tiden, i samme kall vi alt gjør — feltet ble bare kastet i adapteren (funnet
# 2026-09-04). Et menneske hos NLM har lest papiret; en substreng-match i et abstract har
# ikke. Der begge finnes, vinner NLM.
NLM_TYPER: dict[str, str] = {
    "systematic review": "Systematisk oversikt/meta-analyse",
    "meta-analysis": "Systematisk oversikt/meta-analyse",
    "randomized controlled trial": "Randomisert kontrollert studie",
    "controlled clinical trial": "Randomisert kontrollert studie",
    "observational study": "Kohort-/observasjonsstudie",
    "case reports": "Case-rapport/case-serie",
}
# «Journal Article» og «Review» utelates med vilje. Den første sier ingenting om design
# (alt er en journal article), og den andre er NLMs merkelapp for enhver oversiktsartikkel
# — også ikke-systematiske narrative oversikter, som IKKE hører øverst i et evidenshierarki.
# Å kartlegge «Review» til «Systematisk oversikt» ville løftet en narrativ oversikt til
# toppen på en autoritet den ikke har.


def evidensniva(tittel: str, abstract: str, pubtyper: tuple[str, ...] = ()) -> tuple[str, str]:
    """(nivånavn, kilde) — kilde er "nlm" eller "monster", eller ("Ukjent design", "").

    Returnerer KILDEN sammen med nivået, ikke bare nivået, fordi de to har helt ulik
    epistemisk vekt: «indeksert av NLM» er en påstand noen har stått inne for, mens
    «mønstergjenkjent» er vår heuristikk på ord forfatterne selv brukte. Flaten skal kunne
    si hvilken den viser — å presentere dem likt ville vært å låne NLMs autoritet til vår
    egen gjetning.

    NLM først når den finnes. Mønsteret er fallback, ikke erstattet: preprints (PPR) og
    CORE-treff har ingen pubTypeList i det hele tatt, og for dem er heuristikken fortsatt
    det beste vi har."""
    for pt in pubtyper:
        if (navn := NLM_TYPER.get(pt.strip().lower())):
            return navn, "nlm"
    t = f" {(tittel or '').lower()} {(abstract or '').lower()} "
    for navn, moenstre in NIVAAER:
        if any(m in t for m in moenstre):
            return navn, "monster"
    return "Ukjent design", ""
