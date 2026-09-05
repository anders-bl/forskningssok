"""kilde_liveness.py — er referanse-kildene levende? En SMAL detektor med kontroll.

Citation-gap-testen (`citation_gap.py`) står på tre kilder: Europe PMC `/references`,
OpenAlex, Crossref. EBIs `/references` har vært 503 i en uke uten at noe pekte på roten —
et endepunkt som alltid feiler ser ut som «tregt», ikke «kilden er nede». Denne detektoren
er felle 38-antidoten ([[konsepter/detektorfelle]]): den skiller «kilden svarte 0» fra
«kilden fant vi ikke».

**Kjernen er en positiv kontroll, ikke en tilstands-sjekk.** Vi spør hver kilde om
referansene til et papir vi VET har mange (kontroll-papiret fra profilen, ~79 referanser).
Da betyr et tomt svar noe entydig: kilden er nede eller ødelagt — det kan IKKE være at
papiret genuint mangler referanser. Uten den kontrollen ville «0 referanser» vært
tvetydig, og en stille-nede kilde ville meldt grønt.

Tre utfall, aldri to:
- **OPPE** — kilden ga referanser (> 0) for kontroll-papiret.
- **NEDE** — kallet kastet (503, timeout, nettverk).
- **MISTENKT_NEDE** — kallet returnerte TOMT for et papir vi vet har referanser. Dette er
  hele poenget: et tomt svar på kontrollen er en svikt, ikke en måling.

Modulen er fagfelt-agnostisk: kontroll-papirets id-er er parametre. Kalleren (cli.py) henter
dem fra profilen, samme mønster som resten av fagfelt-kunnskapen.
"""
from dataclasses import dataclass

OPPE = "OPPE"
NEDE = "NEDE"
MISTENKT_NEDE = "MISTENKT_NEDE"


@dataclass
class Kildesvar:
    navn: str
    status: str
    antall: int = 0
    feil: str = ""


def sjekk_kilde(navn: str, hent_fn) -> Kildesvar:
    """`hent_fn` er en no-arg callable som returnerer en referanseliste eller kaster.

    Kastet unntak = NEDE (kilden svarte ikke). Tom liste = MISTENKT_NEDE, fordi hent_fn
    spør om et papir vi VET har referanser — en tom liste kan da ikke bety «ingen
    referanser», bare at kilden ikke leverte. En ikke-tom liste = OPPE."""
    try:
        refs = hent_fn()
    except Exception as e:
        return Kildesvar(navn, NEDE, feil=f"{type(e).__name__}: {str(e)[:120]}")
    n = len(refs or [])
    if n == 0:
        return Kildesvar(navn, MISTENKT_NEDE,
                         feil="tomt svar på et papir som HAR referanser — kilden leverer ikke")
    return Kildesvar(navn, OPPE, antall=n)


def alle_kilder(*, doi: str | None, pmid: str | None, kilde_kode: str,
                epmc_fn=None, openalex_fn=None, crossref_fn=None) -> list[Kildesvar]:
    """Sjekker de tre referanse-kildene mot kontroll-papiret. Adapter-kallene injiseres i
    test (suiten er nettverksfri); ekte kall er default.

    Europe PMC krever pmid; mangler det, meldes kilden som ikke sjekkbar (ikke NEDE — vi
    kunne ikke prøve, og det skal ikke leses som en svikt). OpenAlex/Crossref krever DOI."""
    if epmc_fn is None:
        from adapters import europe_pmc
        epmc_fn = lambda: europe_pmc.referanser(kilde_kode, pmid)
    if openalex_fn is None:
        from adapters import openalex
        openalex_fn = lambda: openalex.referanser(doi)
    if crossref_fn is None:
        from adapters import crossref
        crossref_fn = lambda: crossref.referanser(doi)

    svar = []
    if pmid:
        svar.append(sjekk_kilde("europe_pmc", epmc_fn))
    else:
        svar.append(Kildesvar("europe_pmc", "IKKE_SJEKKBAR",
                              feil="kontroll-papiret mangler PMID — Europe PMC krever den"))
    if doi:
        svar.append(sjekk_kilde("openalex", openalex_fn))
        svar.append(sjekk_kilde("crossref", crossref_fn))
    return svar


def oppsummer(svar: list[Kildesvar]) -> dict:
    """{alle_oppe, nede, mistenkt}. `nede`+`mistenkt` er kildene som trenger et blikk —
    de to holdes fra hverandre fordi de betyr ulike ting: NEDE svarte ikke, MISTENKT_NEDE
    svarte tomt (verre, fordi den ser ut som et gyldig «0»)."""
    nede = [s.navn for s in svar if s.status == NEDE]
    mistenkt = [s.navn for s in svar if s.status == MISTENKT_NEDE]
    return {
        "alle_oppe": all(s.status == OPPE for s in svar if s.status != "IKKE_SJEKKBAR"),
        "nede": nede,
        "mistenkt_nede": mistenkt,
    }
