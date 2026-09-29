"""FDR-107 M4 fase 2b: X-AI-Konsument legges på kall til ai-proxy, og bare dit.

Ekte httpx-klienter med MockTransport (ingen nett): Client, AsyncClient og httpx.post/get-veien.
"""
import asyncio

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ai_proxy_nokkel as apn  # noqa: E402

apn.installer()


def _fanget():
    sett = []

    def svar(request):
        sett.append((str(request.url), request.headers.get(apn.HEADER)))
        return httpx.Response(200, json={})
    return sett, httpx.MockTransport(svar)


@pytest.fixture
def miljo(monkeypatch):
    monkeypatch.setenv("AI_PROXY_URL", "http://ai-proxy:8000")
    monkeypatch.setenv("AI_KONSUMENT_NOKKEL", "fast-nokkel-9f2c")


def test_bare_ai_proxy_faar_nokkelen(miljo):
    sett, transport = _fanget()
    with httpx.Client(transport=transport) as c:
        c.post("http://ai-proxy:8000/complete", json={})
        c.get("https://api.mistral.ai/v1/models")
        c.get("http://ai-proxy:9999/annen-port")
        c.get("http://ai-proxy-lure:8000/complete")
    assert sett == [("http://ai-proxy:8000/complete", "fast-nokkel-9f2c"),
                    ("https://api.mistral.ai/v1/models", None),
                    ("http://ai-proxy:9999/annen-port", None),
                    ("http://ai-proxy-lure:8000/complete", None)]


def test_asynkron_klient(miljo):
    sett, transport = _fanget()

    async def kjor():
        async with httpx.AsyncClient(transport=transport) as c:
            await c.post("http://ai-proxy:8000/embed", json={})
    asyncio.run(kjor())
    assert sett == [("http://ai-proxy:8000/embed", "fast-nokkel-9f2c")]


def test_uten_nokkel_ingen_header(monkeypatch):
    monkeypatch.setenv("AI_PROXY_URL", "http://ai-proxy:8000")
    monkeypatch.delenv("AI_KONSUMENT_NOKKEL", raising=False)
    sett, transport = _fanget()
    with httpx.Client(transport=transport) as c:
        c.post("http://ai-proxy:8000/complete", json={})
    assert sett == [("http://ai-proxy:8000/complete", None)]


def test_egne_kroker_beholdes(miljo):
    sett, transport = _fanget()
    kalt = []
    with httpx.Client(transport=transport, event_hooks={"request": [lambda r: kalt.append(1)]}) as c:
        c.get("http://ai-proxy:8000/health")
    assert kalt == [1] and sett[0][1] == "fast-nokkel-9f2c"
