#!/usr/bin/env python3
"""ai_assistent.py — AI-assistent som svarer MED harde kilder, uten konfabulering.

Prinsipp: Hver påstand har en kilde-knapp → åpner papiret i leseren.
Ingen AI-generering av fakta — kun strukturering av det som allerede finnes i cachen.

For Ulven:
  Bruker: "Hva sier forskningen om ultralyd av lakselever?"
  
  Assistent:
    "Jeg fant 14 relevante studier:
    
    📊 3 norske masteroppgaver (NTNU 2023, NMBU 2022, UiT 2019)
    📊 8 internasjonale artikler (PubMed: 5, Semantic Scholar: 3)
    📊 2 rapporter (Havforskningsinstituttet)
    
    Hovedfunn:
    • Ultralyd kan detektere nefrokalsinose tidlig (NTNU 2023, n=45) [Kilde]
    • Leverekko endres ved stress (NMBU 2022, p<0.05) [Kilde]
    
    ⚠️  Gap: Ingen studier på ultralyd + hepatitt hos laks
    
    [Vis alle 14 kilder med DOI/PMID]"

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
from adapters import evidensniva
from profiler.ulven import FORHAANDSSOK, PRIORITERTE_KILDER


def hent_fra_cache(query: str, db_path: Path = Path("bank.db")) -> list[dict]:
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
            SELECT id, tittel, forfattere, aar, kilde, abstract, doi
            FROM papirer
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
    """Grupper papirer etter kilde."""
    grupper = {}
    for p in papirer:
        kilde = p.get("kilde", "Ukjent")
        # Normaliser kildenavn
        if "CORE" in kilde:
            kilde = "CORE"
        elif "PMC" in kilde or "PubMed" in kilde:
            kilde = "PubMed/Europe PMC"
        elif "OpenAlex" in kilde:
            kilde = "OpenAlex"
        
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


def detekter_hovedfunn(papirer: list[dict]) -> list[dict]:
    """Detekter hovedfunn basert på abstract-mønstre.
    
    Dette er IKKE AI-generering — vi leter etter spesifikke mønstre forfatterne selv bruker:
    - "signifikant" + tall (p-verdier)
    - "kan detektere" / "muliggjør"
    - "foreslår" / "indikerer"
    """
    funn = []
    
    for p in papirer:
        abstract = (p.get("abstract") or "").lower()
        tittel = p.get("tittel", "")
        
        # Mønster 1: Signifikante resultater
        if "signifikant" in abstract or "p<" in abstract or "p <" in abstract:
            funn.append({
                "type": "signifikant",
                "papir": p,
                "utsagn": f"{tittel} rapporterer signifikante funn",
                "kilde_type": "statistisk",
            })
        
        # Mønster 2: Deteksjon/diagnose
        if any(ord in abstract for ord in ["detektere", "oppdage", "diagnostisere", "identifisere"]):
            funn.append({
                "type": "deteksjon",
                "papir": p,
                "utsagn": f"{tittel} beskriver en deteksjonsmetode",
                "kilde_type": "metode",
            })
        
        # Mønster 3: Korrelasjon/årsak
        if any(ord in abstract for ord in ["korrelerer", "assosiert", "påvirker", "årsak"]):
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
    """
    gap = []
    
    # Sjekk om nøkkelbegreper mangler
    forventede_begrep = {
        "ultralyd": ["ultralyd", "ultrasound", "sonografi"],
        "lever": ["lever", "hepatic", "liver"],
        "laks": ["laks", "salmon", "salmo"],
    }
    
    alle_abstract = " ".join(p.get("abstract", "").lower() for p in papirer)
    
    for kategori, begreper in forventede_begrep.items():
        if not any(b in alle_abstract for b in begreper):
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
    svar.append("### 📊 Kilde-fordeling")
    for kilde, liste in sorted(etter_kilde.items(), key=lambda x: -len(x[1])):
        svar.append(f"• {kilde}: {len(liste)} studier")
    
    # 2. Tidsfordeling
    svar.append("\n### 📅 Tidsfordeling")
    for aar, liste in list(etter_aar.items())[:5]:  # Topp 5 år
        svar.append(f"• {aar}: {len(liste)} studier")
    
    # 3. Hovedfunn
    if funn:
        svar.append("\n### 🔍 Hovedfunn (med kilder)")
        for f in funn[:5]:  # Topp 5 funn
            p = f["papir"]
            svar.append(f"• {f['utsagn']}")
            svar.append(f"  → {p.get('forfattere', ['Ukjent'])[0]} et al. ({p.get('aar', 'u.å.')})")
            if p.get("doi"):
                svar.append(f"  DOI: [{p['doi']}](https://doi.org/{p['doi']})")
            svar.append("")
    
    # 4. Gap
    if gap:
        svar.append("\n### ⚠️  Detekterte gap")
        for g in gap:
            svar.append(f"• {g}")
    
    # 5. Alle kilder (liste)
    svar.append("\n### 📚 Alle studier ({})".format(len(papirer)))
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
    parser.add_argument("--query", type=str, default="laks lever ultralyd",
                       help="Spørsmål eller søkeord")
    parser.add_argument("--svar", action="store_true",
                       help="Generer svar (ellers vis info)")
    parser.add_argument("--db", type=str, default="bank.db",
                       help="Database-sti")
    
    args = parser.parse_args()
    
    if args.svar:
        print(f"Søker etter: '{args.query}'...")
        papirer = hent_fra_cache(args.query, Path(args.db))
        svar = lag_svar(args.query, papirer)
        print("\n" + svar)
    else:
        # Vis info om assistenten
        print("""
AI-assistent for forskningssøk — uten konfabulering

Prinsipper:
  ✓ Hver påstand har en kilde
  ✓ Ingen AI-generering av fakta
  ✓ Åpne kilde-knapp → les originalen
  ✓ Gap detekteres, ikke gjettes

Bruk:
  python3 ai_assistent.py --query "laks lever ultralyd" --svar

For Ulven (Lumic):
  • Spesialisert på fiskehelse + ultralyd + lever
  • Finner norske masteroppgaver (CORE)
  • Finner internasjonale studier (PubMed, OpenAlex)
  • Detekterer gap i forskningen

Neste steg:
  1. Oppdater cachen: python3 bank.py --oppdater
  2. Kjør assistenten: python3 ai_assistent.py --svar
  3. Utforsk visuelle koblinger: python3 scivis_koblinger.py
""")


if __name__ == "__main__":
    main()