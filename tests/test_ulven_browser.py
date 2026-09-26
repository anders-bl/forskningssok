"""Nettlesertest av Ulvens desktop- og mobilreise med isolerte API-svar."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Browser, Page, Route, sync_playwright


ROT = Path(__file__).resolve().parent.parent
FRONTEND = ROT / "frontend"

PAPIRER = [
    {
        "id": "pmid:1001",
        "pmid": "1001",
        "doi": None,
        "tittel": "Long-term patterns in the study system",
        "forfattere": "A. Researcher et al.",
        "tidsskrift": "Journal of Testable Findings",
        "aar": 2024,
        "abstract": "A test abstract with a clear result.",
        "siteringstall": 12,
        "open_access": False,
        "kilde_url": "https://example.org/paper/1001",
        "domene_naer": True,
        "arts_naer": True,
        "evidensniva": "Observasjonsstudie",
    },
    {
        "id": "pmid:1002",
        "pmid": "1002",
        "doi": None,
        "tittel": "A second source for comparison",
        "forfattere": "B. Scientist",
        "tidsskrift": "Methods Quarterly",
        "aar": 2019,
        "abstract": "A second test abstract.",
        "siteringstall": 4,
        "open_access": True,
        "kilde_url": "https://example.org/paper/1002",
        "domene_naer": False,
        "arts_naer": True,
    },
]

REVISION = {
    "kilder": {"europe_pmc": True, "core": True, "openalex": True},
    "treff_per_kilde": {"europe_pmc": 2, "core": 1, "openalex": 1},
    "etter_dedup": 2,
    "dubletter_fjernet": 2,
    "cache_alder_s": None,
    "profil": "testprofil",
    "baand": {"domene_naer": 1, "arts_naer": 2},
    "ms": 18,
}

SITAT = {
    "id": 77,
    "paper_id": "pmid:1001",
    "paper_tittel": "Long-term patterns in the study system",
    "paper_forfattere": "A. Researcher et al.",
    "paper_aar": 2024,
    "tekst": "A quoted sentence from the source.",
    "kommentar": "",
}


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


@contextmanager
def frontend_server() -> Iterator[str]:
    handler = lambda *args, **kwargs: QuietHandler(  # noqa: E731
        *args, directory=str(FRONTEND), **kwargs
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def api_fixture(route: Route) -> None:
    request = route.request
    path = request.url.split("?", 1)[0]
    status = 200
    payload: object = {}
    headers = {"content-type": "application/json; charset=utf-8"}

    if path.endswith("/api/profil"):
        payload = {
            "navn": "Testprofil",
            "kort": "testfelt",
            "sok_eksempel": "et eksempel",
            "sok_standard": "testemne",
            "om_domeneprofil": "Testprofil for nettleserreisen.",
            "domenebanker": [],
            "domene_merke": "[FAG]",
            "domene_merke_betyr": "faglig nærhet",
            "art_merke": "[OBS]",
            "art_merke_betyr": "målobjekt-nærhet",
        }
    elif path.endswith("/api/status"):
        payload = {
            "kilder": {"europe_pmc": True, "core": False, "openalex": True},
            "papirer_cachet": 2,
        }
    elif path.endswith("/api/versjon"):
        payload = {"versjon": "test", "bygg": "fixture", "tagline": "Testreise"}
    elif path.endswith("/api/sok"):
        query = parse_qs(urlsplit(request.url).query).get("q", [""])[0]
        if query == "uten-treff":
            payload = {
                "papirer": [],
                "revisjon": {
                    **REVISION,
                    "treff_per_kilde": {"europe_pmc": 0, "core": 0, "openalex": 0},
                    "etter_dedup": 0,
                    "dubletter_fjernet": 0,
                    "baand": {"domene_naer": 0, "arts_naer": 0},
                },
                "eksakt_id": None,
            }
        elif query == "kilde-feil":
            status = 502
            payload = {"detail": "Europe PMC utilgjengelig: testfeil"}
        else:
            payload = {"papirer": PAPIRER, "revisjon": REVISION, "eksakt_id": None}
    elif path.endswith("/api/relevans"):
        payload = {"naboer": []}
    elif path.endswith("/api/dokumenter"):
        payload = {"dokumenter": []}
    elif path.endswith("/api/sitatbank"):
        payload = {
            "papirer": [{
                "paper_id": SITAT["paper_id"], "tittel": SITAT["paper_tittel"],
                "antall": 1, "aar": SITAT["paper_aar"], "tidsskrift": "Journal of Testable Findings",
            }],
            "totalt": 1,
        }
    elif path.endswith("/api/sitater"):
        payload = [SITAT]
    elif "/api/relaterte/" in path:
        payload = {"relaterte": []}
    elif path.endswith("/api/utkast") and request.method == "POST":
        data = request.post_data_json or {}
        payload = {"id": 91, "tittel": data.get("tittel", ""), "innhold": data.get("innhold", "")}
    elif path.endswith("/api/utkast/91"):
        payload = {"id": 91, "tittel": "", "innhold": ""}
    elif path.endswith("/api/utkast"):
        payload = []
    elif "/api/gap/" in path:
        payload = {
            "referanse_kilde": "testfixture",
            "referanse_dekning": None,
            "siterte_antall": 0,
            "gap": [],
            "naboer": [],
        }
    elif "/api/emner/" in path:
        payload = {"emner": []}
    elif path.endswith("/api/dossier/tilgjengelig"):
        payload = {"tilgjengelig": True}
    elif path.endswith("/api/syntese/tilgjengelig"):
        payload = {"tilgjengelig": False}
    elif path.endswith("/api/retningssamtale/tilgjengelig"):
        payload = {"tilgjengelig": False}
    elif path.endswith("/api/verifiser/tilgjengelig"):
        payload = {"tilgjengelig": False}
    elif path.endswith("/api/dossier/innsikt"):
        payload = {
            "antall_kandidater": 2,
            "tidslinje": {"2019": 1, "2024": 1},
            "akse_fordeling": {"Mekanisme": 2},
            "art_konfidens": {"bekreftet": 2, "usikker": 0},
        }
    elif path.endswith("/api/dossier") and request.method == "POST":
        status = 503
        payload = {"detail": "AI-proxy utilgjengelig (test)"}
    elif path.endswith("/api/rapport/kildesamling"):
        headers = {"content-type": "text/markdown; charset=utf-8"}
        return route.fulfill(
            status=200,
            headers=headers,
            body="# Testkildesamling\n\nTo fixture-kilder.\n",
        )

    route.fulfill(status=status, headers=headers, body=json.dumps(payload))


@pytest.mark.parametrize(
    ("viewport", "mobile"),
    [({"width": 1440, "height": 900}, False), ({"width": 390, "height": 844}, True)],
    ids=["desktop", "mobil"],
)
def test_ulven_hovedreise_i_nettleser(
    viewport: dict[str, int], mobile: bool
) -> None:
    with frontend_server() as base_url, sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch()
        page: Page = browser.new_page(viewport=viewport, accept_downloads=True)
        browser_errors: list[str] = []
        page.on("pageerror", lambda error: browser_errors.append(error.stack or str(error)))
        page.route("**/api/**", api_fixture)
        page.goto(base_url, wait_until="networkidle")

        assert page.locator("#search-input").input_value() == "testemne"
        page.locator("#result-list .result").first.wait_for()
        if mobile:
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

        page.locator("#om-knapp").click()
        assert page.locator("#om-overlay").is_visible()
        page.locator("#om-kilder").get_by_text("Europe PMC (søk)").wait_for()
        assert page.get_by_text("Europe PMC (søk) — nåbar nå").is_visible()
        assert page.get_by_text("CORE — utilgjengelig akkurat nå").is_visible()
        page.locator("#om-lukk").click()

        page.locator("#search-input").fill("testemne oppdatert")
        with page.expect_response(lambda response: "/api/sok?q=testemne%20oppdatert" in response.url):
            page.locator("#search-form button[type=submit]").click()
        page.locator("#result-list .result").first.wait_for()
        assert page.locator("#result-count").inner_text() == "2 kandidater"
        assert page.locator("#result-list .result").count() == 2
        assert page.locator("#reader-title").inner_text() == PAPIRER[0]["tittel"]
        assert "Europe PMC 2" in page.locator("#revisjon-sammendrag").inner_text()

        page.locator('#result-list .result[data-id="pmid:1002"]').click()
        assert page.locator("#reader-title").inner_text() == PAPIRER[1]["tittel"]
        page.locator('.shell .tab[data-tab="gap"]').click()
        assert page.locator("#tab-gap").is_visible()
        page.get_by_text("Papiret siterer 0 kilder selv").wait_for()
        with page.expect_download() as download_info:
            page.locator('#eksport-kildesamling [data-format="md"]').click()
        download = download_info.value
        assert download.suggested_filename.endswith(".md")
        assert Path(download.path()).read_text(encoding="utf-8").startswith("# Testkildesamling")

        page.locator("#btn-dossier").click()
        assert page.locator("#dossier-overlay").is_visible()
        page.get_by_text("Publikasjonstidslinje (2 kandidater)").wait_for()
        page.get_by_text("Kunne ikke lage dossier: AI-proxy utilgjengelig (test)").wait_for()
        page.locator("#dossier-lukk").click()

        if mobile:
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert browser_errors == []
        browser.close()


def test_ulven_viser_tomt_svar_og_kildefeil_forskjellig() -> None:
    with frontend_server() as base_url, sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch()
        page: Page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.route("**/api/**", api_fixture)
        page.goto(base_url, wait_until="networkidle")
        page.locator("#result-list .result").first.wait_for()
        page.locator("#eksport-dossier").wait_for(state="visible")

        page.locator("#search-input").fill("kilde-feil")
        with page.expect_response(lambda response: "/api/sok?q=kilde-feil" in response.url):
            page.locator("#search-form button[type=submit]").click()
        page.locator("#result-status").get_by_text("Feil: Europe PMC utilgjengelig: testfeil").wait_for()
        assert page.locator("#result-count").inner_text() == ""
        assert page.locator("#result-list .result").count() == 0
        assert page.locator("#empty-reader").is_visible()
        assert page.locator("#reader-head").is_hidden()
        assert page.locator("#reader-body").is_hidden()
        assert page.locator("#revisjon-sammendrag").is_hidden()
        assert page.locator("#eksport-dossier").is_hidden()

        page.locator("#search-input").fill("uten-treff")
        with page.expect_response(lambda response: "/api/sok?q=uten-treff" in response.url):
            page.locator("#search-form button[type=submit]").click()
        assert page.locator("#result-count").inner_text() == "0 kandidater"
        assert page.locator("#result-status").inner_text() == ""
        assert page.locator("#result-list .result").count() == 0
        assert page.locator("#empty-reader").is_visible()
        assert page.locator("#reader-head").is_hidden()
        assert page.locator("#reader-body").is_hidden()
        browser.close()


def test_ulven_forskningssporsmal_handoff_fyller_sokefeltet() -> None:
    with frontend_server() as base_url, sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch()
        page: Page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.route("**/api/**", api_fixture)
        with page.expect_response(
            lambda response: "/api/sok?q=salmonid%20welfare" in response.url
        ):
            page.goto(f"{base_url}/?q=salmonid%20welfare", wait_until="networkidle")
        assert page.locator("#search-input").input_value() == "salmonid welfare"
        assert page.locator("#result-list .result").count() == 2
        browser.close()


def test_ulven_kan_dra_sitat_fra_bank_til_dokument() -> None:
    with frontend_server() as base_url, sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch()
        page: Page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.route("**/api/**", api_fixture)
        page.goto(base_url, wait_until="networkidle")
        quote = page.locator('#bank-sitater .sitatkort[data-id="77"]')
        quote.wait_for(state="visible")

        page.locator("#skuff-toggle").click()
        with page.expect_request(
            lambda request: request.url.endswith("/api/utkast")
            and request.method == "POST"
            and "[@sitat:77]" in (request.post_data or "")
        ):
            quote.drag_to(page.locator('.skuff-linse[data-linse="dok"]'))

        inserted = page.locator('#dok-editor sitat-ref[data-id="77"]')
        inserted.wait_for(state="visible")
        assert "A quoted sentence from the source." in inserted.inner_text()
        browser.close()
