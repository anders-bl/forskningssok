"""Verifiserer dossier.py — spesielt at kildetro-etterkontrollen faktisk fanger opp
en LLM som ikke fulgte instruksen i bygg_prompt(). Vi stoler ALDRI på selve
LLM-outputen (se dossier.py sin modul-docstring), så testene her simulerer "LLM-svar"
som strengliteraler og sjekker at verifiser_kilder() gjør jobben mekanisk, uten et
ekte API-kall (suiten er nettverksfri, se CLAUDE.md § Testing).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bank  # noqa: E402
import dossier  # noqa: E402
from schemas import PaperDossier  # noqa: E402


def _lagre(db_path, **felter):
    """Samme mønster som test_ai_assistent.py::TestHentFraCache._lagre — bygger cachen
    via den EKTE skjema-oppretteren (bank.lagre), ikke en hånd-skrevet CREATE TABLE."""
    felter.setdefault("pmid", None)
    felter.setdefault("doi", "10.1234/test")
    felter.setdefault("forfattere", "Testesen T")
    felter.setdefault("tidsskrift", "Test Journal")
    felter.setdefault("aar", 2024)
    felter.setdefault("abstract", "en testabstract")
    felter.setdefault("siteringstall", 0)
    felter.setdefault("open_access", False)
    felter.setdefault("kilde_url", "https://example.org/test")
    bank.lagre([PaperDossier(**felter)], embed_fn=lambda tekster: [[0.0] * 1024 for _ in tekster],
               db_path=db_path)


def test_verifiser_kilder_fjerner_ukjent_id():
    papirer = [{"id": 1, "tittel": "A"}, {"id": 2, "tittel": "B"}]
    tekst = "Fisken har X [#1]. Fisken har Y [#999]."
    renset, avvist = dossier.verifiser_kilder(tekst, papirer)
    assert avvist == ["999"]
    assert "[#1]" in renset
    assert "[#999]" not in renset
    assert "KILDE IKKE VERIFISERT" in renset


def test_verifiser_kilder_beholder_alle_kjente_referanser():
    papirer = [{"id": 1}, {"id": 42}]
    tekst = "To funn [#1][#42] støtter dette."
    renset, avvist = dossier.verifiser_kilder(tekst, papirer)
    assert avvist == []
    assert renset == tekst


def test_verifiser_kilder_ingen_referanser_gir_ingen_avvisning():
    renset, avvist = dossier.verifiser_kilder("Ingen påstander her.", [{"id": 1}])
    assert avvist == []
    assert renset == "Ingen påstander her."


def test_bygg_prompt_baerer_id_for_hvert_papir():
    """Etterkontrollen (verifiser_kilder) er verdiløs hvis id-en ikke faktisk står i
    prompten LLM-en ser — denne testen er broen mellom de to."""
    papirer = [{"id": 7, "tittel": "Om linser", "abstract": "linsevev vokser i lag"}]
    prompt = dossier.bygg_prompt("linse-skanning", papirer)
    assert "[#7]" in prompt
    assert "linsevev vokser i lag" in prompt
    for seksjon in dossier.SEKSJONER:
        assert seksjon in prompt


def test_kall_llm_er_ikke_koblet_til_ennaa():
    """Kontraktstest: kall_llm() SKAL feile høylytt til en ekte nøkkel er koblet til —
    en stille fallback (f.eks. tom streng) ville gjort lag_dossier() vanskelig å skille
    fra en fungerende, men tom, generering."""
    import pytest
    with pytest.raises(NotImplementedError):
        dossier.kall_llm("noe prompt")


def test_hent_kandidater_slaar_sammen_emne_og_utstyr_uten_dubletter(tmp_path, monkeypatch):
    db_path = tmp_path / "cache.db"
    _lagre(db_path, tittel="Om laksens nyrer", doi="10.1/a")
    _lagre(db_path, tittel="Ultralydprobe for akvakultur", doi="10.1/b")

    monkeypatch.setitem(dossier.domeneprofil.PROFIL, "sok_utstyr", "ultralydprobe")

    kandidater = dossier.hent_kandidater("nyrer", db_path)
    titler = {p["tittel"] for p in kandidater}
    assert "Om laksens nyrer" in titler
    assert "Ultralydprobe for akvakultur" in titler
    # ingen id dukker opp to ganger selv om begge søkene kunne truffet samme papir
    ider = [p["id"] for p in kandidater]
    assert len(ider) == len(set(ider))


def test_hent_kandidater_uten_sok_utstyr_i_profilen(tmp_path, monkeypatch):
    """sok_utstyr er valgfritt (i motsetning til sok_standard) — fravær skal IKKE krasje,
    kun stille droppe utvidelsen."""
    db_path = tmp_path / "cache.db"
    _lagre(db_path, tittel="Om laksens nyrer")
    monkeypatch.delitem(dossier.domeneprofil.PROFIL, "sok_utstyr", raising=False)

    kandidater = dossier.hent_kandidater("nyrer", db_path)
    assert len(kandidater) == 1


def test_lag_dossier_ingen_kilder_gir_aerlig_beskjed(tmp_path):
    ut = dossier.lag_dossier("noe som ikke finnes", tmp_path / "finnes-ikke.db")
    assert "Ingen kilder i cachen" in ut
    assert "--oppdater" in ut


def test_lag_dossier_advarer_ved_konfabulert_referanse(tmp_path, monkeypatch):
    db_path = tmp_path / "cache.db"
    _lagre(db_path, tittel="Ekte papir")

    def falsk_llm(_prompt):
        [p] = dossier.hent_fra_cache("Ekte", db_path)
        return f"Et ekte funn [#{p['id']}]. Et diktet funn [#99999]."

    monkeypatch.setattr(dossier, "kall_llm", falsk_llm)

    ut = dossier.lag_dossier("Ekte", db_path)
    assert "ADVARSEL" in ut
    assert "99999" in ut
    assert "[KILDE IKKE VERIFISERT" in ut
    assert "## Kildeliste" in ut
