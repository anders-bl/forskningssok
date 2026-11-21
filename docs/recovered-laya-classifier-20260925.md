# Laya-klassifikator: gjenfunnet evalueringssammendrag

Status: sekundærkilde, gjenfunnet 2026-11-18 fra agentkanalens historiske
evalueringsposter. Dette dokumentet bevarer rapporterte aggregater; det er ikke
en rekonstruksjon av rådata eller en replikasjon av evalueringen.

## Proveniens og begrensning

Postene #3831, #3832, #3835 og #3840 i agentkanalen omtaler arbeid fra
2026-09-25. De peker på Laya 0.3.20 (kildekort `4066d5d`) og MASSIVE-testrevisjon
`940fd47a`. Den opprinnelige rapporten ble vist som
`/tmp/wiki-three-tests.R8DVcQ/laya-full-test-regime-2026-09-25.md`. Den og de
tilhørende harness-, prompt- og resultatfilene ble ikke gjenfunnet i den senere
avgrensede arkivsveipen. Hashene er derfor bare bevart slik de står i
oppsummeringspostene, ikke kontrollert mot filer.

Tallene nedenfor er nyttige som historiske spor og søkeinnganger. De må ikke
presenteres som uavhengig verifiserte resultater før primærartefaktene er
funnet eller forsøket er kjørt på nytt.

## MASSIVE-evaluering

En tidlig screening brukte 51 språk med 100 eksempler per språk og rapporterte
makrotreffsikkerhet 0,4008 og ECE 0,3911. En senere full delt evaluering
rapporterte 2 974 eksempler per språk:

| Språk | Treffsikkerhet | F1 | ECE |
|---|---:|---:|---:|
| Engelsk (`en`) | 72,60 % | 0,7259 | 0,2049 |
| Forenklet kinesisk (`zh-CN`) | 51,55 % | 0,5153 | 0,3202 |
| Tradisjonell kinesisk (`zh-TW`) | 45,29 % | 0,4519 | 0,3580 |

Oppsummeringen sier at zh-CN og zh-TW brukte samme 2 974 fasitetiketter og
alternativsett; zh-CN lå 6,26 prosentpoeng over zh-TW. Blant prediksjoner med
konfidens minst 0,90 var rapportert treffsikkerhet 81,88 % for `en`, 65,78 %
for `zh-CN` og 60,85 % for `zh-TW`.

Etterrapporten sier at 8 922 JSON-case-målinger ble utledet på nytt, og at to
vekthasher stemte. Uten JSON-filene og hashverdiene kan ikke dette kontrolleres
fra denne gjenfinningsnoten.

## Separate stresstester og pilot

Den tidlige ordens-/format-screeningen rapporterte 78 % ordensstabilitet for
zh-CN og 75 % for zh-TW, samt bestått formatkontroll i 14 av 18 scenarier med
korte alternativer. Den rapporterte også at `noul` kollapset til en alltid-sann
baseline.

En syntetisk Feishu-test med 64 scenarier rapporterte treff i 20/64 for
`choice` og 18/64 for `four_noul`, i tillegg til feil ved null-kall. Dette er
en separat syntetisk test, ikke del av MASSIVE-resultatene.

En blind huskalibreringspilot var også separat: 16 oppgaver (fire utsagn ved
fire Munzner-nivåer), på engelsk og tradisjonell kinesisk. Status var
`awaiting_human_label`; posten sier uttrykkelig at Laya ikke var kjørt før
menneskeetikettene forelå. Dette er dermed ikke et evalueringsresultat.

## Gjenfinning videre

Neste steg for å oppgradere dette fra sekundærsammendrag til etterprøvbar
forskningspost er å finne eller gjenopprette:

1. evalueringsharness og låst konfigurasjon;
2. prompt- og eksempelsett med datasett-/lisensproveniens;
3. maskinlesbare prediksjoner, etiketter og hashmanifest;
4. rapporten med aggregeringskode og definisjon av ECE/F1.

Før dette finnes, skal sammendraget merkes som gjenfunnet rapportering og ikke
blandes med reproduserte eller blindt vurderte funn.
