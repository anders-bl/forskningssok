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

    @property
    def id(self) -> str:
        """Stabil identitet på tvers av re-søk — DOI foretrukket (kilde-uavhengig),
        PMID som fallback, aldri gjettet fra tittel (titler kan gjenbrukes/endres)."""
        return self.doi or self.pmid or self.kilde_url
