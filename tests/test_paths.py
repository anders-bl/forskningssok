"""paths.py — ETT sted for cache.db-stien (2026-09-04, Dokploy-forberedelse). Fire
moduler beregnet den samme stien uavhengig av hverandre før dette — se paths.py sin
moduldocstring for hvorfor det var en reell fare (halvveis persistert cache)."""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_default_er_repo_rot_cache_db(monkeypatch):
    monkeypatch.delenv("FORSKNINGSSOK_DB", raising=False)
    import paths
    importlib.reload(paths)
    assert paths.DB == Path(__file__).resolve().parent.parent / "cache.db"


def test_env_var_overstyrer_til_volum_sti(monkeypatch):
    monkeypatch.setenv("FORSKNINGSSOK_DB", "/data/cache.db")
    import paths
    importlib.reload(paths)
    assert paths.DB == Path("/data/cache.db")


def test_alle_fire_moduler_deler_samme_db_konstant(monkeypatch):
    """Regresjonsvakt mot at DB igjen driver fra hverandre (bank.py/adapters/*.py)."""
    monkeypatch.setenv("FORSKNINGSSOK_DB", "/data/delt-test.db")
    import paths
    importlib.reload(paths)
    import bank
    import adapters.core as core
    import adapters.europe_pmc as europe_pmc
    import adapters.openalex as openalex
    importlib.reload(bank)
    importlib.reload(europe_pmc)
    importlib.reload(openalex)
    importlib.reload(core)
    assert bank.DB == europe_pmc.DB == openalex.DB == core.DB == Path("/data/delt-test.db")
