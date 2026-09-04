# CLAUDE.md — AI-agent instrukser for forskningssok

## Stack
- Python (venv/, se README for oppsett) — `.python-version` peker på 3.12.0, men
  venv-et som faktisk kjøres her er 3.14 og ingen pyenv er installert på denne
  maskinen; filen er per nå informativ, ikke håndhevet. Ikke la den overstyre det
  ekte venv-et.
- FastAPI — handlers er BEVISST synkrone (`def`, ikke `async def`), og
  `adapters/*.py` bruker synkron `httpx.get()`, ikke `httpx.AsyncClient`. Samme
  ADR-004-disiplin (spørretid + TTL-cache) som resten av huset — ikke en mangel
  som bør "rettes" til async.
- Docker: `Dockerfile` + `docker-compose.yml` finnes (Dokploy-deploy, se README
  §Deploy). Denne linjen sa «ingen Docker i dette repoet» til 2026-09-04 — den var
  sann da den ble skrevet og drev fra virkeligheten da deploy-oppsettet kom inn.

## Konvensjoner
- Typehints er påkrevd.
- Kommentarer: kun når WHY er ikke-opplagt — en skjult forutsetning, en subtil
  invariant, en tidligere feil kommentaren forklarer (samme regel som husets
  globale CLAUDE.md). ALDRI hva koden gjør — det leser man av navn. Dette repoet
  bruker moduldocstrings aktivt til nettopp dette (se f.eks. `rapport.py`,
  `bank.py`, `adapters/*.py`) — de er institusjonell hukommelse for HVORFOR et
  valg ble tatt (ADR-013/ADR-004/FDR-038-referanser, live-verifiseringsresultater,
  tidligere feil), ikke støy å fjerne.

## Testing
```bash
cd ~/prosjekter/forskningssok
venv/bin/python -m pytest -q
```
`direnv allow` aktiverer venv/bin automatisk hvis .envrc er på plass, men er ikke
påkrevd — `venv/bin/python`/`venv/bin/pytest` fungerer alltid direkte.
