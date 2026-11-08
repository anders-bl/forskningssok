# Resultat: Belegg-sok etter ultralydprotokoll for nefrokalsinose

Dato: 2026-11-08
Type: eksplorativ retrieval-probe, ikke blind validering.

## Identitet og protokoll

- Preregistrering: commit `bf63a117423853d07ee54792f4b72ee050e6c042`.
- Siteringsspor-addendum, fryst for disse kallene: commit `a15b76a9f50bc9d05f60797875927a6c84cf2ccc`.
- Branch: `codex/s-198-belegg-ultrasound-search-20261108`.
- Kildekall: seks sporringer mot Europe PMC, CORE og OpenAlex, topp 10 per kilde.
- Ingen modell- eller embeddingkall. Hver adapter brukte en separat midlertidig cache;
  den permanente resultatfilen er den eneste eksperimentelle dataleveransen.
- Radata og metadata: `docs/belegg-ultralyd-retrieval-eksperiment-2026-11-08-results.json`.

## Sokesammenligning

Alle 18 database-/sporring-kombinasjoner svarte. Samlet kom 157 kildeposter tilbake.
Etter deduplisering pa DOI, med normalisert tittel som reserve-ID, sto 116 poster igjen;
73 hadde DOI. Fem normaliserte titler mappet til flere identiteter, sa noe
gjenvaarende dublettfare bestar. Dette er sokeutdata, ikke 116 uavhengig relevante
kilder.

| Arm | Europe PMC | CORE | OpenAlex |
|---|---:|---:|---:|
| Baseline | 10 | 10 | 10 |
| Tilstand/art | 5 | 10 | 10 |
| Modalitet/anatomi | 10 | 10 | 10 |
| Metode/validering | 10 | 10 | 10 |
| Score/protokoll | 10 | 10 | 4 |
| Kjent radiologisk startkilde | 3 | 10 | 5 |

### Treff som kan vaere nyttige

- Direkte kandidat for laksefisknyre + ultralyd + nefrokalsinose-score/skanneomrade:
  0 i tittel-/abstractmaterialet som ble hentet.
- Sykdoms-/artsbakgrunn: bl.a. nefrokalsinose hos regnbueorret, sardiner og laksefisk,
  samt den kjente radiologiske lakseartikkelen.
- Metodeanalogi: en kattestudie sammenligner ultralyd, mikro-CT og histopatologi for
  nefrokalsinose. Den beskriver nyreareal/volum-maling, men er ikke validert pa fisk.
- Metodeanalogi: en studie av europeisk aal brukte ultralyd til gonadeidentifikasjon
  og sammenlignet med histologi. Den viser fiskespesifikk ultralydbruk, men ikke nyre.
- Et ultralydsok i Europe PMC fant ogsa en studie om variasjon i ultralyddeteksjon hos
  premature barn. Den er ikke overforbar til fisk, men viser at operatorkonsistens og
  probevalg kan vaere relevante metodiske sporsmal.
- CORE ga ogsa tydelig avleid stoy, bl.a. kommersielt laksefiske og generelle
  nyre-/nefrokalsinoseartikler. Flere kildeposter var dubletter mellom leverandorer.

## Siteringsspor

Frosne fro: ultralyd av aal-gonader (`10.1111/jfb.70361`) og radiologisk deteksjon av
nefrokalsinose hos atlantisk laks (`10.1111/jfd.13704`).

- Semantic Scholar: aal-artikkelen ga 0 siteringer og 100 referanser. Lakseartikkelen ga
  2 siteringer og 22 referanser. De to siteringene var Klykken et al. (2023) om
  nefrokalsinose-diagnostikk og en fysiologisk oversikt om nyrenes rolle i
  syre-base-regulering.
- OpenAlex: begge grafkall feilet med HTTP 400. Dette er et adapter/API-feilutfall,
  ikke null siteringer.
- Metodeavvik: preregistreringen satte maks 20 poster per retning. Semantic Scholars
  eksisterende adapter har ikke en limit-parameter og returnerte 100 referanser for
  aal-artikkelen. Alle returnerte poster er bevart i JSON; den manuelle kontrollen
  brukte bare de forste 20. Dette siteringssporet skal ikke brukes til dekningsrate.

## Dom mot preregistreringen

- H1: stottet som retrieval-diversitet. Dekomponerte sok fant unike fiskekilder,
  bl.a. aal-ultralyd/histologi og nefrokalsinose hos andre fiskearter. De fant ikke
  direkte protokollstotte for det konkrete sporsmalet.
- H2: stottet. Sokeutvidelse fant mulig metodebakgrunn, men treffene gir ikke grunnlag
  for score 1-4 eller anbefalt nyredel hos smolt.
- H3: stottet etter metadata-screeningen: ingen direkte kandidat oppfylte de
  forhondsdefinerte vilkarene. Dette er en eksplorativ klassifisering av tittel og
  abstract, ikke en dobbelblind fagkyndig vurdering.
- H4: delvis stottet. Siteringsgrafen fant fiskespesifikke naboarbeider, men ikke en
  ultralydprotokoll for nyren. Ett av de to providerne feilet.

## Tester og begrensninger

Kjorte nettverksfrie tester for kildeadaptere, sok, ranking, profil og deduplisering:

`tests/test_cli.py tests/test_core_adapter.py tests/test_domeneprofil.py tests/test_domeneprofil_generisk.py tests/test_europe_pmc_adapter.py tests/test_openalex_adapter.py tests/test_ranking.py tests/test_resolve.py tests/test_dedup.py`

Utfall: 103 passed pa 0.64 s. Disse testene verifiserer lokal kodekontrakt, ikke live
kildekvalitet.

Begrensninger: topp-10; kun metadata/abstract; sokestrengene ble ikke blindt vurdert av
to fagkyndige; OpenAlex siteringsgraf var utilgjengelig; CORE produserte stoy; dette er
ikke en systematisk oversikt. Null direkte treff betyr derfor bare at denne avgrensede
sporrunden ikke fant stotte.

## Praktisk konklusjon

Behold det forsiktige svaret. La Belegg sokedekomponere og eventuelt tilby relevante
metodeanalogier som tydelig merkede lesetips, men ikke la dem bli anbefaling. For a
finne ut om en bredere database gir reelt bedre dekning, bor neste steg vaere en liten
fagkyndig-annotert sammenligning mot en godkjent akvakultur-/veterinaerbase, med de
samme frosne sporringene og DOI-dedup. Ingen betalt base er aktivert eller vurdert for
lisens/kostnad i denne proben.

## Etterkontroll av avvik

OpenAlex-feilen er lokalisert til sort-syntaksen i adapteren. Med seed
`W7128841028` gir adapterens `sort=-publication_date` HTTP 400 med meldingen
`_publication_date is not a valid field`. Ellers identisk kall med
`sort=publication_date:desc` gir HTTP 200. For denne seed-en rapporterer OpenAlex
0 siterende verk. Syntaksproben og statusene er bevart i
`docs/belegg-openalex-400-diagnostikk-2026-11-08-result.json`. Dette forklarer de to
tidligere 400-feilene som foreldet/ugyldig adapter-syntaks, ikke providerfravaer.

OpenAlex' gjeldende sorteringsveiledning bruker `field:desc`, selv om en annen
oppskriftside fortsatt viser eldre `-field`-syntaks. En kodeendring bor ha en liten,
nettverksfri regresjonstest og bor landes separat fra dette resultatnotatet.

Semantic Scholar-avviket var pa protokollsiden: adapteren sender ingen `limit` og
bruker API-standardens forste side pa 100 referanser. Dette er ikke en fullstendig
bibliografi og heller ikke en kilde som feilaktig returnerte for mange. Adapteren
trenger enten eksplisitt `limit=20` og paginering/avkorting etter kontrakt, eller
preregistreringen ma gjore et eksplisitt unntak. Eksperimentet brukte kun de forste
20 i sin manuelle screening; hele API-responsen er bevart.

Dedupliseringa etter DOI/fallbacktittel ga 116 identiteter, mens normalisert tittel
alene ga 112 grupper. Fem tittelgrupper hadde flere identiteter. Dermed er 116 et
svakt overstimat pa verk dersom metadata ikke matcher. Det endrer ikke at ingen av
treffene ble screenet som direkte ultralydprotokoll for laksefisknyre. Nullen er en
en-persons metadata-screening, ikke en blindet relevansfasit.

## Hva den tverrfaglige evidensen tillater

Etter den forste proben ble primarartikkelen Klykken et al. (2022), DOI
`10.1111/jfd.13704`, kontrollert i fulltekst. Den studerte radiografi, ikke ultralyd.
Histologisnitt ble lagt i rekkefolge fra anterior til posterior for a dekke hele
nyrelengden; radiografisk modell hadde en egen kategori for lengdeutbredelse. Den
rapporterer ogsa falske positive/negative og bare moderat samsvar mellom total
radiografi- og histologisk score. Dette gir en direkte lakseforankret grunn til a
undersoke om lesjonenes utbredelse langs nyren betyr noe. Det viser ikke at ultralyd
ma skanne hele nyren eller kan bruke samme score.

Tang et al. (2024), DOI `10.1111/jvim.17011`, sammenlignet ultralyd, mikro-CT og
histopatologi hos katter. Det er et relevant eksempel pa hvordan en ny modalitet kan
valideres mot vevsreferanse, men ikke direkte evidens om fisk, smolt eller valgt
skanneplan.

Disse to kildene er nok til a formulere en testbar metodehypotese: sammenlign
skanning av hele synlige nyrelengden med et lite sett forhandsdefinerte regioner, og
hold resultatene opp mot blindet histologi pa matchede individer. De er ikke nok til
a foresla ett av skanneomradene som beste praksis. Hypotesen er ny fordi den
kombinerer en lakseradiografiobservasjon med en tverrarts ultralydvalideringsmal; den
ma merkes som ekstrapolasjon og testes, ikke framstilles som konsensus.

