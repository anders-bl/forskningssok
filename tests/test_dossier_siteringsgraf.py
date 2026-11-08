"""Verifiserer dossier_siteringsgraf.py (M4, prosjekt/forskningssok-dossier-scivis).
Nettverksfri: adapters.semantic_scholar.siteringsgraf() mockes, samme disiplin som
resten av forskningssok sin testsuite.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dossier_siteringsgraf as dsg  # noqa: E402


def _p(id, doi=None, tittel="", aar=None, kilde="europe_pmc", abstract=""):
    return {"id": id, "doi": doi, "tittel": tittel, "aar": aar, "kilde": kilde, "abstract": abstract}


def _sit(doi, tittel="", innflytelsesrik=False):
    return {"tittel": tittel, "aar": None, "doi": doi, "intents": (), "innflytelsesrik": innflytelsesrik}


def test_bygger_kant_kun_mellom_papirer_internt_i_settet(monkeypatch):
    papirer = [_p("a", doi="10.1/a"), _p("b", doi="10.1/b")]

    def fake_siteringsgraf(doi, **_kw):
        # "b" siterer "a" -- graf hentet FOR "a" skal vise "b" som siterende.
        if doi.lower() == "10.1/a":
            return {"siteringer": [_sit("10.1/b")], "referanser": []}
        return {"siteringer": [], "referanser": []}

    monkeypatch.setattr(dsg.semantic_scholar, "siteringsgraf", fake_siteringsgraf)
    graf = dsg.bygg_siteringsgraf(papirer)
    assert graf["noder"] == ["a", "b"]
    assert graf["kanter"] == [("b", "a")]
    assert graf["inn_grad"] == {"a": 1, "b": 0}
    assert graf["feilede_oppslag"] == []


def test_sitering_utenfor_settet_ignoreres_ikke_lagt_til_som_node():
    papirer = [_p("a", doi="10.1/a")]

    def fake_siteringsgraf(doi, **_kw):
        return {"siteringer": [_sit("10.1/ukjent-utenfor-settet")], "referanser": []}

    import unittest.mock
    with unittest.mock.patch.object(dsg.semantic_scholar, "siteringsgraf", fake_siteringsgraf):
        graf = dsg.bygg_siteringsgraf(papirer)
    assert graf["noder"] == ["a"]
    assert graf["kanter"] == []


def test_papir_uten_doi_blir_isolert_node_ikke_utelatt():
    papirer = [_p("a", doi=None)]
    graf = dsg.bygg_siteringsgraf(papirer)
    assert graf["noder"] == ["a"]
    assert graf["kanter"] == []
    assert graf["inn_grad"]["a"] == 0


def test_feilet_oppslag_degraderer_til_isolert_node_ikke_krasj(monkeypatch):
    papirer = [_p("a", doi="10.1/a"), _p("b", doi="10.1/b")]

    def fake(doi, **_kw):
        if doi.lower() == "10.1/a":
            raise RuntimeError("Semantic Scholar rate-limitet")
        return {"siteringer": [], "referanser": []}

    monkeypatch.setattr(dsg.semantic_scholar, "siteringsgraf", fake)
    graf = dsg.bygg_siteringsgraf(papirer)
    assert graf["noder"] == ["a", "b"]  # begge fortsatt med, ingen krasj
    assert graf["feilede_oppslag"] == ["a"]


def test_selvsitering_utelates(monkeypatch):
    papirer = [_p("a", doi="10.1/a")]
    monkeypatch.setattr(dsg.semantic_scholar, "siteringsgraf",
                         lambda doi, **_kw: {"siteringer": [_sit("10.1/a")], "referanser": []})
    graf = dsg.bygg_siteringsgraf(papirer)
    assert graf["kanter"] == []


def test_tomt_korpus_gir_aerlig_tom_graf():
    graf = dsg.bygg_siteringsgraf([])
    assert graf == {"noder": [], "kanter": [], "inn_grad": {}, "feilede_oppslag": [], "ufullstendige_oppslag": []}


def test_siteringsgraf_for_emne_legger_ved_node_metadata(monkeypatch):
    monkeypatch.setattr(dsg, "hent_kandidater",
                         lambda emne, db_path: [_p("a", doi="10.1/a",
                                                     tittel="Nephrocalcinosis in Atlantic salmon Salmo salar",
                                                     aar=2022)])
    monkeypatch.setattr(dsg.semantic_scholar, "siteringsgraf",
                         lambda doi, **_kw: {"siteringer": [], "referanser": []})
    graf = dsg.siteringsgraf_for_emne("nephrocalcinosis salmon")
    assert graf["noder_meta"]["a"]["tittel"] == "Nephrocalcinosis in Atlantic salmon Salmo salar"
    assert graf["noder_meta"]["a"]["aar"] == 2022
    assert graf["noder_meta"]["a"]["art_bekreftet"] is True


def test_primaer_akse_velger_hoyest_skarende_profilakse():
    # "liver"/"hepat" treffer kun Lever-aksen i fiskehelse.toml -- ingen gjetning,
    # samme nøkkelord-mekanisme som scoping.akse_dekning() allerede bruker for M2.
    p = _p("a", tittel="Hepatic lipidosis markers", abstract="liver histopathology in farmed fish")
    assert dsg._primaer_akse(p) == "Lever"


def test_primaer_akse_gir_aerlig_none_uten_treff():
    # Ingen aksenøkkelord i teksten -- None, ikke en gjettet/default-akse.
    p = _p("a", tittel="xyzabc qwerty", abstract="")
    assert dsg._primaer_akse(p) is None


def test_siteringsgraf_for_papirer_legger_ved_akse_per_node(monkeypatch):
    papirer = [
        _p("a", doi="10.1/a", tittel="Ultrasound imaging", abstract="ultralyd diagnos av nyre"),
        _p("b", doi=None, tittel="xyzabc qwerty", abstract=""),
    ]
    monkeypatch.setattr(dsg.semantic_scholar, "siteringsgraf",
                         lambda doi, **_kw: {"siteringer": [], "referanser": []})
    graf = dsg.siteringsgraf_for_papirer(papirer)
    assert graf["noder_meta"]["a"]["akse"] == "Ultralyd-validering"
    assert graf["noder_meta"]["b"]["akse"] is None


def _side(siteringer, *, complete, has_more, next_offset=None):
    return {"siteringer": siteringer, "referanser": [],
            "siteringer_dekning": {"complete": complete, "has_more": has_more, "next_offset": next_offset}}


def test_dossiergrafen_ber_om_full_side_og_paginerer_til_siste(monkeypatch):
    """s-19d HOLD #46295: adapterens standardgrense 20 kappet dossierets kanter stille."""
    papirer = [_p("a", doi="10.1/a"), _p("b", doi="10.1/b"), _p("c", doi="10.1/c")]
    kall = []

    def fake(doi, limit=20, offset=0):
        kall.append((doi, limit, offset))
        if doi != "10.1/a":
            return _side([], complete=True, has_more=False)
        if offset == 0:
            return _side([_sit("10.1/b")], complete=False, has_more=True, next_offset=1000)
        return _side([_sit("10.1/c")], complete=True, has_more=False)

    monkeypatch.setattr(dsg.semantic_scholar, "siteringsgraf", fake)
    graf = dsg.bygg_siteringsgraf(papirer)
    assert ("10.1/a", dsg.SIDE_GRENSE, 0) in kall and ("10.1/a", dsg.SIDE_GRENSE, 1000) in kall
    assert graf["kanter"] == [("b", "a"), ("c", "a")]
    assert graf["ufullstendige_oppslag"] == []


def test_ukjent_dekning_eller_nadd_tak_merkes_ufullstendig(monkeypatch):
    papirer = [_p("ukjent", doi="10.1/u"), _p("tak", doi="10.1/t")]
    kall = []

    def fake(doi, limit=20, offset=0):
        kall.append(doi)
        if doi == "10.1/u":
            return {"siteringer": [], "referanser": []}
        return _side([], complete=False, has_more=True, next_offset=offset + limit)

    monkeypatch.setattr(dsg.semantic_scholar, "siteringsgraf", fake)
    graf = dsg.bygg_siteringsgraf(papirer)
    assert graf["ufullstendige_oppslag"] == ["ukjent", "tak"]
    assert kall.count("10.1/t") == dsg.MAKS_SIDER
