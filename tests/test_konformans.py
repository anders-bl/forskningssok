"""Verifiserer konformans.py to-armet: en konform payload gir INGEN avvik (positiv
kontroll), og hver ekte overtredelse fanges (negativ kontroll). En validator som bare kan
si «ok» er en no-op-vakt.

Kjører også forskningssøks EGEN /health gjennom validatoren — regresjonsvakt på at vi
faktisk følger standarden vi målte at ingen andre gjør.
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import konformans as k  # noqa: E402


# ── Positiv kontroll ──────────────────────────────────────────────────────────────────

def test_konform_detalj_gir_ingen_avvik():
    ok = {"status": "pass", "version": "1", "releaseId": "1.0.0+abc123",
          "checks": {"cache:innhold": [{"status": "pass"}]}}
    assert k.sjekk_detalj(ok) == []


def test_konform_offentlig_gir_ingen_avvik():
    assert k.sjekk_offentlig({"status": "pass"}) == []


# ── Negativ kontroll: hver overtredelse MÅ fanges ──────────────────────────────────────

def test_full_semver_version_er_avvik():
    """Dagens funn: version=«1.0.0» gjør en patch til en synlig kontraktendring."""
    avvik = k.sjekk_detalj({"status": "pass", "version": "1.0.0",
                            "releaseId": "1.0.0+x", "checks": {}})
    assert any("semver" in a for a in avvik)


def test_manglende_releaseId_er_avvik():
    avvik = k.sjekk_detalj({"status": "pass", "version": "1", "checks": {}})
    assert any("releaseId" in a for a in avvik)


def test_releaseId_lik_version_er_avvik():
    avvik = k.sjekk_detalj({"status": "pass", "version": "1", "releaseId": "1", "checks": {}})
    assert any("EKSAKTE" in a for a in avvik)


def test_ugyldig_status_er_avvik():
    assert any("status" in a for a in k.sjekk_detalj(
        {"status": "grønn", "version": "1", "releaseId": "1.0.0+x", "checks": {}}))


def test_manglende_checks_er_avvik():
    avvik = k.sjekk_detalj({"status": "pass", "version": "1", "releaseId": "1.0.0+x"})
    assert any("checks" in a for a in avvik)


def test_offentlig_som_lekker_version_er_avvik():
    """Den bærende regelen for det offentlige svaret: status og ingenting mer."""
    avvik = k.sjekk_offentlig({"status": "pass", "version": "1", "releaseId": "1.0.0+x"})
    assert any("lekker" in a for a in avvik)


# ── Regresjonsvakt: forskningssøks EGEN /health følger standarden ─────────────────────

def test_forskningssoks_eget_health_er_konformt(tmp_path, monkeypatch):
    import api
    import bank
    from fastapi.testclient import TestClient
    from schemas import PaperDossier

    db = tmp_path / "cache.db"
    bank.lagre([PaperDossier(pmid="1", doi="10.1/x", tittel="t", forfattere="", tidsskrift="",
                             aar=2024, abstract="a", siteringstall=0, open_access=False,
                             kilde_url="u")],
               embed_fn=lambda t: [[0.0] * 1024 for _ in t], db_path=db)
    monkeypatch.setattr(api, "CACHE_DB", db)
    c = TestClient(api.app)

    # offentlig: kun status
    assert k.sjekk_offentlig(c.get("/health").json()) == []
    # detalj bak nøkkel: full konformans
    with patch.dict(os.environ, {"INTERNAL_API_KEY": "hemmelig"}, clear=False), \
            patch("api.bank.kilde_status", return_value=[]):
        detalj = c.get("/health", headers={"X-Internal-Key": "hemmelig"}).json()
    assert k.sjekk_detalj(detalj) == [], f"eget /health bryter standarden: {k.sjekk_detalj(detalj)}"
