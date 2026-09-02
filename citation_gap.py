"""citation_gap.py — Aaron Tays fleksibilitets-probe som en kjørbar akseptansetest.

Bakgrunn: prosjekt/idebank/29-forskningssok-rammeverk §Mønstre verdt å stjele, punkt 5.
Probe: *«finn papirer som BURDE vært sitert av papir X, men ikke er det.»* Spesialiserte
forskningsverktøy (Elicit, Consensus Deep Search, Undermind, AI2 Paperfinder) feilet denne
testen systematisk i uavhengige tester — de kjører forhåndsbygde skript med AI-
beslutningspunkter, ikke ekte resonnering, og «finner» stort sett bare det kildepapiret
allerede siterer.

Testen her: for et cachet papir, hent dets FAKTISKE referanseliste (Europe PMC
`/references` — hva PAPIRET SELV siterer), og se om `bank.py`s embedding-avstand finner
cachede naboer som IKKE er i den listen. Er det relasjonelle laget (`bank.py:lignende`)
ekte semantisk nærhet, eller bare et pent rangert ekko av det som uansett siteres?

**Ærlighets-prinsippet gjelder også dommen:** et gap-kandidat er IKKE en påstand om at
noe MANGLER i litteraturen — det er en kandidat for et menneske (Ulven/Anders) å vurdere.
Verktøyet leverer listen, gjetter aldri selv om noe «burde» vært sitert.
"""
import re

from adapters.europe_pmc import referanser
from bank import lignende


def _norm_tittel(t: str) -> str:
    """Fjerner tegnsetting FØR whitespace kollapses — «Tittel — Undertittel!» og
    «tittel undertittel» skal matche selv om kilden (/search vs. /references) formaterer
    bindestrek/tegnsetting ulikt. Fanget av en ekte testfeil under bygging (em-dash i én
    kilde ga dobbelt mellomrom som IKKE matchet enkelt mellomrom i den andre)."""
    uten_tegn = re.sub(r"[^a-z0-9 ]", " ", (t or "").lower())
    return re.sub(r"\s+", " ", uten_tegn).strip()


def gap_kandidater(paper_id: str, kilde_kode: str, ekte_id: str, k: int = 10) -> dict:
    """paper_id = cache-id brukt i bank.py (doi/pmid). kilde_kode+ekte_id = det Europe
    PMC trenger for /references (f.eks. "MED", "41363532"). Matcher naboer mot den
    faktiske referanselisten på DOI FØRST (mest presist når til stede), tittel som
    fallback (DOI mangler ofte i referanselister — se adapters/europe_pmc.py:referanser
    sin docstring). Returnerer {siterte_antall, naboer, gap} — `gap` er naboene som
    verken DOI- eller tittel-matcher noe i referanselisten."""
    ref_rader = referanser(kilde_kode, ekte_id)
    siterte_doier = {r["doi"].lower() for r in ref_rader if r.get("doi")}
    siterte_titler = {_norm_tittel(r.get("title", "")) for r in ref_rader if r.get("title")}

    naboer = lignende(paper_id, k=k)
    gap = []
    for n in naboer:
        doi = (n.get("doi") or "").lower()
        if doi and doi in siterte_doier:
            continue
        if _norm_tittel(n.get("tittel", "")) in siterte_titler:
            continue
        gap.append(n)

    return {"siterte_antall": len(ref_rader), "naboer": naboer, "gap": gap}
