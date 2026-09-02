"""dedup.py — tittel-normalisering og kilde-tvers-dedup for PaperDossier.

Delt av citation_gap.py (referanse-tittel-matching, opprinnelig der) og
cli.py (fler-kilde-søk-sammenslåing, Europe PMC + CORE — se sok_og_ranger).
Samme normaliseringsbehov begge steder: kilder formaterer tegnsetting ulikt
(em-dash vs. mellomrom mellom tittel/undertittel), DOI er mest presist når
til stede, normalisert tittel er fallback.
"""
import re

from schemas import PaperDossier


def norm_tittel(t: str) -> str:
    """Fjerner tegnsetting FØR whitespace kollapses — «Tittel — Undertittel!» og
    «tittel undertittel» skal matche selv om kilden formaterer bindestrek/tegnsetting
    ulikt. Fanget av en ekte testfeil under bygging (em-dash i én kilde ga dobbelt
    mellomrom som IKKE matchet enkelt mellomrom i den andre)."""
    uten_tegn = re.sub(r"[^a-z0-9 ]", " ", (t or "").lower())
    return re.sub(r"\s+", " ", uten_tegn).strip()


def dedupliser(papirer: list[PaperDossier]) -> list[PaperDossier]:
    """Fjerner dubletter på tvers av kilder — DOI FØRST (mest presist), normalisert
    tittel som fallback (samme papir kan mangle DOI i én kilde, ha det i en annen —
    f.eks. en CORE-institusjonsarkiv-kopi av et Europe PMC-indeksert funn). Beholder
    FØRSTE forekomst — kall-rekkefølgen på input avgjør hvilken kildes metadata vinner."""
    sette_doi: set[str] = set()
    sette_tittel: set[str] = set()
    ut = []
    for p in papirer:
        doi = (p.doi or "").lower()
        tittel = norm_tittel(p.tittel)
        if (doi and doi in sette_doi) or (tittel and tittel in sette_tittel):
            continue
        if doi:
            sette_doi.add(doi)
        if tittel:
            sette_tittel.add(tittel)
        ut.append(p)
    return ut
