"""scivis_koblinger.hent_papirer mot adapternes faktiske returtype.

Funnet 2026-09-27 av ruff F821 (`openalex_sok` aldri importert). Under lå en større feil:
alle tre adapterne returnerer PaperDossier (dataclass), og hent_papirer kalte `.get()` på
dem. Hver kilde kastet AttributeError inni sin egen `except Exception`, så verktøyet fant
alltid 0 papirer og sa «Ingen papirer funnet» som om søket var tomt.

Hermetisk: falske adaptere, og numpy/umap stubbes i sys.modules fordi scivis-avhengighetene
bor i requirements-scivis.txt og ikke i test-venven. Ingen nett.
"""
import sys
import types

import pytest

from schemas import PaperDossier


def _papir(tittel, kilde, doi="10.1/x", forfattere="A. Berg, C. Dahl"):
    return PaperDossier(pmid=None, doi=doi, tittel=tittel, forfattere=forfattere,
                        tidsskrift="T", aar=2024, abstract="abs", siteringstall=None,
                        open_access=True, kilde_url="https://eksempel.invalid/p", kilde=kilde)


@pytest.fixture
def scivis(monkeypatch):
    monkeypatch.setitem(sys.modules, "numpy", types.ModuleType("numpy"))
    monkeypatch.setitem(sys.modules, "umap", types.ModuleType("umap"))
    monkeypatch.delitem(sys.modules, "scivis_koblinger", raising=False)
    import scivis_koblinger as m
    return m


def test_alle_tre_kilder_gir_rader(scivis, monkeypatch):
    monkeypatch.setattr(scivis, "core_sok", lambda q, **k: [_papir("Core-papir", "core")])
    monkeypatch.setattr(scivis, "europe_pmc_sok", lambda q, **k: [_papir("PMC-papir", "europe_pmc")])
    monkeypatch.setattr(scivis, "openalex_sok", lambda q, **k: [_papir("Alex-papir", "openalex")])
    rader = scivis.hent_papirer("laks lever")
    assert [r["kilde"] for r in rader] == ["CORE", "Europe PMC", "OpenAlex"]
    r = rader[0]
    assert r["tittel"] == "Core-papir" and r["doi"] == "10.1/x" and r["aar"] == 2024
    # HTML-en gjør d.forfattere.join(", ") -- må være en liste.
    assert r["forfattere"] == ["A. Berg, C. Dahl"]
    assert r["id"]


def test_en_kilde_som_feiler_stopper_ikke_de_andre(scivis, monkeypatch, capsys):
    def boom(q, **k):
        raise RuntimeError("nede")
    monkeypatch.setattr(scivis, "core_sok", boom)
    monkeypatch.setattr(scivis, "europe_pmc_sok", lambda q, **k: [_papir("PMC-papir", "europe_pmc")])
    monkeypatch.setattr(scivis, "openalex_sok", lambda q, **k: [])
    rader = scivis.hent_papirer("x")
    assert [r["tittel"] for r in rader] == ["PMC-papir"]
    assert "CORE feilet: nede" in capsys.readouterr().out
