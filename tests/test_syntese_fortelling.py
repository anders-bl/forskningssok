"""Verifiserer syntese_fortelling.py — spesielt at kildetro-etterkontrollen faktisk
fanger opp en LLM som ikke fulgte instruksen i bygg_prompt(). Vi stoler ALDRI på selve
LLM-outputen (se syntese_fortelling.py sin modul-docstring), så testene her simulerer
"LLM-svar" som strengliteraler og sjekker at verifiser_kilder() gjør jobben mekanisk,
uten et ekte API-kall (suiten er nettverksfri, se CLAUDE.md § Testing).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bank  # noqa: E402
import syntese_fortelling  # noqa: E402
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
    """Samme test som dossier.py — etterkontrollen er identisk."""
    papirer = [{"id": 1, "tittel": "A"}, {"id": 2, "tittel": "B"}]
    tekst = "Fisken har X [#1]. Fisken har Y [#999]."
    renset, avvist = syntese_fortelling.verifiser_kilder(tekst, papirer)
    assert avvist == ["999"]
    assert "[#1]" in renset
    assert "[#999]" not in renset
    assert "KILDE IKKE VERIFISERT" in renset


def test_verifiser_kilder_beholder_alle_kjente_referanser():
    papirer = [{"id": 1}, {"id": 42}]
    tekst = "To funn [#1][#42] støtter dette."
    renset, avvist = syntese_fortelling.verifiser_kilder(tekst, papirer)
    assert avvist == []
    assert renset == tekst


def test_verifiser_kilder_ingen_referanser_gir_ingen_avvisning():
    renset, avvist = syntese_fortelling.verifiser_kilder("Ingen påstander her.", [{"id": 1}])
    assert avvist == []
    assert renset == "Ingen påstander her."


def test_bygg_prompt_baerer_id_for_hvert_papir_og_ber_om_fortelling():
    """Etterkontrollen (verifiser_kilder) er verdiløs hvis id-en ikke faktisk står i
    prompten LLM-en ser — denne testen er broen mellom de to.

    Forskjell fra dossier.py: prompten skal be om ÉN sammenhengende fortelling, ikke
    fem adskilte seksjoner."""
    papirer = [{"id": 7, "tittel": "Om linser", "abstract": "linsevev vokser i lag"}]
    prompt = syntese_fortelling.bygg_prompt("linse-skanning", papirer)
    assert "[#7]" in prompt
    assert "linsevev vokser i lag" in prompt
    # Skal be om fortelling, ikke seksjoner
    assert "ÉN sammenhengende fortelling" in prompt
    assert "sammenhengende fortelling" in prompt
    assert "Hvordan henger disse funnene sammen" in prompt
    # Skal IKKE nevne de fem dossier-seksjonene
    assert "Hard vitenskap" not in prompt
    assert "Hull i forskningen" not in prompt


def _importer_ollama_port():
    """Samme lat sys.path-import som syntese_fortelling.kall_llm() selv gjør — importert
    her KUN for å monkeypatche modulen FØR kall_llm() henter den samme (cachede) modulen
    fra sys.modules. Ingen nettverkskall skjer ved selve importen."""
    sys.path.insert(0, str(Path.home() / "prosjekter" / "silverbullet" / "ops"))
    import _ollama_port
    return _ollama_port


def test_kall_llm_ruter_til_lokal_ollama_uten_ai_proxy_url(monkeypatch):
    """kall_llm() sin dispatcher: AI_PROXY_URL usatt → dev-veien (Anders' Mac). Eksplisitt
    delenv, ikke stole på at testmiljøet tilfeldigvis mangler variabelen."""
    monkeypatch.delenv("AI_PROXY_URL", raising=False)
    op = _importer_ollama_port()
    monkeypatch.setattr(op, "sjekk_dommer", lambda model, **kw: None)
    monkeypatch.setattr(
        op, "kall_dommer",
        lambda model, prompt, **kw: {"message": {"content": "lokalt svar"}},
    )
    assert syntese_fortelling.kall_llm("noe prompt") == "lokalt svar"


def test_kall_llm_feiler_tydelig_naar_ollama_ikke_er_klar(monkeypatch):
    """Kontraktstest: en død/manglende lokal Ollama skal gi en lesbar RuntimeError her,
    ikke en stack trace fra httpx to nivåer ned — samme disiplin _ollama_port selv
    krever av enhver konsument."""
    monkeypatch.delenv("AI_PROXY_URL", raising=False)
    op = _importer_ollama_port()
    monkeypatch.setattr(op, "sjekk_dommer", lambda model, **kw: "Ollama utilgjengelig (test)")
    with pytest.raises(RuntimeError, match="ikke klar"):
        syntese_fortelling.kall_llm("noe prompt")


def test_kall_llm_returnerer_meldingsinnhold_ved_suksess(monkeypatch):
    """kall_llm() skal plukke ut ["message"]["content"] fra _ollama_port sitt rå
    JSON-svar — samme kontrakt evaluer.py::_hus_dommer allerede bruker."""
    monkeypatch.delenv("AI_PROXY_URL", raising=False)
    op = _importer_ollama_port()
    monkeypatch.setattr(op, "sjekk_dommer", lambda model, **kw: None)
    monkeypatch.setattr(
        op, "kall_dommer",
        lambda model, prompt, **kw: {"message": {"content": "en ekte syntese-fortelling"}},
    )
    assert syntese_fortelling.kall_llm("noe prompt") == "en ekte syntese-fortelling"


class _FalskSvar:
    """Samme fake-respons-mønster som test_verifiser.py — syntese_fortelling.py sin
    ai-proxy-vei gjenbruker verifiser.py sin kall-stil, så testen gjenbruker samme
    teststil."""

    def __init__(self, status=200, data=None, tekst=""):
        self.status_code = status
        self._data = data if data is not None else {}
        self.text = tekst

    def json(self):
        return self._data


def test_kall_llm_ruter_til_ai_proxy_naar_url_er_satt(monkeypatch):
    """kall_llm() sin dispatcher: AI_PROXY_URL satt → prod-veien, ALDRI lokal Ollama —
    samme "hvilket miljø er vi i"-signal som verifiser.py::tilgjengelig()."""
    monkeypatch.setenv("AI_PROXY_URL", "http://ai-proxy:8000")

    def falsk_post(url, json, timeout):
        assert url == "http://ai-proxy:8000/complete"
        assert json["role"] == syntese_fortelling.AI_PROXY_ROLLE
        assert json["wiki_id"] == syntese_fortelling.AI_PROXY_WIKI_ID
        assert json["messages"] == [{"role": "user", "content": "noe prompt"}]
        return _FalskSvar(data={"content": "prod-svar fra ai-proxy"})

    assert syntese_fortelling._kall_llm_ai_proxy("noe prompt", post_fn=falsk_post) == "prod-svar fra ai-proxy"


def test_kall_llm_ai_proxy_feil_status_gir_lesbar_runtimeerror(monkeypatch):
    monkeypatch.setenv("AI_PROXY_URL", "http://ai-proxy:8000")
    with pytest.raises(RuntimeError, match=r"feiler \(503\)"):
        syntese_fortelling._kall_llm_ai_proxy(
            "noe prompt",
            post_fn=lambda *a, **k: _FalskSvar(status=503, tekst="ai-proxy nede"),
        )


def test_hent_kandidater_slaar_sammen_emne_og_utstyr_uten_dubletter(tmp_path, monkeypatch):
    db_path = tmp_path / "cache.db"
    _lagre(db_path, tittel="Om laksens nyrer", doi="10.1/a")
    _lagre(db_path, tittel="Ultralydprobe for akvakultur", doi="10.1/b")

    monkeypatch.setitem(syntese_fortelling.domeneprofil.PROFIL, "sok_utstyr", "ultralydprobe")

    kandidater = syntese_fortelling.hent_kandidater("nyrer", db_path)
    titler = {p["tittel"] for p in kandidater}
    assert "Om laksens nyrer" in titler
    assert "Ultralydprobe for akvakultur" in titler
    # ingen id dukker opp to ganger selv om begge søkene kunne truffet samme papir
    ider = [p["id"] for p in kandidater]
    assert len(ider) == len(set(ider))


def test_hent_kandidater_kapper_ved_maks_kilder(tmp_path):
    """Målt live 2026-09-11: et to-ords emne kan treffe hundrevis av løst relaterte
    cachede papirer (hent_fra_cache gjør per-ord OR uten rangering) — uten en kapp
    sprenger et LLM-kall konteksten stille. Se MAKS_KILDER sin egen kommentar."""
    db_path = tmp_path / "cache.db"
    for i in range(syntese_fortelling.MAKS_KILDER + 10):
        _lagre(db_path, tittel=f"Papir om laks {i}", doi=f"10.1/{i}")

    kandidater = syntese_fortelling.hent_kandidater("laks", db_path)
    assert len(kandidater) == syntese_fortelling.MAKS_KILDER


def test_hent_kandidater_uten_sok_utstyr_i_profilen(tmp_path, monkeypatch):
    """sok_utstyr er valgfritt (i motsetning til sok_standard) — fravær skal IKKE krasje,
    kun stille droppe utvidelsen."""
    db_path = tmp_path / "cache.db"
    _lagre(db_path, tittel="Om laksens nyrer")
    monkeypatch.delitem(syntese_fortelling.domeneprofil.PROFIL, "sok_utstyr", raising=False)

    kandidater = syntese_fortelling.hent_kandidater("nyrer", db_path)
    assert len(kandidater) == 1


def test_lag_syntese_fortelling_ingen_kilder_gir_aerlig_beskjed(tmp_path):
    ut = syntese_fortelling.lag_syntese_fortelling("noe som ikke finnes", tmp_path / "finnes-ikke.db")
    assert "Ingen kilder i cachen" in ut
    assert "--oppdater" in ut


def test_lag_syntese_fortelling_advarer_ved_konfabulert_referanse(tmp_path, monkeypatch):
    db_path = tmp_path / "cache.db"
    _lagre(db_path, tittel="Ekte papir")

    def falsk_llm(_prompt):
        [p] = syntese_fortelling.hent_fra_cache("Ekte", db_path)
        return f"Et ekte funn [#{p['id']}]. Et diktet funn [#99999]."

    monkeypatch.setattr(syntese_fortelling, "kall_llm", falsk_llm)

    ut = syntese_fortelling.lag_syntese_fortelling("Ekte", db_path)
    assert "ADVARSEL" in ut
    assert "99999" in ut
    assert "[KILDE IKKE VERIFISERT" in ut
    assert "## Kildeliste" in ut
