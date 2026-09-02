"""Verifiserer cache/embed-laget uten å røre Ollama/husets embedder — embed_fn injiseres,
samme disiplin som fag_bank.py men testbar offline. Fake-embedderen returnerer et
deterministisk vektor-par som gjør «lignende» geometrisk sjekkbar (to nære vinkler,
én fjern), ikke bare «returnerer noe».
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bank import (  # noqa: E402
    hent_utkast, lagre, lagre_utkast, lignende, lignende_tekst, liste_utkast,
)
from schemas import PaperDossier  # noqa: E402

DIM = 1024


def _vec(vinkel_grader: float) -> list[float]:
    """2D-retning bakt inn i de to første dimensjonene, resten nullet — nok til at
    kosinus-/L2-avstand skiller «nær» fra «fjern» uten ekte semantikk."""
    r = math.radians(vinkel_grader)
    v = [0.0] * DIM
    v[0], v[1] = math.cos(r), math.sin(r)
    return v


def _fake_embed(texts: list[str]) -> list[list[float]]:
    vinkler = {"A": 0.0, "B": 5.0, "C": 90.0}
    return [_vec(vinkler.get(t[0], 0.0)) for t in texts]


def _p(pid, tittel, abstract="noe abstract-tekst"):
    return PaperDossier(pmid=pid, doi=None, tittel=tittel, forfattere="", tidsskrift="",
                        aar=2026, abstract=abstract, siteringstall=0, open_access=False,
                        kilde_url=f"https://example.org/{pid}")


def test_papir_uten_abstract_embeddes_aldri(tmp_path):
    db = tmp_path / "cache.db"
    n = lagre([_p("1", "Atittel", abstract="")], embed_fn=_fake_embed, db_path=db)
    assert n == 0
    assert lignende("1", db_path=db) == []


def test_idempotent_lagring_dobbeltlagrer_ikke(tmp_path):
    db = tmp_path / "cache.db"
    lagre([_p("1", "Atittel")], embed_fn=_fake_embed, db_path=db)
    n2 = lagre([_p("1", "Atittel")], embed_fn=_fake_embed, db_path=db)
    assert n2 == 0


def test_lignende_finner_naert_papir_ikke_fjernt(tmp_path):
    db = tmp_path / "cache.db"
    lagre([_p("1", "Atittel"), _p("2", "Btittel"), _p("3", "Ctittel")],
          embed_fn=_fake_embed, db_path=db)
    naboer = lignende("1", k=2, db_path=db)
    assert naboer, "forventet minst én nabo"
    assert naboer[0]["tittel"] == "Btittel"  # 5° unna, klart nærmest
    titler = [n["tittel"] for n in naboer]
    assert "Ctittel" not in titler[:1]  # 90° unna skal ikke slå 5°-naboen


def test_ukjent_id_gir_aerlig_tom_liste_ikke_feil(tmp_path):
    db = tmp_path / "cache.db"
    assert lignende("finnes-ikke", db_path=db) == []


# ---------- lignende_tekst (FDR-038 ambient-modus) ----------

def test_lignende_tekst_finner_naert_papir_ikke_fjernt(tmp_path):
    db = tmp_path / "cache.db"
    lagre([_p("1", "Atittel"), _p("2", "Btittel"), _p("3", "Ctittel")],
          embed_fn=_fake_embed, db_path=db)
    naboer = lignende_tekst("A snippet Ulven just typed, long enough to embed", k=2,
                            embed_fn=_fake_embed, db_path=db)
    assert naboer, "forventet minst én nabo"
    assert naboer[0]["tittel"] == "Atittel"  # samme vinkel (0°) — nærmest per konstruksjon
    assert naboer[1]["tittel"] == "Btittel"  # 5° unna, nest nærmest


def test_lignende_tekst_for_kort_gir_aerlig_tom_liste(tmp_path):
    db = tmp_path / "cache.db"
    lagre([_p("1", "Atittel")], embed_fn=_fake_embed, db_path=db)
    assert lignende_tekst("kort", db_path=db) == []  # < 20 tegn — for lite til å embedde meningsfullt
    assert lignende_tekst("", db_path=db) == []


def test_lignende_tekst_tom_cache_gir_aerlig_tom_liste_ikke_feil(tmp_path):
    db = tmp_path / "cache.db"
    assert lignende_tekst("En lang nok tekst uten noe cachet å sammenligne mot", db_path=db) == []


# ---------- utkast (Skriv-modus) ----------

def test_lagre_og_hente_utkast(tmp_path):
    db = tmp_path / "cache.db"
    u = lagre_utkast("Feltnotat", "innhold her", db_path=db)
    assert u["id"] is not None
    hentet = hent_utkast(u["id"], db_path=db)
    assert hentet["tittel"] == "Feltnotat"
    assert hentet["innhold"] == "innhold her"


def test_lagre_utkast_med_id_oppdaterer_ikke_dupliserer(tmp_path):
    db = tmp_path / "cache.db"
    u1 = lagre_utkast("v1", "tekst v1", db_path=db)
    u2 = lagre_utkast("v2", "tekst v2", utkast_id=u1["id"], db_path=db)
    assert u2["id"] == u1["id"]
    assert len(liste_utkast(db_path=db)) == 1
    assert hent_utkast(u1["id"], db_path=db)["innhold"] == "tekst v2"


def test_liste_utkast_nyeste_forst(tmp_path):
    db = tmp_path / "cache.db"
    lagre_utkast("først", "a", db_path=db)
    lagre_utkast("sist", "b", db_path=db)
    liste = liste_utkast(db_path=db)
    assert liste[0]["tittel"] == "sist"


def test_hent_ukjent_utkast_gir_aerlig_none(tmp_path):
    db = tmp_path / "cache.db"
    assert hent_utkast(999, db_path=db) is None
