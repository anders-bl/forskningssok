"""tema.py — temaer per artikkel, utledet fra innholdet, flere per artikkel, med bevis.

Bank-samlingene (nyrehelse, vaksine, ...) er navngitt etter SØKET som fant artikkelen, så en
sjøpølse-artikkel ligger i «vaksine» og en fiskehelseartikkel bare i én samling selv om den
handler om tre ting. Dette gir et annet svar: hvilke temaer handler teksten om.

Regel: et treff i tittelen gir temaet (score 3 per treff); ellers kreves minst MIN_TREFF_TEKST
treff i teksten fordelt på minst MIN_ULIKE_TEKST ulike termer (score 1 per treff). To treff på
samme generelle ord er ikke et tema; terskelene ble valgt ved et rutenett over utviklingsdelen
av fasiten (én enkelt omtale ga presisjon 55 %, fire treff på tre termer 78 %). Maks MAKS_TEMAER, rangert på score. Termene bor i profilen
(`[tema]`); signal som merkes, aldri et filter. Ingen fagfelt-ord i denne fila.
"""
from dataclasses import dataclass

import domeneprofil
from art_niva import _monster

MIN_TREFF_TEKST = 4
MIN_ULIKE_TEKST = 3
MAKS_TEMAER = 4


@dataclass(frozen=True)
class TemaFunn:
    tema: str
    score: int
    bevis: tuple[str, ...]


def _monstre() -> dict:
    tabell = domeneprofil.PROFIL.get("tema") or {}
    return {navn: _monster(termer) for navn, termer in tabell.items()}


def klassifiser(tittel: str | None, tekst: str | None = "") -> list[TemaFunn]:
    t_tittel = (tittel or "").lower()
    t_tekst = f"{tittel or ''} {tekst or ''}".lower()
    funn = []
    for navn, monster in _monstre().items():
        if monster is None:
            continue
        i_tittel = monster.findall(t_tittel)
        i_tekst = monster.findall(t_tekst)
        if i_tittel or (len(i_tekst) >= MIN_TREFF_TEKST and len(set(i_tekst)) >= MIN_ULIKE_TEKST):
            funn.append(TemaFunn(navn, 3 * len(i_tittel) + len(i_tekst),
                                 tuple(dict.fromkeys(i_tittel + i_tekst))[:5]))
    funn.sort(key=lambda f: -f.score)
    return funn[:MAKS_TEMAER]
