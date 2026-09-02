"""Generisk tiered sorteringsnøkkel — «et lavt bånd slår aldri et høyere bånd».

Destillert fra to uavhengige implementasjoner som begge landet på nøyaktig samme figur
uten å vite om hverandre:

- teknisk-enhets-sok/rank.py: `sorted(dossierer, key=lambda d: (d.grad != "full",
  not utnyttet(d), -alvorlighet(d)))` — kilde-fullstendighet FØR faktisk alvorlighet.
- bruktmarked/backend/deal_score.py:deal_sort_key: tre bånd (målt deal / uanriket-fersk
  pending / resten) der pending ALDRI kan trenge ut en målt god deal, uansett hvor fersk.

Begge er «sorter først på en kvalitets-/kategori-nøkkel, så på en kontinuerlig score
INNENFOR den kategorien» — men bandet kan selv være en tuple (teknisk-enhets-sok bruker
to), og scoren kan være band-avhengig (bruktmarked: negert deal-score i bånd 0, ren
alder i bånd 1). Derfor er `score` en funksjon av HELE elementet, ikke bare et tall —
den kan gren på samme tilstand `band` grenet på. Ingen global «synkende»-bryter: begge
callables returnerer verdier orientert for STIGENDE sortering (mindre = først), akkurat
som originalene selv negerer per felt der det trengs.
"""
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def tiered_sort_key(element: T, band: Callable[[T], Any], score: Callable[[T], Any]) -> tuple:
    """band(element): lavere/tidligere i sorteringsrekkefølge = bedre bånd — kan være
    en enkelt verdi eller en tuple (flere bånd-kriterier, sammenlignes leksikografisk).
    score(element): sorteringsverdi INNENFOR bandet, allerede orientert stigende."""
    return (band(element), score(element))


def rank(elementer: list[T], band: Callable[[T], Any], score: Callable[[T], Any]) -> list[T]:
    """Stabil sortering: elementer med likt (band, score) beholder sin opprinnelige
    rekkefølge — samme garanti Pythons sorted() alltid gir."""
    return sorted(elementer, key=lambda e: tiered_sort_key(e, band, score))
