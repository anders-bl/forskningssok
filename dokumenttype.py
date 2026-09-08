"""dokumenttype.py — sjanger-klassifisering, IKKE studiedesign (se evidensniva.py for
det andre hierarkiet — de to akslene svarer på ulike spørsmål og skal aldri slås sammen).

Bygget 2026-09-08 etter at «Elevrapport: Marine dager ved Sandgotna ungdomsskole» (et
skoleformidlingsprosjekt) og «Fiskehelserapporten 2020» (Veterinærinstituttets offisielle
årlige nasjonale overvåkingsrapport) havnet i samme udifferensierte samling — to
dokumenter med vidt forskjellig epistemisk vekt, usynlig fra hverandre uten denne.

NVA (Sikt) sin egen `documentType`-verdi (Cristin-vokabular) er kilden der den finnes —
et menneske i institusjonens bibliotektjeneste har klassifisert dokumentet; det er
sterkere enn noe vi kan gjette fra tittelen alene. MEN vokabularet skiller ikke formidling
fra ekte institusjonelt arbeid: «Elevrapport» og «Kompetanseheving skjellpatologi»
klassifiseres BEGGE som `ReportWorkingPaper` av NVA (målt 2026-09-08, ni-rapport-stikkprøve)
— derfor kjører _FORMIDLING_HEURISTIKK FØR NVA-kartleggingen, ikke etter, og kan overstyre
et NVA-svar. Dette er samme klasse presisjonshull som epmc_harvest.py sin artsanker-gate:
en autoritativ kilde kan være riktig på sitt eget spørsmål (»hva slags Cristin-post er
dette») uten å svare på VÅRT spørsmål (»er dette forskning eller skoleformidling»).

Ingen gjetning uten et treff — «Ukjent» er et gyldig, hyppig utfall (samme prinsipp som
evidensniva.py: et dokument uten treff er «Ukjent», ALDRI en gjettet kategori).
"""
import re

FORMIDLING = "Formidling"
INSTITUSJONELL_RAPPORT = "Institusjonell rapport"
AVHANDLING = "Avhandling/oppgave"
BOK = "Bok/monografi"
JOURNAL_ARTIKKEL = "Fagfellevurdert artikkel"
UKJENT = "Ukjent"

# NVA/Cristin sitt kontrollerte vokabular → våre fire kategorier. Ukjente NVA-typer
# (vokabularet har mange flere enn dette — Dataset, MusicRecord, Interview, …) faller
# bevisst til UKJENT i stedet for å gjettes inn i nærmeste bøtte.
_NVA_KART: dict[str, str] = {
    "ReportResearch": INSTITUSJONELL_RAPPORT,
    "ReportWorkingPaper": INSTITUSJONELL_RAPPORT,
    "ReportPolicy": INSTITUSJONELL_RAPPORT,
    "PopularScienceArticle": FORMIDLING,
    "PopularScienceMonograph": FORMIDLING,
    "DegreeMaster": AVHANDLING,
    "DegreeBachelor": AVHANDLING,
    "DegreePhd": AVHANDLING,
    "DegreeLicentiate": AVHANDLING,
    "AcademicMonograph": BOK,
    "NonFictionMonograph": BOK,
    "AcademicArticle": JOURNAL_ARTIKKEL,
    "AcademicLiteratureReview": JOURNAL_ARTIKKEL,
}

# NLMs `pubtyper` (Europe PMC) → samme fire kategorier, for treff som ALLEREDE har det
# feltet (unngår et unødvendig NVA-kall for noe vi alt vet).
_NLM_KART: dict[str, str] = {
    "journal article": JOURNAL_ARTIKKEL,
    "review": JOURNAL_ARTIKKEL,
    "systematic review": JOURNAL_ARTIKKEL,
    "case reports": JOURNAL_ARTIKKEL,
    "randomized controlled trial": JOURNAL_ARTIKKEL,
    "letter": FORMIDLING,
    "comment": FORMIDLING,
    "news": FORMIDLING,
}

# Fanget 2026-09-08: NVA klassifiserer skoleformidling som ReportWorkingPaper, samme
# bøtte som ekte kompetansehevingsrapporter. Tittelmønstre er en svakere kilde enn NVA
# sitt eget felt (samme klasse forbehold som artsanker-gaten i epmc_harvest.py), men
# kjøres FØRST fordi dette ene tilfellet er en KJENT, målt NVA-feilklassifisering, ikke
# en spekulativ forbedring.
_FORMIDLING_HEURISTIKK = re.compile(
    r"\belevrapport\b|\bskoleprosjekt\b|\bungdomsskole\b|\bvideregående skole\b",
    re.IGNORECASE,
)


def fra_nva(document_type: str | None, tittel: str = "") -> str:
    """NVA sin documentType (Cristin-vokabular) → én av våre fire kategorier, ELLER
    UKJENT hvis typen ikke er kartlagt. Sjekker formidlings-heuristikken FØRST — se
    moduldocstring for hvorfor."""
    if _FORMIDLING_HEURISTIKK.search(tittel or ""):
        return FORMIDLING
    if not document_type:
        return UKJENT
    return _NVA_KART.get(document_type, UKJENT)


def fra_nlm(pubtyper: tuple[str, ...], tittel: str = "") -> str:
    """NLMs pubTypeList (Europe PMC) → samme fire kategorier. Ingen formidlings-
    heuristikk her — Europe PMC har ikke skoleformidling i korpuset sitt, og å kjøre
    heuristikken uansett ville vært en løsning uten et observert problem."""
    for pt in pubtyper:
        if (kat := _NLM_KART.get(pt.strip().lower())):
            return kat
    return UKJENT
