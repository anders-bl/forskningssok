"""Network-free tests for the loopback-only Ollama transport contract."""

from __future__ import annotations

import hashlib
import io
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops"))

import local_ollama_transport as transport


@pytest.fixture
def local_http_server() -> tuple[str, dict[str, int]]:
    state = {"redirect_target_hits": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/redirect":
                body = b"redirect response body"
                self.send_response(302)
                self.send_header(
                    "Location", f"http://127.0.0.1:{self.server.server_port}/collect"
                )
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/collect":
                state["redirect_target_hits"] += 1
            body = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11434/api/version",
        "http://127.0.0.1:11434/api/tags",
        "http://127.0.0.1:11434/api/embed",
        "http://127.0.0.1:11434/api/chat",
    ],
)
def test_registered_loopback_endpoints_are_accepted(url: str) -> None:
    transport.assert_loopback_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:11434/api/embed",
        "http://localhost:11434/api/embed",
        "http://127.0.0.2:11434/api/embed",
        "http://127.0.0.1:11435/api/embed",
        "http://user@127.0.0.1:11434/api/embed",
        "http://127.0.0.1:11434/api/embed?debug=1",
        "http://127.0.0.1:11434/api/delete",
    ],
)
def test_request_json_rejects_invalid_endpoint_before_open(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    class MustNotOpen:
        def open(self, request: urllib.request.Request, timeout: int) -> object:
            raise AssertionError("invalid endpoint reached the request opener")

    monkeypatch.setattr(transport, "_OPENER", MustNotOpen())
    with pytest.raises(RuntimeError, match="outside the registered loopback API"):
        transport.request_json(url)


def test_request_json_uses_the_guarded_opener(
    local_http_server: tuple[str, dict[str, int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = local_http_server
    monkeypatch.setattr(transport, "assert_loopback_url", lambda url: None)
    result = transport.request_json(f"{root}/api/version")
    assert result == {"ok": True}


def test_install_routes_urllib_through_proxy_free_opener(
    local_http_server: tuple[str, dict[str, int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = local_http_server
    proxy = "http://127.0.0.1:9"
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(name, proxy)
    for name in ("http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.setenv(name, proxy)
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")
    monkeypatch.setattr(transport, "assert_loopback_url", lambda url: None)
    monkeypatch.setattr(urllib.request, "_opener", None, raising=False)

    transport.install()
    with urllib.request.urlopen(f"{root}/api/version", timeout=2) as response:
        assert json.load(response) == {"ok": True}


def test_configured_opener_rejects_redirect_without_contacting_target(
    local_http_server: tuple[str, dict[str, int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, state = local_http_server
    monkeypatch.setattr(transport, "assert_loopback_url", lambda url: None)

    with pytest.raises(RuntimeError, match="local Ollama HTTP 302"):
        transport.request_json(f"{root}/redirect")

    assert state["redirect_target_hits"] == 0


def test_http_error_reports_hash_without_response_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_body = b"private prompt and corpus excerpt"

    class FailingOpener:
        def open(self, request: urllib.request.Request, timeout: int) -> object:
            raise urllib.error.HTTPError(
                request.full_url,
                500,
                "Internal Server Error",
                {},
                io.BytesIO(private_body),
            )

    monkeypatch.setattr(transport, "_OPENER", FailingOpener())
    with pytest.raises(RuntimeError) as error:
        transport.request_json("http://127.0.0.1:11434/api/chat", {"prompt": "test"})

    message = str(error.value)
    assert "HTTP 500" in message
    assert hashlib.sha256(private_body).hexdigest() in message
    assert private_body.decode() not in message
