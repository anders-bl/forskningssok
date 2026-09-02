# CLAUDE.md — AI-agent instrukser for forskningssok

## Stack
- Python 3.12.0
- FastAPI
- Docker (se Dockerfile)

## Konvensjoner
- Bruk `async/await` for alle I/O-operasjoner
- Typehints er påkrevd
- Ingen kommentarer i produksjonskode

## Testing
```bash
cd ~/prosjekter/forskningssok
direnv allow
pytest
```

## Hus-standard
- `.envrc` — automatisk venv-aktivering
- `.python-version` — Python 3.12.0
