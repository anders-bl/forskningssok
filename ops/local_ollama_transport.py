"""Keep local Ollama requests on loopback and out of configured proxies."""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit

LOCAL_API_PATHS = {"/api/version", "/api/tags", "/api/embed", "/api/chat"}


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Do not let a loopback response redirect prompts or corpus text elsewhere."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        return None


_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    _NoRedirectHandler(),
)


def assert_loopback_url(url: str) -> None:
    parsed = urlsplit(url)
    try:
        port = parsed.port
    except ValueError as error:
        raise RuntimeError("refusing malformed Ollama endpoint") from error
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or port != 11434
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in LOCAL_API_PATHS or parsed.query or parsed.fragment):
        raise RuntimeError("refusing Ollama endpoint outside the registered loopback API")


def install() -> None:
    """Route legacy urllib callers in the embedding helper through the no-proxy opener."""
    urllib.request.install_opener(_OPENER)


def request_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    assert_loopback_url(url)
    data = None if payload is None else json.dumps(payload, ensure_ascii=True).encode("utf-8")
    request = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="POST" if data is not None else "GET",
    )
    try:
        with _OPENER.open(request, timeout=300) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail_hash = hashlib.sha256(error.read(4096)).hexdigest()
        raise RuntimeError(f"local Ollama HTTP {error.code}; body_sha256={detail_hash}") from error
