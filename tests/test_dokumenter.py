"""Verifiserer dokumenter.py: en dratt-inn PDF blir et ekte papir, DOI-en i dokumentet
er identiteten, og et manglende tekstlag sies høyt i stedet for å se ut som et tomt papir.

PDF-ene her er EKTE PDF-er, bygget med reportlab (alt en avhengighet for rapport.py) og
lest tilbake med pypdf. En fixture med håndskrevne `%PDF`-bytes ville testet parseren vår
mot vår egen idé om PDF-format i stedet for mot formatet.
"""
import io
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bank  # noqa: E402
import dokumenter  # noqa: E402
from schemas import PaperDossier  # noqa: E402


def _fake_embed(texts):
    return [[0.0] * 1024 for _ in texts]


def _pdf(*linjer: str) -> bytes:
    """Ekte, tekstbærende PDF."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for linje in linjer:
        c.drawString(60, y, linje)
        y -= 20
    c.save()
    return buf.getvalue()


def _pdf_uten_tekstlag() -> bytes:
    """En side uten et eneste tekst-objekt — det en skannet side er for en parser."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.rect(50, 50, 200, 200, fill=1)  # kun grafikk
    c.save()
    return buf.getvalue()


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Egen cache OG egen dokumentmappe. Uten mappe-omdirigeringen ville testene skrevet
    PDF-er ved siden av Anders' ekte cache.db — samme verts-avhengighet som gjorde
    test_api_status rød i CI i sju kjøringer."""
    monkeypatch.setattr(dokumenter, "MAPPE", tmp_path / "dokumenter")
    return tmp_path / "cache.db"


def _cache_papir(db, doi="10.1111/jfd.70099", tittel="Ekte tittel fra kilden"):
    p = PaperDossier(pmid="1", doi=doi, tittel=tittel, forfattere="Hansen A",
                     tidsskrift="Journal of Fish Diseases", aar=2024, abstract="abstract",
                     siteringstall=3, open_access=False, kilde_url="u")
    bank.lagre([p], embed_fn=_fake_embed, db_path=db)
    return p


def test_les_pdf_henter_tekst_og_sidetall():
    d = dokumenter.les_pdf(_pdf("Nefrokalsinose hos atlantisk laks", "Metode og funn"))
    assert "Nefrokalsinose" in d["tekst"]
    assert d["sider"] == 1


def test_ikke_pdf_gir_ValueError():
    with pytest.raises(ValueError):
        dokumenter.les_pdf(b"dette er ikke en PDF")


@pytest.mark.parametrize("rå, ventet", [
    ("doi:10.1111/jfd.70099", "10.1111/jfd.70099"),
    ("https://doi.org/10.1111/JFD.70099.", "10.1111/jfd.70099"),   # trimmer setningstegn
    ("(10.1038/s41598-024-1234-5)", "10.1038/s41598-024-1234-5"),
    ("ingen identifikator her", None),
])
def test_finn_doi(rå, ventet):
    assert dokumenter.finn_doi(rå) == ventet


def test_doi_hentes_fra_forsiden_ikke_referanselista(db):
    """Den verste feilen modulen kan gjøre: feste fulltekst på et papir dokumentet bare
    SITERER. Forsidens DOI er dokumentets egen; side 12 er andres."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(60, 800, "doi:10.1111/egen.1")   # side 1
    c.showPage()
    for _ in range(4):                             # fyll til forbi _DOI_SIDER
        c.showPage()
    c.drawString(60, 800, "Referanser: 10.9999/andres.2")
    c.save()

    lest = dokumenter.les_pdf(buf.getvalue())
    assert dokumenter.finn_doi(lest["forside"]) == "10.1111/egen.1"
    assert "10.9999/andres.2" in lest["tekst"]  # den ER lest, den brukes bare ikke som id


def test_pdf_fester_seg_paa_allerede_cachet_papir(db):
    _cache_papir(db)
    d = dokumenter.lagre("nedlastet (3).pdf", _pdf("doi:10.1111/jfd.70099", "Fulltekst her"),
                         embed_fn=_fake_embed, db_path=db)
    assert d["paper_id"] == "10.1111/jfd.70099"
    assert d["knyttet_via"] == "doi-i-cache"
    # Ingen dublett: papiret skal fortsatt ha kildens tittel, ikke filnavnet.
    assert bank.hent("10.1111/jfd.70099", db_path=db)["tittel"] == "Ekte tittel fra kilden"


def test_valgt_paper_id_vinner_over_doi_i_fila(db):
    _cache_papir(db, doi="10.1000/valgt", tittel="Valgt")
    _cache_papir(db, doi="10.1111/jfd.70099")
    d = dokumenter.lagre("f.pdf", _pdf("doi:10.1111/jfd.70099"), paper_id="10.1000/valgt",
                         embed_fn=_fake_embed, db_path=db)
    assert d["paper_id"] == "10.1000/valgt" and d["knyttet_via"] == "valgt"


def test_ukjent_doi_slaas_opp_hos_kilden_for_ekte_metadata(db):
    """PDF-metadataens tittel skal aldri bli stående som om den var kildens."""
    ekte = PaperDossier(pmid="9", doi="10.5000/ny", tittel="Kildens egen tittel",
                        forfattere="Ulven K", tidsskrift="Aquaculture", aar=2025,
                        abstract="ekte abstract", siteringstall=0, open_access=True,
                        kilde_url="u")
    d = dokumenter.lagre("untitled.pdf", _pdf("doi:10.5000/ny"),
                         oppslag_fn=lambda q, n: [ekte], embed_fn=_fake_embed, db_path=db)
    assert d["knyttet_via"] == "doi-slatt-opp"
    assert bank.hent("10.5000/ny", db_path=db)["tittel"] == "Kildens egen tittel"


def test_kilde_nede_avviser_ikke_brukerens_egen_fil(db):
    """EBI lå nede i DAGEVIS i september. En nede tredjepart skal ikke kunne hindre Ulven
    i å legge inn et papir han allerede HAR."""
    def nede(q, n):
        raise RuntimeError("503")
    d = dokumenter.lagre("f.pdf", _pdf("doi:10.5000/ny"), oppslag_fn=nede,
                         embed_fn=_fake_embed, db_path=db)
    assert d["paper_id"] == "10.5000/ny" and d["knyttet_via"] == "lokal-doi"
    assert bank.hent("10.5000/ny", db_path=db)["kilde_kode"] == "LOKAL"


def test_uten_doi_blir_lokal_identitet_fra_filas_innhold_ikke_filnavnet(db):
    """Samme FIL to ganger er ett dokument, uansett hva den heter — det vanlige tilfellet
    er at samme nedlasting dras inn på nytt.

    Ærlig grense, målt her og ikke antatt: identiteten er sha256 av BYTENE. To ulike
    eksporter av samme artikkel (ulik utgiver-PDF, eller to reportlab-kjøringer, som
    stempler et tidspunkt inn i fila) er derfor to dokumenter. Å hashe den uttrukne
    TEKSTEN i stedet ville løst det — og samtidig kollapset hver eneste skannede PDF til
    samme id, siden de alle trekker ut tom streng. Byte-identitet er den trygge av de to."""
    data = _pdf("En intern rapport uten DOI")
    a = dokumenter.lagre("rapport.pdf", data, embed_fn=_fake_embed, db_path=db)
    b = dokumenter.lagre("helt annet navn.pdf", data, embed_fn=_fake_embed, db_path=db)
    assert a["id"] == b["id"], "samme fil = samme dokument, uansett filnavn"
    assert a["paper_id"].startswith("lokal:")
    assert len(dokumenter.liste(db_path=db)) == 1

    annen_eksport = _pdf("En intern rapport uten DOI")
    c = dokumenter.lagre("rapport.pdf", annen_eksport, embed_fn=_fake_embed, db_path=db)
    assert c["id"] != a["id"], "dokumentert grense, ikke en påstand om tekst-identitet"


def test_lokalt_papir_faar_ALDRI_oppdiktet_abstract(db):
    """Fulltekstens første avsnitt ville vært et fristende «abstract» — og en plassholder
    som ser ut som data er verre enn ingen data (README §Metadata-gapet)."""
    d = dokumenter.lagre("r.pdf", _pdf("Innledning", "Dette er ikke et abstract"),
                         embed_fn=_fake_embed, db_path=db)
    assert bank.hent(d["paper_id"], db_path=db)["abstract"] == ""


def test_skannet_pdf_sier_fra_i_stedet_for_aa_se_tom_ut(db):
    d = dokumenter.lagre("skann.pdf", _pdf_uten_tekstlag(), embed_fn=_fake_embed, db_path=db)
    assert d["tekstlag"] is False and d["tegn"] == 0
    assert d["sider"] == 1, "fila er lagret og lesbar som PDF selv uten tekstlag"
    assert dokumenter.fil_sti(d["id"]).exists()


def test_for_stor_fil_avvises_med_grensen_i_meldingen(db):
    with patch.object(dokumenter, "MAKS_BYTES", 100):
        with pytest.raises(ValueError, match="grensen"):
            dokumenter.lagre("stor.pdf", _pdf("x" * 500), db_path=db)


def test_tom_fil_avvises(db):
    with pytest.raises(ValueError, match="tom fil"):
        dokumenter.lagre("tom.pdf", b"", db_path=db)


def test_sletting_beholder_sitatene_men_fjerner_fila(db):
    d = dokumenter.lagre("f.pdf", _pdf("noe tekst"), embed_fn=_fake_embed, db_path=db)
    bank.lagre_sitat(d["paper_id"], "et sitat Ulven skrev", db_path=db)
    sti = dokumenter.fil_sti(d["id"])
    assert sti.exists()

    assert dokumenter.slett(d["id"], db_path=db) is True
    assert not sti.exists()
    assert dokumenter.hent(d["id"], db_path=db) is None
    assert len(bank.hent_sitater(d["paper_id"], db_path=db)) == 1, "notatene er hans arbeid"
    assert dokumenter.slett(d["id"], db_path=db) is False, "idempotent, ikke en feil"


def test_flere_dokumenter_paa_samme_papir(db):
    _cache_papir(db)
    dokumenter.lagre("hoved.pdf", _pdf("doi:10.1111/jfd.70099", "hoveddel"),
                     embed_fn=_fake_embed, db_path=db)
    dokumenter.lagre("supplement.pdf", _pdf("doi:10.1111/jfd.70099", "vedlegg S1"),
                     embed_fn=_fake_embed, db_path=db)
    assert len(dokumenter.for_papir("10.1111/jfd.70099", db_path=db)) == 2


def test_fulltekst_er_faktisk_lesbar_tilbake(db):
    d = dokumenter.lagre("f.pdf", _pdf("Nefrokalsinose ble påvist i 12 av 40 individer"),
                         embed_fn=_fake_embed, db_path=db)
    assert "12 av 40" in dokumenter.hent(d["id"], db_path=db)["tekst"]


# ---------- Endepunktene ----------

def _klient(db, monkeypatch):
    import api
    monkeypatch.setattr(api, "CACHE_DB", db)
    from fastapi.testclient import TestClient
    return api, TestClient(api.app)


def test_endepunkt_laster_opp_og_svarer_hvilket_papir_fila_landet_paa(db, monkeypatch):
    _cache_papir(db)
    api, c = _klient(db, monkeypatch)
    with patch("bank._hus_embed", return_value=_fake_embed):
        r = c.post("/api/dokument",
                   files={"fil": ("nedlastet.pdf", _pdf("doi:10.1111/jfd.70099", "brødtekst"),
                                  "application/pdf")})
    assert r.status_code == 200
    d = r.json()
    assert d["paper_id"] == "10.1111/jfd.70099" and d["tekstlag"] is True


def test_endepunkt_avviser_noe_som_ikke_er_pdf_med_400_ikke_500(db, monkeypatch):
    api, c = _klient(db, monkeypatch)
    r = c.post("/api/dokument", files={"fil": ("bilde.png", b"\x89PNG\r\n", "image/png")})
    assert r.status_code == 400
    assert "PDF" in r.json()["detail"]


def test_endepunkt_gir_fulltekst_og_selve_fila_tilbake(db, monkeypatch):
    api, c = _klient(db, monkeypatch)
    with patch("bank._hus_embed", return_value=_fake_embed):
        doc = c.post("/api/dokument", files={
            "fil": ("r.pdf", _pdf("Nefrokalsinose i 12 av 40"), "application/pdf")}).json()

    tekst = c.get(f"/api/dokument/{doc['id']}")
    assert "12 av 40" in tekst.json()["tekst"]

    fil = c.get(f"/api/dokument/{doc['id']}/fil")
    assert fil.status_code == 200
    assert fil.headers["content-type"] == "application/pdf"
    assert fil.content.startswith(b"%PDF")


def test_ukjent_dokument_gir_404_ikke_en_tom_fil(db, monkeypatch):
    api, c = _klient(db, monkeypatch)
    assert c.get("/api/dokument/finnesikke").status_code == 404
    assert c.get("/api/dokument/finnesikke/fil").status_code == 404
    assert c.delete("/api/dokument/finnesikke").status_code == 404


def test_dokumentlista_filtreres_paa_papir_via_query_ikke_sti(db, monkeypatch):
    """Regresjonsvakt for rutekollisjonen: /api/papir/{id:path} er registrert FØR
    dokument-rutene, så en sti-variant ville blitt slukt av papir-oppslaget."""
    _cache_papir(db)
    api, c = _klient(db, monkeypatch)
    with patch("bank._hus_embed", return_value=_fake_embed):
        c.post("/api/dokument", files={"fil": (
            "a.pdf", _pdf("doi:10.1111/jfd.70099", "en"), "application/pdf")})
        c.post("/api/dokument", files={"fil": (
            "b.pdf", _pdf("uten identifikator"), "application/pdf")})

    assert len(c.get("/api/dokumenter").json()["dokumenter"]) == 2
    kun = c.get("/api/dokumenter", params={"paper_id": "10.1111/jfd.70099"}).json()
    assert len(kun["dokumenter"]) == 1 and kun["dokumenter"][0]["filnavn"] == "a.pdf"

    # Sti-varianten finnes ikke, og skal ikke stille returnere et papir-oppslag i stedet.
    assert c.get("/api/papir/10.1111/jfd.70099/dokumenter").status_code == 404
