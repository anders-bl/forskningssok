# Forskningssøk v2

Dette dokumentet beskriver neste iterasjon etter `VERSJON = 1.0.0`. v1 er
produksjonsversjonen og skal kunne stå stabilt mens v2 bygges trinnvis. Lokal
testsuite består av 679 tester (`venv/bin/python -m pytest -q`, 2026-09-20).

UIX-statusen med levert og utestående flatearbeid står samlet i
[`UIX-STATUS.md`](UIX-STATUS.md).

## Hva v1 allerede leverer

v1 har søk fra Europe PMC og CORE, domeneprofil, rangering, revisjonsspor,
evidensmerker, citation-gap, semantisk kart, dossier, syntese-fortelling,
retningssamtale, egne PDF-er, sitatbank, dokumenteditor og eksport. Den er
deployet bak autentisering. Live-versjonen er ikke kontrollert i denne økten
fordi endepunktene krever credentials.

## v2-prinsipp

Vi bygger først det som gjør forskningsarbeidet delbart og målbart. Nye kilder
og mer AI kommer etter at identitet, sporbarhet og kvalitetsmåling er på plass.
Ingen v2-funksjon skal gjøre råkilder, AI-syntese og brukerens egne notater
vanskeligere å skille.

Smartsøk og dossier hører begge til i v2, men på ulike nivåer:

- **Smartsøk** er husets inngang og ruter eksplisitte forskningsspørsmål til
  Forskningssøk. Det skal ikke kopiere eller omskrive forskningsresultater.
- **Dossier** er et brukerinitiert forskningsprodukt over et avgrenset sett
  kilder. Det skal beholde kildehenvisning, modellspor og status helt fram til
  eksport.

## Arbeidspakker i rekkefølge

### 1. Arbeidsrom og eierskap

v1 bruker én delt database. V2 trenger en bruker-/arbeidsromsmodell før
kommentarer, sitatbank, dokumenter og varme kan deles trygt.

Første leveranse:

- identitet på arbeidsrom og bruker i alle brukerrelaterte tabeller
- migrering som beholder eksisterende v1-data i et eksplisitt arbeidsrom
- tilgangskontroll i API-et og en enkel arbeidsromvelger i flaten
- tester for isolasjon, deling og sletting

Port: ingen automatisk flerbruker-deploy før en test kan vise at bruker A ikke
leser eller endrer bruker B sine sitater, dokumenter eller varmedata.

### 2. Varsler som arbeidsflyt

Automatiske varsler er neste produktlag etter arbeidsrommet: nye studier,
siteringer og endringer i et tema. Varsler skal være observerbare og
idempotente, ikke bare en cron-jobb som sender e-post.

Første leveranse:

- lagrede søk med eier, frekvens og kanal
- planlagt kjøring med kilde- og cache-status i hvert varsel
- deduplisering på papir og kjøring
- lesbar historikk over sendt, hoppet over og feilet
- én leveringskanal først; flere kanaler krever eget behov

Port: en simulert kjøring skal kunne gjentas uten doble varsler og uten å skjule
oppstrømsfeil.

### 3. Kvalitetsmåling for søk og syntese

`evaluer.py` finnes lokalt, men er ikke deployert og mangler en fast, versjonert
evalueringspakke. V2 skal måle rangering og syntese mot forhåndsregistrerte
kontroller, med modell- og kildeversjon i resultatet.

Første leveranse:

- et lite, håndkontrollert sett med søk og relevante/irrelevante kontroller
- blind relevansdom med positiv kontroll og tydelig ugyldig-status
- måling av kildeunion, dekningsforbehold, deduplisering og cache-alder
- resultatartefakt som kan sammenlignes mellom bygg
- separat måling av rå søk, dossier og syntese-fortelling

Port: ingen rangering eller prompt justeres etter én kjøring; terskler og
kontroller registreres før målingen.

### 4. Smartsøk som stabil forskningsruting

Smartsøk i portalen har allerede en eksplisitt forskningskanal og holder
forskning adskilt fra innover, utover og verifisering. V2 skal gjøre denne
integrasjonen mer operasjonell:

- felles request-id fra smartsøk til Forskningssøk og tilbake
- synlig kilde-, cache- og oppstrømsstatus i seksjonen
- tydelig skille mellom «ingen treff», «tjenesten svarte ikke» og «ikke
  konfigurert»
- revisjonsspor som peker på samme søk uten å deponere en ny kopi ved hver
  forespørsel

Port: en simulert feil i Forskningssøk skal gi en ærlig, avgrenset
forskningsseksjon og aldri bli vist som «ingen treff» i smartsøk.

### 5. Dossier som sporbar arbeidsprodukt

Dossier, syntese-fortelling, retningssamtale og dossierinnsikt finnes allerede
som brukerinitierte funksjoner. Dossier-endepunktet gjør i dag et kostbart kall
og returnerer et ferdig svar; neste iterasjon bør gi det en egen livssyklus:

- jobbstatus (`venter`, `kjører`, `ferdig`, `feilet`) med idempotent nøkkel
- lagring av søk, kildesett, prompt-/modellversjon og verifikasjonsresultat
- separat mekanisk innsikt (M1–M4) som kan lastes uten å kjøre syntesen på nytt
- eksplisitt markering av påstander som ble fjernet fordi kildehenvisningen
  ikke kunne verifiseres
- eksport som peker på nøyaktig dossierutgave, ikke bare emnet

Port: et dossier som feiler eller mangler kilder skal ikke kunne se ferdig og
verifisert ut, og en ny visning skal ikke starte samme kostbare jobb på nytt.

### 6. Kilde- og tilgangsforbedringer

Når de tre første arbeidspakkene er stabile, kan vi prioritere neste kilde,
betalte kilder og bedre fulltekst. DisCoCat-sitasjonsgraf og fulltekst-mining
står fortsatt på vent fordi dagens datagrunnlag ikke bærer påstandene.

Mulige kandidater vurderes med samme port:

- kilde-liveness og lisens/tilgang må vises i svaret
- CORE/Europe PMC/OpenAlex må kunne feile hver for seg uten stille tap
- ny kilde må ha en egen evalueringsprobe før den får påvirke rangeringen

## Ut av v1 før v2

Utkast-endepunktene og eldre skriveflatekode ligger fortsatt i backend, mens
flaten nå har dokumenteditor og sitatbank. Før arbeidsrom bygges skal vi ta en
eksplisitt beslutning om hvilke gamle endepunkter som skal beholdes,
avskrives eller få en ny kaller. De skal ikke få ny funksjonalitet i mellomtiden.

## Første konkrete sprint

1. Kartlegg tabeller og API-kall som bærer brukerdata.
2. Skriv migreringsskisse for arbeidsrom og eksisterende delt database.
3. Lag isolasjonstester før schemaendring.
4. Registrer en fast evalueringspakke for rangering, smartsøk-ruting og dossier
   parallelt, uten å koble den til produksjonsflyten.
5. Skisser dossier-jobbkontrakten før vi gjør endepunktet asynkront.

V2 får først egen versjonsbump når arbeidspakke 1 har en gjennomtestet
migrering og produksjonsobservasjon. Fram til da er `1.0.0` den gjeldende
produktkontrakten.
