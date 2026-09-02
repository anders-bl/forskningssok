"""Verifiserer rapport.py — kildesamling-malen: gruppering på domene-nærhet, ærlig
tomt-utvalg, og at rapportens tekst faktisk inneholder det den skal (ikke bare at
funksjonen ikke krasjer)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rapport import kildesamling  # noqa: E402


def _p(id_, tittel, forfattere="", tidsskrift="", abstract="", **kw):
    base = {"id": id_, "tittel": tittel, "forfattere": forfattere, "tidsskrift": tidsskrift,
            "aar": 2026, "doi": None, "abstract": abstract, "siteringstall": 0,
            "open_access": False, "kilde_url": "https://example.org/" + id_}
    base.update(kw)
    return base


def test_tomt_utvalg_gir_aerlig_melding_ikke_feil():
    ut = kildesamling([])
    assert "ingen papirer" in ut


def test_grupperer_domene_naere_og_oevrige_i_egne_seksjoner():
    naer = _p("1", "Norsk funn", forfattere="Havforskningsinstituttet")
    fjern = _p("2", "Urelatert funn", forfattere="MIT", tidsskrift="Nature")
    ut = kildesamling([naer, fjern])
    assert ut.index("## Nordisk fagmiljø") < ut.index("Norsk funn")
    assert ut.index("## Øvrige treff") < ut.index("Urelatert funn")
    assert ut.index("Norsk funn") < ut.index("## Øvrige treff")  # riktig seksjon, ikke bare til stede


def test_kun_naere_gir_ingen_oevrig_seksjon():
    naer = _p("1", "Norsk funn", forfattere="NMBU")
    ut = kildesamling([naer])
    assert "## Øvrige treff" not in ut


def test_abstract_kuttes_med_ellipse_ved_lang_tekst():
    langt = "x" * 500
    ut = kildesamling([_p("1", "T", abstract=langt)])
    assert "…" in ut
    assert "x" * 401 not in ut  # faktisk kuttet, ikke bare tilfeldigvis kort nok


def test_tittel_parameter_brukes_som_overskrift():
    ut = kildesamling([_p("1", "T")], tittel="Min egen tittel")
    assert ut.startswith("# Min egen tittel")
