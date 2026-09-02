"""Verifiserer matching-logikken i gap_kandidater(): DOI-match og tittel-match ekskluderer
korrekt fra gap-lista, og et papir uten treff i referanselisten forblir i gap. Dette er selve
Aaron Tay-proben (idébank #29) — matching-logikken er det som avgjør om testen sier noe
sant, så den er verifisert isolert fra selve HTTP-laget (mocket her, HTTP mocket i
test_europe_pmc_referanser.py).
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from citation_gap import gap_kandidater  # noqa: E402

REFERANSER = [
    {"id": "1", "doi": "10.1000/sitert-med-doi", "title": "Sitert, matches på DOI"},
    {"id": "2", "title": "Sitert Uten DOI — Matcher På Tittel!"},  # store bokstaver+tegn testet
]

NABOER = [
    {"id": "a", "doi": "10.1000/sitert-med-doi", "tittel": "et annet navn enn referansen selv",
     "tidsskrift": "X", "aar": 2020, "kilde_url": "u", "avstand": 0.1},
    {"id": "b", "doi": None, "tittel": "sitert uten doi matcher på tittel",
     "tidsskrift": "X", "aar": 2019, "kilde_url": "u", "avstand": 0.2},
    {"id": "c", "doi": "10.1000/ikke-sitert", "tittel": "et helt ferskt, usitert funn",
     "tidsskrift": "X", "aar": 2026, "kilde_url": "u", "avstand": 0.3},
]


def test_doi_match_ekskluderer_fra_gap():
    with patch("citation_gap.europepmc_referanser", return_value=REFERANSER), \
         patch("citation_gap.lignende", return_value=NABOER):
        ut = gap_kandidater("mitt-papir", "MED", "123")
    gap_ider = {g["id"] for g in ut["gap"]}
    assert "a" not in gap_ider  # matchet på DOI, selv om tittelen er ulik


def test_tittel_match_ekskluderer_fra_gap_case_og_tegn_insensitivt():
    with patch("citation_gap.europepmc_referanser", return_value=REFERANSER), \
         patch("citation_gap.lignende", return_value=NABOER):
        ut = gap_kandidater("mitt-papir", "MED", "123")
    gap_ider = {g["id"] for g in ut["gap"]}
    assert "b" not in gap_ider  # matchet på normalisert tittel, ingen DOI å matche på


def test_usitert_papir_blir_i_gap():
    with patch("citation_gap.europepmc_referanser", return_value=REFERANSER), \
         patch("citation_gap.lignende", return_value=NABOER):
        ut = gap_kandidater("mitt-papir", "MED", "123")
    gap_ider = {g["id"] for g in ut["gap"]}
    assert gap_ider == {"c"}
    assert ut["siterte_antall"] == 2
    assert len(ut["naboer"]) == 3


def test_tom_referanseliste_gir_alle_naboer_som_gap():
    with patch("citation_gap.europepmc_referanser", return_value=[]), \
         patch("citation_gap.lignende", return_value=NABOER):
        ut = gap_kandidater("mitt-papir", "MED", "123")
    assert len(ut["gap"]) == 3
    assert ut["siterte_antall"] == 0


def test_europe_pmc_svarer_normalt_bruker_ikke_openalex():
    with patch("citation_gap.europepmc_referanser", return_value=REFERANSER) as m_pmc, \
         patch("citation_gap.openalex.referanser") as m_oa, \
         patch("citation_gap.lignende", return_value=NABOER):
        ut = gap_kandidater("10.1000/mitt-papir", "MED", "123")
    m_pmc.assert_called_once()
    m_oa.assert_not_called()
    assert ut["referanse_kilde"] == "europe_pmc"


def test_europe_pmc_feiler_faller_over_paa_openalex_for_doi():
    with patch("citation_gap.europepmc_referanser", side_effect=RuntimeError("503")), \
         patch("citation_gap.openalex.referanser", return_value=REFERANSER) as m_oa, \
         patch("citation_gap.lignende", return_value=NABOER):
        ut = gap_kandidater("10.1000/mitt-papir", "MED", "123")
    m_oa.assert_called_once_with("10.1000/mitt-papir")
    assert ut["referanse_kilde"].startswith("openalex")
    assert ut["siterte_antall"] == 2  # samme matching-logikk virker uansett kilde


def test_europe_pmc_feiler_uten_doi_gir_ikke_openalex_fallback():
    """PMID-only papir (ingen DOI) -> OpenAlex-oppslag (som krever DOI) er meningsløst,
    ikke bare unødvendig — riktig oppførsel er å forplante feilen, ikke late som om
    fallback ble forsøkt."""
    with patch("citation_gap.europepmc_referanser", side_effect=RuntimeError("503")), \
         patch("citation_gap.openalex.referanser") as m_oa, \
         patch("citation_gap.lignende", return_value=NABOER):
        with pytest.raises(RuntimeError):
            gap_kandidater("41363532", "MED", "41363532")  # PMID som id, ikke DOI
    m_oa.assert_not_called()


def test_begge_kilder_feiler_gir_kombinert_feilmelding():
    with patch("citation_gap.europepmc_referanser", side_effect=RuntimeError("EBI nede")), \
         patch("citation_gap.openalex.referanser", side_effect=RuntimeError("OA nede")), \
         patch("citation_gap.lignende", return_value=NABOER):
        with pytest.raises(RuntimeError, match="EBI nede.*OA nede"):
            gap_kandidater("10.1000/mitt-papir", "MED", "123")
