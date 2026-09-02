"""Verifiserer rapport.py — kildesamling-malen: gruppering på domene-nærhet, ærlig
tomt-utvalg, og at rapportens tekst faktisk inneholder det den skal (ikke bare at
funksjonen ikke krasjer)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rapport import (  # noqa: E402
    Blokk, gap_rapport, kildesamling, kildesamling_blokker, omfang_rapport,
    sitatnotater, til_bibtex, til_pdf_bytes, til_ris,
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


def test_kildesamling_viser_evidensniva_naar_gjenkjent():
    p = _p("1", "A systematic review of nephrocalcinosis in salmon")
    ut = kildesamling([p])
    assert "Systematisk oversikt/meta-analyse" in ut


def test_kildesamling_flagger_species_trap_i_rapporten():
    """Det faktiske caset 2026-09-02 — ingen fisketerm — skal varsles i EKSPORTEN også,
    ikke bare i UI-badgen."""
    p = _p("1", "CYP24A1 pathogenic variant nephrocalcinosis case report")
    ut = kildesamling([p])
    assert "nevner ikke laks" in ut.lower()


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


# ---------- sitasjonseksport: BibTeX/RIS ----------

def test_bibtex_inneholder_forfatter_tittel_aar_doi():
    p = _p("1", "Nephrocalcinosis in salmon", forfattere="Dalum AS, Alarcon M", doi="10.1/x")
    ut = til_bibtex([p])
    assert ut.startswith("@article{dalum2026,")
    assert "author = {Dalum AS and Alarcon M}" in ut
    assert "title = {Nephrocalcinosis in salmon}" in ut
    assert "doi = {10.1/x}" in ut


def test_bibtex_nokler_deduplisert_ved_kollisjon():
    a = _p("1", "Første", forfattere="Dalum AS")
    b = _p("2", "Andre", forfattere="Dalum AS")  # samme forfatter+år → samme nøkkel-base
    ut = til_bibtex([a, b])
    assert "@article{dalum2026," in ut
    assert "@article{dalum20262," in ut


def test_bibtex_tomt_utvalg_gir_tom_streng():
    assert til_bibtex([]) == ""


def test_bibtex_semikolon_separerte_forfattere_openalex_form():
    p = _p("1", "T", forfattere="A. Forfatter; B. Medforfatter")
    ut = til_bibtex([p])
    assert "author = {A. Forfatter and B. Medforfatter}" in ut


def test_ris_har_riktig_tag_struktur():
    p = _p("1", "Nephrocalcinosis i laks", forfattere="Dalum AS, Alarcon M",
           tidsskrift="Journal of fish diseases", doi="10.1/x")
    ut = til_ris([p])
    linjer = ut.rstrip("\n").split("\n")
    assert linjer[0] == "TY  - JOUR"
    assert "AU  - Dalum AS" in linjer
    assert "AU  - Alarcon M" in linjer
    assert "TI  - Nephrocalcinosis i laks" in linjer
    assert "JO  - Journal of fish diseases" in linjer
    assert "PY  - 2026" in linjer
    assert "DO  - 10.1/x" in linjer
    assert linjer[-1] == "ER  - "


def test_ris_flere_papirer_separert_med_tomlinje():
    a = _p("1", "Første")
    b = _p("2", "Andre")
    ut = til_ris([a, b])
    assert ut.count("TY  - JOUR") == 2
    assert "\n\n" in ut


def test_ris_tomt_utvalg_gir_tom_streng():
    assert til_ris([]) == ""
