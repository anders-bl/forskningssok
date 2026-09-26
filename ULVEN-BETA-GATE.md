# Ulven-beta: inngangskriterier

Dette er sjekklisten for en trygg, innlogget lesetest av Forskningssøk. Den
skiller lokal kodeverifikasjon fra kontroll gjennom Ulvens faktiske
tilgangsvei. Status sist gjennomgått 2026-09-24.

## Status

Den lokale Forskningssøk-suiten har 715 beståtte tester, inkludert reelle
Chromium-løp for desktop og mobil med isolerte API-fixtures. Portalens backend har
1682 beståtte og 44 hoppede tester. Portalens frontend har 243 beståtte
enhetstester og 25/25 beståtte Playwright-tester, hvorav 12 dekker
Ulven/Luna-integrasjonen. TypeScript-sjekk, produksjonsbygg og lokale
sikkerhetsskann bestod. Disse verifiserer kode og portalintegrasjon; de
verifiserer ikke en innlogget Forskningssøk-økt i produksjon.

Portalens samlede `gate_runner.py` ble ikke fullført: den stoppet før
migreringstesten fordi `backend/.env` manglet. Backendens komplette pytest-suite
ble kjørt separat med isolerte testverdier og bestod. Lokal database-migrering
via gate-runneren er dermed ikke målt.

Ved live-kontroll 2026-09-24 svarte `/`, `/health`, `/api/status`, `/api/versjon`
og `/api/profil` alle `401 {"detail":"Ikke autentisert"}` uten
`WWW-Authenticate: Basic`. Det bekrefter at produksjonsdomenet krever portal-
sesjon; ForwardAuth er aktiv ifølge samme signatur som appens auth-middleware.
Autentisert sjekk ble ikke mulig fra denne økten. Produksjonsversjon/build,
innlogget lesereise og ekte AI-proxy-kall er derfor fortsatt umålt.

Lokal container-smoke 2026-09-24 bygget image med runtime-bygg `1c0f2fc9`.
`/health/live`, `/api/versjon`, `/api/profil` og `/api/status` svarte 200.
Kildestatus pinget Europe PMC, Europe PMC-referanser, OpenAlex, CORE og
Crossref; alle fem var nåbare. Ett offentlig søk mot Europe PMC og CORE ga tre
viste treff, og 32 kandidater ble cachet. Embedding-endepunktet var en lokal
1024-dimensjonal kontraktsmock, ikke produksjonens AI-proxy. Med mocken svarte
`/health/ready` 200 etter søket. Før søket svarte readiness 503 fordi den
isolerte, ferske cachen var tom, som forventet.

| Kontroll | Lokal verifikasjon | Innlogget produksjon |
|---|---|---|
| Autentisering og tilgang | Uautorisert 401 bekreftet | Aktiv portaløkt mangler |
| `/health` og `/api/status`, versjon/build | Image-build `1c0f2fc9`, lokal health/status/profil målt | Ikke målt via innlogget tilgangsvei |
| Søk, treff, kildelenke, Om og eksport | Nettleserreise + ekte Europe PMC/CORE-søk i lokal container | Ikke målt som samlet innlogget økt |
| Tomt svar mot oppstrømsfeil | Nettleser-fixture for begge tilstander | Ikke målt |
| AI-proxy for dossier/syntese/retningssamtale | Feilsti i nettleser og embedding-kontrakt med lokal mock | Ikke målt med produksjonsproxy |
| Forskningsspørsmål-handoff | `?q=`-handoff testet i lokal Forskningssøk-nettleser | Ikke målt i produksjon |
| DOI-handoff fra Luna | Eksakt treff og manglende treff dekket av portalens Playwright-mock | Ikke målt i produksjon |
| Sitatbank til dokument | Dra til Dokument-fanen oppretter/åpner dokument og autolagrer `[@sitat:ID]` i lokal nettleser | Ikke målt i produksjon |

Forskningssøkets lokale nettlesertest dekker også tomt svar mot kildefeil; den
verifiserer at forrige artikkel, revisjonsspor og dossierhandlinger fjernes ved
nytt søk. Den dekker papirvalg, gap-fane,
dossierinnsikt, synlig AI-proxy-feil, forskningsspørsmål-handoff via URL, og dra-og-slipp av sitat med lagring som `[@sitat:ID]`. Den dekker også Markdown-
nedlasting og mobilens horisontale overflow. Nettleser-fixtures verifiserer
ikke eksterne kilder eller produksjonskonfigurasjon.

Dermed er betaen teknisk klar for en avgrenset gjennomgang, men den første
innloggede live-smoken gjenstår før lesetesten kan godkjennes. En 401 uten
sesjon er ikke bevis på at innloggingsbanen virker.

## Før første innloggede lesetest

- Åpne `forskningssok.lauvasdata.no` gjennom den faktiske portaltilgangen. Live-
  kontroll fant ForwardAuth aktiv og ingen Basic Auth-utfordring. Kontoen må ha
  `app_access="forskningssok"`; nettlesertestenes mockbruker er ikke en
  produksjonskonto.
- Gjennom samme økt: kontroller `/health` og `/api/status`, og noter versjon og
  build som faktisk kjører.
- Prøv et søk, åpne en kilde, kontroller Om-panelet, og eksporter en liten
  litteraturliste.
- Prøv dossier, syntese og retningssamtale. AI-utilgjengelighet skal vises som
  en tydelig tilstand, ikke som tomt eller ferdig resultat.
- Noter resultat og feiltilstand for scenariene under. Bruk syntetiske eller
  offentlige spørsmål og ikke legg credentials i rapporten.

## Lesetestscenarier

Kjør disse i rekkefølge og noter resultatet, tidspunktet, funksjonen og
eventuell release/build:

1. Et kjent fagspørsmål med treff fra Europe PMC.
2. Et spørsmål som bør hente gråtekst fra CORE.
3. Et bredt spørsmål som viser rangering, evidensnivå og kildefordeling.
4. Et spørsmål uten treff. Det skal stå «ingen treff», ikke «tjenesten feilet».
5. Et spørsmål med feil art eller homonym. Kontroller domeneadvarselen.
6. Dossier over et lite treffsett. Kontroller kildehenvisning på hver påstand,
   fjernet-tekst-advarsel og at dossierinnsikt kan vises uten ny syntese.
7. Syntese-fortelling og retningssamtale. Kontroller at begge er merket som
   LLM-syntese over hentede kilder.
8. Semantisk kart, citation-gap og eksport til minst ett tekstformat.

Fra smartsøk skal et eksplisitt forskningsspørsmål rutes til Forskningssøk,
mens en vanlig tvetydig spørring ikke skal rutes dit. Kontroller også forskjell
på tomt forskningssvar og oppstrømsfeil.

## Tilbakemelding

Portalens demooverflate har et fungerende tilbakemeldingsskjema. Det sender
demo, kategori, melding og eventuell kontaktinformasjon til demo-feedback.
Skjemaet ber ikke direkte om søk, funksjon eller releaseId. Ved rapportering
bør Ulven derfor oppgi hvilket offentlig/syntetisk søk og hvilken funksjon det
gjaldt, samt omtrent tidspunkt og build dersom den er synlig. Ikke ta med
private credentials eller sensitivt arbeidsmateriale.

## Avgrensning for data

Sitatbank, dokumenter, varme, kommentarer og deling skal ikke brukes med ekte
arbeidsdata før arbeidsrom- og brukereierskap er innført. Forskningssøk v1 har
én delt database; vurderinger av gap-kandidater er dessuten kun lagret i
nettleserens `sessionStorage`. Atelierets historiske/underlenkede spor er
prototypiske og bygger på eksempeldata, ikke en live kildeanalyse. Merk dette
tydelig i demoen.

Varsler og automatiske kjøringer er heller ikke del av første test. De krever
egen leveringskanal og idempotent kjøringshistorikk.

## Godkjenningsport

Betaen kan godkjennes når:

- alle lesescenariene har et dokumentert resultat eller en ærlig blokkering
- ingen kildehenvisning peker til en kilde som ikke er hentet
- dossier/syntese ikke viser et ferdig svar uten kilder
- smartsøk skiller tomt svar, tjenestefeil og manglende konfigurasjon
- Ulven kan rapportere hva som hjalp eller feilet med nok metadata til å
  gjenskape forløpet

Etter denne porten kan vi velge om arbeidsrom, deling eller varsler skal være
første funksjonelle v2-leveranse.
