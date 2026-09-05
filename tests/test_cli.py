"""Verifiserer selve poenget med §resolve-notatet i cli.py: en emne-spørring med treff
skal ALDRI rapporteres som tomt (resolve.py sin substreng-gren ville gjort nettopp det
mot lange papirtitler) — og en spørring som er ORDRETT en tittel skal flagges eksakt.
Verifiserer også fler-kilde-sammenslåingen (Europe PMC + CORE, lagt til 2026-09-02):
CORE er en tilleggskilde, en CORE-feil skal degradere synlig (kilder-dict), ikke ta
ned søket, og dubletter på tvers av kildene skal ikke dobbeltvises.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import sok_og_ranger  # noqa: E402
from schemas import PaperDossier  # noqa: E402


def _p(pid, tittel, doi=None):
    return PaperDossier(pmid=pid, doi=doi, tittel=tittel, forfattere="Havforskningsinstituttet",
                        tidsskrift="Journal of Fish Diseases", aar=2026, abstract="abstract",
                        siteringstall=0, open_access=False, kilde_url=f"https://example.org/{pid}")


def test_emnesporring_med_treff_er_aldri_ingen_treff(tmp_path):
    """Kjernen i notatet i cli.py: 'nephrocalcinosis smolt' er ikke en substreng av og
    inneholder ikke noen av titlene — resolve()s kandidat-gren ville gitt tom liste her."""
    treff = [_p("1", "Nephrocalcinosis progression in Atlantic salmon post-seawater transfer")]
    with patch("cli.sok", return_value=treff), patch("cli.core_adapter.sok", return_value=[]), \
         patch("cli.lagre") as mock_lagre:
        papirer, eksakt_id, revisjon = sok_og_ranger("nephrocalcinosis smolt seawater transfer")
    mock_lagre.assert_not_called()  # 2026-09-04: lagre() er kallerens ansvar, ikke denne
    assert len(papirer) == 1
    assert eksakt_id is None  # ikke en ordrett tittel — skal IKKE feilaktig flagges eksakt
    assert revisjon["kilder"] == {"europe_pmc": True, "core": True}


def test_ordrett_tittel_flagges_eksakt(tmp_path):
    tittel = "Nephrocalcinosis progression in Atlantic salmon post-seawater transfer"
    treff = [_p("1", tittel), _p("2", "Et annet, urelatert papir")]
    with patch("cli.sok", return_value=treff), patch("cli.core_adapter.sok", return_value=[]), \
         patch("cli.lagre"):
        papirer, eksakt_id, revisjon = sok_og_ranger(tittel)
    assert eksakt_id == "1"


def test_tom_europe_pmc_respons_er_aerlig_tomt(tmp_path):
    with patch("cli.sok", return_value=[]), patch("cli.core_adapter.sok", return_value=[]), \
         patch("cli.lagre"):
        papirer, eksakt_id, revisjon = sok_og_ranger("et sikkert ubesvarlig søk xyzzy123")
    assert papirer == []
    assert eksakt_id is None


def test_core_treff_slaas_sammen_med_europe_pmc(tmp_path):
    pmc_treff = [_p("1", "Europe PMC-funn")]
    core_treff = [_p(None, "Et CORE-funn (institusjonsarkiv)")]
    with patch("cli.sok", return_value=pmc_treff), patch("cli.core_adapter.sok", return_value=core_treff), \
         patch("cli.lagre"):
        papirer, eksakt_id, revisjon = sok_og_ranger("nephrocalcinosis salmon")
    titler = {p.tittel for p in papirer}
    assert titler == {"Europe PMC-funn", "Et CORE-funn (institusjonsarkiv)"}
    assert revisjon["kilder"] == {"europe_pmc": True, "core": True}


def test_core_feiler_degraderer_synlig_uten_aa_ta_ned_soeket(tmp_path):
    pmc_treff = [_p("1", "Europe PMC-funn")]
    with patch("cli.sok", return_value=pmc_treff), \
         patch("cli.core_adapter.sok", side_effect=RuntimeError("CORE utilgjengelig: 503")), \
         patch("cli.lagre"):
        papirer, eksakt_id, revisjon = sok_og_ranger("nephrocalcinosis salmon")
    assert len(papirer) == 1  # Europe PMC-resultatet er ikke tapt
    assert revisjon["kilder"] == {"europe_pmc": True, "core": False}  # kun CORE feilet, synlig
    assert revisjon["treff_per_kilde"]["core"] == 0, "en nede kilde teller null, ikke ingenting"


def test_samme_papir_fra_begge_kilder_dedupliseres_paa_tittel(tmp_path):
    """Samme funn kan finnes både i Europe PMC og som institusjonsarkiv-kopi i CORE —
    uten DOI i CORE-kopien er tittel eneste felles nøkkel."""
    delt_tittel = "Nephrocalcinosis in juvenile farmed Atlantic salmon"
    pmc_treff = [_p("1", delt_tittel, doi="10.1/delt")]
    core_treff = [_p(None, delt_tittel)]  # samme tittel, ingen DOI (typisk CORE-mastergrad)
    with patch("cli.sok", return_value=pmc_treff), patch("cli.core_adapter.sok", return_value=core_treff), \
         patch("cli.lagre"):
        papirer, eksakt_id, revisjon = sok_og_ranger("nephrocalcinosis salmon")
    assert len(papirer) == 1  # ikke to rader for samme papir


def test_revisjonen_forteller_hva_som_faktisk_kjorte(tmp_path):
    """«20 treff» kan bety fire ulike ting. Revisjonen skiller dem: hvor mange hver kilde
    ga, hvor mange dubletter som ble slått sammen, og om svaret kom fra cache."""
    pmc = [_p("1", "Et funn"), _p("2", "Et delt funn", doi="10.1/delt")]
    core = [_p(None, "Et delt funn")]  # samme tittel, ingen DOI — dedupliseres bort
    with patch("cli.sok", return_value=pmc), patch("cli.core_adapter.sok", return_value=core), \
         patch("cli.europe_pmc_cache_alder", return_value=3600.0), patch("cli.lagre"):
        papirer, _, revisjon = sok_og_ranger("nephrocalcinosis salmon")
    assert revisjon["treff_per_kilde"] == {"europe_pmc": 2, "core": 1}
    assert revisjon["dubletter_fjernet"] == 1
    assert revisjon["etter_dedup"] == 2 == len(papirer)
    assert revisjon["cache_alder_s"] == 3600
    assert "baand" in revisjon and "profil" in revisjon


def test_cache_alder_leses_FOR_soket_ellers_er_den_alltid_null(tmp_path):
    """sok() skriver en fersk cache-rad. Leses alderen etterpå, blir svaret «0 sekunder»
    for hvert eneste søk — et tall som alltid ser likt ut måler ingenting."""
    rekkefolge = []
    with patch("cli.europe_pmc_cache_alder", side_effect=lambda *a, **k: rekkefolge.append("alder")), \
         patch("cli.sok", side_effect=lambda *a, **k: rekkefolge.append("sok") or []), \
         patch("cli.core_adapter.sok", return_value=[]), patch("cli.lagre"):
        sok_og_ranger("noe")
    assert rekkefolge == ["alder", "sok"]
