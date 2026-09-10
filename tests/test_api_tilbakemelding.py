"""/api/tilbakemelding — videresender til lauvasdata sin ALLEREDE eksisterende
DemoFeedback-mekanikk (se lauvasdata/backend/app/routers/demo.py:submit_feedback)
i stedet for en egen lagringstabell forskningssok verken har eller trenger. Mocket
her, samme disiplin som resten av forskningssok (se tests/test_embedder.py for
samme monkeypatch.setattr(<modul>.httpx, "post", ...)-mønster)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402


class _FakeResponse:
    def __init__(self, status_code=201):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("feil", request=None, response=self)


def _client():
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def test_sender_melding_med_riktig_demo_slug_og_url(monkeypatch):
    kalt = {}

    def _fake_post(url, json, timeout):
        kalt["url"] = url
        kalt["json"] = json
        kalt["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(api.httpx, "post", _fake_post)
    r = _client().post("/api/tilbakemelding", json={"melding": "Dette var nyttig!"})

    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert kalt["url"] == f"{api._PORTAL_API_URL}/api/demo/feedback"
    assert kalt["json"]["demo_slug"] == "forskningssok"
    assert kalt["json"]["message"] == "Dette var nyttig!"
    assert kalt["json"]["kategori"] == "annet"  # default uten oppgitt kategori


def test_kjent_kategori_sendes_videre(monkeypatch):
    kalt = {}
    monkeypatch.setattr(api.httpx, "post", lambda url, json, timeout: (kalt.update(json=json), _FakeResponse())[1])
    _client().post("/api/tilbakemelding", json={"melding": "Fant en feil", "kategori": "bug"})
    assert kalt["json"]["kategori"] == "bug"


def test_ukjent_kategori_faller_tilbake_til_annet(monkeypatch):
    kalt = {}
    monkeypatch.setattr(api.httpx, "post", lambda url, json, timeout: (kalt.update(json=json), _FakeResponse())[1])
    _client().post("/api/tilbakemelding", json={"melding": "x", "kategori": "noe-oppdiktet"})
    assert kalt["json"]["kategori"] == "annet"


def test_kontekst_er_valgfri_og_utelates_naar_tom(monkeypatch):
    kalt = {}
    monkeypatch.setattr(api.httpx, "post", lambda url, json, timeout: (kalt.update(json=json), _FakeResponse())[1])
    _client().post("/api/tilbakemelding", json={"melding": "x"})
    assert "context" not in kalt["json"]


def test_kontekst_sendes_med_naar_oppgitt(monkeypatch):
    kalt = {}
    monkeypatch.setattr(api.httpx, "post", lambda url, json, timeout: (kalt.update(json=json), _FakeResponse())[1])
    _client().post("/api/tilbakemelding", json={"melding": "x", "kontekst": "søk: laks lever"})
    assert kalt["json"]["context"] == "søk: laks lever"


def test_tom_melding_gir_400_uten_aa_ringe_lauvasdata(monkeypatch):
    kalt_noen_gang = []
    monkeypatch.setattr(api.httpx, "post", lambda *a, **kw: kalt_noen_gang.append(1))
    r = _client().post("/api/tilbakemelding", json={"melding": "   "})
    assert r.status_code == 400
    assert kalt_noen_gang == []


def test_lauvasdata_nede_gir_aerlig_502_ikke_en_stille_ok(monkeypatch):
    """Samme disiplin som identify_text() sin 503-håndtering ellers i huset: Ulven
    skal ALDRI tro noe ble sendt når det ikke ble det."""
    import httpx as httpx_modul

    def _fake_post(url, json, timeout):
        raise httpx_modul.ConnectTimeout("tidsavbrudd")

    monkeypatch.setattr(api.httpx, "post", _fake_post)
    r = _client().post("/api/tilbakemelding", json={"melding": "x"})
    assert r.status_code == 502
    assert "ok" not in r.json()
