#!/usr/bin/env python3
"""dossier_siteringsgraf.py — M4 fra prosjekt/forskningssok-dossier-scivis:
sitasjonsgraf mellom et dossiers egne kandidater.

I MOTSETNING til dossier_innsikt.py (M1-M3): denne gjør EKTE, kostbare eksterne
kall — opptil ett Semantic Scholar-kall per kandidat med DOI. Bevisst en egen, mindre
modul (ikke lagt inn i dossier_innsikt.py), nettopp fordi den bryter dens "ingen nye
kall"-prinsipp. Skal kalles LAT (kun når brukeren faktisk ber om sitasjonsgrafen), ikke
synkront med hverken dossier-generering eller /api/dossier/innsikt.

Kantene bygges KUN mellom kandidater INTERNT i settet (speiler
silverbullet/ops/personlig_hage.py::bygg_graf() sitt eget prinsipp — "kun lenker til
eksisterende sider blir kanter" — se prosjekt/forskningssok-dossier-scivis B3), matchet
via DOI (semantic_scholar.siteringsgraf() sitt `doi`-felt, lagt til 2026-09-14 nettopp
for dette formålet — tittel-matching ville vært skjørt).

Degraderer ærlig: et Semantic Scholar-oppslag som feiler (429/nettverk) for ÉN kandidat
tar ikke ned hele grafen — den kandidaten bidrar bare som en isolert node (inn_grad=0),
og feilen listes i `feilede_oppslag` slik flaten kan si det ærlig i stedet for late som
alt gikk bra."""
from __future__ import annotations

from pathlib import Path

import scoping
from adapters import semantic_scholar
from dossier import hent_kandidater
from paths import DB


def _primaer_akse(p: dict) -> str | None:
    """Høyest-skårende forskningsakse for ett papir (`scoping.AKSER`, profilstyrt — se
    CLAUDE.md §Konvensjoner: aksenavn bor i profiler/*.toml, ikke her). Ingen akse traff
    (dekning 0.0 for alle) gir None -- ærlig ukjent, ikke en gjettet akse. Brukes til å
    klynge M4-sitasjonsgrafen tematisk (idébank-ønske fra Ulven-miljøet 2026-10-03: samme
    aksene M2/akse_dekning() allerede måler, nå som node-posisjon i stedet for bar-chart)."""
    tekst = f"{p.get('tittel') or ''} {p.get('abstract') or ''}"
    dekning = scoping.akse_dekning(tekst)
    if not dekning:
        return None
    beste = max(dekning, key=dekning.get)
    return beste if dekning[beste] > 0 else None


# Semantic Scholar sin side-grense er 1000; adapteren avviser større. Ett kall dekker
# nesten alle dossierkandidater. MAKS_SIDER er et tak på eksterne kall per kandidat:
# blir det nådd, merkes kandidaten som ufullstendig i stedet for å se komplett ut.
SIDE_GRENSE = 1000
MAKS_SIDER = 5


def _alle_siteringer(doi: str) -> tuple[list[dict], bool]:
    """(siteringer, komplett). Paginerer på leverandørens next_offset til siste side eller
    MAKS_SIDER. Ukjent dekning (ingen next/total) regnes som ufullstendig, aldri som komplett
    (s-19d HOLD #46295: standardgrensen 20 kappet dossierets kanter stille)."""
    siteringer: list[dict] = []
    offset = 0
    for _ in range(MAKS_SIDER):
        side = semantic_scholar.siteringsgraf(doi, limit=SIDE_GRENSE, offset=offset)
        siteringer.extend(side.get("siteringer") or [])
        dekning = side.get("siteringer_dekning") or {}
        if dekning.get("complete") is True:
            return siteringer, True
        neste = dekning.get("next_offset")
        if dekning.get("has_more") is not True or not isinstance(neste, int) or neste <= offset:
            return siteringer, False
        offset = neste
    return siteringer, False


def bygg_siteringsgraf(papirer: list[dict]) -> dict:
    """{"noder": [id, ...], "kanter": [(fra_id, til_id), ...], "inn_grad": {id: n},
    "feilede_oppslag": [id, ...], "ufullstendige_oppslag": [id, ...]}. `fra_id` siterer
    `til_id` (samme retning som personlig_hage.Graf sine kanter). Kandidater uten DOI blir
    noder uten utgående sitasjonsoppslag (kan fortsatt motta innkommende kanter fra andre).
    `ufullstendige_oppslag` er kandidater der ikke alle siterende arbeider ble hentet, så
    manglende kanter inn til dem ikke beviser at de ikke er sitert i settet."""
    doi_til_id = {p["doi"].lower(): p["id"] for p in papirer if p.get("doi")}
    noder = [p["id"] for p in papirer]
    kanter: set[tuple[str, str]] = set()
    feilede: list[str] = []
    ufullstendige: list[str] = []

    for p in papirer:
        if not p.get("doi"):
            continue
        try:
            siteringer, komplett = _alle_siteringer(p["doi"])
        except RuntimeError:
            feilede.append(p["id"])
            continue
        if not komplett:
            ufullstendige.append(p["id"])
        for sitering in siteringer:
            doi = (sitering.get("doi") or "").lower()
            fra_id = doi_til_id.get(doi)
            if fra_id and fra_id != p["id"]:
                kanter.add((fra_id, p["id"]))

    inn_grad = {n: 0 for n in noder}
    for _, til in kanter:
        inn_grad[til] = inn_grad.get(til, 0) + 1

    return {
        "noder": noder,
        "kanter": sorted(kanter),
        "inn_grad": inn_grad,
        "feilede_oppslag": feilede,
        "ufullstendige_oppslag": ufullstendige,
    }


def siteringsgraf_for_emne(emne: str, db_path: Path = DB) -> dict:
    """Henter dossierets kandidater og bygger grafen i ett kall — samme
    hent_kandidater() som dossier.py/dossier_innsikt.py bruker, så nodene i grafen
    speiler nøyaktig de samme ~25 papirene et generert dossier siterer.

    Node-metadata (tittel/aar/kilde/art-konfidens) legges ved HER, ikke i
    bygg_siteringsgraf() — den funksjonen kjenner kun id-er, denne kjenner papirene."""
    papirer = hent_kandidater(emne, db_path)
    return siteringsgraf_for_papirer(papirer)


def siteringsgraf_for_papirer(papirer: list[dict]) -> dict:
    """Bygger samme graf direkte over et eksplisitt, allerede hentet kildesett.

    Review er live og trenger ikke å skrive hvert resultat til den lokale cachet. En
    emneoppslagsgraf kunne derfor vise et annet sett enn det brukeren nettopp så.
    Atelieret sender Review-postene inn hit slik noder og kanter deler kildeidentitet.
    """
    import domeneprofil

    graf = bygg_siteringsgraf(papirer)
    graf["noder_meta"] = {
        p["id"]: {
            "tittel": p.get("tittel") or "",
            "aar": p.get("aar"),
            "kilde": p.get("kilde"),
            "art_bekreftet": domeneprofil.arts_naer_tekst(f"{p.get('tittel') or ''} {p.get('abstract') or ''}"),
            "akse": _primaer_akse(p),
        }
        for p in papirer
    }
    return graf
