# Lumic: uvanlige, testbare muligheter for fagkunnskap og markedsforing

Status: utforskende scope-notat; ideer for diskusjon, ikke beslutninger eller produktopplegg.
Dato: 2026-11-23.
Utgangspunkt: preregistreringen og scoping review i de to tilhorende Lumic-notatene.
Beslutningseier: Anders.

## Arbeidshypotese

Den mest interessante muligheten er ikke en generisk chatbot eller et stoerre publiseringsvolum. Det er en liten, sporbar faglig kjerne som kan brukes pa flere steder: internt for salg og markedsforing, offentlig som nyttige beslutningsressurser, og analytisk som et system for a oppdage kunnskapshull.

Arbeidstesen er:

> En fagpastand registreres en gang med kilde, gyldighetsomrade, ansvarlig og status. Den kan deretter brukes i flere formater, men alle formater peker tilbake til samme belegg og kan trekkes tilbake nar belegget endres.

Dette er en produkt-/arbeidsflythypotese. Litteraturen gir ikke grunnlag for a anta at den vil skape leads eller inntekt for Lumic.

## Syv ideer som er verdt a vurdere

| Idé | Hva det kan vaere | Hvorfor det er uvanlig/nyttig | Forste test |
|---|---|---|---|
| 1. Beleggsgraf, ikke bare dokumentkorpus | Koble pastand -> kildesitat/maling -> prosess/utstyr -> gyldighetsvilkar -> godkjenner -> publisert innhold. | Gjør kilde, motstrid, utloept gyldighet og gjenbruk synlig. AI kan foresla relasjoner, men mennesker godkjenner dem. | Ta 10 reelle tekniske pastander og sjekk om salg raskere kan svare pa «hvor vet vi dette fra, og nar gjelder det?». |
| 2. Sporsmalsradar til dokumentert kunnskap | Anonymiserte, frivillig innsamlede kundesporsmal blir gruppert til gjentakende behov, manglende belegg og forslag til svar. | Lukker loopen mellom salg, fagmiljo og innhold. Markedsplanen oppdateres fra observerte sporsmal, ikke ideer i et tomt rom. | Kode 30-50 allerede tilgjengelige og godkjente sporsmal manuelt; se om gruppene endrer prioriteringen. |
| 3. Kjopers beslutningsverktoy | Enkel guide, sjekkliste eller scenarioverktøy som hjelper kunden med en oppgave, for eksempel forberedelse til teknisk vurdering eller dokumentasjonsbehov. | Gir kunden en brukbar arbeidsflate istedenfor en nedlastbar generisk brosjyre. Kan gi bedre innsikt i uttrykt behov uten skjult sporing. | Papirprototype pa fem kundesituasjoner; observer om brukeren tar en bedre informert neste beslutning. |
| 4. Levende bevispakke | En sammenhengende samling med metode, datagrunnlag, avgrensninger, sammenligning og godkjente resultater for hvert produkt-/effektutsagn. | Hjelper salg a vaere presis og hindrer at et avgrenset resultat blir til en ubetinget markedsclaim. | Velg en offentlig eller intern pastand. Spor hvert ledd fra utsagn tilbake til originaldokument og faglig godkjenner. |
| 5. Innhold som kan kompileres | Strukturert kunnskapsenhet produserer forslag til FAQ, salgssvar, nettsidetekst og intern veiledning, med kildepeker og review-status. | Gjenbruk skjer fra samme faglige sannhet; formatene blir ikke separate, foreldrelopte varianter. | Lag tre manuelle output fra ett kildekort og maal mot tre uavhengige tekster for tidsbruk, samsvar og korrekt kilde. |
| 6. Kundestyrt, frivillig behovsdeling | Brukeren kan velge kontekst og hva slags hjelp som er nyttig, og fa en konkret verdi tilbake, for eksempel en sjekkliste eller vurderingsramme. | Kan gi eksplisitt og kontekstuell intent uten a utlede identitet fra skjult atferd eller tvinge fram skjema for hver ressurs. | Test et kort, valgfritt sporsmal etter at nytten er levert; ikke ta svar som fasit om faktisk kjopsintensjon. |
| 7. Synlighet som observerbar distribusjon | Mal hvilke faglige URL-er som blir vist i vanlige sokeresultater og generative sokeflater, og hvilke sider som gir engasjement/henvendelser. | Skiller faktisk synlighet fra bransjens spekulative «GEO score»-pakker. | Verifiser Search Console-eierskap; registrer utgangsperiode og koble rapporterte URL-er til egne innholdstester. |

## Hva kildene sier om ideene

### Strukturert belegg og proveniens

W3C PROV-O beskriver hvordan en kilde, en aktivitet som bruker eller endrer kilden, og en ansvarlig agent kan knyttes i en provenienskjede. Det passer som begrepsmodell for kildesporing, men krever ikke at Lumic tar i bruk en RDF-database. En enkel tabell, YAML-fil eller eksisterende CMS-felt kan prove samme arbeidsflyt forst. [W3C PROV-O](https://www.w3.org/TR/prov-o/)

SHACL er en W3C-standard for a validere en datagraf mot definerte former/krav. Overfort som ide kan et kunnskapskort avvises hvis det mangler kilde, gyldighetsomrade, eier eller godkjenner. Dette er et nyttig prinsipp for kvalitetskontroll, ikke bevis for at RDF/SHACL er riktig implementasjon for Lumic. [W3C SHACL](https://www.w3.org/TR/shacl/)

SKOS modellerer kontrollerte begreper med foretrukket etikett, alternative etiketter, definisjoner og relasjoner. Det kan hjelpe med synonymrikdom mellom kundesprak, faguttrykk og produktnavn, uten a innfore et tungt domeneontologi-prosjekt. [W3C SKOS](https://www.w3.org/TR/skos-reference/)

### Graf-RAG: nyttig hypotese, ingen magisk kvalitetssikring

CRAG introduserte et benchmark med 4 409 fakta-QA-par i fem domener og simulerte sok/knowledge-graph API-er. I den publiserte evalueringen la enkel RAG bare en begrenset forbedring til modellene. Resultatene gjelder benchmarken og modellene i studien, ikke dagens alle systemer, men de viser hvorfor Lumic ma teste egne feiltyper framfor a anta at RAG gir faktasikkerhet. [NeurIPS 2024 CRAG](https://proceedings.neurips.cc/paper_files/paper/2024/hash/1435d2d0fca85a84d83ddcb754f58c29-Abstract-Datasets_and_Benchmarks_Track.html)

Et arbeid om KG-RAG under manglende kunnskap finner at systemer ofte sliter nar direkte fakta er fjernet, og at modellene kan lene seg pa egen memorering. Det peker pa en sarlig Lumic-test: kan systemet si «kilden dekker ikke dette» istedenfor a fylle inn plausible, men udokumenterte produktdetaljer? [Zhou mfl., 2025](https://arxiv.org/abs/2508.08344)

Microsoft GraphRAG er en MIT-lisensiert forskningsimplementasjon for grafbasert uthenting og strukturering. Prosjektet beskriver seg na som i vedlikeholdsmodus, ikke som offisielt stottet Microsoft-produkt, og advarer om at indeksering kan koste mye. Det er god inspirasjon for hvordan globale tema kan undersokes pa et dokumentkorpus, men en daarlig grunn til a begynne Lumic-arbeidet med dyr grafindeksering. [GraphRAG-repo](https://github.com/microsoft/graphrag)

### Beslutningsverktoy og konfigurerbare salgserfaringer

Mahlamaki mfl. studerte kunders aksept av B2B-salgskonfiguratorer med en PLS-SEM-modell pa survey fra 115 finske B2B-distributorer. Opplevd brukervennlighet og tilpasning bidro til opplevd effektivitet/nytte; opplevd glede hadde sterkest sammenheng med opplevd nytte i modellen. Det er surveybasert akseptforskning, ikke randomisert test av inntekt. For Lumic er den nyttige implikasjonen a designe verktøy fra kjoperens perspektiv, holde dem enkle og relevante, og teste brukbarhet; ikke automatisk bygge en konfigurator. [Industrial Marketing Management, 2020](https://doi.org/10.1016/j.indmarman.2020.08.024)

Et beslektet prinsipp er at interaktivitet bor lose en ekte jobb. En enkel, transparent sjekkliste eller scenariooversikt kan vaere mer nyttig og lettere a vedlikeholde enn et omfattende produktvalgverktoy hvis produktrommet eller underliggende data ikke er strukturert.

### Frivillig behovsdeling og personvern

«Zero-party data» beskrives ofte som direkte uttrykt preferanse eller intensjon. En perspektivartikkel peker pa en viktig begrensning: selvrapportering pavirkes av hvordan sporsmalet stilles, og folk har ikke alltid god innsikt i egne handlinger. Frivillige svar kan supplere andre signaler, men skal ikke behandles som objektiv sannhet eller som samtykke til ethvert viderebruk. [Polonioli, 2022](https://doi.org/10.3389/fdata.2022.943372)

For Lumic er den forsiktige testen et sporsmal som gir brukeren en konkret gevinst og forklarer hva svaret brukes til. Ikke gjem et kontaktkrav bak en fagressurs, og ikke bruk et selvrapportert svar alene som leadscore.

### Google- og AI-sok: maalbar synlighet, ingen hemmelig optimalisering

Google lanserte i 2026 egne Search Console-rapporter for generative sokeflater. Etter utrulling globalt kan rapporten vise visninger, URL-er, land, enheter og utvikling over tid for AI Overviews/AI Mode og relaterte flater. Dette kan gi et faktisk utgangspunkt for distribusjon hvis Lumic har en verifisert Search Console-eiendom. Visninger dokumenterer ikke attribuert salg. [Google Search Central, juni 2026](https://developers.google.com/search/blog/2026/06/gen-ai-performance-reports)

Google sier at strukturert data ma representere synlig innhold og ikke garanterer rich result. Det samme prinsippet gjelder AI-sok: skriv tydelig, originalt og etterprovbart innhold; bruk strukturert data der den passer; ikke bygg en separat taksonomi av sporsmaalsvar kun for a manipulere retrieval. [Google: strukturert-dataregler](https://developers.google.com/search/docs/appearance/structured-data/sd-policies)

## Apen kildekode og hva som er verdt a laane

| Prosjekt/standard | Hva det gir | Lisens/status fra kildesok | Egnet som inspirasjon | Avgrensning |
|---|---|---|---|---|
| Microsoft GraphRAG | Pipeline for a trekke ut konsepter/relasjoner og lage graph-retrieval. | MIT; prosjektet beskriver vedlikeholdsmodus og dyr indeksering. | Test globalt sporsmal pa et lite, ikke-fortrolig dokumentutvalg. | Ikke anta at graph = korrekt svar; drift/kostnad og prosjektretning ma revurderes for eventuell bruk. |
| Haystack | Apen orkestrering av sok, retrieval, routing og generering med tydelige pipelines. | Apache-2.0 ifolge repository. | Referanse for modulare, evaluerbare kjeder og mulighet for modellbytte. | Rammeverk, ikke ferdig kunnskapsprodukt; krever integrasjon, sikkerhetsdesign og drift. |
| Onyx | Organisasjonskunnskapssok, dokumentkoblinger og MCP-tilgang til egen kunnskapsbase. | Community Edition er MIT-lisensiert; Enterprise Edition-komponenter har egen lisens, og kildebasert tilgangssynk krever Enterprise Edition ifolge dokumentasjonen. | Referanse for connectors, kildesett, brukerinitiert sok og tilgangsbevissthet. | Ikke last opp Lumic-materiale uten separat vurdering av drift, tilgang, dataflyt, lisens og kommersielle vilkar. |
| W3C PROV-O + SHACL + SKOS | Proveniens, valideringsregler og synonym-/begrepskart. | W3C-standarder. | Datamodell for kilde, pastand, owner, godkjenning, begrep og kvalitetssjekk. | Start med lettvektsformat; innfor grafteknologi forst hvis konkrete arbeidsoppgaver krever det. |

Lenker: [Haystack GitHub](https://github.com/deepset-ai/haystack), [Onyx connector docs](https://github.com/onyx-dot-app/onyx/blob/main/documentation/overview/core_features/connectors.mdx), [Onyx MCP docs](https://github.com/onyx-dot-app/onyx/blob/main/backend/onyx/mcp_server/README.md), [Onyx license](https://github.com/onyx-dot-app/onyx/blob/main/LICENSE).

Funksjon og lisensstatus kan endre seg; denne tabellen er en orienterende gjennomgang av prosjektkildene pa datoen over, ikke en teknisk due diligence.

## Foreslatt scope: tre smale spor

### Spor A: Beviskort og kildegraf, uten chatbot

**Sporsmal:** Kan salg/markedsforing gjenbruke godkjent kunnskap uten a miste proveniens?

- Datamodell: `claim_id`, utsagn, kilde/avsnitt, kildeversjon, scope/forbehold, owner, approver, review date, linked assets.
- Begynn i Markdown/CSV eller felter i eksisterende CMS; ikke velg graph database na.
- Bruk enkle valideringsregler: publiserbar pastand ma ha kilde, scope, godkjenner og reviewdato.
- Leveranse: 10-20 beviskort og tre formatforslag fra samme godkjente grunnlag.
- Eval: hvor mange paastander kan spores; redaksjonell tidsbruk; uoverensstemmelser; stale/utlopte kort.

**Go/no-go:** hvis ingen i Lumic kan eie og godkjenne fagkort, stopp her og bygg forst kildeansvar.

### Spor B: Kunnskapshullradar

**Sporsmal:** Kan gjentakende sporsmal gjore innholdsplanen mer treffsikker og produktdokumentasjonen bedre?

- Inndata: manuelle, anonymiserte sporsmal eller frivillig aggregerte notater; ikke ufiltrerte opptak.
- LLM-oppgave: foresla tema, synonym, sporsmalstype og manglende kilde; menneske godkjenner kategorien.
- Output: backlog med sporsmal, antall forekomster, rolle, konsekvens ved manglende svar, status pa belegg.
- Eval: to menneskelige kodere pa et lite utvalg, overlapp/uenighet, nye relevante behov som ikke fantes i eksisterende innholdsplan.

**Go/no-go:** stopp dersom datagrunnlaget er for lite eller for skjevt til at frekvens gir mening. Ta vare pa enkeltsporsmal som kvalitative signaler uten a framstille dem som representativ markedsdata.

### Spor C: Ett kjoperrettet beslutningsverktoy

**Sporsmal:** Hjelper et lite interaktivt artefakt brukeren a ta et bedre informert neste steg?

- Velg en konkret jobb som kan beskrives uten uverifiserte effektpastander.
- Lag papirprototype og test med 3-5 relevante personer for forstaelse og nytte.
- Hvis verdifullt: bygg en webside/wizard/sjekkliste. La brukeren fa resultatet for et frivillig kontaktvalg.
- Eval: completion, forstaelse, beslutningssikkerhet/oppgavekvalitet og frivillig neste steg. Ikke optimaliser klikk alene.

**Go/no-go:** stopp hvis verdien avhenger av at Lumic samler inn mer person- eller prosessdata enn brukeren forventer.

## Prioritering etter uvanlighet, verdi og risiko

1. Start med Spor A. Det skaper gjenbrukbar faglig infrastruktur og reduserer risiko for ubegrunnede pastander.
2. Prove Spor B med eksisterende, anonymiserte eksempler. Lav byggkostnad og direkte kobling til salgs-/kundebehov.
3. Velg ett verktøy i Spor C bare nar Spor A har en godkjent kildekjerne og en identifisert kundeoppgave.
4. Ikke bygg GraphRAG, leadscoring, automatisk publiseringsagent eller full produktkonfigurator i forste runde.

## Relevante husressurser for videre arbeid

- `forskningssok`: bruk som evidenslogg, litteraturkart og eierrepo for metode. Ikke bland Lumic-kundedata inn i felles forskningskorpus.
- `boker`: laan evalueringsdisiplin, holdout og benchmarktenking; det eksisterende bokkorpuset er ikke Lumic-fagdata.
- `prosesser/feltprove-husstandard` og `prosesser/eval-forskning-hjemmene`: bruk ved forhandsregistrering, skille teknisk verifikasjon fra brukertest og krav om versjonerte datasett.
- LauvasData Belegg Kildepilot: studer kildevalgs-/samtykkemodellen som arkitekturcase. Deployment, tilganger og drift er ikke verifisert; ikke bruk den som Lumic-tjeneste uten egen gjennomgang.
- Google Search Console: dersom Lumic har eierskap, hent ekte baseline for sok og generative flater; aldri erstatt med tredjeparts «AI visibility»-score.

## Sporsmal Ulven og Hans Magne kan avgjore

1. Hvilke tre kundeoppgaver ville spart tid eller redusert risiko hvis kunden fant et presist svar uten mote?
2. Hvilke fagpastander/proofs gar oftest igjen i salg, og hvem kan godkjenne dem?
3. Er hovedproblemet at innhold mangler, at det er vanskelig a finne, eller at det er vanskelig a stole pa?
4. Hvilke kunde- eller bruksdata er faktisk tilgjengelige med avklart rett til bruk?
5. Hvilken liten interaktiv ressurs ville kundene selv valgt a bruke, selv uten lead-form?
6. Hva er en «kvalifisert mulighet» i Lumics egen salgsprosess, og hvem registrerer den?
7. Hvor ma en prototype leve for at den passer eksisterende markeds-/salgsarbeid uten a innfore en ny tung plattform?

## Forslag til foerste 10 arbeidsdager etter prioritering

- Dag 1-2: Ulven og Hans Magne velger ett kundeproblem og eier for kildene.
- Dag 3-4: Anders lager format for beviskort og kort evalueringsplan, hvis det er ønsket.
- Dag 5-6: fagansvarlig godkjenner 10-20 kildekort; hull registreres eksplisitt.
- Dag 7-8: bygg tre gjenbrukseksempler og en papirprototype av beslutningsverktoy.
- Dag 9: 3-5 brukere/kolleger tester forstaelse og oppgavefullforing; ingen effektkonklusjon fra dette lille utvalget.
- Dag 10: beslutning om stoppe, forbedre eller finansiere ett lite eksperiment; SEO-/leadutfall ma ha egen baseline og tilstrekkelig tid/data.

Dette er en foreslatt arbeidsrytme, ikke en bindende kalender eller en antakelse om at de andre deltakerne har kapasitet.
