"""Verifiserer ADR-013-pending-prinsippet anvendt på papirer: et FERSKT, domene-nært,
lite-sitert papir skal ALDRI begraves under et eldre, høyt-sitert, domene-fjernt papir —
og domene-nærhet slår aldri et manglende abstract (band 2 sjekker abstract KUN innenfor
samme domene-status).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ranking import domene_naer, ranger  # noqa: E402
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
