"""scoping.py — akse-dekning for Skriv-modus «Omfang»-fanen.

Ulvens forskningsakser (idébank #28: faser/miljøfaktorer/regenerasjon; idébank #30:
lever/ultralyd-validering lagt til). Dette er BEVISST den kjedelige, enkle versjonen —
nøkkelord-tilstedeværelse, ikke en semantisk klassifikator — samme designvalg som
multisok gjorde eksplisitt («tenk kjedelig + enkelt», Anders 2026-07-26): en akse-
dekningsindikator er et scoping-HJELPEMIDDEL, ikke en dom, og trenger ikke mer presisjon
enn det. Terskelen (2+ nøkkelord = full stolpe) er en ukalibrert heuristikk — dokumentert
som det, ikke fremstilt som målt presisjon.

Ærlighets-prinsippet gjelder også her: LAV dekning betyr «du har ikke skrevet/søkt om
dette ennå», ALDRI «forskningen mangler» — samme distinksjon citation_gap.py insisterer på.

Aksene selv bor i domeneprofil.py (samlet med ranking.py sin domeneliste 2026-09-02,
Svart hatt-funn — se den fila for hvorfor)."""
from collections import Counter

import art_niva
import tema
from domeneprofil import AKSER

_FULL_VED_ANTALL = 2  # 2+ distinkte nøkkelord i teksten = full stolpe — ukalibrert, se moduldocstring


def akse_dekning(tekst: str) -> dict[str, float]:
    """tekst → {akse: 0.0-1.0}. Tom/kort tekst gir alle akser 0.0 (ærlig, ikke en feil)."""
    t = (tekst or "").lower()
    ut = {}
    for akse, ord in AKSER.items():
        treff = sum(1 for o in ord if o in t)
        ut[akse] = round(min(1.0, treff / _FULL_VED_ANTALL), 2)
    return ut


def kilde_sammensetning(papirer: list[dict]) -> dict:
    """Hva kildene handler om: fordeling på artsnivå og temaer, fra tittel + abstract per kilde.

    Regelbasert merking (art_niva.py, tema.py), ikke en dom: målt mot en modell-merket fasit til
    ca. 92 % presisjon for målart og ca. 71 % for temaer (holdout, 2026-09-25). Et tema teller
    én gang per kilde. Tom kildeliste gir tomt svar, ikke en feil."""
    n = len(papirer)
    art = Counter()
    temaer: dict[str, list] = {}
    for p in papirer:
        art[art_niva.klassifiser(p.get("tittel"), p.get("abstract"), p.get("mesh")).niva] += 1
        for f in tema.klassifiser(p.get("tittel"), p.get("abstract")):
            temaer.setdefault(f.tema, []).append(p.get("id"))
    return {"antall": n,
            "art": {niva: art.get(niva, 0) for niva in art_niva.NIVAER},
            "temaer": {t: {"kilder": len(ids), "andel": round(len(ids) / n, 2) if n else 0.0}
                       for t, ids in sorted(temaer.items(), key=lambda x: -len(x[1]))}}
