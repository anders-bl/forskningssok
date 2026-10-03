# Oppgave: mistral-kalibrering for bank-bakgrunn i prod

Avgrenset oppfølgingsoppgave: etabler en repeterbar Mistral-kalibrering og blind
holdout per godkjent bruksområde, slik at det kan avgjøres om bankbakgrunn kan prøves
i shadow/staging. Oppgaven godkjenner ikke aktivering i PROD; det krever en separat
go/no-go med verifisert runtime, datakilde og rollback-plan. Ikke en blokker for å
lande `integrasjon/bank-full` lokalt.

## Hvorfor den finnes

`bank_bakgrunn.hent_bakgrunn` fail-closer når utdraget er mistral-embeddet uten en
kalibrert relevansterskel (`bank_bakgrunn.py`, `kal`-valget: `None` for mistral-embed).
Grunnen er reell, ikke overforsiktig: MORKT-terskelen kommer fra `bøker/bok_kalibrering.py`
(SKARPT=0.85 / MORKT=0.93), som er sqlite-vec L2 mot **bge-m3**, empirisk 3-bånds,
kalibrert for SETNINGS-queries. Mistral-embed er et ANNET vektorrom: de tallene er
meningsløse der, og å gjenbruke dem ville latt vilkårlig nærmeste-treff se ut som
faglig bakgrunn - nettopp "stille søppel"-klassen modulen er bygget for å vokte.

I prod (`AI_PROXY_URL` satt) brukes bare utdraget, og spørringer embeddes med mistral
via ai-proxy. Utdraget MÅ derfor være mistral-embeddet i prod (kan ikke søkes med
bge-m3-utdrag: kryss-vektorrom). Så terskelen må måles PÅ mistral, ikke lånes.

## Forutsetninger

- JSONL-kilden finnes: `data/bank_utdrag.jsonl` (4732 chunks, lisensgatet).
- Mistral-utdraget bygges i prod med `AI_PROXY_URL` satt fra en komplett, committet
  JSONL + manifest: `python bank_utdrag.py bygg --speil`. Speilmodus verifiserer hash,
  radantall og formatversjon foer den avstemmer det varige volumet.
- Et fiskehelse SETNINGS-query-sett må forfattes OG BEVARES i repoet. FDR-082 sin
  dyreste lærdom var at "de 24 matte-spørringene" aldri ble bevart og måtte
  gjenskapes - ikke gjenta det. Legg settet i `data/` som en committet fil, med
  spørringen ved siden av hvert målte tall.

## Metode (speil glod sin 3-bånds, på mistral)

1. Bygg mistral-utdraget (over).
2. Kjør query-settet mot utdraget (mistral-embed), samle distansefordelingen
   query -> nærmeste chunks.
3. Avled bånd med samme empiriske 3-bånds-metode `scivis/glod.py` brukte for bge-m3:
   SKARPT (korpuset dekker), delvis (tilgrensende), MORKT (ekte gap). Distanse-skalaen
   er mistral sin egen - ikke gjenbruk 0.85/0.93.
4. Lagre tersklene ÉN kilde (parallell `mistral_kalibrering`, samme mønster som
   `bok_kalibrering` - importer, ikke kopier).
5. Bind kalibreringen til en eksakt retrieval-identitet før den kobles inn. Minstekrav:
   snapshotets manifestversjon, SHA-256 og radantall; embedding-endepunkt/modell-ID;
   query- og dokumentprefiks/instruksjon; vektordimensjon og avstandsmetrikken; samt
   chunk-/eksportformat og retrieval-oppsett (inkludert topp-k og filtrering/per-bok-tak).
   Lagre identiteten sammen med tersklene og sammenlign den med det bygde utdragets
   manifestmetadata og aktive søkeoppsett ved hver bruk. Manglende felt eller avvik betyr
   fail-closed. Et flyttbart modellalias er ikke en stabil modellidentitet; hvis leverandøren
   ikke tilbyr en versjonsfestet ID, dokumenter begrensningen og krev ny kalibrering ved
   aliasbytte eller modelloppdatering.
6. Koble inn i `bank_bakgrunn.py` `kal`-valget: bruk `mistral_kalibrering` når
   `bank_utdrag.embed_modell() == "mistral-embed"` og en kalibrering finnes; ellers
   stående fail-closed.

## Drepbare kontroller

Disse kontrollene er nødvendige, men ikke tilstrekkelige for å godkjenne en
terskel. Kontrollspørringene må ha realistisk setningslengde, og fasiten må være satt
før avstandene undersøkes.

- Dekket tema -> `skarpt`: minst én kontroll i et tett dekket tema må havne i
  `skarpt` og hente relevant støtte. Hvis ikke, måles korpus-/chunkdekning og spørsmålet
  justeres før terskelen.
- Off-domene -> `MORKT`: minst én tydelig kontroll utenfor fiskehelse må havne i
  `MORKT` og ikke sende bankchunks videre til syntesen.
- Nabotema -> relevant bakgrunn eller `MORKT`: kontroller som deler ord eller faglig
  kontekst med korpuset, men ber om fakta korpuset ikke dekker, ma vurderes separat.
  De kan ikke automatisk regnes som relevante fordi avstanden er lav.

## Evalueringsdesign og sikkerhetsgrense

Avstandsterskelen er en retrieval-port, ikke en relevansfasit. Nærmeste avstand alene
verifiserer ikke at alle chunkene som sendes videre er nyttige. Banken kan ha flere
brukerreiser. Ikke anta at ett spørsmålssett eller ett kvalitetsmål dekker dem alle.

- Lag først en bruksområdeliste med bruker, inngang, hva banken bidrar med, og hva et
  feiltreff kan føre til. Avklar hvilke bruksområder som faktisk er aktive eller
  planlagt for denne banken; ikke utled dette bare fra kode eller gamle spørsmål.
- Bruk en felles retrieval-del for tekniske mål som nærmeste avstand, topp-k-relevans,
  avvisning og dekning. Lag egne spørsmål, fasit og akseptgrenser per bruksområde.
  Eksempler på ulike mål er direkte faktastøtte, supplerende bakgrunn, relaterte kilder
  for videre lesning og tematiske nabotreff.
- Skill mellom `direkte svar`, `nyttig bakgrunn`, `irrelevant` og `utenfor domene`.
  Et treff som er uegnet som svargrunnlag kan fortsatt være nyttig som lesetips, men
  bare dersom bruksområdet sier det på forhånd.
- For hvert bruksområde, bestem om banken bare supplerer, kan underbygge svar eller
  viser kilder til brukeren. Sett egen toleranse for irrelevans, manglende dekning,
  kildekrav og konsekvens av feil.

- Frys et håndskrevet, målbart sett med søk, tema, forventet dekning og etikett
  før måling. Ikke bruk historiske brukerforespørsler uten eksplisitt godkjenning.
- Spørsmålene fra pilotene i `data/mistral_bank_kalibrering_2026-09-26.json` og
  `data/bank_near_control_experiment_2026-09-26.json` er allerede maalt og gjennomgaatt;
  de kan brukes som utviklings-/sanity-materiale, men ikke gjenbrukes i en blind
  holdout eller omtales som uavhengig validering.
- Del settet i kalibreringsdel og urørt holdout etter tema/faktatype. Nærliggende
  parafraser av samme spørsmål skal bli i samme del. Størrelsen må begrunnes ut fra
  ønsket usikkerhet; et lite kontrollsett gir bare en eksplorativ måling.
- To fagkyndige vurderere merker toppchunkene uavhengig og blindt for modell,
  avstand og terskel. Avgjør uenighet og bevar etiketter og begrunnelser.
- Evaluer faktisk topp-k som går videre: relevans per chunk, andel irrelevante treff per
  spørsmål, dekning og avvisningsrate. Rapporter resultat per tema og samlet;
  skjul ikke lekkasjer bak et godt gjennomsnitt.
- Kjør bank-av/på-sammenligning for hvert bruksområde på fryste vilkår. For syntese,
  blind og randomiser armene; mål faktiske påstander, kilde-/sitatstøtte, irrelevante
  bankkilder og reparasjonskall. For kildelisting eller videre lesning, mål om kildene
  passer til brukerens formål og om relevansbegrensningene vises tydelig. Skill
  faktuell støtte fra generell tekstkvalitet.
- Rapporter intervaller/usikkerhet, alle feilede og tomme kjøringer, cachetreff,
  modell-/korpusidentitet og antall kall. Ikke fjern avvik fra nevneren.

## Akseptkriterier

- `mistral_kalibrering` er en kilde; ingen terskler kopieres fra BGE.
- Kalibreringen er bundet til eksakt retrieval-identitet, og runtime avviser manglende
  eller avvikende snapshot-, modell- eller søkeoppsettmetadata.
- Spørsmålssett, etiketter, målinger, korpus-/modellidentitet og beregningsmetode er
  bevart, slik at målingen kan gjentas.
- Begge drepbare kontroller passerer, og blindvurdert holdout støtter hvert godkjent
  bruksområde. Resultater og go/no-go er separate per bruksområde.
- For bankchunks som skal inn i syntesen er toleranse for irrelevante treff fastsatt
  på forhånd. Holdout har null off-domain-lekkasjer; øvrig feilrate rapporteres med
  usikkerhetsintervall og må ligge innenfor den forhåndsbestemte toleransen.
- Holdout viser at hvert bruksområde oppfyller sine forhåndsbestemte kvalitets- og
  sikkerhetsgrenser. For syntese må dette inkludere udokumenterte påstander og
  irrelevante kilder. Påstått nytte må støttes av blindvurderingen, ikke bare av
  avstandstall.
- Når kriteriene er møtt, kan kalibreringen prøves i shadow/staging med fail-closed
  som tilbakefall. Dette er ikke i seg selv godkjenning til å åpne funksjonen i PROD;
  produksjonsaktivering krever en separat go/no-go med verifisert runtime, datakilde
  og rollback-plan.
- `bank_bakgrunn` beholder fail-closed når kalibrering mangler eller modell-/korpus-
  identitet ikke stemmer. Ingen terskel settes aktiv bare fordi kalibreringssettet
  passerer.

## Forbehold

- Snill mot ai-proxy: minimal live-prøving, bruk fixtures der mulig, respekter
  rate-limits (kalibrering er et bulk-embed - ett pass, ikke en løkke).
- Alternativet (kjøre bge-m3 ende-til-ende i prod) er et større infra-valg, ikke
  denne avgrensede oppgaven.

## Kontroll av eksisterende kode (2026-10-03)

`venv/bin/python -m pytest tests/test_bank_bakgrunn.py tests/test_bank_utdrag.py -q`
består med 28 tester. Dette dekker dagens fail-closed-rute når Mistral-utdraget mangler
kalibrering, men tester ikke kalibreringsmetoden eller et nytt blindt holdout. De tre
pilotfilene er Git-sporet; målespørsmålene der er allerede sett og skal ikke telles som
uavhengig validering.

## Første måling (2026-09-26)

Kjørte én Mistral-passering over hele utdraget: 4 732 chunks / 68 dokumenter, 1 310 853
input-token, 242 API-kall, estimert USD 0,1311 etter publisert pris på USD 0,10 per
million token. Målemetrikken er samme sqlite-vec L2 som søkeveien bruker.

Det foreløpige settet ligger i `data/mistral_bank_kalibrering.json`; alle spørsmål og
målinger ligger i `data/mistral_bank_kalibrering_2026-09-26.json`.

- Dekkede: min 0,395824, median 0,496809, maks 0,517202.
- Fjerne: min 0,618867, median 0,649075, maks 0,686889.
- Gap mellom dekket-maks og fjern-min: 0,101665.
- Oppgitt fasitdokument var nærmeste for 2/10. Denne eksakte dokumentfasiten var for
  streng: manuell gjennomgang av faktisk topp-chunk fant 3 direkte svar, 6 delvise
  bakgrunnstreff og 1 irrelevant treff. Blant annet svarer en annen håndbokchunk direkte
  på nefrokalsinose-spørsmålet.

Avstanden skiller foreløpig dekket fra fjernt i dette settet, og de fleste topp-chunks er
minst nyttig bakgrunn. Det foerste settet manglet tilgrensende kontroller, saa SKARPT og
MORKT kunne ikke deles forsvarlig i tre baand. Den ene irrelevante chunk-en viser ogsaa at
avstandsbånd ikke erstatter relevanskontroll.

## Oppfoelging med nabokontroller (2026-09-26)

Etter foerste maaling ble 10 haandskrevne spoersmaal lagt til. De er naerliggende fiskehelse-
og akvakulturspoersmaal som ber om spesifikke maaleverdier eller metoder korpuset ikke oppgir.
Samme kontrollspoersmaal ble maalt mot hele Mistral- og Nomic-korpuset. Resultat, topp 5 og
manuell vurdering per modell ligger i `data/bank_near_control_experiment_2026-09-26.json`.

Mistral-avstandene var 0.4106-0.5855 for kontrollene, mot 0.3958-0.5172 for dekkede og
0.6189-0.6869 for fjerne spoersmaal. Kontrollene overlapper de dekkede spoersmaalene, men
ikke de fjerne. Manuell vurdering fant 8 delvise bakgrunnstreff og 2 irrelevante for Mistral.
Dette gir en mulig mellomgruppe i dette utvalget, men ikke en blind fasit eller et
tilstrekkelig grunnlag for produksjonsterskler.

Oppfoelgingskjoeringen gjentok ogsaa de opprinnelige Mistral-spoerringene og traff samme
naermeste chunk og avstand. Medianoppsummeringen i foerste rapport var likevel feil: den
brukte oevre midtverdi for ti observasjoner. Medianene er rettet til gjennomsnittet av de to
midterste verdiene; raamalingene er uendret.

Ingen Mistral-terskel er aktivert; prod failer fortsatt lukket. De opprinnelige
akseptkriteriene er ikke oppfylt ennaa.

## Nomic-kontekstrevisjon (2026-09-26)

Alle 4 732 chunks ble sendt gjennom Ollama-koordinatoren med `truncate=false`. Partier som
feilet ble delt til hver enkelt overskridende chunk var identifisert. 4 723 chunks passerte;
ni overskred modellens 512-tokenvindu. `llama-tokenize` mot installert GGUF, med
`search_document:`-prefiks og BOS/EOS, maalte dem til 586-4 103 tokens. Standardoppsettet
`truncate=true` i den forrige Nomic-embeddingpasseringen avkortet dermed disse ni stille.
Ingen av ID-ene finnes i topp-5-resultatene som er lagret fra kalibreringsspoerringene, men
det fulle korpuset er ikke representert uten tap. Detaljer: `data/nomic_context_audit_2026-09-26.json`.

Dette lukker selve maalehullet, ikke modellens egnethet: Nomic maa enten faa en eksplisitt
re-chunkingstrategi eller holdes ute av produksjon. Mistral-beslutningen er uendret.
