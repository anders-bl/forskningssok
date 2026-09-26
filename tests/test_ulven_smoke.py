"""Nettverksfri kontrakts-smoke for Ulvens viktigste lesereise.

Den sikrer API-kontrakten og DOM-landemerkene nettlesertesten bruker.
Desktop-/mobilatferden ligger i test_ulven_browser.py; produksjonstilgang
verifiseres separat.
"""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import api
from schemas import PaperDossier


ROT = Path(__file__).resolve().parent.parent
FRONTEND = ROT / "frontend" / "index.html"


def _papir(pid: str = "1") -> PaperDossier:
    return PaperDossier(
        pmid=pid,
        doi=None,
        tittel="Nephrocalcinosis in Atlantic salmon",
        forfattere="Testforfatter",
        tidsskrift="Journal of Fish Diseases",
        aar=2026,
        abstract="Et testabstract.",
        siteringstall=2,
        open_access=False,
        kilde_url="https://example.org/paper",
    )


def test_ulven_flaten_har_status_og_smoke_landemerker() -> None:
    html = FRONTEND.read_text(encoding="utf-8")
    for landmark in (
        'id="search-form"',
        'id="result-list"',
        'id="revisjon-sammendrag"',
        'id="btn-dossier"',
        'id="btn-syntese"',
        'id="rapport-i-appen"',
        'data-tab="kart"',
        'data-tab="gap"',
        'data-tab="sti"',
    ):
        assert landmark in html
    assert "@media (max-width:760px)" in html
    assert "Kilder: ${kildeStatus}" in html


def test_doi_handoff_velger_ikke_fremmed_treff_ved_manglende_doi() -> None:
    html = FRONTEND.read_text(encoding="utf-8")
    start = html.index("async function utforSok(")
    slutt = html.index("\n}\n", start) + 2
    sokefunksjon = html[start:slutt]

    assert "if (foretrukket) openPaper(foretrukket.id);" in sokefunksjon
    assert (
        "else if (!foretrukketDoi && data.papirer.length) "
        "openPaper(data.papirer[0].id);"
    ) in sokefunksjon
    assert "Fant ikke et eksakt DOI-treff" in sokefunksjon


def test_ulven_hovedreise_beholder_revisjon_og_resultater() -> None:
    treff = [_papir()]
    revisjon = {
        "kilder": {"europe_pmc": True, "core": True, "openalex": True},
        "treff_per_kilde": {"europe_pmc": 1, "core": 0, "openalex": 0},
        "etter_dedup": 1,
        "dubletter_fjernet": 0,
        "cache_alder_s": None,
        "profil": "test",
        "baand": {"domene_naer": 1, "arts_naer": 1},
        "ms": 1,
    }
    with patch("api.sok_og_ranger", return_value=(treff, None, revisjon)), \
         patch("api.bank.lagre"), patch("api.bank.logg_sok"), \
         patch("api.bank.registrer_kildekall"):
        response = TestClient(api.app).get("/api/sok?q=nephrocalcinosis+salmon&n=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["papirer"][0]["id"] == "1"
    assert payload["revisjon"]["kilder"] == revisjon["kilder"]
    assert payload["revisjon"]["treff_per_kilde"] == revisjon["treff_per_kilde"]
