"""schemas.py — PaperDossier: strukturert papir-entitet (Lag-3-spec, prosjekt/idebank/28)."""
from dataclasses import dataclass


@dataclass
class PaperDossier:
    pmid: str | None
    doi: str | None
    tittel: str
    forfattere: str
    tidsskrift: str
    aar: int | None
    abstract: str
    siteringstall: int | None
    open_access: bool
    kilde_url: str
    kilde: str = "europe_pmc"
    kilde_kode: str = "MED"  # Europe PMC sin egen kildekode (MED/PPR/PMC …) — trengs for /references
    # Sitasjonsfeltene, lagt til 2026-09-04. Europe PMC har RETURNERT dem hele tiden
    # (journalInfo.volume/issue, pageInfo, journal.issn) — adapteren kastet dem.
    # Uten dem er enhver referanse verktøyet lager ufullstendig i både Vancouver og APA,
    # som begge krever volum og sidetall. Nullbare med vilje: preprints (PPR) og mange
    # institusjonsarkiv-treff HAR ingen volum/hefte, og en tom streng der er sannheten —
    # ikke noe å fylle inn (samme ærlighets-prinsipp som resten av huset).
    volum: str | None = None
    hefte: str | None = None
    sider: str | None = None
    issn: str | None = None
    # NLMs egen indeksering, lagt til 2026-09-04. Europe PMC har returnert begge hele
    # tiden i samme `resultType=core`-svar vi alt gjør — vi kastet dem og gjettet i stedet.
    #
    # pubtyper: NLMs autoritative publikasjonstype («Journal Article», «Review»,
    #   «Randomized Controlled Trial», «Case Reports»). evidensniva.py mønstermatcher
    #   ord i tittel/abstract for å ANSLÅ nettopp dette.
    # mesh: Medical Subject Headings — menneske-indeksert kontrollert vokabular, med
    #   major-topic-flagg. For 10.1111/jfd.70099 sier den «Salmo salar (major)»,
    #   «Fish Diseases (major)» — sterkere og mer presist enn en substreng-liste.
    #
    # Tomme lister, ikke None: et papir UTEN MeSH er som regel et preprint eller et
    # arkivtreff som aldri ble indeksert, ikke et papir uten emne. Fraværet er ekte og
    # skal kunne skilles fra «ikke hentet».
    pubtyper: tuple[str, ...] = ()
    mesh: tuple[str, ...] = ()
    mesh_major: tuple[str, ...] = ()

    @property
    def id(self) -> str:
        """Stabil identitet på tvers av re-søk — DOI foretrukket (kilde-uavhengig),
        PMID som fallback, aldri gjettet fra tittel (titler kan gjenbrukes/endres)."""
        return self.doi or self.pmid or self.kilde_url
