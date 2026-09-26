"""Verifiserer art_niva.klassifiser: nivåene, beviset, og de feilene som gjorde at
ja/nei-testen (arts_naer_tekst) ble byttet ut. Enhetstestene bruker profilens ekte lister;
selve treffsikkerheten måles av art_niva_eval.py mot tests/fixtures/art_fasit.json."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import art_niva  # noqa: E402
import art_niva_eval  # noqa: E402
import domeneprofil  # noqa: E402

k = art_niva.klassifiser


def test_tittel_med_malart_gir_maal_med_bevis():
    f = k("Nephrocalcinosis in farmed salmonids", "")
    assert (f.niva, f.kilde) == ("maal", "tittel") and "salmonid" in f.bevis


def test_generell_fisk_er_naer_ikke_maal():
    assert k("Skeletal deformities in fish", "").niva == "naer"
    assert k("Ultrasound in Nile tilapia", "").niva == "naer"


def test_skalldyr_i_tittel_slaar_generelt_akvakultur_ord():
    f = k("Phage Therapy for Sustainable Sea Cucumber Aquaculture", "")
    assert (f.niva, f.kilde) == ("annet", "tittel")


def test_salmoides_og_salmonella_er_ikke_malart():
    assert k("Health status of Largemouth Bass (Micropterus salmoides)", "").niva != "maal"
    assert k("Salmonella outbreak in poultry", "Salmonella enterica was isolated").niva != "maal"


def test_korte_termer_matcher_bare_hele_ord():
    assert k("Data encoded in a codec", "").niva == "ingen"        # «cod» i «encoded»/«codec»
    assert k("Cod stocks in the North Sea", "").niva == "naer"


def test_en_enkelt_omtale_i_teksten_er_ikke_maal():
    f = k("A review of aquaculture systems", "Species such as salmon are farmed. Many fish are farmed.")
    assert f.niva == "naer"


def test_mange_omtaler_med_hoy_andel_gir_maal_fra_tekst():
    f = k("Vertebral fusions in a teleost model", "We studied Atlantic salmon. Salmon were reared at high temperature.")
    assert (f.niva, f.kilde) == ("maal", "tekst")


def test_mesh_med_spesifikk_art_avgjor_alene():
    f = k("A cartilage extract toxicity study", "rats", mesh="Salmon|Rats")
    assert (f.niva, f.kilde) == ("maal", "mesh")


def test_bred_mesh_gir_bare_gulv_naer_og_ikke_indeksert_gir_ingen_slutning():
    assert k("Some study", "no organism", mesh="Fishes").niva == "naer"
    assert k("Some study", "no organism", mesh=None).niva == "ingen"
    assert k("Some study", "no organism", mesh="").niva == "ingen"


def test_pattedyr_og_mennesker_er_annet():
    assert k("Calcitonin in osteoporosis", "patients were treated").niva == "annet"


def test_profil_uten_niva_faller_tilbake_til_gammel_ja_nei_og_sier_det(monkeypatch):
    monkeypatch.setattr(domeneprofil, "PROFIL", {**domeneprofil.PROFIL, "art": {"termer": ["salmon"]}})
    monkeypatch.setattr(domeneprofil, "ARTSTERMER", ("salmon",))
    f = k("Salmon health", "")
    assert (f.niva, f.kilde) == ("maal", "legacy")
    assert k("Cattle health", "").kilde == "legacy"


def test_fasit_er_hash_delt_uten_lekkasje_og_har_alle_nivaer():
    fasit = json.loads(art_niva_eval.FASIT.read_text(encoding="utf-8"))
    utv = {g["id"] for g in fasit if g["del"] == "utvikling"}
    hold = {g["id"] for g in fasit if g["del"] == "holdout"}
    assert utv.isdisjoint(hold) and len(fasit) >= 100
    assert {g["niva"] for g in fasit} == set(art_niva.NIVAER)


def test_ny_regel_slaar_gammel_paa_utviklingsdelen():
    r = art_niva_eval.rapport(art_niva_eval.last("utvikling"))
    assert r["ny"]["maal_presisjon"] > r["gammel"]["maal_presisjon"] + 0.3
    assert r["ny"]["maal_gjenfinning"] >= r["gammel"]["maal_gjenfinning"] - 0.05
