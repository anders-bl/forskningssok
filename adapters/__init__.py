# Adapters — kilde-adaptere for forskningssøk
# Hver adapter oversetter en ekstern API til vårt interne PaperDossier-format.

from .core import sok as core_sok
from .europe_pmc import sok as europe_pmc_sok
from .openalex import sok as openalex_sok
from .crossref import sok as crossref_sok
from .unpaywall import finn_fulltekst as unpaywall_finn_fulltekst
from .semantic_scholar import sok as semantic_scholar_sok

__all__ = [
    "core_sok",
    "europe_pmc_sok",
    "openalex_sok",
    "crossref_sok",
    "unpaywall_finn_fulltekst",
    "semantic_scholar_sok",
]
