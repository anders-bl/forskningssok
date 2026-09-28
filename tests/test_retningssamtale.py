"""Verifiserer retningssamtale.py (fase 2b, prosjekt/forskningssok-smartsyntese-for-ulven).

Mekanisk lag (ekstraksjon/segregering/linser) er ren funksjon-testing, ingen mocking
nødvendig. hent_kilder()/lag_retningsrapport() mocker cli.sok_og_ranger og
syntese_fortelling.kall_llm — nettverksfri, samme disiplin som resten av forskningssok.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import retningssamtale as rs  # noqa: E402
from schemas import PaperDossier  # noqa: E402


def _p(id, tittel="", aar=None, doi=None, abstract="", kilde_kode="EUROPE_PMC"):
    # PaperDossier.id er en @property (doi or pmid or kilde_url, se schemas.py) --
    # doi=id som DEFAULT her gjør at p.id faktisk blir den forventede testverdien,
    # med mindre en test eksplisitt vil teste doi-fallback-kjeden selv.
    return PaperDossier(pmid=None, doi=doi or id, tittel=tittel, forfattere="Testesen T",
                        tidsskrift="Test Journal", aar=aar, abstract=abstract,
                        siteringstall=0, open_access=False,
                        kilde_url=f"https://example.org/{id}", kilde_kode=kilde_kode)


# ---------- Lag 1a: stoppord-stripping ----------

def test_ekstraher_innholdsord_fjerner_stoppord_bevarer_rekkefolge():
    ord = rs.ekstraher_innholdsord("Jeg har lurt litt på om nefrokalsinose henger sammen med stress")
    assert "jeg" not in ord and "har" not in ord and "litt" not in ord
    assert ord == ["nefrokalsinose", "henger", "sammen", "stress"]
    assert ord.index("nefrokalsinose") < ord.index("stress")


def test_ekstraher_innholdsord_dropper_korte_ord():
    ord = rs.ekstraher_innholdsord("er om på av i og")
    assert ord == []


def test_ekstraher_innholdsord_ingen_duplikater():
    ord = rs.ekstraher_innholdsord("nefrokalsinose stress nefrokalsinose")
    assert ord.count("nefrokalsinose") == 1


def test_ekstraher_innholdsord_splitter_pa_bindestrek():
    """Regresjon 2026-09-15: kodevekslede sammensetninger som 'metabolism-greie' skal
    IKKE forbli ett langt ord — de forgifter prioriter_spesifikke()s lengde-sortering."""
    ord = rs.ekstraher_innholdsord("en metabolism-greie og noe stress-relatert her")
    assert "metabolism-greie" not in ord
    assert "metabolism" in ord
    assert "greie" not in ord  # stoppord, strippet
    assert "relatert" not in ord  # stoppord, strippet
    assert "stress" in ord


def test_ekstraher_innholdsord_tomt_gir_tomt():
    assert rs.ekstraher_innholdsord("") == []
    assert rs.ekstraher_innholdsord(None) == []


# ---------- Lag 1b: språk-segregering ----------

def test_segreger_sprak_kjenner_norske_ord_med_aeoa():
    norske, andre = rs.segreger_sprak(["sjøvann", "kalsium", "nephrocalcinosis"])
    assert "sjøvann" in norske
    assert "nephrocalcinosis" in andre


def test_segreger_sprak_ukjent_ord_default_til_andre():
    """Lav presisjon er akseptabelt (se moduldocstring) — men default-retningen skal
    være mot 'andre' (engelsk-kandidat), ikke norsk, for et ord verken i NORSKE_ORD
    eller med æøå."""
    norske, andre = rs.segreger_sprak(["osmoregulation", "xenobiotikatterm"])
    assert norske == []
    assert set(andre) == {"osmoregulation", "xenobiotikatterm"}


def test_segreger_sprak_tomt_gir_to_tomme_lister():
    assert rs.segreger_sprak([]) == ([], [])


# ---------- prioriter_spesifikke ----------

def test_prioriter_spesifikke_lengste_forst_kappet():
    ord = ["a", "bb", "ccc", "dddd", "eeeee"]
    assert rs.prioriter_spesifikke(ord, maks=3) == ["eeeee", "dddd", "ccc"]


def test_prioriter_spesifikke_under_maks_beholder_alle():
    assert rs.prioriter_spesifikke(["a", "bb"], maks=5) == ["bb", "a"]


# ---------- bygg_sokefraser ----------

def test_bygg_sokefraser_gir_to_buckets():
    fraser = rs.bygg_sokefraser("Nefrokalsinose hos laks henger sammen med calcium metabolism")
    assert "nefrokalsinose" in fraser["norsk"] or "laks" in fraser["norsk"]
    assert "calcium" in fraser["engelsk"] or "metabolism" in fraser["engelsk"]


def test_bygg_sokefraser_tomt_bucket_er_aerlig_tom_streng():
    """Kun norske ord i input (æøå-signal + NORSKE_ORD) -> engelsk-bucket skal være
    '' (ærlig fravær), ikke et søk kjørt på ingenting."""
    fraser = rs.bygg_sokefraser("laksen svømmer i sjøvannet")
    assert fraser["engelsk"] == ""
    assert fraser["norsk"] != ""


def test_bygg_sokefraser_helt_tom_tekst_gir_to_tomme_buckets():
    assert rs.bygg_sokefraser("") == {"norsk": "", "engelsk": ""}
    assert rs.bygg_sokefraser("er på av i og som") == {"norsk": "", "engelsk": ""}


# ---------- hent_kilder (mocket sok_og_ranger) ----------

def test_hent_kilder_kaller_sok_for_hvert_ikke_tomt_bucket(monkeypatch):
    kalt = []

    def fake_sok(q, page_size=20):
        kalt.append(q)
        return [_p("a", tittel=f"Treff for {q}")], None, {"kilder": {}, "treff_per_kilde": {}}

    monkeypatch.setattr(rs, "sok_og_ranger", fake_sok)
    papirer, fraser, detaljer = rs.hent_kilder("forskning viser calcium metabolism")
    assert len(kalt) == 2  # norsk + engelsk bucket, begge ikke-tomme her
    assert detaljer["norsk"]["kjort"] and detaljer["engelsk"]["kjort"]


def test_hent_kilder_hopper_over_tomt_bucket_uten_a_kalle_sok(monkeypatch):
    kalt = []

    def fake_sok(q, page_size=20):
        kalt.append(q)
        return [], None, {"kilder": {}, "treff_per_kilde": {}}

    monkeypatch.setattr(rs, "sok_og_ranger", fake_sok)
    # Kun norske ord -- engelsk-bucket skal vaere tomt og ALDRI trigge et sok.
    papirer, fraser, detaljer = rs.hent_kilder("laksen svømmer fint i sjøvannet")
    assert detaljer["engelsk"]["kjort"] is False
    assert fraser["engelsk"] == ""


def test_hent_kilder_dedupliserer_pa_tvers_av_sprak(monkeypatch):
    # Tittelen nevner søkeordet: hent_kilder forkaster treff uten søkeord (2026-09-28).
    felles = _p("felles-id", tittel="Samme calcium-papir begge veier", doi="10.1/felles")

    def fake_sok(q, page_size=20):
        return [felles], None, {"kilder": {}, "treff_per_kilde": {}}

    monkeypatch.setattr(rs, "sok_og_ranger", fake_sok)
    papirer, _, _ = rs.hent_kilder("nefrokalsinose calcium")
    assert len(papirer) == 1


# ---------- tre linser ----------

def test_linse_aktuell_filtrerer_pa_ar_nyeste_forst():
    papirer = [_p("a", aar=2020), _p("b", aar=2024), _p("c", aar=2010)]
    aktuelle = rs.linse_aktuell(papirer, i_ar=2026)
    assert [p.id for p in aktuelle] == ["b"]  # kun 2024, innenfor AKTUELL_TERSKEL_AR=5


def test_linse_glemt_filtrerer_pa_ar_eldste_forst():
    papirer = [_p("a", aar=2020), _p("b", aar=2005), _p("c", aar=1990)]
    glemte = rs.linse_glemt(papirer, i_ar=2026)
    assert [p.id for p in glemte] == ["c", "b"]  # eldre enn GLEMT_TERSKEL_AR=10, eldste forst


def test_linse_aktuell_og_glemt_hopper_over_ukjent_ar():
    papirer = [_p("a", aar=None)]
    assert rs.linse_aktuell(papirer, i_ar=2026) == []
    assert rs.linse_glemt(papirer, i_ar=2026) == []


def test_linse_hull_teller_per_papir_ikke_aggregert():
    papirer = [
        _p("a", tittel="Liver histopathology in farmed salmon"),
        _p("b", tittel="Environmental temperature effects", abstract="salinity and co2"),
    ]
    hull = rs.linse_hull(papirer)
    assert hull["Lever"] == 1
    assert hull["Miljøfaktorer"] == 1


def test_linse_hull_tomt_korpus_gir_alle_akser_null():
    hull = rs.linse_hull([])
    assert all(v == 0 for v in hull.values())


def test_linse_domenetreff_knytter_ordtreff_til_stabile_kilde_ider():
    papirer = [
        _p("lever-1", tittel="Liver histopathology in farmed salmon"),
        _p("miljo-1", tittel="Environmental temperature effects", abstract="salinity and co2"),
        _p("uten-treff", tittel="Unrelated topic"),
    ]
    treff = rs.linse_domenetreff(papirer)
    assert treff["Lever"] == ["lever-1"]
    assert treff["Miljøfaktorer"] == ["miljo-1"]
    assert "uten-treff" not in {ident for ids in treff.values() for ident in ids}


# ---------- bygg_prompt ----------

def test_bygg_prompt_baerer_kilde_id_og_de_tre_linsene():
    aktuelle = [{"id": "1", "tittel": "Aktuell", "forfattere": "A", "aar": 2024,
                 "kilde": "europe_pmc", "abstract": "abstract aktuell"}]
    glemte = [{"id": "2", "tittel": "Gammel", "forfattere": "B", "aar": 2005,
               "kilde": "core", "abstract": "abstract gammel"}]
    prompt = rs.bygg_prompt("mine tanker", aktuelle, glemte, {"Lever": 1}, antall_kilder=2)
    assert "[#1]" in prompt and "[#2]" in prompt
    assert "mine tanker" in prompt
    assert "AKTUELT" in prompt.upper()
    assert "OVERSETT" in prompt.upper()
    assert "HULL" in prompt.upper()
    assert "Lever" in prompt


def test_bygg_prompt_tom_kategori_sier_det_aerlig():
    prompt = rs.bygg_prompt("noe", [], [], {}, antall_kilder=0)
    assert "ingen kilder i denne kategorien" in prompt.lower()


# ---------- lag_retningsrapport (full orkestrering, mocket) ----------

def test_lag_retningsrapport_tom_tekst_gir_aerlig_beskjed():
    assert "Ingen tekst" in rs.lag_retningsrapport("")
    assert "Ingen tekst" in rs.lag_retningsrapport("   ")


def test_lag_review_tomt_input_har_stabil_kontrakt():
    review = rs.lag_review("   ")
    assert review["kontrakt"] == "review.v1"
    assert review["status"] == "tomt_input"
    assert review["ai"]["brukt"] is False


def test_lag_retningsrapport_ingen_treff_gir_aerlig_beskjed(monkeypatch):
    monkeypatch.setattr(rs, "sok_og_ranger",
                         lambda q, page_size=20: ([], None, {"kilder": {}, "treff_per_kilde": {}}))
    ut = rs.lag_retningsrapport("nefrokalsinose calcium metabolism")
    assert "Ingen kilder funnet" in ut


def test_lag_retningsrapport_degraderer_til_mekanisk_naar_llm_feiler(monkeypatch):
    """Roadmap-krav (prosjekt/forskningssok-smartsyntese-for-ulven, fase 2b): "Faller
    lag 2 (Ollama wedget/ai-proxy nede), skal retningssamtalen fortsatt gi
    kildespråk-treff via lag 1 alene, ikke feile helt." Mekanisk henting/linser skal
    IKKE forsvinne bare fordi AI-kallet feiler."""
    ekte = _p("ekte-id", tittel="Ekte papir", aar=2024, abstract="calcium abstract")
    monkeypatch.setattr(rs, "sok_og_ranger",
                         lambda q, page_size=20: ([ekte], None, {"kilder": {}, "treff_per_kilde": {}}))

    def sprenger(prompt):
        raise RuntimeError("Ollama wedget (test)")
    monkeypatch.setattr(rs.syntese_fortelling, "kall_llm", sprenger)

    ut = rs.lag_retningsrapport("nefrokalsinose calcium")
    assert "IKKE tilgjengelig" in ut
    assert "ekte-id" in ut  # den mekaniske kilden er fortsatt synlig
    assert "## Kildeliste" in ut  # kildelisten legges alltid til, selv ved degradering


def test_lag_review_beholder_proveniens_og_ai_status(monkeypatch):
    ekte = _p("ekte-id", tittel="Ekte papir", aar=2024, abstract="calcium abstract")
    monkeypatch.setattr(rs, "sok_og_ranger",
                        lambda q, page_size=20: ([ekte], None, {"kilder": {"core": True},
                                                                 "treff_per_kilde": {"core": 1}}))
    monkeypatch.setattr(rs.syntese_fortelling, "kall_llm",
                        lambda prompt: "Et kildebundet funn [#ekte-id].")
    review = rs.lag_review("nefrokalsinose calcium")
    assert review["kontrakt"] == "review.v1"
    assert review["status"] == "fullfort"
    assert review["ai"] == {"brukt": True, "avvist": []}
    assert review["kilder"][0]["id"] == "ekte-id"
    assert review["linser"]["domenetreff"] == {}
    kjort = [d for d in review["sok"]["detaljer"].values() if d["kjort"]]
    assert kjort and kjort[0]["revisjon"]["kilder"] == {"core": True}
    assert "[#ekte-id]" in review["rapport"]


def test_lag_retningsrapport_advarer_ved_konfabulert_referanse(monkeypatch):
    ekte = _p("ekte-id", tittel="Ekte papir", aar=2024, abstract="calcium abstract")
    monkeypatch.setattr(rs, "sok_og_ranger",
                         lambda q, page_size=20: ([ekte], None, {"kilder": {}, "treff_per_kilde": {}}))
    monkeypatch.setattr(rs.syntese_fortelling, "kall_llm",
                         lambda prompt: "Et ekte funn [#ekte-id]. Et diktet funn [#99999].")
    ut = rs.lag_retningsrapport("nefrokalsinose calcium")
    assert "ADVARSEL" in ut
    assert "99999" in ut
    assert "[KILDE IKKE VERIFISERT" in ut
    assert "## Kildeliste" in ut
    assert "ekte-id" in ut


# Fixturene under nevner «calcium» i abstract: hent_kilder forkaster treff som ikke nevner
# noe søkeord (2026-09-28), og testene her gjelder rapporten, ikke filteret.
def test_lag_retningsrapport_gyldig_referanse_beholdes(monkeypatch):
    ekte = _p("ekte-id", tittel="Ekte papir", aar=2024, abstract="calcium abstract")
    monkeypatch.setattr(rs, "sok_og_ranger",
                         lambda q, page_size=20: ([ekte], None, {"kilder": {}, "treff_per_kilde": {}}))
    monkeypatch.setattr(rs.syntese_fortelling, "kall_llm",
                         lambda prompt: "Et velgrunnet funn [#ekte-id].")
    ut = rs.lag_retningsrapport("nefrokalsinose calcium")
    assert "ADVARSEL" not in ut
    assert "[#ekte-id]" in ut


def test_lag_retningsrapport_kapper_ved_maks_kilder(monkeypatch):
    mange = [_p(f"id{i}", tittel=f"Calcium-papir {i}", aar=2020)
             for i in range(rs.MAKS_KILDER + 10)]
    monkeypatch.setattr(rs, "sok_og_ranger",
                         lambda q, page_size=20: (mange, None, {"kilder": {}, "treff_per_kilde": {}}))
    kalt_med = {}
    monkeypatch.setattr(rs.syntese_fortelling, "kall_llm",
                         lambda prompt: kalt_med.setdefault("prompt", prompt) or "svar uten referanser")
    rs.lag_retningsrapport("nefrokalsinose calcium")
    # kildelisten i selve prompten skal aldri overstige MAKS_KILDER kilder totalt
    assert kalt_med["prompt"].count("Abstract:") <= rs.MAKS_KILDER


def test_tilgjengelig_speiler_syntese_fortelling(monkeypatch):
    monkeypatch.setattr(rs.syntese_fortelling, "tilgjengelig", lambda: True)
    assert rs.tilgjengelig() is True
    monkeypatch.setattr(rs.syntese_fortelling, "tilgjengelig", lambda: False)
    assert rs.tilgjengelig() is False


# ---------- fagtermer og støyfilter (2026-09-28, Ulvens spørsmål ga 0/10 relevante) ----------

def test_fagterm_eksakt_sammensatt_og_skrivefeil():
    assert rs.fagterm("nefrokalsinose") == ("nefrokalsinose", "nephrocalcinosis")
    assert rs.fagterm("ultralydscreening") == ("ultralyd", "ultrasound")
    assert rs.fagterm("nerfokalsinose") == ("nefrokalsinose", "nephrocalcinosis")
    assert rs.fagterm("nefrokalsinonse") == ("nefrokalsinose", "nephrocalcinosis")
    assert rs.fagterm("dersom") is None


def test_norsk_sporsmal_gir_engelsk_frase_av_fagtermer_ikke_norske_restord():
    fraser = rs.bygg_sokefraser(
        "Dersom ultralyd skal brukes for detektere graden av nerfokalsinose, hvilket deler av nyren bør scannes?")
    eng = fraser["engelsk"].split()
    assert eng[0] == "nephrocalcinosis"
    assert "ultrasound" in eng and "kidney" in eng
    for norsk in ("dersom", "detektere", "hvilket", "ultralyd", "nerfokalsinose"):
        assert norsk not in eng
    assert len(eng) <= rs.MAKS_ENGELSK_TERMER


def test_engelsk_tekst_uten_norske_signaler_er_uendret():
    assert rs.bygg_sokefraser("nephrocalcinosis Atlantic salmon ultrasound")["norsk"] == ""


def test_hent_kilder_forkaster_treff_uten_sokeord_og_legger_engelsk_forst(monkeypatch):
    stoy = _p("lus", tittel="Temporal and spatial variations in lice numbers")

    def fake_sok(q, page_size=20):
        if "nephrocalcinosis" in q:
            # Nevner laks, som det norske treffet: testen gjelder språkrekkefølgen, ikke artsrekkefølgen.
            return ([_p(f"e{i}", tittel=f"Nephrocalcinosis in salmon, study {i}") for i in range(6)] + [stoy],
                    None, {"kilder": {}, "treff_per_kilde": {}})
        return [stoy, _p("n1", tittel="Nefrokalsinose hos laks")], None, {"kilder": {}, "treff_per_kilde": {}}

    monkeypatch.setattr(rs, "sok_og_ranger", fake_sok)
    papirer, _, detaljer = rs.hent_kilder("Hvordan oppstår nefrokalsinose hos laks?")
    ider = [p.id for p in papirer]
    assert "lus" not in ider
    assert ider[0] == "e0" and ider[-1] == "n1"
    assert detaljer["engelsk"]["forkastet_uten_sokeord"] == 1


def test_hent_kilder_tilbakefall_kutter_minst_spesifikke_ledd(monkeypatch):
    kalt = []

    def fake_sok(q, page_size=20):
        kalt.append(q)
        n = 6 if q == "nephrocalcinosis" else 0
        return [_p(f"x{i}", tittel=f"nephrocalcinosis x{i}") for i in range(n)], None, {"kilder": {}, "treff_per_kilde": {}}

    monkeypatch.setattr(rs, "sok_og_ranger", fake_sok)
    papirer, _, detaljer = rs.hent_kilder("Kan ultralyd og røntgen gradere nefrokalsinose?")
    engelske = [q for q in kalt if "nephrocalcinosis" in q]
    assert engelske[0].startswith("nephrocalcinosis ") and engelske[-1] == "nephrocalcinosis"
    assert len(engelske) <= 1 + rs.MAKS_TILBAKEFALL
    assert detaljer["engelsk"]["sokefrase"] == "nephrocalcinosis"
    assert len(papirer) == 6


# ---------- kontekst for korte oppfølginger og artsrekkefølge (2026-09-28) ----------

def test_kort_oppfolging_laaner_mest_spesifikke_fagterm_fra_kontekst():
    k = "Dersom ultralyd skal brukes for detektere graden av nefrokalsinose, hvilke deler av nyren?"
    assert rs.bygg_sokefraser("hvorfor radiologi")["engelsk"] == "radiology"
    assert rs.bygg_sokefraser("hvorfor radiologi", k)["engelsk"] == "nephrocalcinosis radiology"


def test_langt_sporsmal_med_egne_fagtermer_ignorerer_kontekst():
    q = "Finnes det studier som sammenligner ultralyd med røntgen for å gradere nefrokalsinose?"
    assert rs.bygg_sokefraser(q, "noe om hyperkapni og histologi") == rs.bygg_sokefraser(q)


def test_artsnaere_treff_rykker_foran_uten_at_noe_fjernes(monkeypatch):
    menneske = _p("m", tittel="Sotos syndrome and nephrocalcinosis in children")
    laks = _p("l", tittel="Nephrocalcinosis in farmed Atlantic salmon")

    def fake_sok(q, page_size=20):
        return [menneske, laks], None, {"kilder": {}, "treff_per_kilde": {}}

    monkeypatch.setattr(rs, "sok_og_ranger", fake_sok)
    papirer, _, _ = rs.hent_kilder("nephrocalcinosis")
    assert [p.id for p in papirer] == ["l", "m"]


# ---------- tvetydige ord: avgjøres av kontekst, tolkningen erklæres (2026-09-28) ----------

def test_lever_som_organ_naar_konteksten_sier_det():
    for q, grunn in [("Hva med ultralyd av lever?", "«av lever»"), ("Kan man se lever og nyre?", "«nyre» i spørsmålet")]:
        _, tolk = rs.les_tvetydige(q)
        assert tolk == [{"ord": "lever", "lest_som": "organ (liver)", "grunn": grunn}]
        assert "liver" in rs.bygg_sokefraser(q)["engelsk"]


def test_lever_som_verb_eller_uavgjort_sokes_ikke_men_erklaeres():
    for q, lest in [("Hvor lenge lever laksen?", "annet"), ("Laksen som lever i merden", "annet"), ("lever", "uavgjort")]:
        _, tolk = rs.les_tvetydige(q)
        assert tolk[0]["lest_som"] == lest
        fraser = rs.bygg_sokefraser(q)
        assert "liver" not in fraser["engelsk"] and "lever" not in fraser["engelsk"].split()


def test_kort_ord_faar_ikke_skrivefeiltoleranse():
    assert rs.fagterm("levere") is None
    assert rs.fagterm("nerfokalsinose") == ("nefrokalsinose", "nephrocalcinosis")


def test_review_erklaerer_tolkninger(monkeypatch):
    monkeypatch.setattr(rs, "sok_og_ranger", lambda q, page_size=20: ([], None, {"kilder": {}, "treff_per_kilde": {}}))
    review = rs.lag_review("Hva med ultralyd av lever?")
    assert review["sok"]["tolkninger"][0]["lest_som"] == "organ (liver)"


# ---------- uten_ai: kalleren lager eget svar (Belegg, 2026-09-28) ----------

def test_uten_ai_kaller_aldri_modellen_og_gir_mekanisk_rapport(monkeypatch):
    ekte = _p("e", tittel="Nephrocalcinosis in salmon", aar=2024, abstract="calcium")
    monkeypatch.setattr(rs, "sok_og_ranger", lambda q, page_size=20: ([ekte], None, {"kilder": {}, "treff_per_kilde": {}}))

    def forbudt(prompt):
        raise AssertionError("modellen skal ikke kalles med uten_ai")

    monkeypatch.setattr(rs.syntese_fortelling, "kall_llm", forbudt)
    review = rs.lag_review("nefrokalsinose calcium", uten_ai=True)
    assert review["status"] == "fullfort"
    assert review["ai"] == {"brukt": False, "avvist": [], "hoppet_over": "etter_foresporsel"}
    assert [k["id"] for k in review["kilder"]] == ["e"]
    assert "Kildeliste (1 kilder)" in review["rapport"]


def test_uten_flagg_kalles_modellen_som_foer(monkeypatch):
    ekte = _p("e", tittel="Nephrocalcinosis in salmon", aar=2024, abstract="calcium")
    monkeypatch.setattr(rs, "sok_og_ranger", lambda q, page_size=20: ([ekte], None, {"kilder": {}, "treff_per_kilde": {}}))
    kalt = []
    monkeypatch.setattr(rs.syntese_fortelling, "kall_llm", lambda prompt: kalt.append(1) or "Funn [#e].")
    review = rs.lag_review("nefrokalsinose calcium")
    assert kalt == [1] and review["ai"]["brukt"] is True
