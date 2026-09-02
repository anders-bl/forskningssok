"""Verifiserer rapport.py — kildesamling-malen: gruppering på domene-nærhet, ærlig
tomt-utvalg, og at rapportens tekst faktisk inneholder det den skal (ikke bare at
funksjonen ikke krasjer)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rapport import (  # noqa: E402
    Blokk, gap_rapport, kildesamling, kildesamling_blokker, omfang_rapport,
    sitatnotater, til_pdf_bytes,
)


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


# ---------- PDF-rendering (delt av alle malene) ----------

def test_pdf_gir_gyldige_pdf_bytes():
    blokker = kildesamling_blokker([_p("1", "T", forfattere="Havforskningsinstituttet",
                                        abstract="Et sammendrag & <spesialtegn> her")])
    pdf = til_pdf_bytes(blokker, tittel="T")
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 500  # ikke bare et tomt skall


def test_pdf_tolererer_xml_spesialtegn_uten_aa_krasje():
    """Reportlabs Paragraph-tekst er mini-XML — en tittel med & < > skal escapes,
    ikke knekke rendering stille eller kaste en parse-feil."""
    blokk = [Blokk("h1", "Tittel med & < > \" ' i seg")]
    pdf = til_pdf_bytes(blokk)
    assert pdf.startswith(b"%PDF")


# ---------- sitatnotater ----------

def _s(id_, paper_tittel, tekst, kommentar="", doi=None, opprettet=1700000000.0):
    return {"id": id_, "paper_id": "p" + str(id_), "tekst": tekst, "kommentar": kommentar,
            "opprettet": opprettet, "paper_tittel": paper_tittel, "paper_doi": doi}


def test_sitatnotater_tomt_gir_aerlig_melding():
    assert "ingen sitater" in sitatnotater([])


def test_sitatnotater_inneholder_sitat_og_kommentar():
    ut = sitatnotater([_s(1, "Papir A", "det viktige sitatet", kommentar="min tanke")])
    assert "Papir A" in ut
    assert "det viktige sitatet" in ut
    assert "min tanke" in ut


def test_sitatnotater_uten_kommentar_utelater_kommentarlinje():
    ut = sitatnotater([_s(1, "Papir A", "sitat")])
    assert "Kommentar:" not in ut


# ---------- gap-rapport ----------

def _gap_papir(tittel="Kildepapir"):
    return {"id": "1", "tittel": tittel, "forfattere": "", "tidsskrift": "", "aar": 2026,
            "doi": None, "abstract": "", "siteringstall": 0, "open_access": False, "kilde_url": "u"}


def test_gap_rapport_lister_kandidater_og_ikke_sitert_paastand():
    resultat = {"siterte_antall": 2, "referanse_kilde": "europe_pmc",
                "naboer": [{"id": "a", "tittel": "Sitert nabo", "tidsskrift": "X", "aar": 2020,
                            "kilde_url": "u", "avstand": 0.1},
                           {"id": "b", "tittel": "Ikke sitert nabo", "tidsskrift": "Y", "aar": 2021,
                            "kilde_url": "u", "avstand": 0.2}],
                "gap": [{"id": "b", "tittel": "Ikke sitert nabo", "tidsskrift": "Y", "aar": 2021,
                         "kilde_url": "u", "avstand": 0.2}]}
    ut = gap_rapport(_gap_papir("Kildepapir X"), resultat)
    assert "Citation-gap: Kildepapir X" in ut
    assert "Ikke sitert nabo" in ut
    assert "kandidater for" in ut.lower()
    assert "aldri en påstand" in ut.lower()


def test_gap_rapport_ingen_gap_gir_aerlig_melding():
    resultat = {"siterte_antall": 5, "referanse_kilde": "openalex",
                "naboer": [{"id": "a", "tittel": "T", "tidsskrift": "X", "aar": 2020,
                            "kilde_url": "u", "avstand": 0.1}],
                "gap": []}
    ut = gap_rapport(_gap_papir(), resultat)
    assert "Ingen kandidater" in ut


# ---------- omfang-rapport ----------

def test_omfang_rapport_full_dekning_ingen_forslag():
    ut = omfang_rapport({"Lever": 1.0}, {})
    assert "Lever — 100 %" in ut
    assert "Godt dekket" in ut


def test_omfang_rapport_tynn_dekning_lister_forslag():
    forslag = {"Lever": [{"tittel": "Kandidat om lever", "aar": 2023, "tidsskrift": "X"}]}
    ut = omfang_rapport({"Lever": 0.0}, forslag)
    assert "Lever — 0 %" in ut
    assert "Kandidat om lever" in ut
