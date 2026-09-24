"""Browser checks for the portal thread reference carried into Forskningssok."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

from playwright.sync_api import Route, sync_playwright


FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


@contextmanager
def frontend_server() -> Iterator[str]:
    handler = lambda *args, **kwargs: SimpleHTTPRequestHandler(  # noqa: E731
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
    path = route.request.url.split("?", 1)[0]
    payload: object = {}
    if path.endswith("/api/profil"):
        payload = {
            "navn": "Testprofil", "kort": "testfelt", "sok_eksempel": "et eksempel",
            "sok_standard": "", "om_domeneprofil": "Testprofil.", "domenebanker": [],
            "domene_merke": "[FAG]", "domene_merke_betyr": "faglig nærhet",
            "art_merke": "[OBS]", "art_merke_betyr": "målobjekt-nærhet",
        }
    elif path.endswith("/api/sitatbank"):
        payload = {"papirer": [], "totalt": 0}
    elif path.endswith("/api/sitater"):
        payload = []
    elif path.endswith("/api/varme"):
        payload = {"papirer": []}
    elif path.endswith("/api/context/luna/517"):
        payload = {
            "kontrakt": "luna-context.v1",
            "samtale": {"title": "Ulven: videre lesning", "antall_meldinger": 2},
            "meldinger": [
                {"role": "user", "content": "Finn historiske kilder om temaet"},
                {"role": "assistant", "content": "Her er noen mulige spor."},
            ],
        }
    route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))


def test_luna_thread_reference_returns_to_the_same_portal_thread() -> None:
    with frontend_server() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.route("**/api/**", api_fixture)
        page.goto(f"{base_url}/?luna_samtale=517", wait_until="networkidle")

        link = page.locator("#luna-thread-return")
        link.wait_for(state="visible")
        assert link.get_attribute("href") == "https://portal.lauvasdata.no/luna?samtale=517"
        assert page.locator("#luna-context-title").inner_text() == "Ulven: videre lesning"
        page.get_by_role("button", name="Bruk i søkefeltet").click()
        assert page.locator("#search-input").input_value() == "Finn historiske kilder om temaet"
        browser.close()


def test_invalid_luna_thread_reference_does_not_create_a_return_link() -> None:
    with frontend_server() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.route("**/api/**", api_fixture)
        page.goto(f"{base_url}/?luna_samtale=../../517", wait_until="networkidle")

        assert page.locator("#luna-thread-return").is_hidden()
        browser.close()
