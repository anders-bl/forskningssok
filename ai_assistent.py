#!/usr/bin/env python3
"""ai_assistent.py — AI-assistent som svarer MED harde kilder, uten konfabulering.

Prinsipp: Hver påstand har en kilde-knapp → åpner papiret i leseren.
Ingen AI-generering av fakta — kun strukturering (kilde-fordeling, mønstergjenkjente
hovedfunn via detekter_hovedfunn(), gap-deteksjon) av det som allerede finnes i cachen.
Samme motor som Forskningsrapport-fanens «Hovedfunn»-seksjon i selve web-appen
(api.py:api_rapport_konvergens) — denne CLI-en er en frittstående, terminalvennlig
inngang til det samme, ikke et eget system.

Bruk:
  python3 ai_assistent.py --query "laks lever ultralyd" --svar
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from collections import Counter

# Importer forskningssøk sine moduler
import sys
sys.path.insert(0, str(Path(__file__).parent))
import domeneprofil
from adapters import evidensniva
from paths import DB
from profiler.ulven import FORHAANDSSOK, PRIORITERTE_KILDER


def hent_fra_cache(query: str, db_path: Path = DB) -> list[dict]:
    """Hent papirer fra cachen som matcher queryen."""
    if not db_path.exists():
        return []
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Enkel søk i tittel/abstract
    query_ord = query.lower().split()
    papirer = []
    
    for ord in query_ord:
        rows = conn.execute("""
            SELECT id, tittel, forfattere, aar, kilde_kode AS kilde, abstract, doi
            FROM papers
            WHERE tittel LIKE ? OR abstract LIKE ?
            ORDER BY aar DESC
        """, (f"%{ord}%", f"%{ord}%")).fetchall()
        
        for row in rows:
            papirer.append(dict(row))
    
    conn.close()
    
    # Fjern duplikater (basert på DOI eller tittel)
    sett = set()
    unike = []
    for p in papirer:
        ident = p.get("doi") or p.get("tittel", "")
        if ident not in sett:
            sett.add(ident)
            unike.append(p)
    
    return unike


def grupper_etter_kilde(papirer: list[dict]) -> dict[str, list]:
    """Grupper papirer etter kilde. `kilde` her er `papers.kilde_kode` — Europe PMC sin
    EGEN kildekode (MED/AGR/PPR/…, se schemas.py:PaperDossier.kilde_kode), ikke et
    forhåndsformatert visningsnavn. Samme «alt som ikke er CORE/OpenAlex er Europe
    PMC»-gruppering som frontend/index.html sin kildeGruppe() — matcher DEN, ikke en
    egen liste over Europe PMC-kildekoder som ville driftet fra virkeligheten hver
    gang Europe PMC legger til en ny (fant MED/AGR/PPR i cachen 2026-09-10, ikke en
    uttømmende liste)."""
    grupper = {}
    for p in papirer:
        kilde = (p.get("kilde") or "").upper()
        if kilde == "CORE":
            kilde = "CORE"
        elif kilde == "OPENALEX":
            kilde = "OpenAlex"
        else:
            kilde = "PubMed/Europe PMC"

        if kilde not in grupper:
            grupper[kilde] = []
        grupper[kilde].append(p)

    return grupper


def grupper_etter_aar(papirer: list[dict]) -> dict[int, list]:
    """Grupper papirer etter år."""
    grupper = {}
    for p in papirer:
        aar = p.get("aar")
        if aar:
            if aar not in grupper:
                grupper[aar] = []
            grupper[aar].append(p)
    return dict(sorted(grupper.items(), reverse=True))


# Bokmål OG engelsk — korpuset er i praksis overveiende engelsk (Europe PMC/OpenAlex),
# og de norske mønstrene alene traff kun 7 % av 191 ekte cachede abstracts (målt
# 2026-09-10, kun via en tilfeldig "identifi*"-delstreng-overlapp). Substreng-match, ikke
# ordgrense: fanger bøyningsformer (detect/detects/detected, correlat-ion/-ed/-es) uten en
# egen stemmer.
_SIGNIFIKANT_ORD = ("signifikant", "significant", "p<", "p <")
_DETEKSJON_ORD = ("detektere", "oppdage", "diagnostisere", "identifisere",
                   "detect", "discover", "diagnos", "identif")
_KORRELASJON_ORD = ("korrelerer", "assosiert", "påvirker", "årsak",
                     "correlat", "associat", "affect", "linked to")


def detekter_hovedfunn(papirer: list[dict]) -> list[dict]:
    """Detekter hovedfunn basert på abstract-mønstre.

    Dette er IKKE AI-generering — vi leter etter spesifikke mønstre forfatterne selv bruker:
    - "signifikant"/"significant" + tall (p-verdier)
    - "kan detektere"/"can detect" / "muliggjør"
    - "foreslår"/"suggests" / "indikerer"/"indicates"
    """
    funn = []

    for p in papirer:
        abstract = (p.get("abstract") or "").lower()
        tittel = p.get("tittel", "")

        # Mønster 1: Signifikante resultater
        if any(ord in abstract for ord in _SIGNIFIKANT_ORD):
            funn.append({
                "type": "signifikant",
                "papir": p,
                "utsagn": f"{tittel} rapporterer signifikante funn",
                "kilde_type": "statistisk",
            })

        # Mønster 2: Deteksjon/diagnose
        if any(ord in abstract for ord in _DETEKSJON_ORD):
            funn.append({
                "type": "deteksjon",
                "papir": p,
                "utsagn": f"{tittel} beskriver en deteksjonsmetode",
                "kilde_type": "metode",
            })

        # Mønster 3: Korrelasjon/årsak
        if any(ord in abstract for ord in _KORRELASJON_ORD):
            funn.append({
                "type": "korrelasjon",
                "papir": p,
                "utsagn": f"{tittel} finner en sammenheng",
                "kilde_type": "observasjon",
            })

    return funn


def detekter_gap(papirer: list[dict], query: str) -> list[str]:
    """Detekter mulige forskningsgap.

    Gap er:
    - Emner som ikke nevnes i noen abstract
    - Tidsrom med få studier
    - Kilder som mangler

    Nøkkelbegrepene hentes fra profilens forskningsakser (domeneprofil.AKSER), ikke
    hardkodet her — akkurat de aksene rapport.py allerede bruker til «Omfang»-panelet,
    så et profilbytte (FORSKNINGSSOK_PROFIL) endrer gap-kategoriene med, ikke bare
    domene-matchingen.
    """
    gap = []

    forventede_begrep = domeneprofil.AKSER

    alle_abstract = " ".join(p.get("abstract", "").lower() for p in papirer)
    
    for kategori, begreper in forventede_begrep.items():
        if not any(b.lower() in alle_abstract for b in begreper):
            gap.append(f"Ingen studier nevner {kategori} eksplisitt")
    
    # Tids-gap
    aar_grupper = grupper_etter_aar(papirer)
    if aar_grupper:
        aar_liste = sorted(aar_grupper.keys())
        for i in range(len(aar_liste) - 1):
            if aar_liste[i+1] - aar_liste[i] > 2:
                gap.append(f"Få eller ingen studier mellom {aar_liste[i]} og {aar_liste[i+1]}")
    
    return gap


def lag_svar(query: str, papirer: list[dict]) -> str:
    """Lag et strukturert svar MED kilder, uten konfabulering."""
    
    if not papirer:
        return """Ingen studier funnet i cachen.

Prøv:
  • Et bredere søk (færre begreper)
  • Synonymer (f.eks. "ultrasound" i stedet for "ultralyd")
  • Å oppdatere cachen først: python3 bank.py --oppdater

For Ulven: Prøv ett av de forhåndsdefinerte søkene i profiler.ulven.FORHAANDSSOK"""
    
    # Grupperinger
    etter_kilde = grupper_etter_kilde(papirer)
    etter_aar = grupper_etter_aar(papirer)
    
    # Hovedfunn
    funn = detekter_hovedfunn(papirer)
    
    # Gap
    gap = detekter_gap(papirer, query)
    
    # Bygg svaret
    svar = []
    svar.append(f"**Forskningsassistent: {len(papirer)} studier funnet**\n")
    
    # 1. Kilde-oversikt
    svar.append("### Kilde-fordeling")
    for kilde, liste in sorted(etter_kilde.items(), key=lambda x: -len(x[1])):
        svar.append(f"• {kilde}: {len(liste)} studier")

    # 2. Tidsfordeling
    svar.append("\n### Tidsfordeling")
    for aar, liste in list(etter_aar.items())[:5]:  # Topp 5 år
        svar.append(f"• {aar}: {len(liste)} studier")

    # 3. Hovedfunn
    if funn:
        svar.append("\n### Hovedfunn (med kilder)")
        for f in funn[:5]:  # Topp 5 funn
            p = f["papir"]
            svar.append(f"• {f['utsagn']}")
            svar.append(f"  → {p.get('forfattere', ['Ukjent'])[0]} et al. ({p.get('aar', 'u.å.')})")
            if p.get("doi"):
                svar.append(f"  DOI: [{p['doi']}](https://doi.org/{p['doi']})")
            svar.append("")
    
    # 4. Gap
    if gap:
        svar.append("\n### Detekterte gap")
        for g in gap:
            svar.append(f"• {g}")

    # 5. Alle kilder (liste)
    svar.append("\n### Alle studier ({})".format(len(papirer)))
    for i, p in enumerate(papirer[:10], 1):  # Vis topp 10
        svar.append(f"{i}. **{p.get('tittel', 'Ukjent tittel')}**")
        svar.append(f"   {p.get('forfattere', ['Ukjent'])[0]} et al. ({p.get('aar', 'u.å.')})")
        svar.append(f"   Kilde: {p.get('kilde', 'Ukjent')}")
        if p.get("doi"):
            svar.append(f"   DOI: {p['doi']}")
        svar.append("")
    
    if len(papirer) > 10:
        svar.append(f"*... og {len(papirer) - 10} flere studier*")
    
    return "\n".join(svar)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="AI-assistent uten konfabulering")
    parser.add_argument("--query", type=str, default=domeneprofil.PROFIL["sok_standard"],
                       help=f"Spørsmål eller søkeord, f.eks. '{domeneprofil.PROFIL['sok_eksempel']}'")
    parser.add_argument("--svar", action="store_true",
                       help="Generer svar (ellers vis info)")
    parser.add_argument("--db", type=str, default=str(DB),
                       help="Database-sti")

    args = parser.parse_args()

    if args.svar:
        print(f"Søker etter: '{args.query}'...")
        papirer = hent_fra_cache(args.query, Path(args.db))
        svar = lag_svar(args.query, papirer)
        print("\n" + svar)
    else:
        # Vis info om assistenten
        print(f"""
AI-assistent for forskningssøk — uten konfabulering

Prinsipper:
  - Hver påstand har en kilde
  - Ingen AI-generering av fakta
  - Åpne kilde-knapp → les originalen
  - Gap detekteres, ikke gjettes

Bruk:
  python3 ai_assistent.py --query "{domeneprofil.PROFIL['sok_eksempel']}" --svar

Profil: {domeneprofil.NAVN}
  • {domeneprofil.PROFIL['kort']}
  • Finner norske masteroppgaver (CORE)
  • Finner internasjonale studier (PubMed, OpenAlex)
  • Detekterer gap i forskningen

Neste steg:
  1. Oppdater cachen: python3 cli.py --oppdater
  2. Kjør assistenten: python3 ai_assistent.py --svar
  3. Se hovedfunn og visuelle koblinger i selve appen: Forskningsrapport-fanen og
     Kart-fanen for et gitt søk (nettleser, ikke kommandolinje)
""")


if __name__ == "__main__":
    main()