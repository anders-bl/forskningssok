#!/usr/bin/env python3
"""Mål søkefrasene i retningssamtale mot ekte forskerspørsmål (LIVE, Lag 1, ingen AI).

Spørsmålene er Kristian Ulvens egne fra samtalen 21.09 (ordrett, skrivefeil beholdt)
pluss to oppfølginger fra ende-til-ende-testen 2026-09-28. Alle handler om
nefrokalsinose hos laks, så relevans måles mekanisk: tittel eller abstract nevner
nyre/forkalkning (RELEVANT under). Grov proxy, men den skiller «lakselus» fra
«nephrocalcinosis» uten dom.

Snill mot kildene: hvert spørsmål = maks to søk (norsk + engelsk frase), kjør sjelden.

  ../forskningssok/venv/bin/python ops/fagterm_eval.py --etikett foer
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROT))
import retningssamtale as r

SPORSMAL = [
    "Jeg vil prøve noe; kan du forklare hvordan utfelling av mineraler i nefrokalsinonse i laks foregår?",
    "Hvor vil utfelling først oppstå i nyren i tidlig fase, og hvordan vil dette videre akummuleres når sykdommen utvikler seg?",
    "Dersom ultralyd skal brukes for detektere graden av nerfokalsinose, score 1-4, hvilket deler av nyren, eventuelt hele nyren bør scannes?",
    "dersom man scanner 75 prosent fra hodenyren og bakover, kan man være sikker på resultatet da? også høye scorer",
    "hvorfor radiologi",
    "kan man på en god måte trene en ai modell på sli ultralydscreening, slik som greenfox marine og lumic skal",
    "Hvilke studier har målt sammenhengen mellom CO2-nivå i vannet og grad av nefrokalsinose hos smolt?",
    "Finnes det studier som sammenligner ultralyd med røntgen for å gradere nefrokalsinose hos laks?",
]
RELEVANT = re.compile(r"nephro|calc|kidney|renal|urolith|mineral", re.IGNORECASE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--etikett", required=True)
    ap.add_argument("--kontekst", action="store_true", help="send de tre forrige spørsmålene som kontekst")
    a = ap.parse_args()
    rader = []
    for i, q in enumerate(SPORSMAL):
        # Kontekst som Belegg sender: de tre forrige brukerspørsmålene i samtalen.
        kontekst = " ".join(SPORSMAL[max(0, i - 3):i]) if a.kontekst else ""
        papirer, fraser, _ = r.hent_kilder(q, kontekst=kontekst)
        topp = papirer[:10]
        treff = sum(1 for p in topp if RELEVANT.search(f"{p.tittel or ''} {p.abstract or ''}"))
        art = sum(1 for p in topp if r.domeneprofil.arts_naer_tekst(f"{p.tittel or ''} {p.abstract or ''}"))
        rader.append({"q": q, "fraser": fraser, "antall": len(papirer), "relevante_topp10": treff,
                      "artsnaere_topp10": art,
                      "topp3": [(p.tittel or "")[:80] for p in topp[:3]]})
        print(f"{treff:>2}/10 art {art:>2}/10  n={len(papirer):>2}  {fraser}  <- {q[:60]}")
    snitt = sum(x["relevante_topp10"] for x in rader) / len(rader)
    art_snitt = sum(x["artsnaere_topp10"] for x in rader) / len(rader)
    print(f"[{a.etikett}] snitt relevante av topp 10: {snitt:.1f}, artsnaere: {art_snitt:.1f}")
    ut = ROT / "data" / f"fagterm_eval_{a.etikett}_{datetime.now(timezone.utc):%Y-%m-%d}.json"
    ut.write_text(json.dumps({"etikett": a.etikett, "snitt": snitt, "rader": rader}, ensure_ascii=False, indent=1))
    print("skrevet:", ut.relative_to(ROT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
