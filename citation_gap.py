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

**Kilde-fallback (lagt til 2026-09-02):** Europe PMC sin `/references` var i et
vedlikeholdsvindu HELE kvelden koden ble bygget — samme kveld ble `adapters/openalex.py`
verifisert som en ekte fungerende erstatning for nøyaktig denne biten (batch-oppløste
`referenced_works` til reelle titler/DOI-er). Faller derfor over automatisk, og
RAPPORTERER hvilken kilde som faktisk svarte (transparens-prinsippet, idébank #29
§Mønstre verdt å stjele punkt 4) — aldri stille.

**Ærlighets-prinsippet gjelder også dommen:** et gap-kandidat er IKKE en påstand om at
noe MANGLER i litteraturen — det er en kandidat for et menneske (Ulven/Anders) å vurdere.
Verktøyet leverer listen, gjetter aldri selv om noe «burde» vært sitert.
"""
import re

from adapters import openalex
from adapters.europe_pmc import referanser as europepmc_referanser
from bank import lignende


def _norm_tittel(t: str) -> str:
    """Fjerner tegnsetting FØR whitespace kollapses — «Tittel — Undertittel!» og
    «tittel undertittel» skal matche selv om kilden (/search vs. /references) formaterer
    bindestrek/tegnsetting ulikt. Fanget av en ekte testfeil under bygging (em-dash i én
    kilde ga dobbelt mellomrom som IKKE matchet enkelt mellomrom i den andre)."""
    uten_tegn = re.sub(r"[^a-z0-9 ]", " ", (t or "").lower())
    return re.sub(r"\s+", " ", uten_tegn).strip()


def _hent_referanser(paper_id: str, kilde_kode: str, ekte_id: str) -> tuple[list[dict], str]:
    """Europe PMC først (mest presis kilde-tro — dette ER kilden vi ellers bruker).
    OpenAlex kun hvis Europe PMC faktisk feiler, OG bare når paper_id er en DOI (OpenAlex
    slår opp på DOI, ikke PMID) — begge feiler -> RuntimeError forplantes uendret, aldri
    et stille tomt resultat som ville sett ut som «ingenting å sammenligne mot»."""
    try:
        return europepmc_referanser(kilde_kode, ekte_id), "europe_pmc"
    except RuntimeError as e_pmc:
        if not paper_id.startswith("10."):
            raise
        try:
            return openalex.referanser(paper_id), "openalex (fallback — Europe PMC utilgjengelig)"
        except RuntimeError as e_oa:
            raise RuntimeError(f"begge referanse-kilder feilet — Europe PMC: {e_pmc} | OpenAlex: {e_oa}") from e_oa


def gap_kandidater(paper_id: str, kilde_kode: str, ekte_id: str, k: int = 10) -> dict:
    """paper_id = cache-id brukt i bank.py (doi/pmid). kilde_kode+ekte_id = det Europe
    PMC trenger for /references (f.eks. "MED", "41363532"). Matcher naboer mot den
    faktiske referanselisten på DOI FØRST (mest presist når til stede), tittel som
    fallback (DOI mangler ofte i referanselister — se adapters/europe_pmc.py:referanser
    sin docstring). Returnerer {siterte_antall, referanse_kilde, naboer, gap} — `gap` er
    naboene som verken DOI- eller tittel-matcher noe i referanselisten."""
    ref_rader, kilde_brukt = _hent_referanser(paper_id, kilde_kode, ekte_id)
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

    return {"siterte_antall": len(ref_rader), "referanse_kilde": kilde_brukt,
            "naboer": naboer, "gap": gap}
