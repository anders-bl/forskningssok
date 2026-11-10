"""Network-free tests for the loopback-only Ollama transport contract."""
from __future__ import annotations

import hashlib
import io
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops"))

import local_ollama_transport as transport


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
def test_non_registered_endpoints_are_rejected(url: str) -> None:
    with pytest.raises(RuntimeError, match="outside the registered loopback API"):
        transport.assert_loopback_url(url)


def test_opener_bypasses_proxies_and_installs_redirect_blocker() -> None:
    proxy_handlers = [
        handler for handler in transport._OPENER.handlers
        if isinstance(handler, urllib.request.ProxyHandler)
    ]
    # An empty ProxyHandler has no dispatch methods, so urllib omits it from
    # the opener after it suppresses the environment-backed default handler.
    assert proxy_handlers == []
    assert any(
        isinstance(handler, transport._NoRedirectHandler)
        for handler in transport._OPENER.handlers
    )


def test_redirect_handler_refuses_redirect_target() -> None:
    request = urllib.request.Request("http://127.0.0.1:11434/api/chat")
    handler = transport._NoRedirectHandler()
    assert handler.redirect_request(
        request, io.BytesIO(), 302, "Found", {}, "https://example.invalid/collect"
    ) is None


def test_http_error_reports_hash_without_response_body(monkeypatch: pytest.MonkeyPatch) -> None:
    private_body = b"private prompt and corpus excerpt"

    class FailingOpener:
        def open(self, request: urllib.request.Request, timeout: int) -> object:
            raise urllib.error.HTTPError(
                request.full_url, 500, "Internal Server Error", {}, io.BytesIO(private_body)
            )

    monkeypatch.setattr(transport, "_OPENER", FailingOpener())
    with pytest.raises(RuntimeError) as error:
        transport.request_json("http://127.0.0.1:11434/api/chat", {"prompt": "test"})

    message = str(error.value)
    assert "HTTP 500" in message
    assert hashlib.sha256(private_body).hexdigest() in message
    assert private_body.decode() not in message
