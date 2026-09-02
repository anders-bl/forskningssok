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


def evidensniva(tittel: str, abstract: str) -> str:
    """tittel+abstract → nivånavn, eller "Ukjent design" hvis ingen mønster treffer.
    Sjekker nivåene i den rekkefølgen de står i NIVAAER (høyest evidenshierarki-antakelse
    først) — et abstract som nevner både «systematic review» og «case report» (f.eks. en
    oversikt SOM DISKUTERER en case-serie) klassifiseres som oversikten, ikke case-serien."""
    t = f" {(tittel or '').lower()} {(abstract or '').lower()} "
    for navn, moenstre in NIVAAER:
        if any(m in t for m in moenstre):
            return navn
    return "Ukjent design"
