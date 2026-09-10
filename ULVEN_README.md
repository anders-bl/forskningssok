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

### 🔍 AI-assistent (uten konfabulering)

Spør på naturlig språk, få svar **med harde kilder**:

```bash
python3 ai_assistent.py --query "laks lever ultralyd" --svar
```

**Eksempelsvar:**
```
**Forskningsassistent: 14 studier funnet**

### 📊 Kilde-fordeling
• CORE: 3 studier (norske masteroppgaver)
• PubMed/Europe PMC: 8 studier
• OpenAlex: 3 studier

### 🔍 Hovedfunn (med kilder)
• Ultralyd kan detektere nefrokalsinose tidlig
  → Hansen et al. (2023, NTNU)
  DOI: 10.xxxx/xxxxx

• Leverekko endres ved stress
  → Johansen et al. (2022, NMBU)
  DOI: 10.xxxx/xxxxx

### ⚠️  Detekterte gap
• Ingen studier på ultralyd + hepatitt hos laks
• Få studier mellom 2020-2022
```

**Prinsipp:** Hver påstand har en kilde. Ingen AI-generering av fakta.

---

### 🗺️ Visuelle koblinger

Se forskningslandskapet som et interaktivt kart:

```bash
python3 scivis_koblinger.py --query "laks lever ultralyd" --output landskap.html
```

**Hva du ser:**
- **Punkter:** Hver sirkel er en studie
- **Farger:** Kilde (blå=CORE/norsk, oransje=PubMed, grønn=OpenAlex)
- **Nærhet:** Studier som handler om det samme ligger nær hverandre
- **Størrelse:** Hvor mye sitert (større = mer innflytelsesrik)

**Gap-deteksjon:**
- Røde områder: Tidsrom med få studier
- Manglende kilder: Hvis f.eks. ingen norske studier finnes
- Tema-gap: Emner som nesten ikke er forsket på

Åpne `landskap.html` i nettleseren og utforsk!

---

### 📊 Evidensnivå

Hver studie får et badge som viser studiedesign:

| Badge | Betydning | Eksempel |
|-------|-----------|----------|
| 🟦 **Systematisk oversikt** | Oppsummerer mange studier | Meta-analyse av 20 studier |
| 🟩 **Randomisert kontrollert** | Gullstandard for eksperimenter | 45 laks randomisert til 2 grupper |
| 🟨 **Observasjonsstudie** | Naturlige variasjoner | Måler leverekko i et oppdrettsanlegg |
| 🟧 **Case-rapport** | Enkelttilfeller | Beskrivelse av én syk laks |

**Kilde til badge:**
- **"nlm"**: Indeksert av PubMed (menneske-kuratert)
- **"monster"**: Ordmønster i tittel/abstract (automatisk)

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
# Start med et bredt søk
python3 ai_assistent.py --query "ikke-invasiv fiskehelse" --svar

# Lag et landskap for å se sammenhenger
python3 scivis_koblinger.py --query "laks lever ultralyd"
```

### Kveld: Dypdykk
1. Åpne `landskap.html` i nettleseren
2. Klikk på interessante punkter
3. Les abstractene i leseren
4. Siter viktige funn (de lagres i sitatbanken)
5. Se "Varmt"-fanen for å finne flere lignende studier

---

## Neste steg (under utvikling)

### 1. Eksport av litteraturlister
- BibTeX for Zotero/Mendeley
- PDF-samling med alle abstractene
- Rapport-generering (Typst)

### 2. Samarbeid med kolleger
- Del sitatbank med Lumic-teamet
- Kommenter studier sammen
- Felles "varme" kart

### 3. Automatiske varsler
- "3 nye studier på laks + lever denne uka"
- "Noen siterte Hansen et al. (2023)"
- "Nefrokalsinose er trending"

---

## Spørsmål og support

**For Ulven spesifikt:**
- Synonymer kan utvides (si ifra hvilke ord du bruker)
- Nye kilder kan legges til (har du tilgang til betalingsvegger?)
- Landskapet kan tilpasses (vil du se andre dimensjoner?)

**Kontakt:** kontakt@lauvasdata.no

---

## Teknisk dokumentasjon

Se hoved-README.md for generell dokumentasjon om forskningssøk.

**Profiler:** `profiler/ulven.py`  
**AI-assistent:** `ai_assistent.py`  
**Visuell koblinger:** `scivis_koblinger.py`  
**Evidensnivå:** `adapters/evidensniva.py`
