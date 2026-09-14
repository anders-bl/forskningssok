"""Verifiserer /api/rapport/omfang — spesifikt at synonym-teksten bank.lignende_tekst()
mates med bærer domeneprofil.ARTSTERMER, ikke bare aksens eget nøkkelordsett.

Regresjon for et ekte funn 2026-09-14 (fase 2b-scoping, forskningssok-smartsyntese-for-
ulven): uten artstermer ga en tynt dekket akse som "Lever" k-NN-naboer fra HELE cachen
uten artsfilter — målt live at de tre nærmeste for "Lever" var bavian-, hest- og
hunde-leverhistologi, ikke laks. bank.lignende_tekst() har ingen avstand-terskel
(_naboer_fra_rader "banding fjerner INGEN kandidat"), så dette er ikke en corner case —
det er dagens oppførsel for enhver tynt dekket akse uten artskontekst i søketeksten.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402
import domeneprofil  # noqa: E402


def _client():
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def test_synonym_tekst_baerer_artstermer_for_tynt_dekket_akse(monkeypatch):
    monkeypatch.setattr(api.scoping, "akse_dekning", lambda tekst: {"Lever": 0.0})
    sette_tekster = []

    def fake_lignende_tekst(tekst, k=3):
        sette_tekster.append(tekst)
        return []

    monkeypatch.setattr(api.bank, "lignende_tekst", fake_lignende_tekst)

    r = _client().get("/api/rapport/omfang", params={"tekst": "noe fritekst"})
    assert r.status_code == 200
    assert len(sette_tekster) == 1
    for term in domeneprofil.ARTSTERMER:
        assert term in sette_tekster[0], f"artsterm {term!r} manglet i synonym-teksten"


def test_full_dekket_akse_kaller_aldri_lignende_tekst(monkeypatch):
    monkeypatch.setattr(api.scoping, "akse_dekning", lambda tekst: {"Lever": 1.0})
    kalt = []
    monkeypatch.setattr(api.bank, "lignende_tekst", lambda tekst, k=3: kalt.append(tekst) or [])

    r = _client().get("/api/rapport/omfang", params={"tekst": "noe fritekst"})
    assert r.status_code == 200
    assert kalt == []
