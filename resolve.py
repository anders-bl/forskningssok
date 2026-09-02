"""Generisk entitets-resolve — tre-veis gren (eksakt / tvetydig / ingen), aldri en gjetning.

Destillert fra to uavhengige, produksjonsverifiserte implementasjoner (idébank #12s
to-konsument-port har fyrt — dette er skjelettet, ikke en tredje re-oppfinnelse):

- teknisk-enhets-sok/resolve.py — statisk DEVICES-tabell, eksakt normalisert likhet
  vinner umiddelbart, ellers samles substreng-treff som kandidater.
- bruktmarked/backend/extraction.py — AI-basert fritekst-ekstraksjon mot Discogs/
  MusicBrainz, samme tre-veis logikk i ånd (treff / usikker / ingen match).

Kontrakten: ÉN normalisert eksakt-match returneres som eksakt. Flere delvise treff
returneres som en kandidatliste — ALDRI det første, en tvetydighet skal opp til
kalleren (CLI-en spør brukeren, en API returnerer 300/409). Ingen treff er en tom
liste, ikke en unntak — fravær er en gyldig, stille tilstand.

REVIDERT etter tredje vertikal (rollesok, 2026-08-03): eksakt-treff KORTSLUTTER ikke
lenger. Første utgave antok «navn ≈ identitet» og returnerte første eksakte treff —
riktig for de to første vertikalene (én enhetsmodell, én release per navn), en stille
gjetning for den tredje (to «Ola Hansen» med ulik fødselsdato er to entiteter). Flere
eksakte treff er nå TVETYDIG med nøyaktig de eksakte som kandidater — samme «aldri
gjett»-kontrakt, anvendt på grenen som til nå var unntatt fra den.
"""
from dataclasses import dataclass, field
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


def normalize(query: str) -> str:
    return query.lower().strip().replace("  ", " ")


@dataclass
class ResolveResult(Generic[T]):
    eksakt: T | None = None
    kandidater: list[T] = field(default_factory=list)

    @property
    def tvetydig(self) -> bool:
        return self.eksakt is None and len(self.kandidater) > 1

    @property
    def ingen_treff(self) -> bool:
        return self.eksakt is None and not self.kandidater


def resolve(query: str, entiteter: list[T], tekst: Callable[[T], str]) -> ResolveResult[T]:
    """query mot en liste av entiteter. `tekst(entitet)` henter navnestrengen å matche
    mot (teknisk-enhets-sok bruker `device["entitet"]`; en ny vertikal bruker sitt eget
    felt — f.eks. et personnavn i en arkiv-søkevertikal). ÉN normalisert eksakt likhet
    vinner; FLERE eksakte er tvetydig (navnekollisjon — se docstring øverst); ellers
    samles ALLE delvise substreng-treff (begge retninger) som kandidater."""
    q = normalize(query)
    eksakte: list[T] = []
    kandidater: list[T] = []
    for e in entiteter:
        t = normalize(tekst(e))
        if q == t:
            eksakte.append(e)
        elif q in t or t in q:
            kandidater.append(e)
    if len(eksakte) == 1:
        return ResolveResult(eksakt=eksakte[0])
    if eksakte:
        # Navnekollisjon: flere entiteter bærer nøyaktig samme normaliserte tekst.
        # Kun de eksakte er kandidater — delvise treff er strengt svakere og ville
        # bare vannet ut listen kalleren må disambiguere.
        return ResolveResult(kandidater=eksakte)
    return ResolveResult(kandidater=kandidater)
