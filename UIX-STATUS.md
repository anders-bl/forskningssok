# UIX-status for Forskningssøk

Status gjennomgått 2026-09-24. Skillet mellom portalens Ulven/Luna-tester og
Forskningssøkets egne nettlesertester er gjort eksplisitt.

## Levert i v1

- Fjordstein-basert skall med søk, treffliste, leseflate og relasjonspaneler.
- Ett arbeidsrom med sammenleggbar skuff i stedet for Les/Skriv-modusbryter.
- Sitatbank, dokumentlinse, innsetting som sitat-node og varme-panel.
- Om-panel med metodikk, kildegrenser og profilinformasjon.
- Fanegruppering og forklaringstekst for Lignende, Kart, Gap og Sti.
- Dossier, syntese-fortelling, retningssamtale og fremdriftsindikator.
- Kildekart med kildefarge, siteringsstørrelse, tooltip og label-kontroller.
- Eksportknapper for rå kildesamling og rapporter.
- Responsiv mobilflate under 760 px med vertikal lesereise og berøringsvennlige
  verktøy.

Forskningssøk har 715 beståtte tester, inkludert to Chromium-regresjonsløp for
desktop og mobil. Lauvasdata-portalen
har 243 beståtte frontend-enhetstester og 25/25 beståtte Playwright-tester.
Tolv Playwright-tester dekker Ulven/Luna-integrasjonen, blant annet desktop og
mobil, DOI-handoff, lagring, gjenoppretting og SciVis. De er ikke en
nettleserregresjonstest av Forskningssøkets hovedreise.

## Gjenstår før gjentakbar Forskningssøk-beta

### Hovedreise i nettleser

Permanent desktop- og mobiltest for Forskningssøk ligger i
`tests/test_ulven_browser.py`. Den bruker isolerte API-fixtures og dekker
standardsøk, kilde-status, revisjonsspor, papirvalg, gap-fane, Markdown-eksport,
dossierinnsikt, synlig AI-proxy-feil og forskningsspørsmål-handoff via URL og dra-og-slipp av sitat til Dokument-fanen. Mobilrunden sjekker også horisontal
overflow ved 390 px. Dette er lokal regresjonsdekning; den erstatter ikke den
innloggede produksjonssmoken i [beta-gaten](ULVEN-BETA-GATE.md).

Nettlesertesten dekker også tomt søkeresultat og oppstrømsfeil. En regresjon
avslørte at leseflate, revisjonsspor og dossierhandlinger kunne bli stående fra
forrige søk; dette nullstilles nå idet nytt søk starter. Produksjonsversjon,
innlogget API-tilgang og ekte AI-proxy er fortsatt uverifisert.

### Mobilnavigasjon

Den første mobilflaten er en vertikal lesereise. En eksplisitt liten stegkontroll
bør vurderes etter observasjon dersom brukere trenger å hoppe direkte mellom
søk, lesing og varme.

### Dra-og-slipp fra sitatbank til dokument

Levert: slipp sitatet på Dokument-fanen. Det åpner skuffen, oppretter dokument
når det trengs og bruker samme sitat-node som klikkinnsetting. Chromium-testen
verifiserer denne banen.

### Rik tekst i PDF

Editorens grunnlag er på plass, men fet/kursiv i PDF er fortsatt markdown-lite.
Avklar hvilke TipTap-markeringer som skal overleve i Blokk-modellen før
emitteren utvides.

## V2, etter arbeidsrom

### Deling av dokumenter

Deling krever arbeidsrom, eier, tilgangsnivå, tilbakekalling og sporbar eksport.
Den følger derfor bruker-/arbeidsromsmodellen i v2.

### Dossier som arbeidsflate

Dossieret har visning, innsikt og graf. Neste steg er å vise jobbstatus,
kildegrunnlag, modellutgave og verifikasjonsstatus uten at en ny visning starter
samme kostbare jobb.

## Avgrensning

Forskningssøk v1 har én delt database. Ikke bruk sitatbank, dokumenter, varme,
kommentarer eller deling med ekte arbeidsdata før bruker- og arbeidsromseierskap
er på plass. Gap-kandidatvurderinger lagres bare i `sessionStorage`. Historiske
og underlenkede spor i atelieret er prototypeinnhold med eksempeldata, ikke en
live kildeanalyse; demoen bør vise denne forskjellen.

Varsler, nye kilder, rangeringsevaluering og flerbrukerlagring er produkt- og
backendarbeid. UIX bør vise tydelige tilstander og metadata når disse bygges.

## Beta-konsekvens

Portalens Luna/Ulven-integrasjon har nettleserdekning, og lokal Forskningssøk-
verifikasjon er omfattende. Den innloggede produksjonssmoken for Forskningssøk
er likevel ikke kjørt. Bruk syntetiske eller offentlige data i første demo;
ekte deling og personlige arbeidsdata venter på arbeidsrommodellen.
