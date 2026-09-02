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
from adapters import openalex
from adapters.europe_pmc import referanser as europepmc_referanser
from bank import lignende
from dedup import norm_tittel as _norm_tittel


def _hent_referanser(paper_id: str, kilde_kode: str, pmid: str | None) -> tuple[list[dict], str]:
    """Europe PMC først NÅR pmid finnes (mest presis kilde-tro — dette ER kilden vi
    ellers bruker); Europe PMC krever PMID, så uten det hopper vi rett til OpenAlex i
    stedet for å gjøre et kall vi vet feiler. OpenAlex krever DOI — brukt enten fordi
    pmid manglet (CORE/OpenAlex-only-papirer har ofte ikke PMID) eller som fallback når
    Europe PMC faktisk feiler mens paper_id er en DOI. Ingen brukbar kilde -> RuntimeError
    forplantes uendret, aldri et stille tomt resultat som ville sett ut som «ingenting å
    sammenligne mot»."""
    e_pmc = None
    if pmid:
        try:
            return europepmc_referanser(kilde_kode, pmid), "europe_pmc"
        except RuntimeError as e:
            e_pmc = e
    if paper_id.startswith("10."):
        try:
            data = openalex.referanser(paper_id)
            kilde = "openalex" if e_pmc is None else "openalex (fallback — Europe PMC utilgjengelig)"
            return data, kilde
        except RuntimeError as e_oa:
            if e_pmc is not None:
                raise RuntimeError(f"begge referanse-kilder feilet — Europe PMC: {e_pmc} | OpenAlex: {e_oa}") from e_oa
            raise RuntimeError(f"OpenAlex utilgjengelig, og papiret mangler PMID for Europe PMC: {e_oa}") from e_oa
    if e_pmc is not None:
        raise e_pmc
    raise RuntimeError("papiret mangler både PMID og DOI — ingen referanse-kilde tilgjengelig")


def gap_kandidater(paper_id: str, kilde_kode: str, pmid: str | None, k: int = 10) -> dict:
    """paper_id = cache-id brukt i bank.py (doi/pmid). kilde_kode+pmid = det Europe PMC
    trenger for /references (f.eks. "MED", "41363532") — pmid kan være None (CORE/
    OpenAlex-only-papirer mangler ofte PMID), da brukes OpenAlex direkte (krever i
    stedet at paper_id er en DOI). Matcher naboer mot den faktiske referanselisten på
    DOI FØRST (mest presist når til stede), tittel som fallback (DOI mangler ofte i
    referanselister — se adapters/europe_pmc.py:referanser sin docstring). Returnerer
    {siterte_antall, referanse_kilde, naboer, gap} — `gap` er naboene som verken DOI-
    eller tittel-matcher noe i referanselisten."""
    ref_rader, kilde_brukt = _hent_referanser(paper_id, kilde_kode, pmid)
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
