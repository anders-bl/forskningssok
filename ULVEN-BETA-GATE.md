# Ulven-beta: inngangskriterier

Dette er sjekklisten før Ulven får teste Forskningssøk. Den skiller en trygg
lesetest fra funksjoner som krever arbeidsrom og bruker-eierskap.

## Må være på plass før første lesetest

- Ulven har en fungerende tilgangsvei til `forskningssok.lauvasdata.no`.
  Velg én mekanisme og verifiser den med en ekte nettleserøkt: Basic Auth med
  eget testcredential eller ForwardAuth med ferdig portalinvitasjon.
- `/health` og `/api/status` er kontrollert gjennom samme tilgangsvei som
  brukeren får. Vi må kjenne versjon og bygg for akkurat den deployen.
- En smoke-test dekker søk, kildelenke, Om-panelet og eksport av en liten
  litteraturliste.
- AI-proxyen er tilgjengelig for dossier, syntese og retningssamtale. Et
  utilgjengelig AI-lag skal gi en synlig utilgjengelig-tilstand, ikke et tomt
  eller tilsynelatende ferdig resultat.
- Det finnes én avtalt kanal for tilbakemelding med søk, tidspunkt, funksjon og
  eventuell `releaseId`. Ikke be Ulven gjengi private credentials i rapporten.

## Lesetestens scenarier

Kjør disse i rekkefølge og lagre både resultat og feiltilstand:

1. Et kjent fagspørsmål med treff fra Europe PMC.
2. Et spørsmål som bør hente gråtekst fra CORE.
3. Et bredt spørsmål som viser rangering, evidensnivå og kildefordeling.
4. Et spørsmål uten treff. Det skal stå «ingen treff», ikke «tjenesten feilet».
5. Et spørsmål med feil art eller homonym. Det skal synliggjøre domeneadvarsel.
6. Dossier over et lite treffsett. Kontroller kildehenvisning på hver påstand,
   fjernet-tekst-advarsel og at dossierinnsikt kan vises uten ny syntese.
7. Syntese-fortelling og retningssamtale. Kontroller at de er merket som
   LLM-syntese over hentede kilder.
8. Semantisk kart, citation-gap og eksport til minst ett tekstformat.

Fra smartsøk skal i tillegg ett eksplisitt forskningsspørsmål rutes til
Forskningssøk, mens en vanlig tvetydig spørring ikke skal rutes dit. Test også
forskjellen mellom tomt forskningssvar og oppstrømsfeil.

## Skal ikke inngå i første test

Sitatbank, dokumenter, varme, kommentarer og deling skal ikke brukes med ekte
arbeidsdata før arbeidsrommodellen er på plass. v1 har én delt database; dette
er en kjent begrensning, ikke en skjult flerbrukerløsning.

Varsler og automatiske kjøringer er heller ikke en del av første test. De
krever en egen leveringskanal og idempotent kjøringshistorikk.

## Godkjenningsport

Betaen kan gå videre når:

- alle lesescenariene har et dokumentert resultat eller en ærlig blokkering
- ingen kildehenvisning peker til en ikke-hentet kilde
- dossier/syntese aldri viser et ferdig grønt svar uten kilder
- smartsøk skiller tomt svar, tjenestefeil og manglende konfigurasjon
- Ulven har en kort arbeidsflyt for å rapportere «dette hjalp» og «dette var
  feil» med nok metadata til å reprodusere søket

Først etter denne porten velger vi om arbeidsrom, deling eller varsler skal være
første funksjonelle v2-leveranse.
