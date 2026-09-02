"""ranking.py — domene-nærhet + ADR-013-pending-prinsippet anvendt på papirer.

v1 har INGEN ekte evidensnivå-KLASSIFISERING (systematisk oversikt > studie > case-rapport
som en rangeringsakse krever NLP over fulltekst — eksplisitt utsatt, se prosjekt/idebank/
28-nefrokalsinose-litteratursok §Ikke nå). `evidensniva.py` (lagt til 2026-09-02) er noe
mindre: et mønster-badge for VISNING, aldri brukt her i band/score — ærlighets-prinsippet
gjelder også her, en heuristikk skal ikke late som den er en rangeringsdom. Med
siteringstall gratis fra Europe PMC (se adapters/europe_pmc.py) brukes DET som den
kontinuerlige aksen — men et FERSKT papir med lavt siteringstall skal
IKKE rangeres som dårlig, samme «pending, ikke verdiløst»-prinsipp som
arkitektur/adr-013-rangering-konfidens-ferskhet: band skiller domene-nære papirer fra
resten FØRST, og INNENFOR et bånd sorteres på (ferskhet, siteringer) — ikke siteringer
alene, som ville begravd et 2026-funn under et 2015-funn med ti års forsprang i tid til
å akkumulere sitater.
"""
from domeneprofil import FAGTIDSSKRIFTER, NORSKE_FAGMILJOER, arts_naer_tekst, domene_naer_tekst
from rank import rank
from schemas import PaperDossier

__all__ = ["FAGTIDSSKRIFTER", "NORSKE_FAGMILJOER", "arts_naer", "domene_naer", "ranger"]


def domene_naer(p: PaperDossier) -> bool:
    """Norske/nordiske oppdretts-fagmiljøer + kjerne-fagtidsskrifter vektes opp — ikke
    fordi de siteres mest generisk, men fordi de er nærmest Ulvens faktiske
    driftskontekst (norsk lakseoppdrett, se domeneprofil.py). Substreng-match mot
    forfatter-affiliasjon-strengen og tidsskriftnavnet Europe PMC allerede returnerer —
    ingen ny henting."""
    return domene_naer_tekst(f"{p.forfattere} {p.tidsskrift}")


def arts_naer(p: PaperDossier) -> bool:
    """Species-trap-motvekt (Svart hatt-funn 2026-09-02, se domeneprofil.py:arts_naer_tekst):
    bånd papirer som i det hele tatt NEVNER målarten over de som ikke gjør det, FØR
    ferskhet/siteringer avgjør — uten dette kan et menneske-nyrestein-funn med lavere
    embedding-avstand utkonkurrere et faktisk fiskefunn kun på tekstlig nærhet. Flagger,
    filtrerer ALDRI bort — et treff uten artstermer forblir i lista, bare lenger ned."""
    return arts_naer_tekst(f"{p.tittel} {p.abstract}")


def _band(p: PaperDossier) -> tuple:
    return (not domene_naer(p), not arts_naer(p), p.abstract == "")


def _score(p: PaperDossier) -> tuple:
    return (-(p.aar or 0), -(p.siteringstall or 0))


def ranger(papirer: list[PaperDossier]) -> list[PaperDossier]:
    return rank(papirer, band=_band, score=_score)
