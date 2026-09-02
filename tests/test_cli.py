"""Verifiserer selve poenget med §resolve-notatet i cli.py: en emne-spørring med treff
skal ALDRI rapporteres som tomt (resolve.py sin substreng-gren ville gjort nettopp det
mot lange papirtitler) — og en spørring som er ORDRETT en tittel skal flagges eksakt.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import sok_og_ranger  # noqa: E402
from schemas import PaperDossier  # noqa: E402


def _p(pid, tittel):
    return PaperDossier(pmid=pid, doi=None, tittel=tittel, forfattere="Havforskningsinstituttet",
                        tidsskrift="Journal of Fish Diseases", aar=2026, abstract="abstract",
                        siteringstall=0, open_access=False, kilde_url=f"https://example.org/{pid}")


def test_emnesporring_med_treff_er_aldri_ingen_treff(tmp_path):
    """Kjernen i notatet i cli.py: 'nephrocalcinosis smolt' er ikke en substreng av og
    inneholder ikke noen av titlene — resolve()s kandidat-gren ville gitt tom liste her."""
    treff = [_p("1", "Nephrocalcinosis progression in Atlantic salmon post-seawater transfer")]
    with patch("cli.sok", return_value=treff), patch("cli.lagre", return_value=1):
        papirer, eksakt_id = sok_og_ranger("nephrocalcinosis smolt seawater transfer")
    assert len(papirer) == 1
    assert eksakt_id is None  # ikke en ordrett tittel — skal IKKE feilaktig flagges eksakt


def test_ordrett_tittel_flagges_eksakt(tmp_path):
    tittel = "Nephrocalcinosis progression in Atlantic salmon post-seawater transfer"
    treff = [_p("1", tittel), _p("2", "Et annet, urelatert papir")]
    with patch("cli.sok", return_value=treff), patch("cli.lagre", return_value=2):
        papirer, eksakt_id = sok_og_ranger(tittel)
    assert eksakt_id == "1"


def test_tom_europe_pmc_respons_er_aerlig_tomt(tmp_path):
    with patch("cli.sok", return_value=[]), patch("cli.lagre", return_value=0):
        papirer, eksakt_id = sok_og_ranger("et sikkert ubesvarlig søk xyzzy123")
    assert papirer == []
    assert eksakt_id is None
