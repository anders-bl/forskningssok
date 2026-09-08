"""Verifiserer dokumenttype.py — sjanger-klassifisering, se moduldocstring for aksen
mot evidensniva.py (studiedesign) den bevisst IKKE overlapper med."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dokumenttype as dt  # noqa: E402


def test_institusjonell_rapport_gjenkjennes():
    assert dt.fra_nva("ReportResearch", "Fiskehelserapporten 2020") == dt.INSTITUSJONELL_RAPPORT
    assert dt.fra_nva("ReportWorkingPaper", "Kompetanseheving skjellpatologi") == dt.INSTITUSJONELL_RAPPORT


def test_avhandling_gjenkjennes():
    assert dt.fra_nva("DegreeMaster", "En mastergrad om noe") == dt.AVHANDLING
    assert dt.fra_nva("DegreePhd", "En avhandling") == dt.AVHANDLING


def test_formidling_heuristikk_overstyrer_nva_feilklassifisering():
    """Den faktiske feilen som motiverte modulen (2026-09-08, målt ni-rapport-stikkprøve):
    NVA klassifiserer skoleformidling som ReportWorkingPaper — SAMME bøtte som ekte
    institusjonelle arbeidsnotater. Heuristikken skal overstyre NVA sitt svar her, ikke
    bare kjøre når NVA-feltet mangler."""
    assert dt.fra_nva("ReportWorkingPaper",
                      "Elevrapport: Marine dager ved Sandgotna ungdomsskole") == dt.FORMIDLING
    assert dt.fra_nva("ReportResearch",
                      "Elevrapport for prosjektet Livet i fjæra") == dt.FORMIDLING


def test_ukjent_nva_type_gir_ukjent_ikke_gjettet_kategori():
    assert dt.fra_nva("Dataset", "Et datasett") == dt.UKJENT
    assert dt.fra_nva(None, "Ingen NVA-type") == dt.UKJENT
    assert dt.fra_nva("", "Tom streng") == dt.UKJENT


def test_nlm_kart_journal_artikkel():
    assert dt.fra_nlm(("Journal Article",)) == dt.JOURNAL_ARTIKKEL
    assert dt.fra_nlm(("Case Reports",)) == dt.JOURNAL_ARTIKKEL


def test_nlm_ingen_treff_gir_ukjent():
    assert dt.fra_nlm(()) == dt.UKJENT
    assert dt.fra_nlm(("Editorial",)) == dt.UKJENT
