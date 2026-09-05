"""Verifiserer evaluer.py: konkordans-regning, den blindt-for-rangering-parsingen, og at
den positive kontrollen faktisk VOIDER en måling der dommeren lures.

Nettverksfri (CLAUDE.md): dommeren injiseres. En ekte Ollama-kjøring gjøres i CLI-en, ikke
her — suiten skal aldri avhenge av at en modell kjører.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import evaluer  # noqa: E402


def _dommer(grader: dict):
    """Dommer-stubb: gir en fast grad per tittel-nøkkelord."""
    def doem(prompt: str) -> str:
        for nokkel, g in grader.items():
            if nokkel in prompt:
                return str(g)
        return "0"
    return doem


def test_parse_grad_tar_forste_gyldige_siffer():
    assert evaluer._parse_grad("3") == 3
    assert evaluer._parse_grad("Karakter: 2 fordi ...") == 2
    assert evaluer._parse_grad("<tenker>...</tenker>\n0") == 0
    assert evaluer._parse_grad("ingen tall her") is None
    assert evaluer._parse_grad("7") is None, "utenfor 0-3 er ikke en gyldig grad"


def test_konkordans_perfekt_rangering_er_1():
    # ikke-økende grader nedover = perfekt
    k, enige, total = evaluer._konkordans([3, 3, 2, 1, 0])
    assert k == 1.0 and enige == total


def test_konkordans_omvendt_rangering_er_0():
    k, enige, total = evaluer._konkordans([0, 1, 2, 3])
    assert k == 0.0 and enige == 0


def test_konkordans_teller_like_grader_som_enige():
    # to like relevante naboer er ikke en rangeringsfeil
    k, _, _ = evaluer._konkordans([2, 2, 2])
    assert k == 1.0


def test_dommer_er_blind_for_rangeringen():
    """Prompten skal aldri inneholde plassering/score. Regresjonsvakt mot å lekke rangen
    inn i dommen — da måler vi om dommeren kan gjenta rangeringen, ikke om den er god."""
    sett = []
    dommer = lambda prompt: (sett.append(prompt), "2")[1]
    evaluer.doem_relevans("q", "En tittel", "Et abstract", dommer_fn=dommer)
    p = sett[0].lower()
    assert "plassering" not in p and "rank" not in p and "score" not in p
    assert "En tittel" in sett[0] and "Et abstract" in sett[0]


def test_positiv_kontroll_bestaar_naar_dommeren_skiller_arten():
    res = evaluer.positiv_kontroll(
        relevant={"tittel": "Nephrocalcinosis in Atlantic salmon", "abstract": "fisk"},
        felle={"tittel": "CYP24A1 nephrocalcinosis in human infants", "abstract": "menneske"},
        dommer_fn=_dommer({"salmon": 3, "human": 0}))
    assert res["bestått"] is True and res["grad_relevant"] == 3 and res["grad_felle"] == 0


def test_positiv_kontroll_FEILER_naar_dommeren_lures_av_ordet():
    """Species-trap: samme ord «nephrocalcinosis», feil art. En dommer som gir fella like
    høyt som det ekte papiret har falt for nøyaktig det rangeringen bander mot."""
    res = evaluer.positiv_kontroll(
        relevant={"tittel": "Nephrocalcinosis in Atlantic salmon", "abstract": "fisk"},
        felle={"tittel": "CYP24A1 nephrocalcinosis in human infants", "abstract": "menneske"},
        dommer_fn=_dommer({"nephrocalcinosis": 3}))  # gir BEGGE 3 — lurt av ordet
    assert res["bestått"] is False


def test_evaluer_voider_maalingen_naar_kontrollen_feiler():
    """Den bærende disiplinen: en høy konkordans betyr INGENTING hvis dommeren ikke besto
    kontrollen. `gyldig` skal da være False selv om konkordansen er perfekt."""
    papirer = [{"tittel": "ZA", "abstract": ""}, {"tittel": "ZB", "abstract": ""}]
    ut = evaluer.evaluer_rangering(
        "laks", papirer,
        dommer_fn=_dommer({"ZA": 3, "ZB": 3, "ZTRAP": 3}),
        kontroll={"relevant": {"tittel": "ZREAL", "abstract": ""},
                  "felle": {"tittel": "ZTRAP", "abstract": ""}})
    assert ut["konkordans"] == 1.0        # rangeringen ser perfekt ut ...
    assert ut["gyldig"] is False          # ... men dommeren er ikke til å stole på


def test_evaluer_gyldig_naar_kontroll_bestaar():
    # NB: tittel-tokens må være unike og IKKE forekomme i prompt-legenden (som selv
    # inneholder ordene «sentral/perifer/relevant/irrelevant») — ellers matcher stubben
    # legenden i stedet for papiret. Fanget som ekte kollisjon 2026-09-05.
    papirer = [{"tittel": "ZTOPP", "abstract": ""}, {"tittel": "ZBUNN", "abstract": ""}]
    ut = evaluer.evaluer_rangering(
        "laks", papirer,
        dommer_fn=_dommer({"ZTOPP": 3, "ZBUNN": 1, "ZEKTE": 3, "ZFELLE": 0}),
        kontroll={"relevant": {"tittel": "ZEKTE", "abstract": ""},
                  "felle": {"tittel": "ZFELLE", "abstract": ""}})
    assert ut["konkordans"] == 1.0 and ut["gyldig"] is True
    assert ut["bestått"] is True


def test_umaalt_svar_telles_ikke_som_null():
    """En dommer som svarer utolkbart er «ikke målt», ikke grad 0 — ellers ville en stum
    dommer sett ut som at alt er irrelevant."""
    papirer = [{"tittel": "A", "abstract": ""}, {"tittel": "B", "abstract": ""}]
    ut = evaluer.evaluer_rangering("q", papirer, dommer_fn=lambda p: "intet siffer")
    assert ut["umålte"] == 2
    assert ut["bestått"] is None, "ingen målte grader → ingen dom, ikke en bestått"
