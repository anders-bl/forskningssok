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

    @property
    def id(self) -> str:
        """Stabil identitet på tvers av re-søk — DOI foretrukket (kilde-uavhengig),
        PMID som fallback, aldri gjettet fra tittel (titler kan gjenbrukes/endres)."""
        return self.doi or self.pmid or self.kilde_url
