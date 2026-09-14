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

from adapters import semantic_scholar
from dossier import hent_kandidater
from paths import DB


def bygg_siteringsgraf(papirer: list[dict]) -> dict:
    """{"noder": [id, ...], "kanter": [(fra_id, til_id), ...], "inn_grad": {id: n},
    "feilede_oppslag": [id, ...]}. `fra_id` siterer `til_id` (samme retning som
    personlig_hage.Graf sine kanter). Kandidater uten DOI blir noder uten utgående
    sitasjonsoppslag (kan fortsatt motta innkommende kanter fra andre)."""
    doi_til_id = {p["doi"].lower(): p["id"] for p in papirer if p.get("doi")}
    noder = [p["id"] for p in papirer]
    kanter: set[tuple[str, str]] = set()
    feilede: list[str] = []

    for p in papirer:
        if not p.get("doi"):
            continue
        try:
            graf = semantic_scholar.siteringsgraf(p["doi"])
        except RuntimeError:
            feilede.append(p["id"])
            continue
        for sitering in graf["siteringer"]:
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
    }


def siteringsgraf_for_emne(emne: str, db_path: Path = DB) -> dict:
    """Henter dossierets kandidater og bygger grafen i ett kall — samme
    hent_kandidater() som dossier.py/dossier_innsikt.py bruker, så nodene i grafen
    speiler nøyaktig de samme ~25 papirene et generert dossier siterer.

    Node-metadata (tittel/aar/kilde/art-konfidens) legges ved HER, ikke i
    bygg_siteringsgraf() — den funksjonen kjenner kun id-er, denne kjenner papirene."""
    import domeneprofil

    papirer = hent_kandidater(emne, db_path)
    graf = bygg_siteringsgraf(papirer)
    per_id = {p["id"]: p for p in papirer}
    graf["noder_meta"] = {
        p["id"]: {
            "tittel": p.get("tittel") or "",
            "aar": p.get("aar"),
            "kilde": p.get("kilde"),
            "art_bekreftet": domeneprofil.arts_naer_tekst(f"{p.get('tittel') or ''} {p.get('abstract') or ''}"),
        }
        for p in papirer
    }
    return graf
