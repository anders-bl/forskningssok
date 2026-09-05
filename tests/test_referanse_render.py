"""Verifiserer rapport.render_referanser: ekte CSL-rendring via citeproc, og at en rapport
ALDRI krasjer på formatering (fallback til prosa).

Asserterer på stabile delstrenger (etternavn, år, DOI), ikke på eksakt citeproc-output —
den kan variere med bibliotekversjon, og en test som låser hele strengen ville vært skjør.
Nettverksfri: citeproc leser lokale .csl-filer, ingen tredjepart.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rapport  # noqa: E402

_PAPIR = {
    "id": "10.1111/jfd.13815", "doi": "10.1111/jfd.13815",
    "tittel": "Nephrocalcinosis in juvenile farmed Atlantic Salmon",
    "forfattere": "Klykken C, Reed AK", "tidsskrift": "Journal of Fish Diseases",
    "aar": 2023, "volum": "46", "sider": "943-956",
}


def test_vancouver_rendrer_journal_standard():
    linjer = rapport.render_referanser([_PAPIR], stil="vancouver")
    assert len(linjer) == 1
    r = linjer[0]
    assert "Klykken" in r          # forfatter
    assert "2023" in r             # år
    assert "Journal of Fish Diseases" in r
    assert "10.1111/jfd.13815" in r  # DOI
    assert r.strip()[0:3].strip("[").strip().startswith(("1", "[")) or "1" in r[:4], \
        "Vancouver er nummerert"


def test_apa_rendrer_annerledes_enn_vancouver():
    v = rapport.render_referanser([_PAPIR], stil="vancouver")[0]
    a = rapport.render_referanser([_PAPIR], stil="apa")[0]
    assert v != a, "ulike stiler skal gi ulik formatering"
    assert "Klykken" in a and "2023" in a  # samme fakta, annen form


def test_ukjent_stil_faller_til_prosa_ikke_krasj():
    linjer = rapport.render_referanser([_PAPIR], stil="finnes-ikke")
    assert len(linjer) == 1
    assert "Klykken" in linjer[0] and "2023" in linjer[0]
    # fallback-formen bærer doi: som prefiks, ikke citeproc sin URL
    assert "doi:10.1111/jfd.13815" in linjer[0]


def test_raatten_data_krasjer_ikke_rapporten():
    """En rapport skal aldri gi 500 på formatering. Et papir uten noe brukbart felt skal
    gi en fallback-linje, ikke et unntak."""
    linjer = rapport.render_referanser([{"tittel": None, "aar": "ikke et tall"}], stil="vancouver")
    assert len(linjer) == 1 and isinstance(linjer[0], str)


def test_tom_liste_gir_tom_referanseliste():
    assert rapport.render_referanser([], stil="vancouver") == []
    assert rapport.referanseliste_blokker([], stil="vancouver") == []


def test_antall_referanser_matcher_antall_papirer():
    """Regresjonsvakt: hvis citeproc dropper en post, faller HELE lista til fallback så
    referanse [3] aldri peker på feil papir."""
    tre = [dict(_PAPIR, id=f"10.1/{i}", doi=f"10.1/{i}") for i in range(3)]
    assert len(rapport.render_referanser(tre, stil="vancouver")) == 3


def test_kildesamling_har_referanser_seksjon():
    md = rapport.kildesamling([_PAPIR], tittel="Test", stil="vancouver")
    assert "## Referanser" in md
    assert "VANCOUVER" in md
    assert "Klykken" in md.split("## Referanser")[1]


def test_csl_post_utelater_felt_vi_ikke_har():
    """Deler feltmapping med til_csl_json: et fraværende felt skal UTELATES, ikke settes
    tomt (ellers renderer citeproc «s. » med tomt sidetall)."""
    post = rapport._csl_post({"tittel": "T", "doi": "10.1/x"})  # ingen volum/sider
    assert "volume" not in post and "page" not in post
    assert post["title"] == "T" and post["DOI"] == "10.1/x"
