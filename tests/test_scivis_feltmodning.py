"""Sjekker at SciVis-tidslinjen skiller andel fra korpusvolum."""

from __future__ import annotations

from evidensniva import NIVAAER
from scivis_feltmodning import bygg_html, normaliser_andeler, tegn_svg


def _lag() -> dict[int, dict[str, dict[str, int]]]:
    lag: dict[int, dict[str, dict[str, int]]] = {}
    for aar in (2020, 2021):
        tomt_baand = {
            navn: {"nlm": 0, "monster": 0, "ukjent": 0} for navn, _ in NIVAAER
        }
        tomt_baand["Ukjent design"] = {"nlm": 0, "monster": 0, "ukjent": 0}
        if aar == 2020:
            tomt_baand["Systematisk oversikt/meta-analyse"].update(
                {"nlm": 1, "monster": 1}
            )
            tomt_baand["Ukjent design"]["ukjent"] = 2
        else:
            tomt_baand["Systematisk oversikt/meta-analyse"]["nlm"] = 1
        lag[aar] = tomt_baand
    return lag


def test_normaliser_andeler_gjor_hvert_ar_til_hundre_uten_a_miste_kildelag():
    andeler = normaliser_andeler(_lag())

    assert sum(
        verdi for band in andeler[2020].values() for verdi in band.values()
    ) == 100
    assert andeler[2020]["Systematisk oversikt/meta-analyse"] == {
        "nlm": 25,
        "monster": 25,
        "ukjent": 0,
    }
    assert sum(
        verdi for band in andeler[2021].values() for verdi in band.values()
    ) == 100


def test_andels_svg_beholder_antall_i_hovertekst_og_n_pa_aar():
    svg, maks = tegn_svg(_lag(), andel=True)

    assert maks == 100
    assert ">100%</text>" in svg
    assert "2020 -- Systematisk oversikt/meta-analyse (nlm): 1 av 4 (25.0%)" in svg
    assert "2020: N=4" in svg


def test_html_gjor_andel_til_standard_og_viser_aarsgrunnlag():
    side = bygg_html(_lag(), "Evidensmerker over tid", 5)

    assert 'aria-pressed="true" aria-controls="andel-visning"' in side
    assert 'id="antall-visning" class="visning" hidden' in side
    assert "Se antall cachede papirer per aar" in side
    assert "ikke om et fagfelt faktisk modnes" in side
    assert side.count("</body>") == 1
    assert side.count("</html>") == 1
