"""FDR-107 M4 fase 2b (2026-09-29): legg konsumentnøkkelen på alle kall fra denne appen til ai-proxy.

ai-proxy kjenner hver fast konsument på X-AI-Konsument (sha256 i AI_KONSUMENT_NOKLER, fra SOPS).
Kallene til ai-proxy står mange steder, skrevet på ulike måter (portalen: 58 i 15 filer; flowplan
hadde adressen hardkodet), så en header per kall ville blitt glemt ved neste nye kall. I stedet
hektes en request-krok på alle httpx-klienter i prosessen (også httpx.post/get, som lager en
Client under panseret). Kroken setter headeren bare når vert og port er ai-proxys (AI_PROXY_URL,
standard http://ai-proxy:8000), og bare når AI_KONSUMENT_NOKKEL er satt. Ingen andre verter får
nøkkelen. Tom nøkkel = ingen endring.

Felles modul i portal, forskningssok, stromkontrol, bruktmarked og flowplan; samme test i hver.
"""
import os
from urllib.parse import urlsplit

import httpx

HEADER = "X-AI-Konsument"
_INSTALLERT = False


def _standardport(scheme: str) -> int:
    return 443 if scheme == "https" else 80


def _ai_proxy_adresse() -> tuple[str, int]:
    u = urlsplit(os.environ.get("AI_PROXY_URL") or "http://ai-proxy:8000")
    return (u.hostname or "ai-proxy", u.port or _standardport(u.scheme))


def gjelder_ai_proxy(url: httpx.URL) -> bool:
    return (url.host, url.port or _standardport(url.scheme)) == _ai_proxy_adresse()


def _sett_nokkel(request: httpx.Request) -> None:
    nokkel = os.environ.get("AI_KONSUMENT_NOKKEL", "")
    if nokkel and gjelder_ai_proxy(request.url):
        request.headers[HEADER] = nokkel


async def _sett_nokkel_async(request: httpx.Request) -> None:
    _sett_nokkel(request)


def installer() -> None:
    """Hekt kroken på httpx.Client og httpx.AsyncClient. Idempotent; kalles ved oppstart."""
    global _INSTALLERT
    if _INSTALLERT:
        return
    for klasse, krok in ((httpx.Client, _sett_nokkel), (httpx.AsyncClient, _sett_nokkel_async)):
        opprinnelig = klasse.__init__

        def ny_init(self, *args, _opprinnelig=opprinnelig, _krok=krok, **kwargs):
            _opprinnelig(self, *args, **kwargs)
            kroker = dict(self.event_hooks)
            kroker["request"] = [*kroker.get("request", []), _krok]
            self.event_hooks = kroker

        klasse.__init__ = ny_init
    _INSTALLERT = True
