# CLAUDE.md — AI-agent instrukser for forskningssok

## Stack
- Python 3.14 hele veien: `.python-version` (3.14.7), venv-et som faktisk kjøres,
  Dockerfile (`python:3.14-slim`) og CI sier alle det samme. Filen er informativ, ikke
  håndhevet (ingen pyenv på denne maskinen) — kjør `venv/bin/python` direkte.
  Denne linjen sa «.python-version peker på 3.12.0» til 2026-09-04; fila var rettet,
  instruksen ikke. Sjekk `cat .python-version` framfor å tro på denne setningen.
- FastAPI — handlers er BEVISST synkrone (`def`, ikke `async def`), og
  `adapters/*.py` bruker synkron `httpx.get()`, ikke `httpx.AsyncClient`. Samme
  ADR-004-disiplin (spørretid + TTL-cache) som resten av huset — ikke en mangel
  som bør "rettes" til async.
- Docker: `Dockerfile` + `docker-compose.yml` finnes (Dokploy-deploy, se README
  §Deploy). Denne linjen sa «ingen Docker i dette repoet» til 2026-09-04 — den var
  sann da den ble skrevet og drev fra virkeligheten da deploy-oppsettet kom inn.

## Konvensjoner
- Typehints er påkrevd.
- **Aldri fagfelt-spesifikke ord i kjørende kode.** Fagmiljøer, tidsskrifter,
  målobjekt-termer, akser, merker og UI-tekster bor i `profiler/*.toml` (valgt med
  `FORSKNINGSSOK_PROFIL`). Docstrings og kommentarer SKAL derimot nevne det konkrete
  tilfellet en mekanisme ble bygget for — det er hvorfor-hukommelsen.
  `tests/test_domeneprofil_generisk.py` håndhever skillet med en AST-detektor og feller
  en ny «laks» i en strengliteral.
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
Suiten skal gå med NULL advarsler — `pytest -q` uten warnings-blokk. Dukker det opp en
DeprecationWarning, les den: `starlette.testclient` sin httpx→httpx2-advarsel var en
try/except rundt en IMPORT, altså «hele API-testdelen faller ved innsamling» den dagen
fallbacken fjernes, ikke en gradvis degradering. Advarsler her er varsler, ikke støy.

Suiten er NETTVERKSFRI, og det er en kontrakt, ikke en tilfeldighet: CI kjører den med
HTTP_PROXY/HTTPS_PROXY pekt på en død adresse. Trenger en ny test en ekstern kilde, mock
den — ellers blir CI rød på en maskin uten internett, og grønn på din, av grunner som
ikke handler om koden. (Skjedde 2026-09-04: Crossref-supplementet gjorde tre gap-tester
nettverksavhengige uten at noe sa fra.)
`direnv allow` aktiverer venv/bin automatisk hvis .envrc er på plass, men er ikke
påkrevd — `venv/bin/python`/`venv/bin/pytest` fungerer alltid direkte.
