# Lumic: forskningsfunn for fagkunnskap, synlighet og AI-stotte

Status: avgrenset scoping review; ikke full systematisk oversikt.
Dato for sok: 2026-11-23.
Preregistrering: `docs/lumic-fagkunnskap-litteraturreview-prereg-2026-11-23.md`, commit `765bbaf`.
Beslutningseier: Anders.

## Konklusjon i kortform

Forskningen gir et godt grunnlag for a starte med faktiske informasjonsbehov, faglig kvalitet, gjenfinning og sporbarhet. Den gir ikke et troverdig generisk anslag pa leads, salg eller SEO-avkastning for Lumic. Kundereiser i B2B er komplekse, ofte selvbetjente og involverer flere roller; relevant innhold ma derfor knyttes til konkrete kjops- og bruksoppgaver. Dokumentasjonsforskning gir kvalitetskriterier, men ikke bevis for at en bestemt kunnskapsbase vil skape omsetning. AI bor forelopig behandles som arbeidsstotte som ma evalueres lokalt.

Anbefalt retning: bygg en liten, kuratert og versjonert fagkunnskapsbase rundt sporsmal kunder og salg faktisk har; vis kilde, dato, kontekst og faglig godkjenner; test om brukere finner og forstar riktige svar; koble senere til kvalifiserte muligheter med en avtalt definisjon og lokal baseline.

## Sok og avgrensning

Dette er en scoping review basert pa de preregistrerte soketemaene, web-sok, utgiver-/DOI-poster og offisielle kilder. Det ble sokt pa B2B-kjopsreise og innholdsrelevans, B2B-innholdsmarkedsforing og leads, dokumentasjonskvalitet/gjenfinning, AI-generert markedsinnhold og offisiell Google-veiledning, samt norsk laksevelferd. Sokefraser omfattet blant annet `B2B buyer journey information needs industrial purchase digital content empirical study`, `technical documentation findability information architecture user study`, `B2B content marketing experiment lead quality sales opportunity attribution` og `generative AI marketing content experiment B2B`.

Soket var ikke en uttommende databasegjennomgang: ingen dedikert fulltekstscreening av alle treff, ingen to uavhengige screenere og ingen metaanalyse. Enkelte artikler er vurdert fra abstract/utgiversammendrag. Tall og effekter er derfor ikke pool'et. Formelle funn nedenfor er det som ble identifisert i soket etter preregistreringen; tidligere utforskende kilder er ikke brukt som dekningsbevis.

Metodeavvikene er samlet i [avviksnotatet](lumic-fagkunnskap-litteraturreview-avvik-2026-11-26.md). Det finnes ikke en komplett, per-sporring sok- og screeningslogg som kan rekonstrueres fra dette notatet. Resultatene skal derfor leses som en avgrenset scoping review av utvalgte kilder, ikke som dokumentasjon pa uttommende dekning eller som en full systematisk oversikt.

## Funn etter sporsmal

### B2B-kjopsreise og informasjonsbehov

Purmonen, Jaakkola og Terho syntetiserer B2B-kjopsreisen som ikke-lineaer og relasjonell, med koblede mal og flere medlemmer i kjops- og brukssenteret. Dette stotter kartlegging av roller, oppgaver og sporsmal, ikke en enkel line aer trakt. Det er en litteraturbasert konseptuell syntese, ikke en Lumic-spesifikk effektstudie. [Industrial Marketing Management, 2023](https://doi.org/10.1016/j.indmarman.2023.05.020)

Lundin og Kindstrom undersoker digitaliserte kundereiser i industrielle virksomheter og beskriver hvordan kunder bruker digital informasjon i reisen for og mellom leverandorkontakt. Studien er kvalitativ og kontekstuell; den begrunner a undersoke selvbetjent faginnhold, men ma ikke leses som dokumentasjon pa flere leads. [Journal of Business Research, 2023](https://doi.org/10.1016/j.jbusres.2022.113639)

Terho mfl. bygger teori om B2B digital content marketing pa intervjuer fra 36 virksomheter. Dette gir praksisnare mekanismer og arbeidsformer, ikke kausal ROI. [Journal of Business & Industrial Marketing, 2022](https://doi.org/10.1016/j.indmarman.2022.06.006)

Marvasti mfl. viser i en avgrenset empirisk studie at nettleseratferd kan brukes til a estimere B2B-kjopsfase for bedrifter. Det viser at atferdssignaler kan modelleres i et konkret datasett; det legitimerer ikke automatisk personsporing, lead scoring eller overforing til Lumic uten volum, samtykke, datakvalitet og lokal validering. [Industrial Marketing Management, 2021](https://doi.org/10.1016/j.indmarman.2021.06.003)

### Relevans, innhold og forretningsutfall

Salonen mfl. tester timing av digitalt innhold langs B2B-kundereisen og finner at relevans for kjopsfasen har betydning for engasjement. Utfallene handler om engasjement i studiedesignet, ikke Lumic-leads eller inntekt. Det gir grunn til a tilpasse faginnhold til oppgave/fase, men ikke til a love konverteringsloft. [Industrial Marketing Management, 2024](https://doi.org/10.1016/j.indmarman.2024.02.002)

Marvasti mfl. (ovenfor) og eksisterende studier av digital innholdsrespons er kontekstspesifikke. Denne gjennomgangen fant ikke direkte replikert kausal evidens som kan forutsi antall kvalifiserte Lumic-muligheter fra en kunnskapsbase eller SEO-tiltak. Det ma males lokalt med en definisjon av kvalifisert mulighet, kildeattribusjon og tidsvindu.

### Kvalitet og gjenfinning av faginnhold

Treude mfl. utvikler et rammeverk for dokumentasjonskvalitet med ti dimensjoner og prover det med fire tekniske redaktorer og 41 R-dokumenter. Arbeidet viser at dokumentasjonskvalitet er bredere enn faktakorrekthet, og gir et nyttig vurderingssprak. Pilotens lille omfang og programvaredokumentasjonens kontekst begrenser direkte generalisering til akvakultur. [FSE 2020](https://doi.org/10.1145/3368089.3417045)

En Siemens-case fra 2026 sammenligner strukturering av tekniske dokumenter for RAG-gjenfinning og rapporterer bedre resultater for mer modulert innhold i sitt datasett. Dette er en avgrenset konferanse-/case-studie pa ett dokumentmiljo; det beviser ikke at chunking eller en bestemt RAG-arkitektur gir bedre svar i Lumic. Bruk den som hypotese for lokal evaluering. [Energies/MDPI, 2026](https://www.mdpi.com/2673-4591/143/1/47)

En loggstudie av dokumentasjonsbruk over 100 000 brukere pa fire tjenester viser ulike lesemonstre og korrelasjoner med erfaring og senere API-bruk. Observasjonsdata gir ikke kausal effekt, men peker pa at bruksspor og oppgaveutfall kan inngaa i evaluering. [Nam mfl., CHI 2024](https://doi.org/10.1145/3613904.3642721)

### AI i markedsinnhold

Eksperimenter sammenligner menneskeskrevet, AI-generert og hybrid innhold, men utfall varierer med kontekst, oppgave, merkevare og deltakergruppe. Et nyere nettbasert eksperiment med 240 britiske og amerikanske deltakere undersoker forfattertype og AI-merking; dette maler oppfatninger, ikke faktisk B2B-salg. [SSRN working paper, 2026](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7269195)

Et nyere forskningspreprint rapporterer online A/B-tester av generert annonsetekst med opp til 9 prosent CTR-forbedring i en bestemt plattform/oppgave. Det er lovende, men preprintet og annonsesettingens utfall kan ikke overfores til organisk SEO, faglig tillit, leadkvalitet eller Lumic. [arXiv, 2025](https://arxiv.org/abs/2506.17863)

Google sier at generativ AI kan brukes til innholdsproduksjon, men masseproduksjon av sider uten selvstendig verdi kan omfattes av reglene mot scaled content abuse. Veiledningen anbefaler nyttig, palitelig og menneskeorientert innhold. Dette er sokemotorpolicy, ikke en effektstudie eller garanti for rangering. [Google Search Central: AI-innhold](https://developers.google.com/search/docs/fundamentals/using-gen-ai-content), [Helpful content](https://developers.google.com/search/docs/fundamentals/creating-helpful-content), [AI-funksjoner i sok](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide)

### Faglig kontekst: laks, vaksinasjon og velferd

Veterinaerinstituttets oppdaterte faktaark om vaksinebivirkninger beskriver vaksinasjon som en prosess med handtering, trenging, pumping, bedoving og injeksjon, og viser at temaet ma forklares med kontekst og balanse. Kilden er aktuell norsk fagmyndighetsformidling; konkrete Lumic-produktpastander krever separat dokumentasjon. [Veterinaerinstituttet, 2026](https://www.vetinst.no/fagomrader/dyrevelferd/faktaark/vaksinebivirkninger-hos-laksefisk)

Veterinaerinstituttets faktaark om teknologi og fiskevelferd framhever at utforming, feil, bruk, opplaering og oppfolging alle kan pavirke velferd; velferdsindikatorer er relevante for vurdering. Dette gir en innholdsmulighet rundt beslutningskriterier og dokumentasjon av utstyr i drift. Det fastsetter ikke at Lumics utstyr oppnar et bestemt utfall. [Veterinaerinstituttet: teknologi og fiskevelferd](https://www.vetinst.no/fagomrader/dyrevelferd/faktaark/teknologi-og-fiskevelferd)

## Hva evidensen stotter

- Kartlegg faktiske oppgaver, roller, innvendinger og kunnskapshull pa tvers av kjops- og bruksreisen.
- Prioriter faginnhold som er nyttig, relevant for en identifisert oppgave, lett a finne og tydelig pa kilde, dato, kontekst og ansvarlig fagperson.
- Mal innholdsnytte med oppgavebaserte tester (finner riktig svar, forstar det, kan handle), i tillegg til sokedata og forretningsutfall.
- Bruk AI til avgrensede steg som transkripsjon/sortering, forslag til metadata, gjenbruk/utkast og oppsummering, med kildepeker og menneskelig godkjenning for publisering.
- Evaluer gjenfinning og svar mot kuraterte sporsmal med holdout-sett; skill feil kilde, manglende svar, feil svar og utdatert svar.
- Start med et lite korpus og en avgrenset arbeidsflyt. Skaler forst nar lokal nytte, kostnad og feilrate er malt.

## Hva evidensen ikke stotter

- Et tallfestet prognoseanslag for Lumics leads, omsetning, SEO-rangering eller tilbakebetalingstid.
- At mer publisert AI-innhold i seg selv gir synlighet eller tillit.
- At syntetiske brukertester, generiske leadscoringmodeller eller ett RAG-benchmark erstatter faktiske kunder og fagpersoner.
- At generelle fiskevelferdsfakta dokumenterer Lumics-utstyrs spesifikke ytelse.
- At et teknisk fungerende korpus er det samme som juridisk, personvernmessig eller kommersielt klart kundetilbud.

## Foreslatt lokal evidensplan

1. Etabler baseline for 5-10 gjentatte sporsmal fra salg/service, dagens svartid og hvor svaret finnes. Ikke samle personopplysninger som ikke trengs.
2. Velg 10-20 godkjente kilder/artefakter og lag en paastandsliste: kilde, dato, eier, gyldighetsomrade, sensitivitet, godkjenner.
3. Lag 20-30 realistiske oppgaver/sporsmal fra ulike roller. Hold noen sporsmal tilbake som blind evalueringssett.
4. Sammenlign manuell dagens praksis med prototypen: treff pa riktig kilde, korrekthet vurdert av fagperson, tid til svar, oppgaveforstaelse og avholdenhet nar dekning mangler.
5. Bare etter en separat godkjenning: test en offentlig innholdsside eller salgsstotte med forhandsdefinert primarutfall, kontroll/sammenligning, tidsvindu og stopprekriterier. Faerre enn tilstrekkelig datavolum gir usikkert estimat, ikke bevis pa null effekt.
6. Logg modell, prompt, kildeversjon, endringer og menneskelig redigering. Ingen automatisk publisering av velferds-, sikkerhets-, ytelses- eller produktpastander.

## Husressurser som kan tas mer i bruk

| Ressurs | Dokumentert bruksmulighet | Status/begrensning |
|---|---|---|
| `forskningssok` | Litteratursok, syntese og evalueringsarbeid; eierrepo for denne forskningsleveransen. | Relevant arbeidsflate; denne rapporten beviser ikke at adaptere eller alle eksterne indekser er operative na. |
| `boker` | Korpus-/retrievalbenchmarking og vurderingsopplegg. | Ikke et kuratert Lumic-korpus; rettigheter, relevans og dataseparasjon ma avklares for bruk. |
| Feltprove-husstandard | Forhandsregistrering, skille mellom teknisk pilot, intern feltprove og ekstern pilot; stopprekriterier. | Gjenbruk prosessen; ny ekstern pilot ma ha egen avklaring og godkjenning. |
| Evalueringsrutinen for forskningshjemmene | Forhandsdefinert eval, datasettversjon og kontroll mot menneskelig vurdering. | Bruk som metodeinspirasjon; kontroller gjeldende wiki-/kodeversjon for hvert konkret lop. |
| LauvasData Belegg Kildepilot | Eksempel pa eksplisitt avgrenset, brukerinitiert kildebruk for egne dokumenter. | Kode er observert, men deployment, rettigheter og gjeldende driftsstatus ble ikke verifisert. Ikke behandle som Lumic-klar tjeneste. |
| Morgenpost, Hub, driftspuls, kodeskog | Husets eksisterende instrumentering kan synliggjore operasjonell aktivitet og lese-/skriverforhold. | Ikke marketing analytics; ingen av disse ma brukes som proxy for Lumic leads uten definert referent. |

Interne wiki-/repo-dokumenter som ble lest omfatter `prosesser/feltprove-husstandard`, `prosesser/eval-forskning-hjemmene`, `prosesser/åpne-datakilder-og-korpus`, `prosesser/fdr-036-far-ekspert-kunnskapsverktøy`, `prosesser/rfc-007-bok-bank-kunnskap`, `prosjekt/forskningssok-smartsyntese-for-ulven`, `prosjekt/forskningssok-veikart`, samt `lauvasdata/docs/eget-korpus-review-pilot.md` og Belegg Kildepilot-komponenten. Gjeldende deployment, eierskap og enkelte wikistatusser er ikke verifisert pa nytt i denne rapporten.

## Nettsider og kunnskapshullradar

En offentlig skrivebordsrevisjon av lumic.no, maskon.no og relevante eksterne datakilder er samlet i [Lumic og Maskon: nettsidescan og Kunnskapshullradar v0.1](lumic-nettsideaudit-og-kunnskapshullradar-2026-11-23.md). Den skiller synlig fravaer fra intern mangel, mulig produktuklarhet fra bekreftet feil, og bransjesignal fra faktisk lead-intent.

## Videre utforsking

For mer originale, men avgrensede mulighetsrom (beleggsgraf, kunnskapshullradar, beslutningsverktoy, apen kildekode og testplaner), se [Lumic: uvanlige, testbare muligheter](lumic-uvanlige-muligheter-og-scope-2026-11-23.md). Dette er et separat utforskende scope, ikke nye effektbevis.

## Kildebegrensninger og referanser

Dette notatet er en beslutningsforberedende kartlegging, ikke evidens for at Lumic har et bestemt markedsproblem. Ulven og Hans Magne ma definere kundesegment, salgsprosess, tilgang til egne data, aktuelle godkjennere og hva de mener med kvalifisert lead. Produktdokumentasjon og paastander ma komme fra Lumic og verifiseres av navngitt fagansvarlig.
