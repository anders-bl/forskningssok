"""Verifiserer sti.py: Dijkstra over kNN-grafen, og at hver ulike grunn til «ingen sti»
sier hva den faktisk er i stedet for å kollapse til samme tomme svar.

Grafen her er konstruert, ikke lest fra cachen: testen skal måle traverseringen, ikke
innholdet i Anders' cache.db (som er gitignorert og aldri finnes i CI).
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sti  # noqa: E402


def _p(pid, abstract="et abstract"):
    return {"id": pid, "tittel": f"Tittel {pid}", "tidsskrift": "X", "aar": 2020,
            "doi": pid if pid.startswith("10.") else None, "kilde_url": "u",
            "abstract": abstract}


# a—b 0.9, a—c 0.3, c—d 0.3, d—b 0.2  →  billigste vei a→b er via c,d (0.8), ikke direkte.
GRAF = {
    "a": [("b", 0.9), ("c", 0.3)],
    "c": [("a", 0.3), ("d", 0.3)],
    "d": [("c", 0.3), ("b", 0.2)],
    "b": [("d", 0.2), ("a", 0.9)],
    "ensom": [],
}


def _lignende(node, k=5, band=True, db_path=None):
    return [{"id": n, "avstand": d} for n, d in GRAF.get(node, [])][:k]


@pytest.fixture(autouse=True)
def graf(monkeypatch):
    monkeypatch.setattr(sti.bank, "lignende",
                        lambda node, k=5, band=True, db_path=None: _lignende(node, k, band))
    monkeypatch.setattr(sti.bank, "hent",
                        lambda pid, db_path=None: _p(pid) if pid in GRAF else None)


def test_velger_korteste_AVSTAND_ikke_faerrest_hopp():
    """Færrest hopp og sterkest forbindelse er ikke det samme. To hopp på 0.95 er en
    svakere kjede enn tre på 0.3, og styrken er det Ulven skal kunne vurdere."""
    ut = sti.finn_sti("a", "b")
    assert [p["id"] for p in ut["sti"]] == ["a", "c", "d", "b"]
    assert ut["hopp"] == 3
    assert ut["total_avstand"] == pytest.approx(0.8)


def test_hvert_ledd_baerer_sin_egen_avstand():
    """En totalsum skjuler om kjeden er jevn eller har ett svakt ledd."""
    ut = sti.finn_sti("a", "b")
    assert [led["avstand"] for led in ut["ledd"]] == [0.3, 0.3, 0.2]
    assert [(led["fra"], led["til"]) for led in ut["ledd"]] == [("a", "c"), ("c", "d"), ("d", "b")]


def test_samme_papir_er_null_hopp_ikke_en_feil():
    ut = sti.finn_sti("a", "a")
    assert ut["hopp"] == 0 and len(ut["sti"]) == 1


def test_ucachet_papir_navngir_HVILKET_som_mangler():
    ut = sti.finn_sti("a", "finnes-ikke")
    assert ut["sti"] == [] and "finnes-ikke" in ut["grunn"]


def test_papir_uten_abstract_meldes_som_isolert_node_ikke_som_lang_avstand():
    """Uten dette skillet ville «ingen vektor» sett ut som en påstand om semantisk
    avstand. Det er manglende data, ikke et fjernt papir."""
    with patch.object(sti.bank, "hent",
                      lambda pid, db_path=None: _p(pid, abstract="" if pid == "b" else "noe")):
        ut = sti.finn_sti("a", "b")
    assert ut["sti"] == []
    assert "isolert node" in ut["grunn"] and "abstract" in ut["grunn"]


def test_ingen_sti_sier_hvilken_k_som_ble_brukt_og_naekter_aa_konkludere():
    """kNN-grafen har k kanter per node. «Ingen sti ved k=6» er ikke «papirene er
    urelaterte» — en høyere k kunne funnet en, og svaret må si det."""
    ut = sti.finn_sti("a", "ensom")
    assert ut["sti"] == []
    assert "k=6" in ut["grunn"] and "ikke en påstand" in ut["grunn"]


def test_maks_hopp_tvinger_fram_den_dyrere_direkte_kanten():
    """Grensen er ekte, ikke kosmetisk: den billigste veien (0.8 over tre hopp) er utenfor
    rekkevidde ved maks_hopp=1, så svaret blir den direkte kanten på 0.9 — en dårligere
    forbindelse, funnet fordi søkedybden var begrenset. Verdt å se i svaret, siden
    total_avstand da ikke er grafens minimum."""
    ut = sti.finn_sti("a", "b", maks_hopp=1)
    assert [p["id"] for p in ut["sti"]] == ["a", "b"]
    assert ut["total_avstand"] == pytest.approx(0.9)


def test_uten_noen_naaabar_vei_er_svaret_tomt_med_grunn():
    ut = sti.finn_sti("a", "ensom", maks_hopp=1)
    assert ut["sti"] == [] and "ingen sti" in ut["grunn"]


def test_traverseringen_bruker_ubandet_naboliste():
    """band=False er ikke en detalj: banding sorterer FØR kuttet til k, så den kan skyve
    den nærmeste naboen ut av kant-mengden. Presentasjon og topologi er ulike spørsmål."""
    sett = []
    with patch.object(sti.bank, "lignende",
                      side_effect=lambda node, k=5, band=True, db_path=None:
                          (sett.append(band), _lignende(node, k, band))[1]):
        sti.finn_sti("a", "b")
    assert sett and all(b is False for b in sett)
