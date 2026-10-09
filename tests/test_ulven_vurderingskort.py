"""Fase A av docs/ulven-menneskevurdering-scope.md: vurderingskortet under syntesen er en prototype UTEN lagring.

Kontrakten som testes: kortet vises bare etter et ferdig svar med kilder, ett trykk er nok, valg kan endres uten å dobbeltregistreres,
og ingenting forlater siden (ingen nettverkskall, ingen nettleserlagring). Det siste er hele poenget med fase A.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, Route, sync_playwright

from tests.test_ulven_browser import api_fixture, frontend_server

FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "index.html"

SYNTESE_MED_KILDER = (
    "Funnene henger sammen slik: [1] viser en sammenheng, [2] nyanserer den.\n"
    "---\n## Kildeliste (2 kilder)\n"
    "A. Researcher et al. (2024). Long-term patterns in the study system. DOI: 10.1/x URL: https://example.org/paper/1001\n"
    "B. Scientist (2019). A second source for comparison. (ingen ekstern lenke)"
)
SYNTESE_UTEN_KILDER = "Ingen kilder i cachen for «tomt».\nKjør først: python3 cli.py \"tomt\" --oppdater"


def _rute(syntese_tekst: dict[str, object], forespurt: list[str]):
    def handler(route: Route) -> None:
        req = route.request
        sti = req.url.split("?", 1)[0]
        forespurt.append(f"{req.method} {sti}")
        if sti.endswith("/api/syntese/tilgjengelig"):
            return route.fulfill(status=200, headers={"content-type": "application/json"}, body='{"tilgjengelig": true}')
        if sti.endswith("/api/syntese") and req.method == "POST":
            svar = syntese_tekst["svar"]
            if isinstance(svar, int):
                return route.fulfill(status=svar, headers={"content-type": "application/json"}, body='{"detail": "testfeil"}')
            return route.fulfill(status=200, headers={"content-type": "application/json"}, body=json.dumps({"syntese": svar}))
        return api_fixture(route)
    return handler


def _apne(page: Page, base: str) -> None:
    page.goto(base, wait_until="networkidle")
    page.locator("#result-list .result").first.wait_for()
    page.locator("#btn-syntese").wait_for(state="visible")


def _kjor_syntese(page: Page) -> None:
    with page.expect_response(lambda r: r.url.endswith("/api/syntese") and r.request.method == "POST"):
        page.locator("#btn-syntese").click()


@pytest.mark.parametrize(
    ("viewport", "mobil"),
    [({"width": 1440, "height": 900}, False), ({"width": 390, "height": 844}, True)],
    ids=["desktop", "mobil"],
)
def test_vurderingskort_ett_trykk_endring_og_ingenting_forlater_siden(viewport: dict[str, int], mobil: bool) -> None:
    forespurt: list[str] = []
    with frontend_server() as base, sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport=viewport)
        feil: list[str] = []
        page.on("pageerror", lambda e: feil.append(e.stack or str(e)))
        page.route("**/api/**", _rute({"svar": SYNTESE_MED_KILDER}, forespurt))
        _apne(page, base)
        assert page.locator("#vurderingskort").is_hidden()
        _kjor_syntese(page)
        page.locator("#vurderingskort").wait_for(state="visible")

        # Etter at svaret er ferdig skal ingenting mer forlate siden, uansett hva som trykkes.
        antall_foer = len(forespurt)
        lager_foer = page.evaluate("[localStorage.length, sessionStorage.length]")
        assert page.locator("#vk-grunner").is_hidden()
        assert page.locator("#vk-status").inner_text() == ""

        page.locator('[data-vk-verdi="delvis"]').click()
        page.locator('[data-vk-verdi="delvis"]').click()  # dobbeltklikk er idempotent
        assert page.locator('[data-vk-verdi="delvis"]').get_attribute("aria-pressed") == "true"
        assert page.locator('[data-vk-verdi="ja"]').get_attribute("aria-pressed") == "false"
        assert page.locator("#vk-grunner").is_visible()
        assert "Notert: Delvis" in page.locator("#vk-status").inner_text()
        assert "ingenting er lagret eller sendt" in page.locator("#vk-status").inner_text()
        page.get_by_label("Mangler direkte kilde").check()

        page.locator('[data-vk-verdi="nei"]').click()  # nytt valg erstatter det forrige
        assert page.locator('[data-vk-verdi="delvis"]').get_attribute("aria-pressed") == "false"
        assert page.locator('[data-vk-verdi="nei"]').get_attribute("aria-pressed") == "true"
        assert page.locator("#vk-grunner").is_visible()

        page.locator('[data-vk-verdi="ja"]').click()  # Ja trenger ingen grunn og tømmer en gammel
        assert page.locator("#vk-grunner").is_hidden()
        assert page.locator('input[name="vk-grunn"]:checked').count() == 0

        page.locator("#vk-kilder summary").click()
        assert page.locator("#vk-kilderader .vk-kilde").count() == 2
        page.locator("#vk-kilderader select").first.select_option("direkte_stotte")
        page.locator("#vk-kommentar").fill("x" * 400)
        assert len(page.locator("#vk-kommentar").input_value()) == 300  # tak på kommentaren

        page.locator("#vk-endre").click()
        assert page.locator('[data-vk-verdi="ja"]').get_attribute("aria-pressed") == "false"
        assert page.locator("#vk-status").inner_text() == ""
        assert page.evaluate("document.activeElement.dataset.vkVerdi") == "ja"  # fokus tilbake til første valg

        # Tastatur: Enter på en fokusert knapp velger.
        page.locator('[data-vk-verdi="nei"]').focus()
        page.keyboard.press("Enter")
        assert page.locator('[data-vk-verdi="nei"]').get_attribute("aria-pressed") == "true"

        assert forespurt[antall_foer:] == [], "vurderingskortet gjorde nettverkskall"
        assert page.evaluate("[localStorage.length, sessionStorage.length]") == lager_foer
        assert "lagres ikke" in page.locator(".vk-prove").inner_text()
        if mobil:
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            for knapp in page.locator(".vk-knapp").all():
                assert knapp.bounding_box()["height"] >= 40  # trykkflate
        assert feil == []
        browser.close()


def test_vurderingskort_vises_ikke_uten_kilder_eller_ved_feil_og_nullstilles_ved_ny_syntese() -> None:
    forespurt: list[str] = []
    svar: dict[str, object] = {"svar": SYNTESE_UTEN_KILDER}
    with frontend_server() as base, sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.route("**/api/**", _rute(svar, forespurt))
        _apne(page, base)

        _kjor_syntese(page)
        page.get_by_text("Ingen kilder i cachen").wait_for()
        assert page.locator("#vurderingskort").is_hidden()  # vellykket kall uten kilder er ikke noe å vurdere
        page.locator("#syntese-lukk").click()

        svar["svar"] = 502
        _kjor_syntese(page)
        page.get_by_text("Kunne ikke lage syntese-fortelling").wait_for()
        assert page.locator("#vurderingskort").is_hidden()
        page.locator("#syntese-lukk").click()

        svar["svar"] = SYNTESE_MED_KILDER
        _kjor_syntese(page)
        page.locator("#vurderingskort").wait_for(state="visible")
        page.locator('[data-vk-verdi="nei"]').click()
        page.get_by_label("For generelt").check()
        page.locator("#syntese-lukk").click()
        assert page.locator("#vurderingskort").is_hidden()  # lukking skjuler kortet

        _kjor_syntese(page)  # ny syntese gir et nytt, tomt kort
        page.locator("#vurderingskort").wait_for(state="visible")
        assert page.locator('[data-vk-verdi="nei"]').get_attribute("aria-pressed") == "false"
        assert page.locator('input[name="vk-grunn"]:checked').count() == 0
        assert page.locator("#vk-status").inner_text() == ""
        browser.close()


def _vk_blokk() -> str:
    html = FRONTEND.read_text(encoding="utf-8")
    start = html.index("// Vurderingskort for syntese-fortellingen")
    slutt = html.index("$('#btn-syntese').addEventListener", start)
    return html[start:slutt]


def test_vurderingskort_koden_har_ingen_vei_ut_av_siden() -> None:
    """Vakt: fase A skal ikke kunne få persistens ved et uhell. Persistens er en egen beslutning (scope §Avhengigheter)."""
    blokk = _vk_blokk()
    # Kommentarlinjene forklarer hvorfor; bare kjørbar kode skal sjekkes.
    kode = "\n".join(l for l in blokk.splitlines() if not l.strip().startswith("//"))
    forbudt = ("fetch(", "api(", "XMLHttpRequest", "sendBeacon", "localStorage", "sessionStorage", "indexedDB", "document.cookie", "/api/")
    treff = [f for f in forbudt if f in kode]
    assert treff == [], f"vurderingskortet bruker {treff}"


def test_vurderingskort_koden_er_i_syntese_overlayet_og_uten_emoji() -> None:
    html = FRONTEND.read_text(encoding="utf-8")
    overlay = html[html.index('id="syntese-overlay"'):html.index('id="syntese-overlay"') + 4000]
    assert 'id="vurderingskort"' in overlay.split("<!-- Fase 2b")[0]
    assert re.search(r'aria-pressed="false"', overlay)
