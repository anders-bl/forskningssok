# Addendum: preregistrering av ett-hops siteringsspor

Tidspunkt: 2026-11-08, etter metadata-proben i commit `bf63a117423853d07ee54792f4b72ee050e6c042`
og for alle kall i dette addendumet.

## Formal

Teste om eksisterende siteringsgraf-kapasitet kan utvide et smalt fiskespesifikt
ultralydsok uten a anta at flere siteringer betyr direkte evidens.

## Fryste frontereferanser og kall

1. DOI `10.1111/jfb.70361`: den returnerte artikkelen om ultralyd for gonadekjonn
   hos europeisk aal, validert mot histologi. Hent ett hopp av siteringer og
   referanser fra Semantic Scholar og OpenAlex.
2. DOI `10.1111/jfd.13704`: artikkelen om radiologisk deteksjon av nefrokalsinose
   hos atlantisk laks. Hent ett hopp av siteringer og referanser fra Semantic Scholar
   og OpenAlex.

Maksimalt 20 poster per grafretning/kilde. Ingen rekursjon, syntese eller modellkall.
Bevar returnerte DOI-er, titler, aar, kallestatus og antall. Ikke bruk sitat-kontekst
som faglig relevansdom uten a kontrollere selve artikkelen.

## Hypotese og stoppregel

- H4: ett-hops sporing kan finne nye artikler som beskriver ultralyd hos fisk, men
  funn av annen anatomi eller art forblir metodebakgrunn.
- En kandidat er direkte evidens bare hvis metadata/abstract eksplisitt viser
  laksefisknyre, nefrokalsinose, ultralydskanneomrade og score/validering.
- Rate-limit, manglende dekning eller feilsvar rapporteres som kunne ikke males for
  den kilden; det omtolkes ikke som null siteringer.

