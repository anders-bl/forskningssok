#!/usr/bin/env python3
"""dossier_innsikt.py — mekaniske visualiseringsdata for et dossier. INGEN AI, ingen
nye kall mot noen kilde — kun aggregering over hva dossier.hent_kandidater() allerede
har hentet. Fungerer derfor uendret om Ollama/ai-proxy er nede (verifisert live
2026-09-14: lokal Ollama var scheduler-wedget da denne fila ble bygget, mekanikken
under er upåvirket av det).

M1/M2/M3 fra prosjekt/forskningssok-dossier-scivis — M4 (sitasjonsgraf, adaptert fra
silverbullet/ops/hage_lenkegraf.py) er en egen, større modul, ikke denne.

Tre funn fra kveldens måling (samme emne, "nephrocalcinosis salmon", 25 kandidater)
formet designet:
- akse_fordeling() teller PER PAPIR, ikke på aggregert tekst — et tidligere forsøk med
  scoping.akse_dekning() kjørt på HELE korpusets sammenslåtte tekst saturerte 4 av 5
  akser til 1.0 (alt "dekket"), fordi funksjonen er bygget for å dømme ÉN tekst, ikke
  måle et korpus. Per-papir telling ga faktisk differensiert data (44%-4%).
- Evidensnivå (systematisk oversikt/RCT/kohort) er BEVISST utelatt — målt 23/25
  "Ukjent design" for denne domeneprofilen (institusjonsarkiv-tunge kilder mangler
  NLM pubTypeList), for tynt til å være en nyttig visualisering i dag.
- art_konfidens() gjenbruker EKSAKT samme domeneprofil.arts_naer_tekst() som
  [art?]-badgen i frontend allerede bruker — samme signal, aggregert i stedet for
  per-resultat.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import domeneprofil
import scoping
from dossier import hent_kandidater
from paths import DB


def _papir_tekst(p: dict) -> str:
    return f"{p.get('tittel') or ''} {p.get('abstract') or ''}"


def tidslinje(papirer: list[dict], bucket: int = 5) -> dict[int, int]:
    """{bucket_start_aar: antall} for papirer med kjent aar, sortert kronologisk.
    Papirer uten aar telles verken som 0 eller gjettes inn et bucket — de er fraværende
    fra returverdien, ærlig, ikke stille slukt inn i et vilkårlig bucket."""
    c: Counter[int] = Counter()
    for p in papirer:
        aar = p.get("aar")
        if aar:
            c[(aar // bucket) * bucket] += 1
    return dict(sorted(c.items()))


def akse_fordeling(papirer: list[dict]) -> dict[str, int]:
    """{akse: antall papirer som nevner aksen i tittel/abstract} — PER PAPIR, se
    moduldocstring for hvorfor aggregert tekst ble forkastet. Alle akser er alltid med
    i returverdien, også med 0 — en akse ingen papirer nevner ER et funn (negativt
    rom), ikke noe å utelate."""
    c: Counter[str] = Counter()
    for p in papirer:
        dekning = scoping.akse_dekning(_papir_tekst(p))
        for akse, d in dekning.items():
            if d > 0:
                c[akse] += 1
    for akse in scoping.AKSER:
        c.setdefault(akse, 0)
    return dict(c)


def art_konfidens(papirer: list[dict]) -> dict[str, int]:
    """{"bekreftet": N, "usikker": M} — samme domeneprofil.arts_naer_tekst()-signal
    [art?]-badgen i frontend viser per resultat, her aggregert over hele dossieret."""
    bekreftet = sum(1 for p in papirer if domeneprofil.arts_naer_tekst(_papir_tekst(p)))
    return {"bekreftet": bekreftet, "usikker": len(papirer) - bekreftet}


def innsikt(emne: str, db_path: Path = DB) -> dict:
    """Samler M1-M3 i ett kall. Ingen AI, ingen nye eksterne kall — kun aggregering
    over dossier.hent_kandidater()s allerede-cachede treff. Trygg å kalle synkront
    (motsatt av /api/dossier, som gjør et ekte, kostbart LLM-kall)."""
    papirer = hent_kandidater(emne, db_path)
    return {
        "antall_kandidater": len(papirer),
        "tidslinje": tidslinje(papirer),
        "akse_fordeling": akse_fordeling(papirer),
        "art_konfidens": art_konfidens(papirer),
    }
