# Forskningssøk for Ulven (Lumic)

**Spesialtilpasset for:** Fiskehelse-forskning med ultralyd av lever og nyre hos oppdrettslaks.

**Firma:** Lumic  
**Fokus:** Ikke-invasiv vurdering av fiskehelse  
**Mål:** Oppdage sykdommer tidlig uten å skade fisken

---

## Kom i gang

### 1. Aktiver Ulven-profilen

Når du søker, utvides søket automatisk med domene-spesifikke synonymer:

```
Ditt søk: "laks lever"
Faktisk søk: "(laks OR Salmo salar OR oppdrettslaks) AND (lever OR hepatic OR liver)"
```

**Synonymer som er lagt til:**
- **Lever:** hepatic, hepatitt, levervev, hepatocytter, liver
- **Ultralyd:** ultrasound, sonografi, echography, ultrasonography
- **Laks:** Salmo salar, oppdrettslaks, atlantic salmon, laksefisk
- **Nyre:** renal, kidney, nefrokalsinose, nephrocalcinosis

### 2. Bruk forhåndsdefinerte søk

Spar tid med ferdige søk som gir gode resultater med en gang:

| Navn | Beskrivelse |
|------|-------------|
| **Lever + ultralyd hos laks** | Grunnleggende søk for ikke-invasiv levervurdering |
| **Nefrokalsinose + ultralyd** | Oppdager nyrestein tidlig med ultralyd |
| **Fiskehelse + avbildning** | Oversikt over ikke-invasive metoder |
| **Norske studier** | Masteroppgaver og PhD-er fra NTNU, NMBU, UiT |
| **Internasjonale studier** | Fra Aquaculture, Fish Diseases, etc. |

### 3. Oppdater cachen regelmessig

```bash
# Hent ferske studier fra alle kilder
python3 cli.py --oppdater
```

Anbefalt: **Én gang i uka** for å få med nyeste forskning.

---

## Funksjoner

### Forskningsrapport (med hovedfunn, uten konfabulering)

Søk i appen, trykk **"Forskningsrapport"**. Du får ett dokument som fletter:

- **Kilde-fordeling** — hvor mange treff fra CORE, PubMed/Europe PMC, OpenAlex
- **Hovedfunn** — mønstergjenkjente påstander fra abstractene ("signifikant funn",
  "kan detektere", "assosiert med"), hver med lenke til papiret den kom fra
- **Detekterte gap** — tidsrom eller temaer med få/ingen studier
- **Citation-gap** på topptreffet, omfang per akse, formaterte referanser (Vancouver/APA)

**Prinsipp:** Hver påstand har en kilde-knapp. Ingen AI-generering av fakta — kun
strukturering av det som allerede finnes i cachen.

Foretrekker du terminalen fremfor nettleseren, er samme motor tilgjengelig som CLI:

```bash
python3 ai_assistent.py --query "laks lever ultralyd" --svar
```

---

### Kart-fanen

Åpne et papir i leseren og velg **"Kart"**-fanen for å se relasjonskartet: de
semantisk nærmeste studiene som sirkler rundt papiret du leser.

**Hva du ser:**
- **Punkter:** hver sirkel er en studie
- **Farger:** kilde (CORE, Europe PMC, OpenAlex — se fargeforklaringen i appens
  Om-panel)
- **Nærhet:** studier som handler om det samme ligger nær hverandre
- **Størrelse:** hvor mye sitert (større = mer innflytelsesrik)

---

### Evidensnivå

Hver studie får et merke som viser studiedesign, fra Europe PMCs egen menneske-
kuraterte indeksering der den finnes, ellers mønstergjenkjent fra tittel/abstract:

| Nivå | Betydning | Kilde |
|------|-----------|-------|
| **Systematisk oversikt/meta-analyse** | Oppsummerer mange studier | NLM-indeksert eller mønstergjenkjent |
| **Randomisert kontrollert studie** | Gullstandard for eksperimenter | NLM-indeksert eller mønstergjenkjent |
| **Kohort-/observasjonsstudie** | Naturlige variasjoner, prevalensstudier | NLM-indeksert eller mønstergjenkjent |
| **Case-rapport/case-serie** | Enkelttilfeller | Mønstergjenkjent |

- **NLM-indeksert**: Europe PMC/PubMed har selv klassifisert publikasjonstypen
- **Mønstergjenkjent**: forskningssøk har gjettet ut fra ord i tittel/abstract —
  mindre sikkert, merket som sådan

---

### Eksport av litteraturlister

Under et søkeresultat: **"Kildesamling"**-knappene eksporterer hele treffsettet i
fire formater:

| Format | Til hva |
|--------|---------|
| **BibTeX** | LaTeX-arbeidsflyt |
| **RIS** | Importeres direkte i Zotero eller EndNote |
| **CSL-JSON** | Rendringsformatet bak 10 000+ ferdige tidsskriftstiler (Zotero, Pandoc, citeproc-js) |
| **PDF** | Én delbar rapport — kilder gruppert på nordisk fagmiljø/øvrige, med abstract-utdrag, evidensnivå og en formatert referanseliste, satt med ekte typografi (Typst) |

Samme knapperad ligger på selve Forskningsrapporten (Markdown/PDF) for det
sammenstilte dokumentet, ikke bare rålisten av kilder.

---

## Kilder som er prioritert for deg

### Norske kilder (gråtekst)
- NTNU Open (masteroppgaver, PhD-er)
- NMBU Åpen (veterinærforskning)
- UiT Munin (arktisk fiskehelse)
- Havforskningsinstituttet (rapporter)
- Veterinærinstituttet (patologi)

### Internasjonale tidsskrifter
- Aquaculture
- Journal of Fish Diseases
- Diseases of Aquatic Organisms
- Aquaculture Research
- Fish & Shellfish Immunology
- Reviews in Aquaculture

---

## Typisk arbeidsflyt for Ulven

### Morgen: Oppdatering
```bash
# Hent nyeste forskning (tar 2-3 minutter)
python3 cli.py --oppdater
```

### Ettermiddag: Utforskning
```bash
# Start med et bredt søk fra terminalen
python3 ai_assistent.py --query "ikke-invasiv fiskehelse" --svar
```
Eller søk direkte i appen — samme hovedfunn og kilde-fordeling der, i Forskningsrapporten.

### Kveld: Dypdykk
1. Åpne et interessant papir i leseren
2. Se "Kart"-fanen for semantisk nærmeste studier
3. Les abstractene i leseren
4. Siter viktige funn (de lagres i sitatbanken)
5. Se "Varmt"-fanen for å finne flere lignende studier

---

## Neste steg (under utvikling)

Eksport av litteraturlister (BibTeX/RIS/CSL-JSON/PDF) sto lenge her som "under
utvikling" — den er ferdig, se **Eksport av litteraturlister** i Funksjoner over.
Det som faktisk gjenstår:

### 1. Samarbeid med kolleger
- Del sitatbank med Lumic-teamet
- Kommenter studier sammen
- Felles "varme" kart

Størst gjenstående jobb: appen har ingen bruker-/kontomodell i dag (én delt
database, ingen innlogging) — ekte per-person-funksjoner krever det bygget først,
ikke bare en ny knapp.

### 2. Automatiske varsler
- "3 nye studier på laks + lever denne uka"
- "Noen siterte [et sitert papir]"
- "[Et tema] er trending"

Trenger en leveringskanal (e-post, eller en side Ulven sjekker) og en planlagt jobb —
ikke bygget ennå.

---

## Spørsmål og support

**For Ulven spesifikt:**
- Synonymer kan utvides (si ifra hvilke ord du bruker)
- Nye kilder kan legges til (har du tilgang til betalingsvegger?)
- Kart-fanen kan tilpasses (vil du se andre dimensjoner enn semantisk nærhet?)

**Kontakt:** kontakt@lauvasdata.no

---

## Teknisk dokumentasjon

Se hoved-README.md for generell dokumentasjon om forskningssøk.

**Profiler:** `profiler/ulven.py`  
**AI-assistent / hovedfunn:** `ai_assistent.py`, `api.py:api_rapport_konvergens`  
**Kart-fanen:** `frontend/index.html:renderKart`, `bank.py:lignende`  
**Evidensnivå:** `adapters/evidensniva.py`  
**Eksport:** `rapport.py` (`til_bibtex`/`til_ris`/`til_csl_json`/`til_pdf_bytes`), `api.py:api_rapport_kildesamling`
