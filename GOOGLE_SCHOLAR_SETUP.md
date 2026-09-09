# Google Scholar Setup via SerpAPI

## Hvorfor SerpAPI?

Google Scholar har **intet offisielt API**. Alternativer:
1. **Scraping** (BeautifulSoup, Scholarly) — bryter ToS, ustabil, IP-blokkering
2. **SerpAPI** — offisielt partner, stabilt, rate-limits, koster penger
3. **Ingen** — stole kun på CORE, Europe PMC, Semantic Scholar

## Oppsett (5 minutter)

### 1. Skaff API-nøkkel
Gå til: https://serpapi.com/manage-api-key

**Gratis plan:**
- 100 søk/måned (~3/dag)
- Bra for testing/utvikling
- Ingen kredittkort kreves

**Betalt plan ($50/mnd):**
- 5000 søk/måned (~160/dag)
- Bra for produksjon
- Krever kredittkort

### 2. Legg til i .env

```bash
# Rediger .env i repo-roten
export SERPAPI_KEY=din-nøkkel-her
```

### 3. Last inn

```bash
direnv allow
```

### 4. Test

```bash
python3 cli.py --oppdater
```

Du skal se:
```
  Google Scholar: 10 papirer
```

## Bruk i AI-assistenten

```bash
python3 ai_assistent.py --query "laks lever ultralyd" --svar
```

Google Scholar resultater blandes med CORE, Europe PMC, Semantic Scholar.

## Kostnadsoversikt

| Plan | Pris | Søker/mnd | Per søk |
|------|------|-----------|---------|
| Gratis | $0 | 100 | $0 |
| Hobby | $50 | 5000 | $0.01 |
| Pro | $150 | 20000 | $0.0075 |

**Anbefaling:** Start med gratis. Oppgrader hvis du trenger mer.

## Alternativer til SerpAPI

- **Scale SERP** — $25/mnd for 2500 søk
- **ValueSERP** — $19/mnd for 2000 søk
- **ScraperAPI** — har Google Scholar, men dyrere

SerpAPI er valgt fordi:
- Best dokumentasjon
- Raskest responstid (målt <2s)
- Returnerer flest metadata (forfattere, år, sitert-av)
- Samme format som andre adapters

## Feilsøking

**"SERPAPI_KEY mangler"**
→ Sjekk at `.env` er lastet: `echo $SERPAPI_KEY`

**"Ugyldig SERPAPI_KEY"**
→ Sjekk nøkkelen på https://serpapi.com/manage-api-key

**"Rate-limitet"**
→ Gratis: vent til neste måned, eller oppgrader
→ Betalt: sjekk dashboard for usage

**"Timeout"**
→ SerpAPI var nede. Prøv igjen om 5 minutter.
