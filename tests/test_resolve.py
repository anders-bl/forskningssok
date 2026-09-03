"""Verifiserer resolve.py sin tre-veis gren (eksakt/tvetydig/ingen) direkte — flagget som
udekket av Six-Hats-sveipen 2026-09-04 (cli.py's egen docstring advarer om substreng-grenens
oppførsel på lange tekster, men ingen test verifiserte den). Testes generisk (strenger),
ikke mot forskningssok sitt PaperDossier-domene — resolve.py er selv domene-nøytral.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from resolve import normalize, resolve  # noqa: E402


def test_ett_eksakt_treff_vinner_umiddelbart():
    r = resolve("ola hansen", ["Ola Hansen", "Kari Hansen"], tekst=lambda x: x)
    assert r.eksakt == "Ola Hansen"
    assert r.kandidater == []
    assert not r.tvetydig
    assert not r.ingen_treff


def test_flere_eksakte_treff_er_tvetydig_ikke_forste_vinner():
    """REVIDERT-regresjonen fra modulens egen docstring (rollesok, 2026-08-03): to
    entiteter med identisk normalisert navn (navnekollisjon) skal ALDRI kortslutte til
    den første — det var en ekte, produksjonsverifisert bug. Kun de eksakte skal stå
    som kandidater, ikke blandet inn med delvise substreng-treff."""
    r = resolve("ola hansen", ["A::ola hansen", "B::ola hansen", "C::ola hansen jr"],
                tekst=lambda x: x.split("::")[1])
    assert r.eksakt is None
    assert r.tvetydig
    assert set(r.kandidater) == {"A::ola hansen", "B::ola hansen"}  # kun de EKSAKTE, ikke jr-substrengen


def test_substreng_treff_query_i_tekst():
    r = resolve("nephrocalcinosis", ["Nephrocalcinosis progression in Atlantic salmon"],
                tekst=lambda x: x)
    assert r.eksakt is None
    assert r.kandidater == ["Nephrocalcinosis progression in Atlantic salmon"]


def test_substreng_treff_tekst_i_query():
    """Motsatt retning av forrige — resolve() sjekker begge veier (q in t OR t in q)."""
    r = resolve("nephrocalcinosis salmon full setning", ["nephrocalcinosis salmon"],
                tekst=lambda x: x)
    assert r.kandidater == ["nephrocalcinosis salmon"]


def test_ingen_treff_er_tom_liste_ikke_unntak():
    r = resolve("noe helt urelatert xyzzy", ["Nephrocalcinosis i laks"], tekst=lambda x: x)
    assert r.eksakt is None
    assert r.kandidater == []
    assert r.ingen_treff
    assert not r.tvetydig


def test_normalize_case_og_whitespace():
    assert normalize("  Nephrocalcinosis SALMON  ") == "nephrocalcinosis salmon"


def test_normalize_kollapser_kun_ETT_par_ekstra_mellomrom():
    """Dokumenterer en reell begrensning, ikke en påstått garanti: normalize() bruker
    ett .replace('  ', ' ')-kall, som IKKE kollapser 3+ sammenhengende mellomrom fullt ut
    (ikke-overlappende enkeltpass). To spørringer som kun skiller seg i mengden ekstra
    mellomrom (f.eks. limt inn fra et sted med formatering) kan dermed normalisere til
    ULIKE strenger og ikke gjenkjennes som samme spørring — funnet ved karakterisering
    av funksjonen, ikke antatt. Se resolve.py:normalize()."""
    assert normalize("a   b") == "a  b"  # 3 mellomrom -> 2, IKKE 1 -- reell begrensning
    assert normalize("a  b") == "a b"    # 2 mellomrom -> 1, som forventet
