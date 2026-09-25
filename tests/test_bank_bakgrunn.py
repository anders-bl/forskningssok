"""Verifiserer bank_bakgrunn.py og bank-bakgrunn-veien i syntese_fortelling.py.

Nettverksfritt: en liten boker.db-lignende fixture med den EKTE skjema-formen (book_chunks +
vec0 book_embeddings_v2) og en fake embedder. Den ekte banken og bge-m3 røres ikke her; det
er en egen live-måling (se commit-meldingen).
"""
import sqlite3
import sys
from pathlib import Path

import pytest
import sqlite_vec

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bank_bakgrunn  # noqa: E402
import syntese_fortelling  # noqa: E402

DIM = 1024


def _vec(*komponenter):
    v = [0.0] * DIM
    for i, x in enumerate(komponenter):
        v[i] = x
    return v


def _embed(tekster):
    return [_vec(1.0) for _ in tekster]


@pytest.fixture
def boker_db(tmp_path):
    sti = tmp_path / "boker.db"
    db = sqlite3.connect(sti)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.execute("""CREATE TABLE book_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, bok TEXT NOT NULL, samling TEXT NOT NULL,
        heading TEXT, chunk_text TEXT NOT NULL, chunk_index INTEGER NOT NULL,
        indexed_at TEXT NOT NULL, proveniens TEXT, UNIQUE(bok, chunk_index))""")
    db.execute("CREATE VIRTUAL TABLE book_embeddings_v2 USING vec0(chunk_id INTEGER PRIMARY KEY, embedding float[1024])")
    rader = [
        # (bok, samling, heading, tekst, proveniens, vektor) — avstand til query e0:
        ("Nephrocalcinosis in farmed salmonids", "nyrehelse", "Intro", "Nephrocalcinosis in salmon kidney.",
         "epmc:nyrehelse:PMC10157097 folded 2026-09-19", _vec(1.0, 0.6)),   # 0.6 skarpt
        ("Human Physiology", "biologi", "Urinary System", "Kidneys regulate calcium.",
         "wikibooks:biologi:hp folded", _vec(1.0, 0.9)),                    # 0.9 delvis
        ("Irrelevant kokebok", "mat", None, "Slik lager du pannekaker.", None, _vec(0.0, 1.0)),  # 1.41 MØRKT
    ]
    for i, (bok, samling, heading, tekst, prov, v) in enumerate(rader, start=1):
        db.execute("INSERT INTO book_chunks(id, bok, samling, heading, chunk_text, chunk_index, indexed_at, proveniens)"
                   " VALUES (?,?,?,?,?,?,?,?)", (i, bok, samling, heading, tekst, 0, "2026-09-25", prov))
        db.execute("INSERT INTO book_embeddings_v2(chunk_id, embedding) VALUES (?,?)",
                   (i, sqlite_vec.serialize_float32(v)))
    db.commit()
    db.close()
    return sti


def test_hent_bakgrunn_rangerer_og_forkaster_morkt(boker_db):
    poster, status = bank_bakgrunn.hent_bakgrunn("nephrocalcinosis", db_path=boker_db, embed_fn=_embed)
    assert [p["tittel"].split(" › ")[0] for p in poster] == [
        "Nephrocalcinosis in farmed salmonids", "Human Physiology"]
    assert status["tilgjengelig"] is True
    assert status["antall"] == 2
    assert status["forkastet_morkt"] == 1
    assert status["beste_avstand"] == pytest.approx(0.6, abs=1e-3)
    assert [p["bank_band"] for p in poster] == ["skarpt", "delvis"]


def test_bankpost_har_verifiserbar_id_og_ekte_lenke_bare_der_den_finnes(boker_db):
    poster, _ = bank_bakgrunn.hent_bakgrunn("nephrocalcinosis", db_path=boker_db, embed_fn=_embed)
    assert poster[0]["id"] == "bank:1"
    assert poster[0]["kilde"] == "bok-bank"
    assert poster[0]["kilde_url"] == "https://pmc.ncbi.nlm.nih.gov/articles/PMC10157097/"
    assert poster[1]["kilde_url"] is None  # ingen påstått URL for en kilde vi ikke kan adressere


def test_manglende_db_gir_arsak_ikke_stille_tom_liste(tmp_path):
    poster, status = bank_bakgrunn.hent_bakgrunn("x", db_path=tmp_path / "finnes-ikke.db", embed_fn=_embed)
    assert poster == []
    assert status["tilgjengelig"] is False
    assert "boker.db" in status["arsak"]


def test_alle_treff_morkt_gir_tilgjengelig_men_tom_med_arsak(boker_db):
    poster, status = bank_bakgrunn.hent_bakgrunn("x", db_path=boker_db,
                                                 embed_fn=lambda t: [_vec(0.0, 0.0, 5.0) for _ in t])
    assert poster == []
    assert status["tilgjengelig"] is True
    assert "MØRKT" in status["arsak"]


def test_bank_id_passerer_verifiser_kilder_og_ukjent_bank_id_fjernes(boker_db):
    poster, _ = bank_bakgrunn.hent_bakgrunn("nephrocalcinosis", db_path=boker_db, embed_fn=_embed)
    renset, avvist = syntese_fortelling.verifiser_kilder(
        "Nyrene forkalkes [#bank:1]. Oppdiktet [#bank:999].", poster)
    assert avvist == ["bank:999"]
    assert "[#bank:1]" in renset
    assert "[#bank:999]" not in renset


def test_prompt_merker_bankbakgrunn_og_direkte_bank_kilde(boker_db):
    poster, _ = bank_bakgrunn.hent_bakgrunn("nephrocalcinosis", db_path=boker_db, embed_fn=_embed)
    prompt = syntese_fortelling.bygg_prompt("nephrocalcinosis salmon", poster)
    assert "[BANK_BAKGRUNN] [#bank:2]" in prompt          # Human Physiology: ikke artsnær
    assert "[DIREKTE_KANDIDAT] [#bank:1]" in prompt       # salmonids: artsnær, får IKKE degraderes


def test_lag_syntese_uten_flagg_rorer_ikke_banken(monkeypatch, tmp_path):
    kall = []
    monkeypatch.setattr(syntese_fortelling, "hent_kandidater",
                        lambda emne, db_path=None: [{"id": 1, "tittel": "A", "forfattere": "X", "aar": 2024}])
    monkeypatch.setattr(syntese_fortelling, "kall_llm", lambda prompt: kall.append(prompt) or "Fakta [#1].")
    monkeypatch.setattr(bank_bakgrunn, "hent_bakgrunn",
                        lambda *a, **k: pytest.fail("banken skal ikke søkes uten bank_bakgrunn=True"))
    ut = syntese_fortelling.lag_syntese_fortelling("emne")
    assert "BANK-BAKGRUNN" not in ut
    assert "bank:" not in kall[0]


def test_lag_syntese_med_flagg_tar_med_bank_og_sier_fra_nar_den_mangler(monkeypatch):
    monkeypatch.setattr(syntese_fortelling, "hent_kandidater",
                        lambda emne, db_path=None: [{"id": 1, "tittel": "A", "forfattere": "X", "aar": 2024}])
    monkeypatch.setattr(syntese_fortelling, "kall_llm", lambda prompt: "Fakta [#1]. Bakgrunn [#bank:7].")

    bankpost = {"id": "bank:7", "tittel": "Human Physiology › Urinary", "forfattere": "bok-bank/biologi",
                "aar": "u.å.", "abstract": "Nyrer.", "doi": None, "kilde_url": None, "kilde": "bok-bank",
                "samling": "biologi", "bank_avstand": 0.9, "bank_band": "delvis"}
    monkeypatch.setattr(bank_bakgrunn, "hent_bakgrunn", lambda emne, *a, **k: (
        [bankpost], {"tilgjengelig": True, "arsak": "", "antall": 1, "beste_avstand": 0.9, "forkastet_morkt": 2}))
    ut = syntese_fortelling.lag_syntese_fortelling("emne", bank_bakgrunn=True)
    assert "[#bank:7]" in ut and "KILDE IKKE VERIFISERT" not in ut
    assert "[BANK-BAKGRUNN: 1 bankposter lagt til" in ut
    assert "[bok-bank, avstand 0.9 delvis]" in ut

    monkeypatch.setattr(bank_bakgrunn, "hent_bakgrunn", lambda emne, *a, **k: (
        [], {"tilgjengelig": False, "arsak": "fant ikke boker.db (sett BOKBANK_DB)", "antall": 0,
             "beste_avstand": None, "forkastet_morkt": 0}))
    ut2 = syntese_fortelling.lag_syntese_fortelling("emne", bank_bakgrunn=True)
    assert "[BANK-BAKGRUNN: ikke brukt — fant ikke boker.db" in ut2
    assert "KILDE IKKE VERIFISERT" in ut2  # modellen siterte [#bank:7] som nå ikke finnes: fjernet


def test_samme_bok_teller_maks_to_ganger(tmp_path):
    sti = tmp_path / "boker.db"
    db = sqlite3.connect(sti)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.execute("""CREATE TABLE book_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, bok TEXT NOT NULL, samling TEXT NOT NULL,
        heading TEXT, chunk_text TEXT NOT NULL, chunk_index INTEGER NOT NULL,
        indexed_at TEXT NOT NULL, proveniens TEXT, UNIQUE(bok, chunk_index))""")
    db.execute("CREATE VIRTUAL TABLE book_embeddings_v2 USING vec0(chunk_id INTEGER PRIMARY KEY, embedding float[1024])")
    for i in range(1, 6):   # fem chunks fra samme bok, stigende avstand
        db.execute("INSERT INTO book_chunks VALUES (?,?,?,?,?,?,?,?)",
                   (i, "Bok A", "s", None, f"tekst {i}", i, "2026-09-25", None))
        db.execute("INSERT INTO book_embeddings_v2(chunk_id, embedding) VALUES (?,?)",
                   (i, sqlite_vec.serialize_float32(_vec(1.0, 0.1 * i))))
    db.execute("INSERT INTO book_chunks VALUES (?,?,?,?,?,?,?,?)", (6, "Bok B", "s", None, "annen", 0, "2026-09-25", None))
    db.execute("INSERT INTO book_embeddings_v2(chunk_id, embedding) VALUES (?,?)",
               (6, sqlite_vec.serialize_float32(_vec(1.0, 0.7))))
    db.commit()
    db.close()
    poster, _ = bank_bakgrunn.hent_bakgrunn("x", k=5, db_path=sti, embed_fn=_embed)
    boker = [p["tittel"] for p in poster]
    assert boker.count("Bok A") == 2
    assert boker.count("Bok B") == 1
