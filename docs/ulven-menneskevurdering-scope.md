# Menneskevurdering for Ulven

Status: scoped forslag, 2026-10-08. Ingen kode eller dataflyt er endret.

## Maal

Gjore det enkelt for Ulven aa si om en syntese hjalp, hva som manglet, og
hvilke kilder som faktisk bar svaret. Vurderingene skal hjelpe oss aa forbedre
brukerreisen og gi sporbare signaler. De skal ikke automatisk bli faglig fasit,
rangeringstrening eller produksjonsgodkjenning.

## Beslutningen vi trenger

Forste leveranse foreslaas som et inline vurderingskort under et vellykket
svar, synlig bare etter at svaret er rendret. Det skal ikke be om vurdering av
alle sok eller hver enkelt kilde. Kildemerking er et valgfritt andre steg fra
kortet.

Det ma velges hvilken flate som eier dette kortet:

- **Forskningssok syntese:** naturlig hvis piloten skal svare pa om akkurat
  denne syntesefunksjonen hjelper. Syntesekallet returnerer tekst, og
  grensesnittet rendrer den i `#syntese-kropp`.
- **Belegg:** naturlig hvis maalgruppen er Ulvens samtalearbeid. Der lagres
  hvert assistentsvar allerede med samtaleeier, status, kilder, modell og
  kildekontroll. Et kort kan knyttes direkte til det assistentsvaret.

Anbefaling: ta et bevisst overflatevalg for implementasjon. Hvis "for Ulven"
betyr Belegg i hans arbeidsflyt, bygg vurderingen der og ikke som en separat
Forskningssok-tilbakemelding. Hvis hensikten er avgrenset evaluering av
Forskningssok-syntesen, behold kortet der og merk tydelig at det ikke dekker
Belegg generelt.

## Hva huset allerede har

| Mekanisme | Hva den kan | Begrensning for Ulven |
|---|---|---|
| Forskningssokets Om-panel | Generell melding med kategori og fritekst; videresendes til Lauvasdata sin cockpit-bjelle | Lite synlig i syntesereisen; sender soketeksten som kontekst; ikke knyttet til et bestemt svar eller kildesett |
| Citation-gap-kandidatvurdering | Relevant, irrelevant eller uavklart | Kun `sessionStorage`; ikke varig og vurderer kandidaten, ikke syntesens nytte |
| Syntesens maskinelle kontroll | Sjekker kildehenvisninger og maaler kilde-/paastandsegenskaper | Ikke en menneskelig kvalitetsdom; lokal kvalitet er ikke det samme som brukerens nytte |
| Lokal relevans- og korpusevaluering | Manuelle vurderinger, evalueringsprober og dokumentert holdout-protokoll | Flere artefakter er eksplorative, gjenbrukte eller ikke blinde; ikke en lopende feedback-kanal |
| To-vurderer-protokoll for banken | Frosne sporsmaal, to uavhengige blinde vurderere, holdout og bevaring av uenighet | Riktig for kvalitetspastander, for tungt for daglig bruk |
| Lauvasdata `DemoFeedback` | Varig databasepost, admin-innboksvarsel, markering som lest | Offentlig endepunkt, generell meldingsmodell og en varslingsrad per innsending; ikke egnet som strukturert klikktelemetri uten vurdering av modell og rate-limit |
| Belegg Review / Kunnskapsvarme | Kildesok, kildekontroll, metadata og dekning fra lagrede Reviews | "Review" er ikke en menneskelig kvalitetsgodkjenning. Kunnskapsvarme oppsummerer maskinelle Review-metadata; den er ikke Ulvens dom over svaret |
| M9 intern feltprove | To virkelige Belegg-svar observert, med spesifiserte oppgaver om kilderelevans og forstaelighet | Dokumentasjonen sier at Anders' vurdering av de forste fem kildene og forstaelighet ikke ble registrert; dette er ikke lukket som menneskevurdering |

Kildelesning: `frontend/index.html`, `api.py`,
`docs/bank-korpus-neste-steg.md`, `docs/bank-korpus-bruksmuligheter.md`,
`docs/mistral-bank-kalibrering-oppgave.md`, `UIX-STATUS.md`,
`ULVEN-BETA-GATE.md`, samt Lauvasdata `backend/app/models.py`,
`backend/app/routers/demo.py` og `backend/app/ratelimit.py`.

## Brukerreise

1. Ulven ber om syntese over et sok og faar et faktisk svar.
2. Etter svaret ser han et lite, rolig kort: **Hjalp dette deg?**
3. Ett trykk registrerer `Ja`, `Delvis` eller `Nei`. Ingen kommentar er pakrevd.
4. Ved `Delvis` eller `Nei` vises valgfrie grunner: `Mangler direkte kilde`,
   `Feil aspekt`, `For generelt`, `Feil eller utdatert`, `Fant bedre selv`,
   `Annet`.
5. `Vurder kildene` aapner en valgfri, kompakt liste over kildene som faktisk
   ble brukt. Hver kilde kan merkes `Direkte stotte`, `Nyttig bakgrunn`,
   `Ikke relevant` eller `Uavklart`. Ulven kan hoppe over hele listen.
6. Fritekst er valgfritt og begrenses til en kort kommentar. Etter innsending
   vises en enkel kvittering og mulighet til aa endre vurderingen.

Kortet skal ikke bruke stjerner eller en generell karakter. De skjuler om
problemet var nytte, dekning, kildebruk eller korrekthet. Kategoriene over gir
baade ett-trykksbruk og forklarende signal uten aa kreve en lang rapport.

## Datakontrakt

Minimal vurderingspost:

```json
{
  "schema_version": 1,
  "run_id": "opaque-random-id",
  "surface": "syntese",
  "rating": "partial",
  "reason": "missing_direct_source",
  "source_ratings": [{"source_id": "opaque-id", "rating": "background"}],
  "comment": null,
  "include_query": false,
  "created_at": "server timestamp",
  "build_id": "build identifier"
}
```

Verdiene skal valideres mot faste enum-er; tekstlengde skal ha tak. `run_id`
skal vaere tilfeldig og ikke utledet fra soketekst, Ulvens navn, cookie eller
IP. `source_id` viser bare til et stabilt, pseudonymisert id-sett for dette
svaret. Lagre ikke syntesetekst, abstracts, full sporring eller kildeinnhold i
vurderingsposten. Hvis vi senere trenger aa inspisere noyaktig hva Ulven saa,
maa det behandles som en separat, eksplisitt evidensmodus med egen lagring,
tilgang, retensjon og samtykkebeslutning.

`include_query` skal starte som `false`. Dersom Ulven aktivt ber om at
sporringen folger med, vises teksten for innsending og det forklares hvem som
kan lese den. Ikke legg query i analytics, URL, serverlogg eller generell
feedback-kontekst som en skjult bieffekt.

## Lagring og integrasjon

Ikke send hvert klikk til `/api/tilbakemelding` slik det staar i dag:
endepunktet videresender en melding til et offentlig, uautentisert portal-API
og skaper en cockpit-varsling. Det er passende for en kommentar eller feilrapport,
men ikke for lavterskel vurderinger.

Foretrukket leveranse for pilot:

- Et nytt, separat, validert endepunkt i Forskningssok for strukturerte
  vurderinger, med samme portaltilgangsgrense som appen.
- Ingen persistens i den delte Forskningssok v1-databasen, sitatbank eller
  brukerarbeidsdata. Persistens ma avklares foer en reell pilot samler data.
- For lokal UX-prove kan vurderingen ligge i nettleseren uten konto og uten
  nettverkskall. Dette er ikke et analysemateriale eller holdbart resultat.
- For varige pilotdata: velg eksplisitt eiertabell/-tjeneste, admin-lesetilgang,
  sletting/retensjon, eksport og redigeringsstrategi. Ikke gjenbruk
  `DemoFeedback` uten aa avklare varslingsstoy, struktur og tilgang.
- Idempotens: en innsending per `run_id` og eventuell kilde; ny innsending
  oppdaterer den forrige vurderingen i stedet for aa lage en ny rad per klikk.
- Rate-limit, servervalidering, CSRF-/auth-moenster, storrelsesgrenser og
  audit av admin-tilgang ma folge eiertjenestens konvensjoner.

### Hvis kortet legges i Belegg

Belegg har en bedre naturlig relasjon enn generell demo-feedback: assistent-
meldingen eies av en samtale som allerede er scopt til bruker, og metadataene
inneholder kilder, modell og kildekontroll. Rating bor likevel ligge i en egen
tabell/rute med fremmednokkel til assistentmeldingen, unikhet per
bruker+melding, og samme eierskapskontroll som `_samtale_for_bruker`. Ikke
skriv rating inn i meldingsteksten eller Review-metadataene. Dermed kan svaret
vises og endres uten at brukervurdering forveksles med systemets analyse.

Dette valget krever Lauvasdata som eierrepo og migrasjon, admin-/brukerlesemodell,
sletting sammen med samtalen, og retensjonsregel. Belegg lagrer allerede
samtaleinnhold; rating er et nytt personrelatert felt og skal ikke arve dette
som stilltiende samtykke eller uten tidsgrense.

## Sikkerhet, personvern og forventningsstyring

- Kortet sier tydelig at vurderingen brukes til aa forbedre Forskningssok.
- Ingen skjult identifikator for Ulven; ved behov for oppfolging ber skjemaet
  ham frivillig legge igjen kontaktinformasjon separat.
- Ikke be om eller invitere til helseopplysninger, konfidensielle bedriftsdata
  eller upubliserte forskningsdata i kommentarfeltet.
- Minimer tekstfeltet og vis en kort personvernlinje ved kortet.
- Sett retention foer persistent pilot; slett eller anonymiser naar perioden
  er utlopet. Ingen evig historikk som standard.
- Ikke bruk enkeltvurderingen til aa rangere eller profilere Ulven.
- Vis ingen admin- eller modellintern terminologi i kortet.

## Hva en vurdering betyr

`Ja/Delvis/Nei` er selvrapportert nytte. Kildeetikettene beskriver Ulvens
opplevde forhold mellom kilde og svar. Begge deler er produktfeedback. De
beviser ikke at et faktum er sant eller at en kilde faktisk underbygger en
paastand.

Bruk tre separate evidensnivaa:

1. **Brukssignal:** ett trykk fra Ulven; kan brukes til aa finne friksjon og
   prioritere forbedring.
2. **Saksreview:** Ulven eller en fagperson vurderer konkrete svarpaastander
   mot kildepassasjer; lagres per sak med begrunnelse.
3. **Kvalitetsevaluering:** frosset, balansert pakke med uavhengige blinde
   vurderere og urort holdout. Bare denne typen kan stotte sammenlignende
   kvalitets- eller kalibreringspastander.

Ikke slaa disse nivaaene sammen i ett prosenttall. Ikke juster terskler,
profil, prompt eller korpus automatisk fra Ulvens feedback.

## Pilotdesign

### Fase A: prototype uten lagring

- Sett kortet under syntesen; ingen kort ved feil, tomt svar eller manglende
  kilder.
- Test tastatur, skjermleser, mobil, sendingstilstand, dobbeltklikk og
  endring/angre.
- Bruk syntetiske/publicerte sporsmaal. Ingen ekte delte arbeidsdata.
- Lokal UX-kvittering; ingen datainnsamling.

### Fase B: avgrenset Ulven-feltprove

Gaa bare videre etter at faktisk innlogget Forskningssok-reise og persistens-
eier er avklart. Be Ulven prove kortet paa 8-12 synteser som dekker:
direkte dekning, nyttig bakgrunn, manglende dekning, irrelevant/nabotreff og
teknisk feil. Dette er et bekvemmelighetsutvalg for produktlaring, ikke en
statistisk evaluering. Han kan stoppe eller hoppe over naar som helst.

For hver prove registreres bare om syntesen ble fullfort, om kortet ble vist,
valgt hovedvurdering, frivillig grunn, build og dato. Sporring og fritekst er
av som standard. Ikke be Ulven bruke 8-12 identiske eller kunstige oppgaver;
bruk realistiske oppgaver han selv velger innenfor avtalt dataramme.

Det finnes allerede en M9 Belegg-prove i
`../lauvasdata/docs/ulven-belegg-feltprove-preflight.md`. Den dokumenterer to
svar i en innlogget okt, men oppgir eksplisitt at menneskelig relevansvurdering
av de fem forste kildene, forstaelighetsvurdering og avvist-konto-sjekk ikke er
registrert/lukket. Lukk eller erstatt disse konkrete observasjonshullene forst;
ikke start en ny generell feltprove og tell samme to svar som uavhengig data.

### Fase C: faglig kvalitetssjekk

Hvis maalsettingen blir aa hevde at syntesen eller bankbakgrunnen forbedrer
faglig korrekthet: bruk eksisterende protokoll i
`docs/bank-korpus-neste-steg.md`. Frys sporsmaal og fasit foer modellkall,
hold tidligere prober utenfor holdout, faa to fagkyndige til aa vurdere
uavhengig og blindt, bevar uenighet og rapporter enkeltsaker, feilede og
tomtreff. Ingen terskel- eller produksjonsendring foelger automatisk.

## Maal og beslutningsporter

For brukerreisen rapporteres kun beskrivende maal:

- synteser som ble fullfort, kortvisninger, svarrate og fordeling Ja/Delvis/Nei;
- grunner ved Delvis/Nei;
- andel kildevurderinger som er direkte stotte/bakgrunn/irrelevant/uavklart;
- tekniske sendefeil, dobbeltinnsendinger og endrede vurderinger;
- kvalitativ oppsummering av frivillige kommentarer.

Ikke presenter svarrate som representativ kvalitet. Ikke tolk fravaer av
feedback som tilfredshet. Ingen minste prosent eller automatisk gate foreslaas
foer vi har observert bruken. En beslutning om bredere utrulling krever
gjennomgang av faktiske tilfeller og personvern-/lagringsopplegg.

## Akseptkriterier for foerste implementasjon

- Kortet vises kun etter et ferdig, ikke-tomt syntesesvar og kildegrunnlag.
- Ett trykk kan sendes uten kommentar; Delvis/Nei-grunner er valgfrie.
- Kildegjennomgang er lukket som standard og bare viser kilder brukt i svaret.
- Query, answer, abstracts, navn og IP sendes ikke i vurderingspayload som
  standard.
- Brukeren faar korrekt status ved lagring, feil, gjentak eller endring.
- Ingen feedback-klikk lager en generell cockpit-varsling.
- Tilgjengelighet, mobilvisning, validering, rate-limit, auth og
  idempotens er verifisert foer persistent pilot.
- Testene dekker lokal rendering og API-kontrakt, men produksjonsbruk er ikke
  kalt verifisert foer innlogget smoke er kjoert.

## Avhengigheter og menneskelige avgjoerelser

Foer persistent feltprove trengs avklaring paa:

1. Om forste pilot kun vurderer syntese, slik dette forslaget anbefaler.
2. Om Ulvens vurderinger kan lagres varig og hvem som faar lese dem.
3. Retensjon og sletting av strukturerte vurderinger og eventuelle kommentarer.
4. Om sporring noen gang kan inkluderes eksplisitt; anbefalt start er nei.
5. Om Ulven skal vurdere hver brukt kilde eller kun frivillig et utvalg; anbefalt
   start er valgfritt utvalg / ingen krav.
6. Hvem som gjennomfoerer en eventuell blind faglig review; det er ikke
   automatisk Ulven alene.

Dette er produkt- og styringsvalg. ADR/FDR-ratifisering og eventuell
produksjonsaktivering krever Anders' beslutning.

## Kilder og gjeldende hull

- `frontend/index.html`: syntese blir rendret i `#syntese-kropp`; eksisterende
  feedback sender soketekst i context; gap-vurdering bruker sessionStorage.
- `api.py`: `/api/syntese` returnerer syntesen; `/api/tilbakemelding`
  videresender generell feedback til portal.
- Lauvasdata `DemoFeedback`: lagrer fritekst/context og sender admin-bjelle;
  offentlig endepunkt har rate limit.
- `UIX-STATUS.md`: Forskningssok v1 har delt database og ingen flerbruker-/
  arbeidsromseierskap; gap-vurderinger er bare sessionlokale.
- `ULVEN-BETA-GATE.md`: innlogget produksjons-smoke er ikke verifisert i
  siste dokumenterte kontroll.
- Lauvasdata `frontend/src/pages/LunaPage.jsx` og `backend/app/routers/luna.py`:
  Belegg viser kilder og lagrer assistentsvar med samtaleeier, Review-metadata,
  modell og kildekontroll. Det er en mulig vurderingsflate med melding som
  relasjonsnokkel, men ingen menneskelig svarrating ble funnet i gjennomgangen.
- Lauvasdata `frontend/src/components/LunaKnowledgePulse.jsx` og
  `backend/app/routers/luna.py`: Kunnskapsvarme bygger pa automatisk Review-
  metadata fra de siste 90 dagene; ikke en menneskevurdering.
- Lauvasdata `docs/ulven-belegg-feltprove-preflight.md`: M9 er delvis; konkrete
  vurderinger av toppkilder og forstaelighet gjenstar. Kristian sin M10-prove
  er dokumentert som ventende i sist gjennomgatt preflight.
- `docs/bank-korpus-neste-steg.md` og
  `docs/mistral-bank-kalibrering-oppgave.md`: menneskelig blindvurdering og
  holdout-kontrakt for faglige kvalitetspastander.

Produksjonsversjon, Ulvens faktiske tilgangsrolle, portalens gjeldende
retensjonspraksis for DemoFeedback og om en egnet eiertabell finnes er ikke
verifisert her. Live-tilgang til Ulvens nettleserflate er heller ikke kontrollert
i denne gjennomgangen.
