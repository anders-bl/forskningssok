"""paths.py — ETT sted for cache.db-stien (lagt til 2026-09-04, Dokploy-forberedelse).

Fire moduler (bank.py, adapters/europe_pmc.py, adapters/openalex.py, adapters/core.py)
beregnet samme sti UAVHENGIG av hverandre — samme fil i praksis (alle repo-rot-relative),
men ville driftet i to retninger samtidig hvis bare NOEN av dem fikk env-var-støtte for
Dokploy-volumet: noen cachetreff ville landet i volumet (overlever redeploy), andre i
containerens flyktige filsystem (forsvinner) — en "halvveis persistert" bug som ikke
viser seg før første redeploy mister deler av dataen stille.

FORSKNINGSSOK_DB (satt kun i Dokploy-miljøet, peker på det monterte volumet) overstyrer;
default er uendret lokal oppførsel (repo-rot/cache.db, samme fil Anders' Mac alltid har
brukt)."""
import os
from pathlib import Path

DB = Path(os.environ["FORSKNINGSSOK_DB"]) if os.environ.get("FORSKNINGSSOK_DB") \
    else Path(__file__).resolve().parent / "cache.db"
