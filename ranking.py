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
from domeneprofil import FAGTIDSSKRIFTER, NORSKE_FAGMILJOER, domene_naer_tekst
from rank import rank
from schemas import PaperDossier

__all__ = ["FAGTIDSSKRIFTER", "NORSKE_FAGMILJOER", "domene_naer", "ranger"]


def domene_naer(p: PaperDossier) -> bool:
    """Norske/nordiske oppdretts-fagmiljøer + kjerne-fagtidsskrifter vektes opp — ikke
    fordi de siteres mest generisk, men fordi de er nærmest Ulvens faktiske
    driftskontekst (norsk lakseoppdrett, se domeneprofil.py). Substreng-match mot
    forfatter-affiliasjon-strengen og tidsskriftnavnet Europe PMC allerede returnerer —
    ingen ny henting."""
    return domene_naer_tekst(f"{p.forfattere} {p.tidsskrift}")


def _band(p: PaperDossier) -> tuple:
    return (not domene_naer(p), p.abstract == "")


def _score(p: PaperDossier) -> tuple:
    return (-(p.aar or 0), -(p.siteringstall or 0))


def ranger(papirer: list[PaperDossier]) -> list[PaperDossier]:
    return rank(papirer, band=_band, score=_score)
