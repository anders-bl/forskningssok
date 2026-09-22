"""Verifiserer syntese_fortelling.py — spesielt at kildetro-etterkontrollen faktisk
fanger opp en LLM som ikke fulgte instruksen i bygg_prompt(). Vi stoler ALDRI på selve
LLM-outputen (se syntese_fortelling.py sin modul-docstring), så testene her simulerer
"LLM-svar" som strengliteraler og sjekker at verifiser_kilder() gjør jobben mekanisk,
uten et ekte API-kall (suiten er nettverksfri, se CLAUDE.md § Testing).
"""
import sys
import types
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


def test_verifiser_kilder_fanger_doi_eller_url_som_id():
    renset, avvist = syntese_fortelling.verifiser_kilder(
        "Påstand [#https://example.org/paper].", [{"id": 1}]
    )
    assert avvist == ["https://example.org/paper"]
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


def test_evaluer_kvalitet_skiller_kildehull_fra_dekket_setning():
    papirer = [{"id": 1, "kilde_url": "https://example.org/1"},
               {"id": 2, "kilde_url": ""}]
    tekst = (
        "Dette er dokumentert [#1]. "
        "Dette mangler dekning. "
        "Ingen kilder i utvalget dekker dette.\n"
        "---\n## Kildeliste (2 kilder)\n[#1] Kilde"
    )

    måling = syntese_fortelling.evaluer_kvalitet(tekst, papirer)

    assert måling["faktiske_enheter"] == 3
    assert måling["dekket_enheter"] == 2
    assert måling["mangler_kilde_enheter"] == 1
    assert måling["eksplisitte_kildehull"] == 1
    assert måling["sitatdekning"] == pytest.approx(2 / 3)
    assert måling["brukte_kilder"] == 1
    assert måling["ubrukte_kilder"] == 1
    assert måling["lenkedekning"] == pytest.approx(1 / 2)


def test_evaluer_kvalitet_fanger_ukjent_kilde_id():
    måling = syntese_fortelling.evaluer_kvalitet(
        "Påstand [#999].", [{"id": 1, "kilde_url": "https://example.org/1"}]
    )

    assert måling["ugyldige_kilde_ider"] == ["999"]
    assert måling["sitatdekning"] == 0.0


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


def test_bygg_prompt_skiller_direkte_kandidater_fra_analogier():
    direkte = {"id": 1, "tittel": "Atlantic salmon kidney", "abstract": "salmon fish",
               "forfattere": "", "tidsskrift": "Journal of Fish Diseases"}
    analogi = {"id": 2, "tittel": "Human kidney disease", "abstract": "human patients",
               "forfattere": "", "tidsskrift": "Clinical Medicine"}

    prompt = syntese_fortelling.bygg_prompt("kidney salmon", [direkte, analogi])

    kilder = prompt.split("KILDER:\n", 1)[1]
    assert kilder.index("DIREKTE_KANDIDATER") < kilder.index("ANALOGI_ELLER_BAKGRUNN")
    assert "kan ikke brukes som direkte evidens" in prompt
    assert "DIREKTE_KANDIDAT" in prompt
    assert "Ikke skriv en udokumentert faktasetning først" in prompt


def _importer_ollama_port():
    """Injiserer en fake `_ollama_port`-modul i sys.modules FØR syntese_fortelling.kall_llm()
    gjør sin egen lazy `import _ollama_port` — samme sys.modules-cache-mekanisme som den
    opprinnelige sys.path-varianten mot silverbullet/ops/ stolte på, men uten avhengighet til
    at silverbullet-repoet faktisk er checket ut ved siden av. Ekte fil finnes kun på Anders'
    Mac; CI checker bare ut DETTE repoet, derfor ModuleNotFoundError der (2026-09-11, fanget
    av CI selv — samme bug-klasse som _hus_embed i test_ai_assistent.py, se den kommentaren).
    Testene bryr seg uansett kun om at kall_llm() kaller riktige funksjonsnavn på modulen den
    importerer, ikke om ekte Ollama-oppførsel — sjekk_dommer/kall_dommer erstattes uansett."""
    if "_ollama_port" not in sys.modules:
        modul = types.ModuleType("_ollama_port")
        modul.sjekk_dommer = lambda *a, **kw: None
        modul.kall_dommer = lambda *a, **kw: {"message": {"content": ""}}
        sys.modules["_ollama_port"] = modul
    return sys.modules["_ollama_port"]


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


# ── FDR-106 fase 1: Ollama-tunnel (Ulvens egen maskin som LLM-backend, via tunnel) ──


def test_kall_llm_tunnel_direkte_suksess(monkeypatch):
    """_kall_llm_tunnel() i isolasjon — samme post_fn-injeksjonsmønster som ai-proxy-
    testen over. Kaller rå /api/chat (Ollama sitt eget format), ikke ai-proxy sitt
    /complete — ingen ai-proxy på den andre siden av denne tunnelen."""
    monkeypatch.setenv("OLLAMA_TUNNEL_URL", "http://127.0.0.1:18711")

    def falsk_post(url, json, timeout):
        assert url == "http://127.0.0.1:18711/api/chat"
        assert json["model"] == syntese_fortelling.OLLAMA_MODELL
        assert json["messages"] == [{"role": "user", "content": "noe prompt"}]
        assert json["stream"] is False
        return _FalskSvar(data={"message": {"content": "svar via tunnel"}})

    assert syntese_fortelling._kall_llm_tunnel("noe prompt", post_fn=falsk_post) == "svar via tunnel"


def test_kall_llm_tunnel_feil_status_gir_lesbar_runtimeerror(monkeypatch):
    monkeypatch.setenv("OLLAMA_TUNNEL_URL", "http://127.0.0.1:18711")
    with pytest.raises(RuntimeError, match=r"feiler \(503\)"):
        syntese_fortelling._kall_llm_tunnel(
            "noe prompt",
            post_fn=lambda *a, **k: _FalskSvar(status=503, tekst="tunnel nede"),
        )


def test_kall_llm_bruker_tunnel_foran_ai_proxy_naar_begge_er_satt(monkeypatch):
    """FDR-106: OLLAMA_TUNNEL_URL (avtalt demo-økt) rutes FØRST, selv i prod der
    AI_PROXY_URL alltid er satt — ellers ville tunnel-veien aldri blitt nådd der Ulven
    faktisk er."""
    monkeypatch.setenv("OLLAMA_TUNNEL_URL", "http://127.0.0.1:18711")
    monkeypatch.setenv("AI_PROXY_URL", "http://ai-proxy:8000")
    monkeypatch.setattr(syntese_fortelling, "_kall_llm_tunnel", lambda p: "svar via tunnel")

    def skal_ikke_naas(_p):
        raise AssertionError("ai-proxy skal ikke kalles når tunnelen svarer")

    monkeypatch.setattr(syntese_fortelling, "_kall_llm_ai_proxy", skal_ikke_naas)
    assert syntese_fortelling.kall_llm("noe prompt") == "svar via tunnel"


def test_kall_llm_faller_til_ai_proxy_naar_tunnel_feiler(monkeypatch):
    """Obligatorisk fallback (FDR-106 §Foreslått funksjon, "Ulven skal ALDRI se en
    feilmelding fordi hans egen maskin var av"): en RuntimeError fra tunnelen skal
    ALDRI nå brukeren — kall_llm() fanger den og prøver ai-proxy i stedet."""
    monkeypatch.setenv("OLLAMA_TUNNEL_URL", "http://127.0.0.1:18711")
    monkeypatch.setenv("AI_PROXY_URL", "http://ai-proxy:8000")

    def sprekker(_p):
        raise RuntimeError("Ollama-tunnel utilgjengelig (test)")

    monkeypatch.setattr(syntese_fortelling, "_kall_llm_tunnel", sprekker)
    monkeypatch.setattr(syntese_fortelling, "_kall_llm_ai_proxy", lambda p: "prod-svar via ai-proxy")
    assert syntese_fortelling.kall_llm("noe prompt") == "prod-svar via ai-proxy"


def test_kall_llm_uendret_rute_naar_tunnel_ikke_er_satt(monkeypatch):
    """Uten OLLAMA_TUNNEL_URL (normaldrift, ingen avtalt demo-økt akkurat nå) er ruten
    UENDRET fra før FDR-106: AI_PROXY_URL avgjør alt, akkurat som testene over denne
    seksjonen alt dekker — denne testen fester bare at det IKKE har drevet."""
    monkeypatch.delenv("OLLAMA_TUNNEL_URL", raising=False)
    monkeypatch.setenv("AI_PROXY_URL", "http://ai-proxy:8000")
    monkeypatch.setattr(syntese_fortelling, "_kall_llm_ai_proxy", lambda p: "prod-svar")
    assert syntese_fortelling.kall_llm("noe prompt") == "prod-svar"


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
