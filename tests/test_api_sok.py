"""Verifiserer /api/sok: caching/embedding (bank.lagre) kjører som en BackgroundTask
ETTER responsen, ikke før — reell fiks 2026-09-04 for at ferske søk (embed_fn opptil
120s, ekte AI-proxy-kall) så ut som de hang. En treg eller feilende lagre() skal ALDRI
forsinke eller velte selve søkeresponsen — den bivirkningen er kallerens (--lignende)
problem, ikke denne brukerens."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schemas import PaperDossier  # noqa: E402


def _p(pid, tittel):
    return PaperDossier(pmid=pid, doi=None, tittel=tittel, forfattere="", tidsskrift="",
                        aar=2026, abstract="noe abstract", siteringstall=0, open_access=False,
                        kilde_url=f"https://example.org/{pid}")


def test_sok_svarer_selv_om_lagre_feiler():
    """Response-en må ALDRI vente på eller velte pga. bank.lagre — det er nettopp
    denne kappløps-/hang-klassen 2026-09-04-fiksen fjerner fra den synkrone stien.
    _lagre_bakgrunn fanger exceptionen (se dens egen docstring for hvorfor det ikke
    holder å bare stole på at BackgroundTasks svelger den)."""
    treff = [_p("1", "Nephrocalcinosis i laks")]
    import api
    from fastapi.testclient import TestClient

    def lagre_som_krasjer(papirer, **kw):
        raise RuntimeError("simulert treg/feilende cache-skriving")

    with patch("api.sok_og_ranger", return_value=(treff, None, {"europe_pmc": True, "core": True})), \
         patch("bank.lagre", side_effect=lagre_som_krasjer):
        client = TestClient(api.app)
        r = client.get("/api/sok?q=nephrocalcinosis+salmon&n=20")
    assert r.status_code == 200
    data = r.json()
    assert len(data["papirer"]) == 1
    assert data["papirer"][0]["tittel"] == "Nephrocalcinosis i laks"


def test_sok_planlegger_lagre_som_backgroundtask():
    """Selve søket skal likevel faktisk bli cachet — bare ikke synkront."""
    treff = [_p("1", "Nephrocalcinosis i laks")]
    import api
    from fastapi.testclient import TestClient

    kalt_med = []
    with patch("api.sok_og_ranger", return_value=(treff, None, {"europe_pmc": True, "core": True})), \
         patch("bank.lagre", side_effect=lambda papirer, **kw: kalt_med.append(papirer)):
        client = TestClient(api.app)
        r = client.get("/api/sok?q=nephrocalcinosis+salmon&n=20")
    assert r.status_code == 200
    assert kalt_med and kalt_med[0] == treff
