# Adapters — kilde-adaptere for forskningssøk
# Hver adapter oversetter en ekstern API til vårt interne PaperDossier-format.

from .core import sok as core_sok
from .europe_pmc import sok as europe_pmc_sok
from .openalex import sok as openalex_sok
from .semantic_scholar import sok as semantic_scholar_sok
# unpaywall har kun tilgang(), crossref har kun referanser() - ingen sok()

__all__ = [
    "core_sok",
    "europe_pmc_sok",
    "openalex_sok",
    "semantic_scholar_sok",
]
