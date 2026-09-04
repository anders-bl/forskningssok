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
from adapters import crossref, openalex
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


def _forén(*lister: list[dict]) -> list[dict]:
    """Slår sammen referanselister fra flere kilder. Nøkkelen er DOI når den finnes,
    normalisert tittel ellers — samme to-trinns identitet som selve gap-matchingen bruker,
    slik at en referanse ikke kan telles to ganger her og likevel matche én gang der.

    Union kan bare gjøre gap-listen KORTERE. Det er poenget: hver referanse en kilde ikke
    kjenner, blir en nabo som feilaktig framstår som «ikke sitert» — et falskt gap av
    nøyaktig den typen probe-en er bygget for å avsløre."""
    sett: dict[str, dict] = {}
    for rader in lister:
        for r in rader:
            doi = (r.get("doi") or "").lower()
            nokkel = doi or ("tittel::" + _norm_tittel(r.get("title", "")))
            if nokkel in ("", "tittel::"):
                continue
            # Første kilde vinner på innhold, men en senere kilde får fylle inn en DOI
            # den første manglet — det gjør matchingen nedenfor mer presis, ikke mindre.
            if nokkel not in sett:
                sett[nokkel] = r
            elif not sett[nokkel].get("doi") and r.get("doi"):
                sett[nokkel] = {**sett[nokkel], "doi": r["doi"]}
    return list(sett.values())


def _referanser_forent(paper_id: str, kilde_kode: str, pmid: str | None) -> tuple[list[dict], str]:
    """Primærkilden (Europe PMC, ellers OpenAlex) SUPPLERT med utgiverens egen
    Crossref-deposit. Crossref er aldri alene nok — mange utgivere deponerer ikke
    referanselister offentlig i det hele tatt — og feiler derfor stille: en manglende
    supplering skal aldri velte et gap-svar primærkilden alt har levert."""
    primaer, kilde = _hent_referanser(paper_id, kilde_kode, pmid)
    if not paper_id.startswith("10."):
        return primaer, kilde
    try:
        supplement = crossref.referanser(paper_id)
    except RuntimeError:
        return primaer, kilde
    if not supplement:
        return primaer, kilde
    forent = _forén(primaer, supplement)
    if len(forent) > len(primaer):
        kilde += f" + crossref (+{len(forent) - len(primaer)} referanser kilden ikke kjente)"
    return forent, kilde


def gap_kandidater(paper_id: str, kilde_kode: str, pmid: str | None, k: int = 10) -> dict:
    """paper_id = cache-id brukt i bank.py (doi/pmid). kilde_kode+pmid = det Europe PMC
    trenger for /references (f.eks. "MED", "41363532") — pmid kan være None (CORE/
    OpenAlex-only-papirer mangler ofte PMID), da brukes OpenAlex direkte (krever i
    stedet at paper_id er en DOI). Matcher naboer mot den faktiske referanselisten på
    DOI FØRST (mest presist når til stede), tittel som fallback (DOI mangler ofte i
    referanselister — se adapters/europe_pmc.py:referanser sin docstring). Returnerer
    {siterte_antall, referanse_kilde, naboer, gap} — `gap` er naboene som verken DOI-
    eller tittel-matcher noe i referanselisten."""
    ref_rader, kilde_brukt = _referanser_forent(paper_id, kilde_kode, pmid)
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

    # Utgiverens eget referansetall er en UAVHENGIG fasit å måle den hentede listen mot.
    # Uten den ble «papiret siterer 13 kilder selv» presentert som et faktum der
    # sannheten var 20 (målt 10.1111/jfd.70099, 2026-09-04) — og de sju ukjente gjorde
    # gap-listen for lang uten at noe sa fra. None = Crossref vet ikke; da påstås ingenting.
    oppgitt = crossref.referanse_antall(paper_id) if paper_id.startswith("10.") else None
    dekning = None
    if oppgitt and len(ref_rader) < oppgitt:
        dekning = {"hentet": len(ref_rader), "oppgitt_av_utgiver": oppgitt}

    return {"siterte_antall": len(ref_rader), "referanse_kilde": kilde_brukt,
            "referanse_dekning": dekning, "naboer": naboer, "gap": gap}
