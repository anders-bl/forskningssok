# Brand-status for Forskningssøk

## Husstandard som gjelder

Forskningssøk bruker Fjordstein 2.0, med den kanoniske portalen som kilde for
kjernetokens:

- primær aksent `#2E5C47`, hover `#4A7D64`
- varm off-white `#F8F7F4`, tekst `#1C1C1A`, dempet tekst `#5A5A56`
- mørk modus med `#141412`, `#EDECE7` og `#7AAF95`
- systemfont for UI, synlig tastaturfokus og respekt for redusert bevegelse
- semantiske CSS-tokens; farger skal ikke hardkodes i komponentlogikk

Fargene og typografien i Forskningssøk samsvarer med disse verdiene. PDF-en
bruker samme aksent, dempet tekst og strek i `rapport_mal.typ`, med innebygd
Libertinus Serif for stabil rendering i container.

## App-spesifikke utvidelser

`--kald`, `--lunken`, `--varm`, `--kilde-core` og `--kilde-alex` er semantiske
datavisualiseringsfarger. De er ikke nye merkevarefarger: de beskriver varme,
kildetype og status, og skal holdes adskilt fra primær aksent.

## Avvik som er lukket nå

- Nettlesertittelen sa «Litteratursøk — forskningssok». Den sier nå
  «Forskningssøk — Lauvasdata».
- Wordmarken viste intern slug sammen med produktnavnet. Den viser nå bare
  produktnavn og husnavn.
- Om-panelets produktnavn følger samme offentlige navn.

## Gjenstående brand-arbeid

- Den statiske frontend-en kopierer Fjordstein-tokenene i stedet for å hente en
  delt pakke. Det er akseptabelt for v1, men bør få en kontroll mot kanonisk
  tokenfil før v2.
- Faviconen er en lokal enkel sirkel, mens wordmarken har et eget bladmerke.
  Dette bør avgjøres som en bevisst huslogo eller erstattes med en kanonisk
  appvariant; det endres ikke automatisk.
- En nettleserregresjon bør kontrollere lys/mørk modus, fokus, lesbarhet,
  dossier-overlay og eksportknapper visuelt.

Branding er dermed ryddet på produktnavn og synlig avsender. Logo- og
tokenpakkeendringer venter på en eksplisitt husbeslutning.
