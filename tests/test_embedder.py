"""bank.py:_hus_embed()/_ai_proxy_embed() — Dokploy-deploy-forberedelse 2026-09-04.
Se bank.py sin moduldocstring for HVORFOR: lokal Ollama er ikke nåbar fra en
Dokploy-container, AI_PROXY_URL bytter til ai-proxy /embed (mistral-embed) der.
Alt offline/mocket her, samme disiplin som resten av forskningssok.
"""
import sys
from pathlib import Path
from types import ModuleType

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bank  # noqa: E402


def test_hus_embed_bruker_ai_proxy_naar_env_satt(monkeypatch):
    monkeypatch.setenv("AI_PROXY_URL", "http://ai-proxy:8000")
    assert bank._hus_embed() is bank._ai_proxy_embed


def test_hus_embed_faller_tilbake_lokalt_uten_ai_proxy_url(monkeypatch):
    """Uten AI_PROXY_URL: uendret lokal oppførsel (Anders' Mac) — semantisk_sok
    mockes inn i sys.modules så testen ikke krever en ekte husinstallasjon."""
    monkeypatch.delenv("AI_PROXY_URL", raising=False)
    fake = ModuleType("semantisk_sok")
    fake.embed = lambda texts: [[0.0]]
    monkeypatch.setitem(sys.modules, "semantisk_sok", fake)
    valgt = bank._hus_embed()
    assert valgt is fake.embed
    assert valgt is not bank._ai_proxy_embed


def test_ai_proxy_embed_poster_riktig_body_til_riktig_url(monkeypatch):
    kalt = {}

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"embeddings": [[0.1, 0.2]], "model": "mistral-embed", "dim": 2}

    def _fake_post(url, json, timeout):
        kalt["url"] = url
        kalt["json"] = json
        kalt["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setenv("AI_PROXY_URL", "http://ai-proxy:8000/")  # med trailing slash
    monkeypatch.setenv("AI_PROXY_WIKI_ID", "forskningssok-test")
    monkeypatch.setattr(bank.httpx, "post", _fake_post)

    ut = bank._ai_proxy_embed(["en tekst om nefrokalsinose"])

    assert kalt["url"] == "http://ai-proxy:8000/embed"  # trailing slash strippet riktig
    assert kalt["json"] == {"wiki_id": "forskningssok-test", "input": ["en tekst om nefrokalsinose"]}
    assert ut == [[0.1, 0.2]]


def test_ai_proxy_embed_default_wiki_id_uten_override(monkeypatch):
    kalt = {}

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"embeddings": [[0.0]]}

    def _fake_post(url, json, timeout):
        kalt["json"] = json
        return _FakeResponse()

    monkeypatch.setenv("AI_PROXY_URL", "http://ai-proxy:8000")
    monkeypatch.delenv("AI_PROXY_WIKI_ID", raising=False)
    monkeypatch.setattr(bank.httpx, "post", _fake_post)

    bank._ai_proxy_embed(["x"])
    assert kalt["json"]["wiki_id"] == "forskningssok"
