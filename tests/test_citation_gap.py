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

@pytest.fixture(autouse=True)
def _ingen_ekte_crossref():
    """Crossref-supplementet ble lagt til 2026-09-04 og gjorde tre av testene under
    NETTVERKSAVHENGIGE uten at noe sa fra — de gikk grønt bare fordi maskinen tilfeldigvis
    hadde internett, og `test_europe_pmc_svarer_normalt_bruker_ikke_openalex` sluttet å
    verifisere det navnet lover. Autouse-fixturen lukker hele klassen: ingen test i denne
    fila kan nå nå nettet uten å overstyre den EKSPLISITT.

    Nøytral standard er «utgiveren har ikke deponert noe» (tom liste, ukjent antall) —
    det er det vanligste ekte svaret, og det som ikke endrer de eksisterende
    forventningene."""
    with patch("citation_gap.crossref.referanser", return_value=[]), \
         patch("citation_gap.crossref.referanse_antall", return_value=None):
        yield


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


def test_manglende_pmid_med_doi_hopper_rett_til_openalex_uten_aa_forsoke_europe_pmc():
    """CORE/OpenAlex-only-papirer mangler ofte PMID — Europe PMC krever det, så et
    forsøk der ville vært bortkastet, ikke bare unødvendig. pmid=None + DOI-id skal
    gå rett til OpenAlex, umerket som fallback (Europe PMC ble aldri forsøkt)."""
    with patch("citation_gap.europepmc_referanser") as m_pmc, \
         patch("citation_gap.openalex.referanser", return_value=REFERANSER) as m_oa, \
         patch("citation_gap.lignende", return_value=NABOER):
        ut = gap_kandidater("10.1000/mitt-papir", "MED", None)
    m_pmc.assert_not_called()
    m_oa.assert_called_once_with("10.1000/mitt-papir")
    assert ut["referanse_kilde"] == "openalex"  # ikke "fallback" — det var ikke ett


def test_manglende_pmid_og_doi_gir_tydelig_feil_ikke_stille_tomt():
    with patch("citation_gap.europepmc_referanser") as m_pmc, \
         patch("citation_gap.openalex.referanser") as m_oa, \
         patch("citation_gap.lignende", return_value=NABOER):
        with pytest.raises(RuntimeError, match="mangler både PMID og DOI"):
            gap_kandidater("41363532", "MED", None)  # PMID-løst id, ikke DOI
    m_pmc.assert_not_called()
    m_oa.assert_not_called()


# ---------- Crossref-supplementet: union, aldri erstatning ----------

CROSSREF_EKSTRA = [
    {"doi": "10.1000/ikke-sitert", "title": "et helt ferskt, usitert funn"},
    {"doi": "10.1000/bare-hos-crossref", "title": "kun i utgiverens deposit"},
]


def test_crossref_supplement_kan_bare_korte_ned_gap_listen():
    """Kjernen: en referanse primærkilden ikke kjente gjorde en nabo til et FALSKT gap.
    Målt live 2026-09-04 — OpenAlex kjente 13 av 20 for 10.1111/jfd.70099."""
    with patch("citation_gap.europepmc_referanser", return_value=REFERANSER), \
         patch("citation_gap.crossref.referanser", return_value=CROSSREF_EKSTRA), \
         patch("citation_gap.crossref.referanse_antall", return_value=None), \
         patch("citation_gap.lignende", return_value=NABOER):
        ut = gap_kandidater("10.1000/mitt-papir", "MED", "123")
    assert ut["gap"] == []           # «c» var et falskt gap, Crossref visste den var sitert
    assert ut["siterte_antall"] == 4
    assert "crossref" in ut["referanse_kilde"]


def test_crossref_uten_nye_referanser_endrer_ingenting():
    with patch("citation_gap.europepmc_referanser", return_value=REFERANSER), \
         patch("citation_gap.crossref.referanser", return_value=REFERANSER), \
         patch("citation_gap.crossref.referanse_antall", return_value=None), \
         patch("citation_gap.lignende", return_value=NABOER):
        ut = gap_kandidater("10.1000/mitt-papir", "MED", "123")
    assert ut["siterte_antall"] == 2
    assert "crossref" not in ut["referanse_kilde"]  # ingen falsk kreditt for null bidrag


def test_crossref_nede_velter_ikke_et_svar_primaerkilden_alt_ga():
    with patch("citation_gap.europepmc_referanser", return_value=REFERANSER), \
         patch("citation_gap.crossref.referanser", side_effect=RuntimeError("503")), \
         patch("citation_gap.crossref.referanse_antall", return_value=None), \
         patch("citation_gap.lignende", return_value=NABOER):
        ut = gap_kandidater("10.1000/mitt-papir", "MED", "123")
    assert ut["referanse_kilde"] == "europe_pmc"
    assert len(ut["gap"]) == 1


def test_kortere_liste_enn_utgiverens_tall_gir_dekningsforbehold():
    with patch("citation_gap.europepmc_referanser", return_value=REFERANSER), \
         patch("citation_gap.crossref.referanser", return_value=[]), \
         patch("citation_gap.crossref.referanse_antall", return_value=20), \
         patch("citation_gap.lignende", return_value=NABOER):
        ut = gap_kandidater("10.1000/mitt-papir", "MED", "123")
    assert ut["referanse_dekning"] == {"hentet": 2, "oppgitt_av_utgiver": 20}


def test_fullstendig_liste_gir_ingen_forbehold():
    """Forbeholdet må forsvinne når det ikke gjelder — et permanent «kan være
    ufullstendig» ville blitt lest som støy og sluttet å bety noe."""
    with patch("citation_gap.europepmc_referanser", return_value=REFERANSER), \
         patch("citation_gap.crossref.referanser", return_value=[]), \
         patch("citation_gap.crossref.referanse_antall", return_value=2), \
         patch("citation_gap.lignende", return_value=NABOER):
        ut = gap_kandidater("10.1000/mitt-papir", "MED", "123")
    assert ut["referanse_dekning"] is None


def test_dekning_uten_crossref_svar_paastaar_ingenting():
    with patch("citation_gap.europepmc_referanser", return_value=REFERANSER), \
         patch("citation_gap.lignende", return_value=NABOER):
        ut = gap_kandidater("10.1000/mitt-papir", "MED", "123")
    assert ut["referanse_dekning"] is None


# ---------- Utgivelsesår: proben overdrev grovt uten det (2026-09-05) ----------

FERSKE_NABOER = [
    {"id": "gammel", "doi": "10.1000/gammel", "tittel": "kunne vært sitert",
     "tidsskrift": "X", "aar": 2021, "kilde_url": "u", "avstand": 0.2},
    {"id": "samme-aar", "doi": "10.1000/samme", "tittel": "utgitt samme år",
     "tidsskrift": "X", "aar": 2023, "kilde_url": "u", "avstand": 0.3},
    {"id": "fersk", "doi": "10.1000/fersk", "tittel": "kom ut tre år etterpå",
     "tidsskrift": "X", "aar": 2026, "kilde_url": "u", "avstand": 0.4},
    {"id": "ukjent-aar", "doi": "10.1000/ukjent", "tittel": "ingen dato i posten",
     "tidsskrift": "X", "aar": None, "kilde_url": "u", "avstand": 0.5},
]


def test_nabo_publisert_etter_kilden_er_ikke_et_gap():
    """Live-målt 2026-09-05 på 10.1111/jfd.13815 (2023): 8 av 10 naboer ble meldt som gap,
    men fem var fra 2024-2026. Et papir fra 2023 kan ikke sitere et papir fra 2026 — de var
    aritmetisk umulige, ikke noe forfatteren overså. Ekte gap var tre."""
    with patch("citation_gap.europepmc_referanser", return_value=[]), \
         patch("citation_gap.lignende", return_value=FERSKE_NABOER):
        ut = gap_kandidater("mitt-papir", "MED", "123", kilde_aar=2023)
    assert {g["id"] for g in ut["gap"]} == {"gammel", "samme-aar", "ukjent-aar"}
    assert {g["id"] for g in ut["publisert_etter"]} == {"fersk"}


def test_de_ferske_kastes_ikke_bare_flyttes():
    """Huset flagger, det filtrerer ikke. «Dette har kommet siden papiret ble skrevet» er
    en interessant liste i seg selv — den skal bare aldri telles som et gap."""
    with patch("citation_gap.europepmc_referanser", return_value=[]), \
         patch("citation_gap.lignende", return_value=FERSKE_NABOER):
        ut = gap_kandidater("mitt-papir", "MED", "123", kilde_aar=2023)
    assert len(ut["gap"]) + len(ut["publisert_etter"]) == len(FERSKE_NABOER)


def test_ukjent_kildeaar_gir_ingen_dom():
    """«Vi vet ikke når kilden kom ut» er ikke det samme som «alt kunne vært sitert» — men
    å gjette ville vært verre. Uten år står alle som kandidater, slik de gjorde før."""
    with patch("citation_gap.europepmc_referanser", return_value=[]), \
         patch("citation_gap.lignende", return_value=FERSKE_NABOER):
        ut = gap_kandidater("mitt-papir", "MED", "123", kilde_aar=None)
    assert len(ut["gap"]) == 4 and ut["publisert_etter"] == []
