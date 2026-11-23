# Lumic og Maskon: offentlig nettsidescan og Kunnskapshullradar v0.1

Status: skrivebordsbasert gjennomgang av offentlig tilgjengelige nettsider og dataregister; ikke en full teknisk SEO-audit eller kundestudie.
Sist kontrollert: 2026-11-23.
Omfang: synlig nettstruktur, produktinformasjon, fagbelegg, buyer journey og mulige eksterne datakilder.
Beslutningseier: Anders. Interne produktfakta og kundedata er ikke tilgangskontrollert eller verifisert her.

## Kort vurdering

Lumic har en tydelig og smal offentlig struktur: hjem, om oss, produkter og kontakt, med seks synlige produktkort og produktsider for manuelle, semi-automatiske, helautomatiske maskiner og bedovelsessystemer. Nettsiden formidler skreddersom, erfaring, leverte systemer/land og overordnede effekt-/velferdsbudskap. De kontrollerte sidene viser lite selvbetjent innhold for kundens beslutningsjobb: valg av oppsett, integrasjonskrav, dokumentert drift, service/vedlikehold, prosessdata, kundecaser eller faglige forklaringer. Dette er en observasjon av sidene som ble lest, ikke en paastand om at informasjonen ikke finnes internt.

Maskons offentlige struktur dekker et bredere systemomfang: vaksinemaskiner, ekstrautstyr, fiskepumper, pumpesystemer, MSKY-datafangst, nyheter, karriere og nettbutikk. MSKY-sidene beskriver datafangst, prosessdokumentasjon, analyse, fiskevektfordeling, bildearkiv og grensesnitt til tredjepart. Dette er Maskons egne produktopplysninger, ikke uavhengig bekreftelse av effekt eller kundeadopsjon. [Lumic hjem](https://www.lumic.no/), [Lumic produkter](https://www.lumic.no/produkter), [Maskon produkter](https://maskon.no/en/products/), [Maskon MSKY](https://maskon.no/en/produkt/data-capture/)

Den raskeste muligheten er ikke a kopiere konkurrentens bredde. Det er a bygge en liten, kildebelagt svarflate rundt de beslutningssporsmalene Lumic faktisk vil eie, med bedre etterprovbarhet og kjoperstotte. Den mest interessante datapiloten er a koble Lumics aggregerte salgs-/service-sporsmal og godkjente produktdata med eksterne, aggregerte bransje- og fiskehelsekilder. Eksterne data kan vise kontekst, men kan ikke i seg selv bevise maskinbehov eller lead-intent.

## Offentlig informasjonsstruktur

| Omrade | Lumic: observert pa sidene | Maskon: observert pa sidene | Mulig kunnskapshull / mulighet |
|---|---|---|---|
| Hjem/posisjon | Vaksinasjonsutstyr, tilpassede oppsett, fiskevelferd/effektivitet, 229 leverte systemer i 22 land. | «Complete, customized automation systems» og et bredere utvalg av utstyr, datafangst og nyheter. | Vis hvilke konkrete driftsoppgaver Lumic dekker, hvem oppsettet passer for, og hva som er utenfor scope. Tall og produktpastander trenger kilde, definisjon og siste kontroll. |
| Produktoversikt | Seks produkter: V2 manuell, V3/V5 semi-automatisk, V4 fullautomatisk, V1/V2 og V3 bedovelsessystem. | Produktfamilier for vaksinasjon, ekstrautstyr, fiskepumper, pumpesystem, dyppvaksinering, MSKY og spesialmaskiner. | Normaliser modellnavn, variant, konfigurasjon og tilleggsutstyr i en kanonisk produktmatrise. |
| Produktdetaljer | Noen sider oppgir art/storrelse, kanaler, kapasitet, dose, vaksiner og sortering. | Produkt-/modellspesifikasjoner, forsyningskrav, tilleggsutstyr og enkelte forbehold om kapasitetsvariasjon. | Knytt hver verdi til modell, konfigurasjon, datakilde, betingelser og revisjonsdato; forklar sammenlignbare driftsbetingelser. |
| Faglig innhold | Om oss-side og produkttekst; i navigasjonen som ble sett ingen tydelig FAQ, kunnskapsbibliotek eller nyhetsseksjon. | Nyhetsarkiv, produktnyheter og omtalt datafangst/dokumentasjon. | Publiser fa, nyttige fagressurser knyttet til kjoperoppgaver og godkjent belegg; ikke voluminnhold for sok. |
| Bevis og erfaring | Hjemmesiden viser samlet leverte systemer/land; produkt-/om oss-sider bruker velferds- og effektspraak. | Maskon beskriver oppgitte bruksformaal, historikk og produktfunksjoner; har nyheter/omtale. | Lumic kan undersoke om det finnes godkjente, delbare driftscase, metodebeskrivelser og referanser. Bruk bare etter kundetillatelse og med avklart nevner/kontekst. |
| Ettermarked | De kontrollerte sidene leder til kontakt; de viste ikke en offentlig forbruksvare-/servicebutikk. | Offentlig nettbutikk med forbruksvarer og reservedeler; produktsider omtaler service/stotte. | Avklar internt om reservedeler, service, opplaring, vedlikehold og responstider er viktige kundeoppgaver, og hva som kan publiseres. |
| Data/innsikt | Nettsiden som ble lest beskriver ikke et eget prosessdata-/monitoreringsprodukt. Det sier ikke om Lumic har eller planlegger slike funksjoner. | MSKY markedsfores med logging, analyse, bilde-/vektdata, prosessdokumentasjon og tredjepartsgrensesnitt. | Strategisk sporsmal: hvilken data leverer Lumic-utstyret i dag, hvem eier den, hva kan deles, og er dokumentasjon/etterproving en reell kundeverdi eller bare et mulig framtidsspor? |
| Kontakt/konvertering | Kontaktoppfordringer og skjema pa produktsider. | Kontaktoppfordringer, nyhetsbrev, produktkontakt og butikk. | Test om kunden far tilstrekkelig nytte for kontaktforesporsel; spor kvalifiserte henvendelser i Lumics egne systemer, ikke konkurrentdata. |

### Hoyprioritert integritetskontroll pa Lumics produktdata

Den tekstbaserte innlesingen av Lumics engelske produktsider viser en mulig uklarhet som bor sjekkes mot den faktiske sidens visuelle layout og Lumics gjeldende produktregister:

- V4-beskrivelsen sier opptil 20 000 fisk/time, mens den samme innlastede siden ogsa inneholder en LV24-linje pa 40 000/time.
- V3-siden oppgir 2 400/time per kanal, men viser ogsa kapasitetsrader for LV4-LV24.
- V5-beskrivelsen oppgir opptil 20 000/time per kanal, mens samme side inneholder tabeller med samlet kapasitet per variant.
- Flere kapasitetsblokker ser ut til a gjentas pa engelsk og norsk.

Dette kan skyldes skjulte faner, varianttabeller, ulike maskinserier eller svak tekstuttrekking; det er ikke grunnlag her for a kalle det en faktisk produktfeil. Men det er en god Kunnskapshullradar-alarm: en kunde eller en sok-/AI-leser kan misforsta hvilken maskin, kanalmodell, enhet og produksjonsbetingelse hvert tall gjelder. Avklar med produkteier, og publiser en entydig tabell med variant-ID, kapasitet, operatortall, antall kanaler, fiskestorrelse, forbehold og sist faglig kontroll. [Lumic V4](https://www.lumic.no/en/produkter/automatisk-vaksinasjonsmaskin-v4), [Lumic V3](https://www.lumic.no/en/produkter/semi---automatisk-vaksinasjonsmaskin-v3), [Lumic V5](https://www.lumic.no/en/produkter/semi---automatisk-vaksinasjonsmaskin-v5)

### Posisjonering som hypotese, ikke konklusjon

Den offentlige presentasjonen antyder at Lumic legger vekt pa tilpassede oppsett, vaksinasjon/bedovelse og skreddersom rundt fisk og anlegg; Maskon viser bredere automatisering og en synlig data-/dokumentasjonsflate med MSKY. Dette kan gi en mulig differensieringsretning for Lumic rundt kvaliteten pa den menneskelige/faglige tilpasningen, dokumenterte driftsbetingelser eller innsyn i prosessen. Det ma valideres mot kunder, produktene Lumic faktisk leverer og selskapets strategi. Maskon oppgir ogsa customized systems, sa «skreddersom» kan ikke uten videre behandles som Lumic-eksklusivt.

## Kunnskapshullradar v0.1

Radarens gjenstand er ikke «hvilke SEO-sider mangler». Den er sporsmalet: hvor mangler Lumic dokumentert, tilgjengelig og oppdatert informasjon som hjelper en bestemt kjoperrolle med en faktisk oppgave?

### Statusetiketter

- `PUBLIC_ABSENCE`: tema ikke funnet i de offentlige sidene som ble kontrollert; dette beviser ikke at informasjonen mangler internt.
- `PUBLIC_AMBIGUITY`: offentlig tekst/data kan tolkes pa flere mater; avklar originalt produktregister/visning for konklusjon.
- `INTERNAL_EVIDENCE_NEEDED`: krever Lumic-kilder, systemer eller faglig eier.
- `CUSTOMER_HYPOTHESIS`: plausibel kundeoppgave som ma valideres gjennom samtaler eller brukertest.
- `EXTERNAL_CONTEXT`: relevant bransjesignal; ikke et direkte kjops-/leadsignal.
- `MEASURE_WITH_FIRST_PARTY`: kan males i Lumics egne sok-/web-/CRM-systemer, med tilgang og definisjoner.

### Seed-radar

| ID | Mulig hull | Observasjon/evidens | Status | Forste evidens som mangler | Foreslatt neste steg | Prioritet |
|---|---|---|---|---|---|---|
| LUM-KH-01 | Modell- og variantkart | Produktoversikten bruker V1-V5 og produktdetaljer inneholder ogsa LV-varianter. Sidetekst kan vaere uklar om hvilke tabeller som tilhorer hvilken modell. | PUBLIC_AMBIGUITY | Gyldig modellregister, definisjoner og faktisk UI-layout. | Faglig eier bekrefter variantkart; redaksjonell/visuell QA av alle produktsider. | P1: tillit og tilbudskvalitet |
| LUM-KH-02 | Kapasitet og driftsforbehold | V4/V3/V5-sidene oppgir kapasitet, kanal-/operatortall og ulike forbehold i produkttekst/tabeller. | PUBLIC_AMBIGUITY + INTERNAL_EVIDENCE_NEEDED | Testprotokoll eller teknisk datagrunnlag, batching, fiskestorrelse, periferiutstyr, enhetsdefinisjon. | Lag ett godkjent datasett per variant og sammenlign mot synlig nettside. | P1 |
| LUM-KH-03 | Grunnlag for velferds-/effektutsagn | Lumic bruker formuleringer om redusert handtering/stress, skansom vaksinering, effektivitet og velferd. | INTERNAL_EVIDENCE_NEEDED | Hvilke direkte maalinger, publiserte kilder, kundedata eller avgrensninger stotter hvert utsagn? | Opprett paastandsregister med kilde, vilkar, godkjenner og lovlig kanalbruk. | P1: faglig og omdommemessig |
| LUM-KH-04 | Kjoperens valg av oppsett | Nettsiden omtaler skreddersydde systemer og enkelte produktegenskaper, men ikke en synlig, sammenhengende valgveiledning pa tvers av art, fiskestorrelse, batch, kapasitet, bemanning og anleggskrav. | PUBLIC_ABSENCE + CUSTOMER_HYPOTHESIS | Topp 10 faktiske valgsporsmal og hvilken informasjon kunden mangler for a velge/ta kontakt. | Kode anonymiserte salgssporsmal og intervjue 3-5 relevante kjopere om jobben (kvalitativ utforsking, ikke markedsestimat). | P1 |
| LUM-KH-05 | Integrasjon og anleggskrav | Maskon synliggjor noen forsyningskrav og systemkoblinger. Lumic-sidene som ble kontrollert viser ikke en tilsvarende strukturert kravmatrise. | PUBLIC_ABSENCE + INTERNAL_EVIDENCE_NEEDED | Strøm, vann, luft, footprint, transport, grensesnitt, datatilkobling og krav som varierer per konfigurasjon. | Be teknisk eier lage godkjent sjekkliste per system; publiser bare det som kan frigis. | P2 |
| LUM-KH-06 | Prosessdata, logging og sporbarhet | Maskon markedsforer MSKY for prosess-/fiskedata og automatisk dokumentasjon; tilsvarende offentlig Lumic-side ble ikke funnet i gjennomgangen. | PUBLIC_ABSENCE + INTERNAL_EVIDENCE_NEEDED | Hvilke data finnes faktisk i Lumics systemer? Kan fisk/individdata lagres eller eksporteres? Hvem har tilgang/ansvar? | Teknisk kartlegging med tydelig skille mellom dagens funksjon, roadmap og ide. | P1 strategisk, men avhengig av intern kartlegging |
| LUM-KH-07 | Ettermarked og livslop | Maskon har synlig butikk for deler/forbruksvarer og omtaler service/stotte; kontrollert Lumic-struktur viser kontakt, men ikke en tilsvarende katalog. | PUBLIC_ABSENCE + CUSTOMER_HYPOTHESIS | Kundesporsmal om deler, forbruk, rengjoring, vedlikehold, service, opplaering og driftsstans. | Analyser aggregerte servicehenvendelser og avklar hvilke data som er publiserbare. | P2 |
| LUM-KH-08 | Dokumenterte bruks-/kundecaser | Lumic viser samlet leverte systemer/land, men fant ikke dedikerte caseartikler pa sidene som ble kontrollert. | PUBLIC_ABSENCE + INTERNAL_EVIDENCE_NEEDED | Tillatte referanser, case-data, sammenligningsgrunnlag, resultatnevner, kontekst og kundetillatelse. | Lag en case-mal med baseline, kontekst, metode, utfall og begrensning; ikke bruk effekt uten dokumentasjon. | P2 |
| LUM-KH-09 | Faglige svar pa velferd og vaksinering | Autoritative fagkilder og nye forskningsprosjekt finnes; Lumics sider lenker ikke i den kontrollerte strukturen til en kildebelagt forklaringssamling. | PUBLIC_ABSENCE + EXTERNAL_CONTEXT | Hvilke fagsporsmal er hyppige, og hvilke svar kan Lumic gi uten a forveksle utstyrseffekt med vaksine-/handteringseffekt? | Velg 5 sporsmal fra salg; svar med Veterinaerinstituttet/Nofima/FHF og tydelig avgrensing. | P2 |
| LUM-KH-10 | Oppdatert internasjonal kundestotte | Hjemmesiden viser 22 land, men det er ikke synlig om spraket, arts-/storrelsekssemplene eller serviceinformasjonen er lokalisert for hvert marked. | PUBLIC_ABSENCE + CUSTOMER_HYPOTHESIS | Hvilke land/arter er strategiske, og hvor stopper selgerne opp i lokal dokumentasjon? | Velg ett viktig eksportmarked og test en lokalisert FAQ/produktpakke med salgsansvarlig. | P2 |
| LUM-KH-11 | Sok og AI-synlighet for egne sider | Kan ikke leses fra nettsiden eller konkurrentens nettsted. | MEASURE_WITH_FIRST_PARTY | Search Console-tilgang, query/page-rapport, organisk landingsside og henvendelsesdefinisjon. | Hent 3-6 maneders baseline fra Lumics egen eiendom; Search Console inkluderer AI-overflater i egne rapporter etter Googles utrulling i 2026. | P1 for SEO-baseline |
| LUM-KH-12 | Hvilke bransjeforhold driver relevante behov? | Offentlige data finnes om lokaliteter, biomasse, lus, sykdom, fiskehelse og handteringsforskning, men dette er indirekte signaler. | EXTERNAL_CONTEXT | Hvilke signaler har dokumentert kobling til investering i akkurat vaksine-/handteringsutstyr? | Koble kun aggregert produksjons-/helsesituasjon til hypoteser; valider med Lumic-CRM og kundesamtaler. | P2 utforskende |

Prioriteringene er kvalitative forslag, ikke beregnede leadscores. En offentlig fravaerende side kan vaere lav verdi, mens en tvetydig kapasitetspastand kan vaere hoy verdi fordi den kan pavirke tillit/tilbudsforstaelse.

## Hvor vi kan finne relevant data

### Offentlig og ekstern data

| Kilde | Hva den kan belyse | Tilgang/rytme | Viktig forbehold |
|---|---|---|---|
| [BarentsWatch Fish Health API](https://developer.barentswatch.no/docs/fishhealth/) | Lokalitet, rapportert lakselus, sykdommer og mottiltak; historikk tilbake til 2012 ifolge BarentsWatch. | API, krever registrering/autentisering; dokumentasjonen ber om sekvensielle batchkall. | Data er rapporterte raadata; dokumentasjonen advarer om feil og sier at Mattilsynet ikke manuelt korrigerer alt for API-bruk. Kvalitetskontroll er brukerens ansvar. API-data alene betyr ikke at lokaliteten trenger Lumic-utstyr. |
| [Fiskeridirektoratet: biomasse etter produksjonsomrade](https://www.fiskeridir.no/statistikk-tall-og-analyse/data-og-statistikk-om-akvakultur/biomassestatistikk-etter-produksjonsomrade) | Innrapportert biomasse for matfiskproduksjon av laks/regnbueorret, fordelt pa produksjonsomrade; filer CSV/JSON/XLSX. | Oppdateres maanedlig den 20. | Makro-/kapasitetskontekst, ikke site-level lead-intent eller direkte ettersporsel etter vaksinasjonsmaskiner. |
| [Offentlig Akvakulturregister API](https://data.norge.no/en/datasets/76ac1294-3732-35bc-8732-0b6584ac8970/offentlig-api-for-akvakulturregister) og [registerets kartlag](https://gis.fiskeridir.no/server/rest/services/Yggdrasil/Akvakulturregisteret/MapServer/layers) | Tillatelser, arter, formol og lokaliteter. | Offentlig tjeneste/API; feature layer tilbyr JSON/GeoJSON. | Godkjent lokalitet betyr ikke at det er fisk eller aktivitet der na; lokasjonspunkt kan vaere omtrentlig. Ikke bruk til personlig profilering. |
| [Veterinaerinstituttet: Fiskehelserapporten 2025](https://www.vetinst.no/rapporter-og-publikasjoner/rapporter/2026/fish-health-report-2025) | Aktuelle helse- og velferdsutfordringer, taps-/dodelighetsbilde, sykdom og kunnskapsbehov. | Arlig rapport og egne statistikksider. | Kontekst for nyttig, faglig innhold; aggregerte tall beviser ikke en produktspesifikk effekt eller kundeintensjon. |
| [Veterinaerinstituttet: oppdrettsfisk](https://www.vetinst.no/dyr/oppdrettsfisk/) | Lenkes videre til sykdomssituasjon, dodelighetsstatistikk og velferdsindikatorer. | Statistikksider oppdateres forskjellig. | Definisjon, nevner, tidsrom og etterregistrering ma med; forelopige tall ma ikke framstilles som endelige. |
| [Nofima: HandleWithCare](https://nofima.no/prosjekt/effekt-av-fisketransport-og-handtering-i-settefiskanlegg/) | Paagaaende arbeid om velferdseffekt av handtering/pumping; planlegger veiledere og datainnsamling pa anlegg. | Prosjekt 2025-2027; resultater/veiledere blir tilgjengelige etter hvert. | Kunnskapsfront og mulig samarbeidstema, ikke ferdig konklusjon om Lumic-utstyr. |
| [Nofima: velferdsindikatorer ved vaksinering](https://nofima.no/wp-content/uploads/2016/06/Velferdsindikatorer-for-oppdrettslaks-2018.pdf) | Praktiske indikatorer som mortalitet, appetitt, atferd og handteringsskader for vurdering rundt vaksinering. | Offentlig PDF/handbok. | Eldre fagressurs; sjekk nyere kunnskap og indikatorenes anvendelsesomrade for aktuell art, storrelse og prosess. |
| [FHF prosjektbase](https://www.fhf.no/prosjekter/) | Finansierte prosjekter, behov, metode, sluttrapporter og fagpersoner i havbruk/fiskehelse. | Sokbar offentlig prosjektdatabase. | Prosjektbeskrivelse er ikke resultat; ga videre til rapport/primarkilde og registrer prosjektstatus. |
| [Lumic egen Search Console](https://search.google.com/search-console/) | Sokeord, landingssider, visninger/klikk og generativ Google-synlighet for Lumics eiendom. | Krever eier-/delegert tilgang; Googles nye generative rapporter er rullet ut globalt per 31.08.2026. | Tilgang er ikke kontrollert. Rapportert synlighet er ikke leads; koble forsvarlig til egne henvendelser og tidsrom. |
| Offentlige konkurrent-/leverandorsider og messenyheter | Produktbegreper, spesifikasjoner, publiserte nyheter, synlig support og tema konkurrenten investerer i a kommunisere. | Offentlig, men endres over tid. | Konkurrentens salgsbudskap er verken sannhetskilde om effekt eller innsikt i markedsandel, priser, kundetilfredshet eller reell teknisk funksjon. |

### Interne data som trolig vil vaere mest verdifulle

Disse er ikke tilgjengelige i researchmaterialet, men vil sannsynligvis gi best signal om Lumics konkrete kunnskapshull:

1. Aggregert liste over sporsmal fra salg, service og idriftsettelse (tekst renset for navn, kontaktinfo, lokalitetsnavn og andre identifikatorer).
2. Tilbuds-/tapt ordre-arsaker og kundens beslutningskriterier, hvis dette er registrert og kan brukes til formaalet.
3. Produktvariantregister, tekniske testprotokoller og dokumentasjon for kapasitet, dose, fiskeart/storrelse, sortering og operatortall.
4. Service-/reservedelslogg aggregert pa feilkategori, symptom og losning; ikke ra kundemail eller private samtaler.
5. Tilbakemeldinger fra kundeopplaring, installasjon, vedlikehold og operatorkurs.
6. Godkjente kundecaser og referansetillatelser.
7. Search Console og webanalyse for Lumic, med konverteringsmal definert av markedsforing/salg.
8. Kunnskaps-/dokumenteier, gyldighetsdato, teknisk godkjenner og publiseringsstatus per dokument.

Ikke legg CRM, tilbud eller samtaletranskripsjoner i husets delte forskningskorpus. Start med aggregerte sporsmal/tema og en lokal databehandler-/tilgangsavklaring.

## Saann kan en lett Kunnskapshullradar fungere

### 1. Innhenting

- Offentlig kilderegister: Lumic- og Maskon-URL-er, offentlige standard-/fagkilder og datasett med sist lest-dato.
- Intern kildebank: bare godkjente Lumic-produktkilder og menneskelig anonymiserte sporsmal, i et separat Lumic-eid miljo.
- Hver import logges med URL, dato, kildeklasse, lisens/vilkar, dataeier, tidsopplosning og kjente feilkilder.

### 2. Uttrekk og vurdering

AI kan foresla produktpastander, sporsmal, duplikater, uklare tall, manglende kildelenker og endret tekst mellom sideversjoner. AI skal ikke selv merke noe som sant, kommersielt relevant eller kundebehov.

En fagperson eller ansvarlig redaktor klassifiserer hvert treff som:
- dokumentert svar finnes;
- svar finnes, men er vanskelig a finne/forsta;
- data eller definisjon mangler;
- kilder er uenige/foreldet;
- mulig kundebehov, ikke validert;
- bevisst ikke et tema Lumic skal dekke.

### 3. Kunnskapshullkort

Minste felter:

```text
id
buyer_task
buyer_role (hvis kjent, ellers ukjent)
question_or_claim
signal_type (public_absence, ambiguity, internal_evidence_needed, customer_hypothesis, external_context, first_party_measurement)
evidence_refs (URL/file id + observed_at)
confidence (observed / inferred / unverified)
impact_hypothesis
what_would_resolve_it
owner
status (new / validating / answered / no_action / stale)
last_reviewed
```

### 4. Prioritering

Ha tre separate vurderinger (lav/middels/hoy):
- kundeverdi hvis hullet lukkes;
- evidens for at behovet faktisk finnes;
- kostnad/risiko ved a svare feil.

Ikke summer til et «lead potential»-tall i v0.1. En enkelt, kritisk teknisk uklarhet kan fortjene oppmerksomhet selv om frekvensen er ukjent. Frekvens fra fa kundehenvendelser beskrives som opptelling i det observerte materialet, ikke som markedsandel eller representativ ettersporsel.

### 5. Utdata

- Ukentlig eller maanedlig redaksjonell backlog, ikke automatisk innholdsproduksjon.
- Liste over publiserte svar med manglende kilde, reviewdato eller eier.
- Endringsvarsel for konkurrentsider/eksterne kilder som menneske vurderer.
- Kort status for hva som er bekreftet, hypoteser, utilgjengelige kilder og neste beslutning.

## Foerste pilot: to uker uten integrasjoner

1. Velg ett Lumic-produkt og 10-15 godkjente interne produkt-/servicekilder.
2. Ta inn 20-30 anonymiserte sporsmal fra salg/service eller merk tydelig at sample mangler.
3. Lag radar-kort manuelt i CSV/Markdown; la modell foresla grupper og manglende metadata.
4. La en fagperson kvalitetssikre alle produktfakta og to personer kontrollere kategoriseringen av et mindre utvalg.
5. Test pa 5 holdout-sporsmal: finner salgsansvarlig rett svar/kilde raskere, og vet systemet nar det ikke vet?
6. Sammenlign resultat med dagens manuelle sok, og logg tidsbruk, kildetreff, feil, avholdenhet og usikkerhet.
7. Etter testen: avgjor om det finnes verdi i a automatisere innhenting fra Search Console, offentlige data eller Lumics CRM.

Ikke start med masseinnlesing av alle BarentsWatch-uker, full webcrawl av konkurrent eller en automatisk agent. Innhent bare felt som svarer pa et navngitt sporsmal. Eksterne API-er kan ha registrering, kallgrenser og lisenskrav.

## Kilde- og tilgangsgrenser

- Gjennomgangen er skrivebordsresearch av offentlig synlige sider. Sitemaps var ikke tilgjengelige via sokeverktoyet; dette er ikke en komplett URL-crawl.
- Tekstuttrekk fra Lumics produktsider kan inkludere skjulte språk-/variantfaner; den observerte kapasitetsuklarheten ma kontrolleres visuelt og mot produktregister.
- Maskons produktsider er kommersielle primarkilder for hva Maskon hevder at produktene gjor; de er ikke uavhengig effektbevis.
- BarentsWatch Fish Health publiserer rapporterte raadata og krever registrering/autentisering; lisensvilkar ma kontrolleres for hver datakilde/eier.
- Fiskehelse-, biomass- og lokalitetsdata er bransjekontekst og kan ikke oversettes direkte til spesifikk investeringsvilje.
- Ingen Lumic CRM-/webanalyse-/service-/testdata er lest. Ingen kontakt er tatt med Lumic, Maskon eller kunder.

## Kilder kontrollert

- Lumic: [hjemmeside](https://www.lumic.no/), [om oss](https://www.lumic.no/om-oss), [produktoversikt](https://www.lumic.no/produkter), [V4](https://www.lumic.no/en/produkter/automatisk-vaksinasjonsmaskin-v4), [V3](https://www.lumic.no/en/produkter/semi---automatisk-vaksinasjonsmaskin-v3), [V5](https://www.lumic.no/en/produkter/semi---automatisk-vaksinasjonsmaskin-v5).
- Maskon: [hjem](https://maskon.no/en/), [produkter](https://maskon.no/en/products/), [vaksinasjon](https://maskon.no/en/produkt/vaccination/), [MSKY](https://maskon.no/en/produkt/data-capture/), [nyheter](https://maskon.no/en/news/), [nettbutikk](https://maskon.no/en/shop/).
- Offentlig data/fag: BarentsWatch Fish Health API og dataveiledning; Fiskeridirektoratets biomasse-/Akvakulturregisterdata; Veterinaerinstituttets Fiskehelserapport 2025; Nofimas HandleWithCare-prosjekt og velferdsindikatorhandbok; FHF-prosjektbase.
- Sok/SEO: Googles [Search Generative AI performance reports](https://developers.google.com/search/blog/2026/06/gen-ai-performance-reports), global utrulling oppgitt fra 31.08.2026.
