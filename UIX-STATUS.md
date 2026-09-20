# UIX-status for Forskningssøk

## Levert i v1

Følgende UIX-planer er gjennomført og beskrevet i historikken:

- Fjordstein-basert skall med søk, treffliste, leseflate og relasjonspaneler.
- Ett arbeidsrom med sammenleggbar skuff i stedet for en Les/Skriv-modusbryter.
- Sitatbank med løse sitater, dokumentlinse og innsetting som egen sitat-node.
- Varme-panelet med tydelig skille mellom varig interesse og aktuell nærhet.
- «Om»-panel med metodikk, kildegrenser og profilinformasjon.
- Fanegruppering og forklaringstekst for Lignende, Kart, Gap og Sti.
- Dossier, syntese-fortelling, retningssamtale og fremdriftsindikator.
- Kildekart med kildefarge, siteringsstørrelse, tooltip og label-kontroller.
- Eksportknapper for rå kildesamling og rapporter.

Dette er verifisert gjennom 679 backend-/kontrakttester og flere manuelle
nettleserverifiseringer. Det er ikke det samme som en permanent UI-regresjonstest.

## Åpent

### Første UIX-sprint

1. **Nettleserregresjon for hovedreisen**
   
   Automatiser: åpne appen, søk, åpne papir, bytt fane, åpne dossier, vis
   innsikt, lukk overlay og eksporter. Test også tomt svar og oppstrømsfeil.
   Dette er den viktigste mangelen før Ulven får en gjentakbar beta.

2. **Dra-og-slipp fra sitatbank til dokument**
   
   Klikkinnsetting fungerer. Dra-og-slipp er fortsatt uttrykkelig ikke bygget.
   Det må bruke samme sitat-node og samme lagring som klikk, ellers får vi to
   identitetsveier.

3. **Rik tekst i PDF**
   
   Editorens grunnlag er på plass, men fet/kursiv i PDF er fortsatt
   markdown-lite og ikke ferdig. Avklar hvilke TipTap-markeringer som skal
   overleve i Blokk-modellen før emitteren utvides.

### V2, etter arbeidsrom

4. **Deling av dokumenter**
   
   Deling er ikke en ren frontend-funksjon. Den krever arbeidsrom, eier,
   tilgangsnivå, tilbakekalling og sporbar eksport. Den skal derfor følge
   bruker-/arbeidsromsmodellen i v2, ikke bygges som en offentlig lenke nå.

5. **Dossier som arbeidsflate**
   
   Dossieret har allerede visning, innsikt og graf. Neste UIX-steg er å vise
   jobbstatus, kildegrunnlag, modellutgave og verifikasjonsstatus uten at en ny
   visning starter samme kostbare jobb.

## Ikke UIX-arbeid

Varsler, nye kilder, rangeringsevaluering og flerbrukerlagring er produkt- og
backendarbeid. De skal påvirke UIX gjennom tydelige tilstander og metadata,
men trenger egne arbeidspakker.

## Beta-konsekvens

Ulven kan teste den leverte lesereisen nå når autentisert live-smoke er utført.
Sitatbank og dokumenteditor kan demonstreres med testdata. Ekte deling og
personlige arbeidsdata venter på arbeidsrommodellen.
