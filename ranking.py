"""ranking.py — domene-nærhet + ADR-013-pending-prinsippet anvendt på papirer.

v1 har INGEN evidensnivå-klassifisering (systematisk oversikt > studie > case-rapport
krever NLP over fulltekst — eksplisitt utsatt, se prosjekt/idebank/28-nefrokalsinose-
litteratursok §Ikke nå). Med siteringstall gratis fra Europe PMC (se adapters/europe_pmc.py)
brukes DET som den kontinuerlige aksen — men et FERSKT papir med lavt siteringstall skal
IKKE rangeres som dårlig, samme «pending, ikke verdiløst»-prinsipp som
arkitektur/adr-013-rangering-konfidens-ferskhet: band skiller domene-nære papirer fra
resten FØRST, og INNENFOR et bånd sorteres på (ferskhet, siteringer) — ikke siteringer
alene, som ville begravd et 2026-funn under et 2015-funn med ti års forsprang i tid til
å akkumulere sitater.
"""
from rank import rank
from schemas import PaperDossier

NORSKE_FAGMILJOER = (
    "havforskningsinstitutt", "veterinærinstitutt", "veterinaerinstitutt",
    "nmbu", "norwegian university of life sciences", "nofima", "pharmaq",
)
FAGTIDSSKRIFTER = (
    "journal of fish diseases", "aquaculture", "diseases of aquatic organisms",
    "journal of fish biology", "fish and shellfish immunology",
)


def domene_naer(p: PaperDossier) -> bool:
    """Norske/nordiske oppdretts-fagmiljøer + kjerne-fagtidsskrifter vektes opp — ikke
    fordi de siteres mest generisk, men fordi de er nærmest Ulvens faktiske
    driftskontekst (norsk lakseoppdrett). Substreng-match mot forfatter-affiliasjon-
    strengen og tidsskriftnavnet Europe PMC allerede returnerer — ingen ny henting."""
    tekst = f"{p.forfattere} {p.tidsskrift}".lower()
    return any(m in tekst for m in NORSKE_FAGMILJOER + FAGTIDSSKRIFTER)


def _band(p: PaperDossier) -> tuple:
    return (not domene_naer(p), p.abstract == "")


def _score(p: PaperDossier) -> tuple:
    return (-(p.aar or 0), -(p.siteringstall or 0))


def ranger(papirer: list[PaperDossier]) -> list[PaperDossier]:
    return rank(papirer, band=_band, score=_score)
