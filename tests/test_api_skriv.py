"""Verifiserer Skriv-modus-endepunktene (utkast/relevans/omfang). Mocker på bank.py/
scoping.py-funksjonsnivå, ikke DB-sti — api.py sine nye endepunkter kaller bank.X() uten
eksplisitt db_path, og bank sine funksjoners db_path-default bindes ved IMPORT (samme
felle api_status()s egen kommentar dokumenterer for CACHE_DB) — å patche bank.DB etter
import ville derfor ikke truffet dem. Funksjonsnivå-mocking unngår fellen helt.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(api.app)


def test_utkast_lagre_og_hente():
    with patch("api.bank.lagre_utkast", return_value={"id": 1, "tittel": "t", "innhold": "i", "oppdatert": 123.0}) as m:
        r = client.post("/api/utkast", json={"tittel": "t", "innhold": "i"})
    assert r.status_code == 200
    assert r.json()["id"] == 1
    m.assert_called_once_with("t", "i", None)


def test_utkast_lagre_tom_tittel_degraderer_ikke_feiler():
    with patch("api.bank.lagre_utkast", return_value={"id": 1, "tittel": "Uten tittel", "innhold": "i", "oppdatert": 1.0}) as m:
        client.post("/api/utkast", json={"innhold": "i"})
    m.assert_called_once_with("Uten tittel", "i", None)


def test_utkast_hent_ukjent_gir_404():
    with patch("api.bank.hent_utkast", return_value=None):
        r = client.get("/api/utkast/999")
    assert r.status_code == 404


def test_relevans_returnerer_naboer():
    naboer = [{"id": "10.1/x", "tittel": "t", "avstand": 0.3}]
    with patch("api.bank.lignende_tekst", return_value=naboer) as m:
        r = client.get("/api/relevans", params={"tekst": "noe langt nok tekst her"})
    assert r.status_code == 200
    assert r.json()["naboer"] == naboer
    m.assert_called_once()


def test_relevans_tomt_svar_er_200_ikke_feil():
    """Ærlig tomt (ingen treff/for kort tekst) skal se ut som stillhet, ikke en feil —
    FDR-038s eget krav."""
    with patch("api.bank.lignende_tekst", return_value=[]):
        r = client.get("/api/relevans", params={"tekst": "kort"})
    assert r.status_code == 200
    assert r.json()["naboer"] == []


def test_utkast_slett():
    with patch("api.bank.slett_utkast", return_value=True) as m:
        r = client.delete("/api/utkast/1")
    assert r.status_code == 200
    m.assert_called_once_with(1)


def test_utkast_slett_ukjent_gir_404():
    with patch("api.bank.slett_utkast", return_value=False):
        r = client.delete("/api/utkast/999")
    assert r.status_code == 404


def test_sitat_slett():
    with patch("api.bank.slett_sitat", return_value=True) as m:
        r = client.delete("/api/sitater/1")
    assert r.status_code == 200
    m.assert_called_once_with(1)


def test_sitat_slett_ukjent_gir_404():
    with patch("api.bank.slett_sitat", return_value=False):
        r = client.delete("/api/sitater/999")
    assert r.status_code == 404


def test_rapport_kildesamling_returnerer_markdown():
    papir = {"id": "1", "tittel": "T", "forfattere": "", "tidsskrift": "", "aar": 2026,
             "doi": None, "abstract": "", "siteringstall": 0, "open_access": False, "kilde_url": "u"}
    with patch("api.bank.hent", return_value=papir):
        r = client.get("/api/rapport/kildesamling", params={"ids": "1"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert "# Kildesamling" in r.text


def test_rapport_kildesamling_ukjente_id_er_droppes_men_kjente_beholdes():
    def _hent(pid):
        return None if pid == "ukjent" else {"id": pid, "tittel": "T", "forfattere": "",
            "tidsskrift": "", "aar": 2026, "doi": None, "abstract": "", "siteringstall": 0,
            "open_access": False, "kilde_url": "u"}
    with patch("api.bank.hent", side_effect=_hent):
        r = client.get("/api/rapport/kildesamling", params={"ids": "1,ukjent"})
    assert r.status_code == 200
    assert "T" in r.text


def test_rapport_kildesamling_ingen_gyldige_id_gir_404():
    with patch("api.bank.hent", return_value=None):
        r = client.get("/api/rapport/kildesamling", params={"ids": "ukjent"})
    assert r.status_code == 404


def test_rapport_kildesamling_tom_ids_gir_400():
    r = client.get("/api/rapport/kildesamling", params={"ids": ""})
    assert r.status_code == 400


def test_rapport_kildesamling_pdf_format_gir_pdf_content_type():
    papir = {"id": "1", "tittel": "T", "forfattere": "", "tidsskrift": "", "aar": 2026,
             "doi": None, "abstract": "", "siteringstall": 0, "open_access": False, "kilde_url": "u"}
    with patch("api.bank.hent", return_value=papir):
        r = client.get("/api/rapport/kildesamling", params={"ids": "1", "format": "pdf"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    assert "attachment" in r.headers["content-disposition"]


def test_rapport_sitatnotater_returnerer_markdown():
    sitater = [{"id": 1, "paper_id": "p1", "tekst": "sitat", "kommentar": "", "opprettet": 1.0,
                "paper_tittel": "P", "paper_doi": None}]
    with patch("api.bank.hent_sitater", return_value=sitater) as m:
        r = client.get("/api/rapport/sitatnotater")
    assert r.status_code == 200
    assert "# Sitatnotater" in r.text
    assert "sitat" in r.text
    m.assert_called_once_with()


def test_rapport_gap_papir_ikke_cachet_gir_404():
    with patch("api.bank.hent", return_value=None):
        r = client.get("/api/rapport/gap/ukjent")
    assert r.status_code == 404


def test_rapport_gap_mangler_pmid_og_doi_gir_422():
    papir = {"pmid": None, "doi": None, "tittel": "T", "kilde_kode": "MED"}
    with patch("api.bank.hent", return_value=papir):
        r = client.get("/api/rapport/gap/x")
    assert r.status_code == 422


def test_rapport_gap_returnerer_markdown():
    papir = {"pmid": "1", "doi": None, "tittel": "Kildepapir", "kilde_kode": "MED"}
    resultat = {"siterte_antall": 1, "referanse_kilde": "europe_pmc",
                "naboer": [{"id": "a", "tittel": "Nabo", "tidsskrift": "X", "aar": 2020,
                            "kilde_url": "u", "avstand": 0.1}],
                "gap": [{"id": "a", "tittel": "Nabo", "tidsskrift": "X", "aar": 2020,
                         "kilde_url": "u", "avstand": 0.1}]}
    with patch("api.bank.hent", return_value=papir), patch("api.gap_kandidater", return_value=resultat):
        r = client.get("/api/rapport/gap/1")
    assert r.status_code == 200
    assert "Citation-gap: Kildepapir" in r.text
    assert "Nabo" in r.text


def test_rapport_omfang_returnerer_markdown_med_forslag():
    akser = {"Lever": 0.0, "Faser": 1.0}
    kandidat = [{"tittel": "Leverfunn", "aar": 2023, "tidsskrift": "X"}]
    with patch("api.scoping.akse_dekning", return_value=akser), \
         patch("api.bank.lignende_tekst", return_value=kandidat):
        r = client.get("/api/rapport/omfang", params={"tekst": "noe tekst"})
    assert r.status_code == 200
    assert "Lever — 0 %" in r.text
    assert "Leverfunn" in r.text
    assert "Faser — 100 %" in r.text


def test_papir_bruker_delt_arts_naer_ikke_egen_reimplementasjon():
    """Regresjon: en tidligere versjon regnet arts_naer inline med ARTSTERMER direkte i
    stedet for å kalle domeneprofil.arts_naer_tekst() — fikk derfor IKKE med seg
    salmon-calcitonin-fiksen for dette endepunktet. Se api.py:api_papir sin kommentar."""
    papir = {"tittel": "CYP24A1 mutations", "forfattere": "", "tidsskrift": "",
             "abstract": "Patients were treated with salmon calcitonin injection.",
             "aar": 2022, "doi": None, "pmid": None, "siteringstall": 0,
             "open_access": False, "kilde_url": "u", "kilde_kode": "MED"}
    with patch("api.bank.hent", return_value=papir):
        r = client.get("/api/papir/x")
    assert r.status_code == 200
    assert r.json()["arts_naer"] is False


def test_papir_ukjent_gir_404():
    with patch("api.bank.hent", return_value=None):
        r = client.get("/api/papir/ukjent")
    assert r.status_code == 404


def test_tilgang_returnerer_lisens_og_pdf():
    info = {"lisens": "cc-by", "fri_pdf_url": "https://x/pdf", "utgiver": "Wiley", "oa_status": "gold"}
    with patch("api.openalex.tilgang", return_value=info) as m:
        r = client.get("/api/tilgang/10.1111/jfd.13815")
    assert r.status_code == 200
    assert r.json() == info
    m.assert_called_once_with("10.1111/jfd.13815")


def test_tilgang_uten_doi_gir_aerlig_tomt_objekt_ikke_feil():
    r = client.get("/api/tilgang/41363532")  # PMID, ikke DOI
    assert r.status_code == 200
    assert r.json() == {"lisens": None, "fri_pdf_url": None, "utgiver": None, "oa_status": None}


def test_tilgang_kilde_feil_gir_502():
    with patch("api.openalex.tilgang", side_effect=RuntimeError("OpenAlex utilgjengelig: x")):
        r = client.get("/api/tilgang/10.1111/jfd.13815")
    assert r.status_code == 502


def test_omfang_returnerer_akser():
    akser = {"Lever": 1.0, "Faser": 0.0}
    with patch("api.scoping.akse_dekning", return_value=akser):
        r = client.get("/api/omfang", params={"tekst": "noe om lever"})
    assert r.status_code == 200
    assert r.json()["akser"] == akser
