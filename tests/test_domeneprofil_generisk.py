"""Beviser at repoet er domeneagnostisk i KODE, ikke bare i navn.

README har siden omdøpingen 2026-09-02 sagt at «arkitekturen var alt ~90 % domeneagnostisk»
og samtidig at instansen «er generisk i navn før den er generisk i kode». Denne fila er
prøven som avgjør hvilken av de to påstandene som stemmer i dag.

Metoden er det som betyr noe: å lese koden og ikke se ordet «laks» beviser ingenting om
hva den GJØR. Testene her laster derfor en profil fra et fagfelt som deler null vokabular
med lakseoppdrett (bygningsakustikk, tests/fixtures/annetfagfelt.toml) og sjekker at
fiske-oppførselen faktisk FORSVINNER — at et laksepapir ikke lenger er domene-nært, at
akse-navnene skifter, og at merketeksten i eksporterte rapporter følger med. Overlever en
fiske-oppførsel profilbyttet, sitter det en hardkodet antakelse igjen et sted.
"""
import importlib
import sys
from pathlib import Path

import pytest

ROT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROT))
ANNET = ROT / "tests" / "fixtures" / "annetfagfelt.toml"


@pytest.fixture
def akustikk(monkeypatch):
    """Laster hele modulkjeden på nytt under en annen profil. PROFIL bindes ved import
    (som paths.DB), så en env-var satt etterpå ville ikke truffet noe — samme felle
    test_api_skriv.py sin moduldocstring beskriver for db_path."""
    monkeypatch.setenv("FORSKNINGSSOK_PROFIL", str(ANNET))
    import domeneprofil
    import ranking
    import scoping
    moduler = [importlib.reload(m) for m in (domeneprofil, ranking, scoping)]
    yield moduler
    # Tilbake til standardprofilen — ellers ville rekkefølgen av testfiler avgjort
    # hvilket fagfelt resten av suiten kjørte under.
    monkeypatch.delenv("FORSKNINGSSOK_PROFIL", raising=False)
    for m in (domeneprofil, ranking, scoping):
        importlib.reload(m)


LAKSETEKST = "Nephrocalcinosis in farmed Atlantic salmon smolt after seawater transfer"
AKUSTIKKTEKST = "Reverberation time and speech intelligibility in a classroom"


def test_standardprofilen_er_fiskehelse():
    import domeneprofil
    importlib.reload(domeneprofil)
    assert "lakseoppdrett" in domeneprofil.NAVN.lower()
    assert domeneprofil.arts_naer_tekst(LAKSETEKST) is True


def test_profilbytte_fjerner_fiske_oppfoerselen(akustikk):
    dp, _, _ = akustikk
    assert dp.NAVN == "Bygningsakustikk"
    # Selve prøven: et laksepapir må IKKE lenger regnes som nært målobjektet.
    assert dp.arts_naer_tekst(LAKSETEKST) is False
    assert dp.arts_naer_tekst(AKUSTIKKTEKST) is True


def test_domene_naerhet_folger_profilen(akustikk):
    dp, _, _ = akustikk
    assert dp.domene_naer_tekst("Havforskningsinstituttet · Journal of Fish Diseases") is False
    assert dp.domene_naer_tekst("SINTEF · Applied Acoustics") is True


def test_aksene_folger_profilen(akustikk):
    _, _, scoping = akustikk
    dekning = scoping.akse_dekning("reverberation and rt60 decay in the room")
    assert set(dekning) == {"Etterklang", "Taleforståelse", "Absorpsjon"}
    assert dekning["Etterklang"] == 1.0
    assert dekning["Absorpsjon"] == 0.0


def test_kollisjonsfrasen_er_profilens_sak_ikke_kodens(akustikk):
    """«salmon calcitonin» var hardkodet i Python. Hvert fagfelt har sine egne homonymer —
    her «room temperature», som er en målebetingelse og ikke en bygningskontekst. Virker
    mekanismen generisk, skal DEN strippes, ikke laksefrasen."""
    dp, _, _ = akustikk
    assert dp.arts_naer_tekst("Measured at room temperature in a water bath") is False
    assert dp.arts_naer_tekst("Measured at room temperature in a classroom") is True


def test_standardprofilens_egen_kollisjon_virker_fortsatt():
    import domeneprofil
    importlib.reload(domeneprofil)
    # Pediatrisk CYP24A1-funn, fanget live 2026-09-02: «salmon calcitonin» er et
    # legemiddelnavn, ikke en art.
    assert domeneprofil.arts_naer_tekst("Effect of salmon calcitonin on hypercalcaemia") is False


def test_ranking_bander_etter_profilen(akustikk):
    _, ranking, _ = akustikk
    from schemas import PaperDossier
    laks = PaperDossier(pmid="1", doi=None, tittel=LAKSETEKST, forfattere="Havforskningsinstituttet",
                        tidsskrift="Journal of Fish Diseases", aar=2026, abstract=LAKSETEKST,
                        siteringstall=99, open_access=False, kilde_url="u")
    rom = PaperDossier(pmid="2", doi=None, tittel=AKUSTIKKTEKST, forfattere="SINTEF",
                       tidsskrift="Applied Acoustics", aar=2020, abstract=AKUSTIKKTEKST,
                       siteringstall=1, open_access=False, kilde_url="u")
    assert ranking.domene_naer(laks) is False
    assert ranking.domene_naer(rom) is True
    # Båndet går FØR ferskhet/siteringer: akustikkpapiret er eldre og mindre sitert,
    # og skal likevel ligge først under denne profilen.
    assert [p.pmid for p in ranking.ranger([laks, rom])] == ["2", "1"]


def test_frontend_kontrakten_baerer_merkene(akustikk):
    dp, _, _ = akustikk
    f = dp.for_frontend()
    assert f["domene_merke"] == "◆" and f["art_merke"] == "⚠ rom?"
    assert "bygg eller rom" in f["art_merke_betyr"]
    # Termlistene skal IKKE sendes til klienten — se for_frontend() sin docstring.
    assert "termer" not in f and "fagmiljoer" not in f


def test_manglende_profil_feiler_hoyt_ikke_stille(tmp_path):
    """En profil som ikke finnes må stoppe oppstarten med stien i feilmeldingen. Stille
    tomme lister ville sett ut som «ingen treff i dette fagfeltet» i hver eneste flate."""
    import domeneprofil
    with pytest.raises(RuntimeError, match="finnes ikke"):
        domeneprofil.last_profil(tmp_path / "borte.toml")


def test_ufullstendig_profil_navngir_feltene_som_mangler(tmp_path):
    import domeneprofil
    halv = tmp_path / "halv.toml"
    halv.write_text('navn = "Halv"\n[domene]\nfagmiljoer = ["x"]\n', encoding="utf-8")
    with pytest.raises(RuntimeError) as e:
        domeneprofil.last_profil(halv)
    for felt in ("kort", "sok_standard", "domene.fagtidsskrifter", "art", "akser"):
        assert felt in str(e.value)


def test_rapportens_artsvarsel_folger_profilen(akustikk):
    """Merketeksten i en EKSPORTERT rapport er den som følger med ut av huset. Sto den
    hardkodet, ville en bruker i et annet fagfelt delt en PDF som påstår feil fagfelt."""
    import rapport
    importlib.reload(rapport)
    blokker = rapport.kildesamling_blokker([{
        "tittel": LAKSETEKST, "abstract": LAKSETEKST, "forfattere": "A",
        "tidsskrift": "J", "aar": 2026, "siteringstall": 0, "open_access": 0, "doi": None,
    }])
    tekst = rapport.til_markdown(blokker)
    assert "rom?" in tekst and "bygg eller rom" in tekst
    assert "laks" not in tekst.lower()
    importlib.reload(rapport)


def test_ingen_python_modul_navngir_fagfeltet_i_kjorende_kode():
    """Grovkornet, men den fanger den ekte regresjonen: at noen skriver «laks» inn i en
    strengliteral igjen. Docstrings og kommentarer er UNNTATT med vilje — de er
    institusjonell hukommelse om HVORFOR mekanismen finnes, og skal nevne det konkrete
    tilfellet den ble bygget for."""
    import ast
    fagord = ("laks", "salmon", "oppdrett", "nephrocalcin", "smolt")
    funn = []
    for fil in ROT.glob("*.py"):
        tre = ast.parse(fil.read_text(encoding="utf-8"))
        docstrings = {d for d in (ast.get_docstring(n, clean=False) for n in ast.walk(tre)
                                  if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef))) if d}
        for node in ast.walk(tre):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if node.value in docstrings:
                continue
            lav = node.value.lower()
            if any(o in lav for o in fagord):
                funn.append(f"{fil.name}:{node.lineno}: {node.value[:60]}")
    assert funn == [], "fagfelt-spesifikk tekst i kjørende kode:\n" + "\n".join(funn)
