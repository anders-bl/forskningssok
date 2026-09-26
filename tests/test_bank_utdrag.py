"""Verifiserer bank_utdrag.py og prod-veien i bank_bakgrunn.py (utdrag i stedet for boker.db).

Nettverksfritt: fake embedder med tekst -> vektor-oppslag, ekte sqlite-vec.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest
import sqlite_vec

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bank_bakgrunn  # noqa: E402
import bank_utdrag  # noqa: E402
import syntese_fortelling  # noqa: E402

DIM = 1024


def _vec(*k):
    v = [0.0] * DIM
    for i, x in enumerate(k):
        v[i] = x
    return v


VEKTORER = {"nyre tekst": _vec(1.0, 0.2), "annen nyre": _vec(1.0, 0.5), "tredje nyre": _vec(1.0, 0.9),
            "helt annet": _vec(0.0, 0.0, 1.0)}


def _embed(tekster):
    return [VEKTORER.get(t, _vec(1.0)) for t in tekster]


@pytest.fixture
def boker(tmp_path):
    sti = tmp_path / "boker.db"
    db = sqlite3.connect(sti)
    db.execute("""CREATE TABLE book_chunks (id INTEGER PRIMARY KEY AUTOINCREMENT, bok TEXT NOT NULL,
        samling TEXT NOT NULL, heading TEXT, chunk_text TEXT NOT NULL, chunk_index INTEGER NOT NULL,
        indexed_at TEXT NOT NULL, proveniens TEXT, UNIQUE(bok, chunk_index))""")
    rader = [(3, "Artikkel A", "nyrehelse", "Intro", "nyre tekst", "epmc:nyrehelse:PMC1 folded"),
             (1, "Artikkel A", "nyrehelse", "Metode", "annen nyre", "epmc:nyrehelse:PMC1 folded"),
             (2, "Artikkel B", "velferd", None, "tredje nyre", "core:fiskehelse-no:9 folded"),
             (4, "Kokebok", "mat", None, "helt annet", "pdf:mat:kokebok backfilt")]
    for cid, bok, samling, h, t, prov in rader:
        db.execute("INSERT INTO book_chunks VALUES (?,?,?,?,?,?,?,?)", (cid, bok, samling, h, t, cid, "d", prov))
    db.commit()
    db.close()
    return sti


def test_eksporter_velger_paa_prefiks_og_er_sortert(boker, tmp_path):
    ut = tmp_path / "u.jsonl"
    n = bank_utdrag.eksporter(boker, ut, ["epmc:", "core:fiskehelse"])
    assert n == 3
    ids = [json.loads(l)["id"] for l in ut.read_text(encoding="utf-8").splitlines()]
    assert ids == [1, 2, 3]  # kokeboka (id 4) er ikke med; sortert på id


def test_eksporter_uten_prefiks_feiler_hoyt(boker, tmp_path, monkeypatch):
    monkeypatch.setattr(bank_utdrag.domeneprofil, "PROFIL", {})
    with pytest.raises(RuntimeError, match="bank_proveniens"):
        bank_utdrag.eksporter(boker, tmp_path / "u.jsonl")


@pytest.fixture
def utdrag(boker, tmp_path):
    jsonl = tmp_path / "u.jsonl"
    bank_utdrag.eksporter(boker, jsonl, ["epmc:", "core:fiskehelse"])
    return jsonl


def test_bygg_er_idempotent_og_bokforer_modell(utdrag, tmp_path):
    db = tmp_path / "utdrag.db"
    kall = []
    def emb(t):
        kall.append(list(t)); return _embed(t)
    r1 = bank_utdrag.bygg(utdrag, db, embed_fn=emb, modell="bge-m3")
    assert r1["nye"] == 3 and r1["totalt"] == 3
    r2 = bank_utdrag.bygg(utdrag, db, embed_fn=emb, modell="bge-m3")
    assert r2["nye"] == 0 and r2["hoppet_over"] == 3
    assert len(kall) == 1  # andre kjøring embedder ingenting
    assert bank_utdrag.finnes(db)


def test_bygg_nekter_a_blande_modeller(utdrag, tmp_path):
    db = tmp_path / "utdrag.db"
    bank_utdrag.bygg(utdrag, db, embed_fn=_embed, modell="bge-m3")
    with pytest.raises(RuntimeError, match="to modeller"):
        bank_utdrag.bygg(utdrag, db, embed_fn=_embed, modell="mistral-embed")


def test_sok_nekter_feil_vektorrom_og_finner_naermeste_ellers(utdrag, tmp_path):
    db = tmp_path / "utdrag.db"
    bank_utdrag.bygg(utdrag, db, embed_fn=_embed, modell="mistral-embed")
    rader, arsak = bank_utdrag.sok("x", 3, db_path=db, embed_fn=_embed, modell="bge-m3")
    assert rader == [] and "feil vektorrom" in arsak
    rader, arsak = bank_utdrag.sok("x", 3, db_path=db, embed_fn=_embed, modell="mistral-embed")
    assert arsak == "" and [r[0] for r in rader] == [3, 1, 2]  # avstand 0.2, 0.5, 0.9 fra e0


@pytest.fixture
def prod(monkeypatch, utdrag, tmp_path):
    monkeypatch.setenv("AI_PROXY_URL", "http://ai-proxy:8000")
    db = tmp_path / "utdrag.db"
    bank_utdrag.bygg(utdrag, db, embed_fn=_embed)  # modell = mistral-embed fordi AI_PROXY_URL er satt
    return db


def test_prod_ukalibrert_mistral_utdrag_failes_lukket(prod, boker, monkeypatch):
    monkeypatch.setenv(bank_bakgrunn.BOKER_DB_ENV, str(boker))   # skal IKKE brukes i prod
    poster, status = bank_bakgrunn.hent_bakgrunn("x", k=5, embed_fn=_embed, utdrag_db=prod)
    assert poster == []
    assert status["kilde"] == "utdrag" and status["tilgjengelig"] is True
    assert "mangler kalibrert relevansterskel" in status["arsak"]


def test_prod_uten_utdrag_gir_arsak(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_PROXY_URL", "http://ai-proxy:8000")
    poster, status = bank_bakgrunn.hent_bakgrunn("x", embed_fn=_embed, utdrag_db=tmp_path / "finnes-ikke.db")
    assert poster == [] and status["tilgjengelig"] is False
    assert "bank_utdrag.py bygg" in status["arsak"]


def test_automatikk_i_syntesen_folger_utdraget(monkeypatch):
    monkeypatch.setattr(syntese_fortelling, "hent_kandidater",
                        lambda emne, db_path=None: [{"id": 1, "tittel": "A", "forfattere": "X", "aar": 2024}])
    monkeypatch.setattr(syntese_fortelling, "kall_llm", lambda prompt: "Fakta [#1].")
    kall = []
    monkeypatch.setattr(bank_bakgrunn, "hent_bakgrunn", lambda emne, *a, **k: kall.append(emne) or (
        [], {"tilgjengelig": False, "arsak": "test", "antall": 0, "beste_avstand": None, "forkastet_morkt": 0}))

    monkeypatch.setattr(bank_bakgrunn, "utdrag_finnes", lambda: False)
    assert "BANK-BAKGRUNN" not in syntese_fortelling.lag_syntese_fortelling("emne")
    assert kall == []

    monkeypatch.setattr(bank_bakgrunn, "utdrag_finnes", lambda: True)
    assert "BANK-BAKGRUNN: ikke brukt" in syntese_fortelling.lag_syntese_fortelling("emne")
    assert kall == ["emne"]

    assert "BANK-BAKGRUNN" not in syntese_fortelling.lag_syntese_fortelling("emne", bank_bakgrunn=False)
    assert kall == ["emne"]  # eksplisitt av vinner over automatikk


def test_batcher_deler_paa_antall_og_tegnbudsjett():
    rader = [{"tekst": "a" * 10} for _ in range(5)]
    assert [len(b) for b in bank_utdrag._batcher(rader, 2)] == [2, 2, 1]
    store = [{"tekst": "a" * 12000}, {"tekst": "b" * 12000}, {"tekst": "c" * 100}]
    assert [len(b) for b in bank_utdrag._batcher(store, 32)] == [1, 2]   # 12000 + 12000 > 20000
    assert list(bank_utdrag._batcher([], 32)) == []


def _bank_med_artikkel(tmp_path, tekster_per_bok):
    """boker.db-fixture der hver artikkel har flere chunks; returnerer (sti, rader-tuples)."""
    sti = tmp_path / "boker2.db"
    db = sqlite3.connect(sti)
    db.execute("""CREATE TABLE book_chunks (id INTEGER PRIMARY KEY AUTOINCREMENT, bok TEXT NOT NULL,
        samling TEXT NOT NULL, heading TEXT, chunk_text TEXT NOT NULL, chunk_index INTEGER NOT NULL,
        indexed_at TEXT NOT NULL, proveniens TEXT, UNIQUE(bok, chunk_index))""")
    cid = 0
    for bok, tekster in tekster_per_bok.items():
        for i, t in enumerate(tekster):
            cid += 1
            db.execute("INSERT INTO book_chunks VALUES (?,?,?,?,?,?,?,?)",
                       (cid, bok, "s", None, t, i, "d", f"epmc:s:PMC{cid} folded"))
    db.commit()
    db.close()
    return sti


def test_eksport_klassifiserer_per_artikkel_ikke_per_chunk(tmp_path):
    sti = _bank_med_artikkel(tmp_path, {
        "Vaccination against IHNV in rainbow trout": ["Kort chunk uten art.", "Ingen art her heller.", "Kidney"],
        "Sea Cucumber Aquaculture phage therapy": ["Bacteria and phage. Phage therapy of virus infection. Pathogen."],
    })
    ut = tmp_path / "u.jsonl"
    bank_utdrag.eksporter(sti, ut, ["epmc:"])
    rader = [json.loads(l) for l in ut.read_text(encoding="utf-8").splitlines()]
    trout = [r for r in rader if r["bok"].startswith("Vaccination")]
    assert {r["art_niva"] for r in trout} == {"maal"}          # arves av ALLE chunks, også de uten artsord
    assert "immun" in trout[0]["tema"]
    komuk = [r for r in rader if r["bok"].startswith("Sea Cucumber")]
    assert komuk[0]["art_niva"] == "annet"


def test_bygg_lagrer_metadata_og_migrerer_eldre_utdrag_uten_reembedding(tmp_path):
    sti = _bank_med_artikkel(tmp_path, {"Nephrocalcinosis in farmed salmonids": ["nyre tekst"]})
    ut = tmp_path / "u.jsonl"
    bank_utdrag.eksporter(sti, ut, ["epmc:"])
    # bygg et «eldre» utdrag uten metadata-kolonnene
    db_sti = tmp_path / "gammel.db"
    gammel = sqlite3.connect(db_sti)
    gammel.enable_load_extension(True)
    sqlite_vec.load(gammel)
    gammel.execute("CREATE TABLE utdrag(chunk_id INTEGER PRIMARY KEY, bok TEXT, samling TEXT, heading TEXT, tekst TEXT, proveniens TEXT)")
    gammel.execute("CREATE VIRTUAL TABLE utdrag_vec USING vec0(chunk_id INTEGER PRIMARY KEY, embedding float[1024])")
    gammel.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
    gammel.execute("INSERT INTO meta VALUES('embed_modell','bge-m3')")
    gammel.execute("INSERT INTO utdrag VALUES (1,'Nephrocalcinosis in farmed salmonids','s',NULL,'nyre tekst','epmc:s:PMC1 folded')")
    gammel.execute("INSERT INTO utdrag_vec VALUES (1, ?)", (sqlite_vec.serialize_float32(_vec(1.0)),))
    gammel.commit()
    gammel.close()
    kall = []
    r = bank_utdrag.bygg(ut, db_sti, embed_fn=lambda t: kall.append(t) or _embed(t), modell="bge-m3")
    assert r["nye"] == 0 and kall == []                       # ingen re-embedding
    rader, _ = bank_utdrag.sok("x", 3, db_path=db_sti, embed_fn=_embed, modell="bge-m3")
    assert rader[0][7] == "maal" and "nyre" in json.loads(rader[0][8])


def test_bank_bakgrunn_bruker_utdragets_artikkelnivaa_og_faller_tilbake_til_chunk(prod, boker, monkeypatch):
    poster, _ = bank_bakgrunn.hent_bakgrunn("x", k=5, embed_fn=_embed, utdrag_db=prod)
    assert all(p["art_grunnlag"] == "artikkel" and p["art_niva"] for p in poster)
    # boker.db-veien har ikke artikkelnivå: da klassifiseres tittel + den ene chunken, og det sies fra
    fall = bank_bakgrunn._art_og_tema("Nephrocalcinosis in salmonids", None, "kidney calcium", None, None)
    assert fall["art_grunnlag"] == "chunk" and fall["art_niva"] == "maal" and "nyre" in fall["tema"]


def test_syntese_prompt_og_referanseliste_viser_art_og_tema_for_bankposter():
    post = {"id": "bank:9", "tittel": "Vaccine paper", "forfattere": "bok-bank/x", "aar": "u.å.", "abstract": "a",
            "doi": None, "kilde_url": None, "kilde": "bok-bank", "samling": "x", "bank_avstand": 0.5,
            "bank_band": None, "art_niva": "maal", "tema": ["immun", "infeksjon"], "art_grunnlag": "artikkel"}
    prompt = syntese_fortelling.bygg_prompt("emne", [post])
    assert "[DIREKTE_KANDIDAT] [#bank:9]" in prompt and "Temaer=immun,infeksjon" in prompt
    assert "[bok-bank, avstand 0.5, art=maal, tema=immun,infeksjon]" in syntese_fortelling.lag_referanseliste([post])
