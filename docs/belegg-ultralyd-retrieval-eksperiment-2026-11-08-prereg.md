# Prereg: Belegg-sok etter ultralydprotokoll for nefrokalsinose

Dato: 2026-11-08
Status: preregistrert for en eksplorativ, metadata-basert sokesammenligning.

## Sporsmal og avgrensning

Brukerens sporsmal er om ultralyd skal brukes til a detektere grad av nefrokalsinose
(score 1-4), hvilke deler av nyren som bor skannes, eller om hele nyren bor skannes.
Eksperimentet undersoker om query-dekomponering mot eksisterende akademiske kilder
finner mer relevante artikler enn dagens sammensatte sok. Det vurderer ikke klinisk
eller veterinarmedisinsk praksis, og gir ikke en skanneanbefaling.

Tidligere malte ultralydsporsmal og prober er kjent utviklingsmateriale, ikke en
uavhengig holdout. Resultatene her er derfor eksplorative og kan ikke brukes som
presisjon-/recall-validering eller produksjonsgodkjenning.

## Fryste sokearmer

Alle fritekstsporringer kjores uendret mot Europe PMC, CORE og OpenAlex gjennom
eksisterende adaptere. Maksimalt 10 treff per kilde per sporring. Ingen LLM-syntese
eller embedding brukes. Treff dedupliseres pa DOI, deretter tittel.

1. Baseline: `ultrasound nephrocalcinosis salmon kidney score`
2. Tilstand/art: `salmonid nephrocalcinosis renal mineralization fish`
3. Modalitet/anatomi: `fish kidney ultrasonography renal anatomy salmon`
4. Metode/validering: `fish renal ultrasound histopathology nephrocalcinosis grading`
5. Score/protokoll: `salmon kidney ultrasound nephrocalcinosis score scanning region`
6. Kjent radiologisk startkilde (kontekstkontroll): `Radiological detection of nephrocalcinosis in farmed Atlantic salmon`

## Hypoteser

- H1: Dekomponerte sokeord finner minst en unik laksefisk- eller fiskespesifikk kilde
  som baseline ikke finner.
- H2: Utvidet modalitet/anatomi-sok kan gi relevante metodebakgrunnskilder uten at de
  dermed validerer score 1-4 eller et skanneomrade for nefrokalsinose hos smolt.
- H3: Et treff teller som mulig direkte evidens for skanneomrade/score bare hvis titel
  eller abstract eksplisitt beskriver fisk, ultralyd, lokalisering/dekning eller scoring
  og en relevant valideringsreferanse. Ellers er det kun bakgrunn/lesetips.

## Utfall og klassifisering

Bevar per kall kilde, eksakt query, status, tidspunkt, antall treff og ra metadata for
de returnerte treffene. Klassifiser unike treff etter titel/abstract som:

- direkte kandidat: eksplisitt fiskespesifikk ultralydprotokoll eller validering av
  nyreomrade/score;
- metodebakgrunn: fiskespesifikk ultralyd/anatomi uten direkte nefrokalsinose-score;
- sykdomsbakgrunn: fiskespesifikk nefrokalsinose uten ultralydprotokoll;
- analogi: annen art eller humanmedisin;
- irrelevant;
- ukjent: metadata gir ikke nok grunnlag.

Rapporter treff per kilde/query, unike DOI-er, etiketter per treff og feilede kilder.
Ikke tell flere databaseposter av samme verk som flere evidensenheter. Ingen etikett
fra metadata alene skal omtales som fagkyndig fasit.

## Beslutningsregler

- Hvis ingen direkte kandidat finnes, behold avstaelsen fra a anbefale skanneomrade.
- Hvis H1 holder, anbefal query-dekomponering som retrieval-forbedring for videre
  vurdering, men ikke som svargrunnlag i seg selv.
- Hvis bare analogier/metodebakgrunn finnes, vis dem eventuelt som tydelig merket
  lesetips. Ikke la dem underbygge en artsspesifikk protokoll.
- Ny database eller betalt tilgang vurderes kun etter at dette oppsettet viser et
  konkret gjenfinningstap, med separat kostnads-/tilgangsvurdering.

## Begrensninger

Seks sporringer, topp-10 per kilde og metadata-only klassifisering gir en liten,
eksplorativ probe. Rangeringsforskjeller, fulltekstdekning, sitasjonsgraf og
ekspertreview males ikke i denne runden. API-treff kan endres over tid. Cache skrives
kun i det isolerte worktreets lokale ignored database og er ikke resultatgrunnlag.
