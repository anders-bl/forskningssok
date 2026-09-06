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
import re

from domeneprofil import FAGTIDSSKRIFTER, NORSKE_FAGMILJOER, arts_naer_tekst, domene_naer_tekst
from rank import rank
from schemas import PaperDossier

__all__ = ["FAGTIDSSKRIFTER", "NORSKE_FAGMILJOER", "arts_naer", "domene_naer", "ranger", "tittel_dekning"]


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


_ORD = re.compile(r"[^\W_]{3,}", re.UNICODE)


def _sokeord(query: str) -> list[str]:
    return [o.lower() for o in _ORD.findall(query or "")]


def tittel_dekning(query: str, tittel: str) -> float:
    """Andel av spørringens ord som står i TITTELEN, 0.0-1.0. Substreng-match, og et
    ord godtas også uten sin siste bokstav, så «salmonids» dekker «salmonid», «diagnostics»
    dekker «diagnostic», uten å dra inn en stemmer for ett språk (profilen kan være norsk).

    Hvorfor dette finnes (målt 2026-09-05/06 med evaluer.py på profilens eget standardsøk):
    når alle topptreff havner i SAMME bånd (domene-nær + arts-nær + abstract), avgjorde
    (-år, -siteringer) alene, og to ferske 2026-papirer som bare NEVNTE søkeordet i
    abstractet lå over seks eldre papirer med søkeordet i selve tittelen. Dommeren ga de
    to grad 1 og de seks grad 3, ferskhet vant over relevans. Kildens egen relevans-
    rekkefølge var like skjev, så den kunne ikke brukes som tie-breaker. Tittelen er det
    ene relevanssignalet som er billig, språkuavhengig og LESBART for brukeren: «alle
    søkeordene står i tittelen» er en forklaring, ikke en vekt."""
    ord = _sokeord(query)
    if not ord:
        return 0.0
    t = (tittel or "").lower()
    treff = sum(1 for o in ord if o in t or (len(o) > 4 and o[:-1] in t))
    return treff / len(ord)


def _score(p: PaperDossier, query: str | None = None) -> tuple:
    """Innenfor et bånd: tittel-dekning FØRST (når det finnes en spørring), så ferskhet, så
    siteringer. ADR-013-prinsippet holdes: et ferskt, lite-sitert papir taper aldri på
    siteringstall, det taper bare på at et annet papir faktisk har spørringen i tittelen."""
    dekning = tittel_dekning(query, p.tittel) if query else 0.0
    return (-dekning, -(p.aar or 0), -(p.siteringstall or 0))


def ranger(papirer: list[PaperDossier], query: str | None = None) -> list[PaperDossier]:
    """`query` er valgfri med vilje: Utforskning (OpenAlex-emne) og andre kallere uten en
    tekstspørring får uendret (ferskhet, siteringer)-rekkefølge innenfor båndet."""
    return rank(papirer, band=_band, score=lambda p: _score(p, query))
