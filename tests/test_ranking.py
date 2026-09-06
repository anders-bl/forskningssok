"""Verifiserer ADR-013-pending-prinsippet anvendt på papirer: et FERSKT, domene-nært,
lite-sitert papir skal ALDRI begraves under et eldre, høyt-sitert, domene-fjernt papir —
og domene-nærhet slår aldri et manglende abstract (band 2 sjekker abstract KUN innenfor
samme domene-status).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ranking import arts_naer, domene_naer, ranger  # noqa: E402
from schemas import PaperDossier  # noqa: E402


def _p(**kw) -> PaperDossier:
    base = dict(pmid="1", doi=None, tittel="t", forfattere="", tidsskrift="",
                aar=2020, abstract="abstract her", siteringstall=0, open_access=False,
                kilde_url="https://example.org")
    base.update(kw)
    return PaperDossier(**base)


def test_domene_naer_matcher_norske_fagmiljoer_og_tidsskrifter():
    havforskning = _p(forfattere="Ola Nordmann", tidsskrift="Havforskningsinstituttet-rapport")
    fagtidsskrift = _p(forfattere="Jane Doe", tidsskrift="Journal of Fish Diseases")
    urelatert = _p(forfattere="Jane Doe, MIT", tidsskrift="Nature")
    assert domene_naer(havforskning)
    assert domene_naer(fagtidsskrift)
    assert not domene_naer(urelatert)


def test_ferskt_domenenaert_paper_slaar_eldre_hoeyt_sitert_utenfor_domenet():
    """Kjernen i ADR-013-overføringen: siteringstall alene ville rangert MIT-papiret
    (50 sitater) over Havforskningsinstituttets 2026-funn (0 sitater) — banding på
    domene-nærhet FØRST forhindrer nettopp det."""
    ferskt_domenenaert = _p(tittel="A", forfattere="Havforskningsinstituttet", aar=2026, siteringstall=0)
    gammelt_hoeyt_sitert_urelatert = _p(tittel="B", forfattere="MIT", tidsskrift="Nature",
                                         aar=2015, siteringstall=50)
    ut = ranger([gammelt_hoeyt_sitert_urelatert, ferskt_domenenaert])
    assert [p.tittel for p in ut] == ["A", "B"]


def test_manglende_abstract_rangeres_lavere_innenfor_samme_domenebaand():
    med_abstract = _p(tittel="med", forfattere="NMBU", abstract="finnes")
    uten_abstract = _p(tittel="uten", forfattere="NMBU", abstract="")
    ut = ranger([uten_abstract, med_abstract])
    assert [p.tittel for p in ut] == ["med", "uten"]


def test_nyere_fremfor_eldre_innenfor_samme_baand():
    eldre = _p(tittel="eldre", aar=2018, siteringstall=10)
    nyere = _p(tittel="nyere", aar=2026, siteringstall=1)
    ut = ranger([eldre, nyere])
    assert [p.tittel for p in ut] == ["nyere", "eldre"]


# ---------- Species-trap-motvekt (Svart hatt-funn 2026-09-02) ----------

def test_arts_naer_matcher_maalart_i_tittel_eller_abstract():
    laks = _p(tittel="Nephrocalcinosis in Atlantic salmon", abstract="")
    menneske = _p(tittel="Nephrocalcinosis and CYP24A1 variant", abstract="a case report")
    assert arts_naer(laks)
    assert not arts_naer(menneske)


def test_ekte_species_trap_caset_menneskefunn_rangeres_under_fiskefunn_utenfor_domenebaand():
    """Det faktiske caset observert live 2026-09-02: et menneske-CYP24A1-funn UTEN norsk
    fagmiljø-tilknytning skal ALDRI rangeres over et fiskefunn UTEN norsk fagmiljø-
    tilknytning, selv om begge er utenfor domene-båndet og menneskefunnet har flere
    siteringer/er ferskere."""
    menneske = _p(tittel="CYP24A1 pathogenic variant nephrocalcinosis", forfattere="Someone, MIT",
                   tidsskrift="Journal of rare diseases", aar=2026, siteringstall=5)
    fisk = _p(tittel="Nephrocalcinosis in farmed Atlantic salmon smolt", forfattere="Someone Else, MIT",
              tidsskrift="Nature", aar=2020, siteringstall=1)
    ut = ranger([menneske, fisk])
    assert [p.tittel for p in ut] == [fisk.tittel, menneske.tittel]


def test_arts_naer_filtrerer_aldri_bort_kun_flagger():
    menneske = _p(tittel="Ukjent art-tittel", abstract="")
    assert ranger([menneske]) == [menneske]  # forblir i lista


# ---------- Tittel-dekning innenfor båndet (målt svakhet 2026-09-05/06) ----------

def test_tittel_dekning_er_andel_sokeord_i_tittelen():
    from ranking import tittel_dekning
    assert tittel_dekning("nephrocalcinosis salmon", "Nephrocalcinosis in farmed Atlantic salmon") == 1.0
    assert tittel_dekning("nephrocalcinosis salmon", "Urocystolithiasis in farmed Atlantic salmon") == 0.5
    assert tittel_dekning("nephrocalcinosis salmon", "Algal bloom at a Norwegian farm") == 0.0
    assert tittel_dekning("", "hva som helst") == 0.0


def test_tittel_dekning_godtar_boyning_uten_stemmer():
    """«salmonids»/«diagnostics» i spørringen skal dekke «salmonid»/«diagnostic» i tittelen ,
    og motsatt, uten en språkspesifikk stemmer (profilen kan være norsk)."""
    from ranking import tittel_dekning
    assert tittel_dekning("salmonids", "Nephrocalcinosis in farmed salmonid populations") == 1.0
    assert tittel_dekning("diagnostic", "Ultrasound diagnostics in fish") == 1.0


def test_sokeordene_i_tittelen_slaar_ferskhet_innenfor_samme_baand():
    """Selve funnet: to ferske papirer som bare NEVNER søkeordet i abstractet lå over eldre
    papirer med søkeordet i tittelen, fordi (-år) avgjorde alene når båndet var mettet."""
    ferskt_tangentielt = _p(tittel="Urocystolithiasis in farmed Atlantic salmon", forfattere="NMBU",
                            abstract="nephrocalcinosis has received attention", aar=2026)
    eldre_sentralt = _p(tittel="Nephrocalcinosis in farmed Atlantic salmon", forfattere="NMBU",
                        abstract="salmon smolt", aar=2022)
    ut = ranger([ferskt_tangentielt, eldre_sentralt], query="nephrocalcinosis salmon")
    assert [p.tittel for p in ut] == [eldre_sentralt.tittel, ferskt_tangentielt.tittel]


def test_uten_query_er_rekkefolgen_uendret_ferskhet_forst():
    """Utforskning (OpenAlex-emne) og andre kallere uten tekstspørring skal få nøyaktig
    den gamle (ferskhet, siteringer)-rekkefølgen, kontrakten for dem er ikke endret."""
    ferskt = _p(tittel="Urocystolithiasis in salmon", forfattere="NMBU", abstract="salmon", aar=2026)
    eldre = _p(tittel="Nephrocalcinosis in salmon", forfattere="NMBU", abstract="salmon", aar=2022)
    assert [p.tittel for p in ranger([eldre, ferskt])] == [ferskt.tittel, eldre.tittel]


def test_tittel_dekning_krysser_aldri_et_baand():
    """Et domene-FJERNT papir med alle søkeordene i tittelen skal fortsatt ligge under et
    domene-nært uten, båndet er fortsatt øverste dommer, dekningen kun innenfor det."""
    fjernt_full_tittel = _p(tittel="Nephrocalcinosis in salmon", forfattere="MIT", tidsskrift="Nature",
                            abstract="salmon", aar=2026)
    naert_uten = _p(tittel="Kidney mineral deposits", forfattere="NMBU", abstract="salmon", aar=2020)
    ut = ranger([fjernt_full_tittel, naert_uten], query="nephrocalcinosis salmon")
    assert [p.tittel for p in ut] == [naert_uten.tittel, fjernt_full_tittel.tittel]
