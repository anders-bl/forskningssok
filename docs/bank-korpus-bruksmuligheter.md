# Bruksmuligheter for bokbankutdraget

Status: forslag basert på lokal korpuseksport og kodegjennomgang, 2026-10-03.
Dette er en arbeidsplan, ikke en beslutning om at alle bruksområdene skal bygges.

## Omfang og grunnlag

Gjennomgangen omfatter `data/bank_utdrag.jsonl` med tilhørende manifest, profilens
tema- og artsklassifisering, `bank_utdrag.py`, `bank_bakgrunn.py`, synteseveien og
lagrede retrieval-/synteseforsøk. Manifestet oppgir 4 732 biter. Dette er den
versjonerte eksporten, ikke en ny kontroll av hele `boker.db` på 1,5 GB eller av
produksjonskopien.

Eksporten inneholder 68 dokumenter. Temaene nedenfor telles per dokument; ett
dokument kan ha flere temaer. Samlingsnavnene er søkekanaler som fant dokumentet,
ikke en pålitelig fagklassifikasjon.

| Tema | Dokumenter |
|---|---:|
| Infeksjon | 35 |
| Immunitet | 23 |
| Miljø | 21 |
| Velferd | 13 |
| Overvåking | 11 |
| Ernæring | 8 |
| Genetikk | 5 |
| Lever | 4 |
| Maskinsyn | 4 |
| Nyre | 3 |
| Økonomi, skjelett, bildediagnostikk, reproduksjon | 1 hver |

Artsnivået fordeler dokumentene slik: 14 mål, 47 nær, 6 annet og 1 ingen. Dette
er en grov artikkelmerking, ikke en relevansfasit for hvert spørsmål. Én norsk
velferdsveileder står for 813 av 4 732 biter (17,2 %), men er fortsatt bare ett
uavhengig dokument. Bakgrunnsoppslaget begrenser allerede uttrekket til to biter
per bok; dette reduserer repetisjon, men ikke skjevheten i dokumentdekningen.

## Mulige arbeidsflyter

| Arbeidsflyt | Korpusgrunnlag | Dagens støtte | Vurdering |
|---|---|---|---|
| Bakgrunn i syntese | Sterkest i infeksjon, immunitet, miljø og velferd | Implementert gjennom `bank_bakgrunn.py`; bankkilder merkes som bakgrunn og kildekontrolleres sammen med øvrige synteskilder | Fortsett som forsiktig tillegg. Ikke la bakgrunnskilder alene bære påstander om målarten. |
| Kildeoppdagelse | Tema- og artsmerker gir innganger på tvers av samlingene | Ingen egen bankbasert brukerreise funnet; dagens bankoppslag går via syntesen | Beste neste produktsteg: egen, read-only treffliste med dokumentantall, kildeidentitet og tydelig artsnivå. |
| Metode- og verktøyfinn | Noe materiale om overvåking, eDNA, bildeanalyse, ultralyd og presisjonsfôring | Ingen egen bankflate | Avgrens til «finn relevante kilder». Trekkene skal ikke fremstilles som komplett metodeveiledning, særlig når temaet bare har ett til fire dokumenter. |
| Direkte faktasvar | Noen spørsmål har direkte bakgrunn i utdraget | Retrieval finnes; en separat, kildebelagt bank-svarreise er ikke etablert | Ikke bygg svarmodus før dekning og falske treff er målt per spørsmålstype. Null treff skal være et gyldig og synlig resultat. |
| Tverrarts- og analogisøk | 47 dokumenter er merket nær, og seks annet | Artsnivået følger banktreff; syntesen kan få disse som bakgrunn | Nyttig for hypoteser og sammenligning, men analogier må merkes og aldri overføres automatisk til målarten. |

## Foreslått første leveranse: kildeoppdagelse

Start med en read-only søkeflate over det eksisterende utdraget. Behold den
semantiske rangeringen, og gjør hvert treff mulig å vurdere selv:

1. Vis tittel, utdragsbit, tema, artsnivå, samling, proveniens og søkeavstand.
   Dokumenter med flere treff grupperes, slik at mange biter fra samme artikkel
   ikke ser ut som uavhengig støtte.
2. Vis antall unike dokumenter i trefflisten og hvilke temaer som faktisk er
   representert. Ikke presenter temaetiketter som fasit eller som filtre som
   skjuler treff.
3. Skill eksplisitt mellom mål, nær, annet og ukjent. La brukeren åpne en
   originalkilde når proveniensen inneholder en verifiserbar lenke; ikke lag en
   URL fra ufullstendige metadata.
4. Vis «ingen kilder funnet» eller «utdraget dekker ikke spørsmålet» når ingen
   treff passer. Et semantisk topp-treff er ikke i seg selv bevis på dekning.
5. Hold funksjonen uten generering og uten skriving til sitatbank eller utkast.
   Lagre søkelogg bare etter samme personvern- og cachekontrakt som eksisterende
   søk.

Dette gir brukeren en måte å utforske bankens innhold uavhengig av syntese, og
gir samtidig et konkret sted å samle vurderinger av relevante, delvise og
irrelevante treff.

## Måling før bredere bruk

Før eksponering som faktasvar eller metodehjelp bør en kontrollpakke dekke minst:

- spørsmål med direkte dekning i hvert av de store temaene;
- delvis relevante nabospørsmål, særlig metode- og artsoverføringer;
- spørsmål uten dekning, der nærmeste treff skal avvises som utilstrekkelig;
- gjentatte biter fra samme dokument og dokumenter med flere temaer;
- norske og engelske formuleringer.

Annoter relevans på dokumentnivå (direkte, delvis, irrelevant, ingen dekning),
og hold spørsmålene og fasiten adskilt fra terskeljusteringen. Rapporter
presisjon@5, andel dekkede spørsmål med relevant dokument i topp 5, andel
spørsmål uten dekning som likevel får et misvisende treff, samt variasjon i
antall unike dokumenter per resultat. Rapporter også tall separat for mål/nær/annet.

Eksisterende målinger er foreløpige: Mistral-eksperimentet fra 2026-09-26 har
10 dekkede og 10 fjerne spørsmål, men dokumenterer overlappende nabokontroller
og har derfor ikke aktivert terskel. Synteserunden fra 2026-09-27 har bare tre
fullførte kontroller, og historikkrepetisjonen er et ugyldig par. Retrieval-proben
fra 2026-10-02 viser både direkte treff og null treff på detaljerte
ultralydspørsmål. Disse forsøkene begrunner videre måling, men beviser ikke at
banken forbedrer svarene.

### Lokal BGE-probe på tvers av temaer (2026-10-03)

En håndskrevet probe kjørte ti setningsspørsmål mot lokal `boker.db` med lokal
bge-m3 og eksisterende proveniensfilter, BGE-kalibrering og `k=8`. Spørsmålene er
ikke hentet fra brukerhistorikk. Fullt søkesett og treffmetadata er lagret i
`data/bank_korpus_retrieval_probe_2026-10-03.json`; fulltekst er utelatt.

- Fem temaspørsmål (velferd, immunitet, nefrokalsinose/miljø, presisjonsfôring og
  rask mikrobedeteksjon) ga alle treff. De viser at søket finner materiale i
  disse brede temaene, men er ikke relevansannotert og kan ikke telles som
  presisjon eller dekningsgrad.
- Tre smale metode-/målespørsmål ga også treff. Ultralydspørsmålet om validert
  probe-frekvens og skannedekning fikk en nefrokalsinoseartikkel i `skarpt`-båndet
  (L2 0,8317), uten at treffet etablerer dekning av den etterspurte
  ultralydprotokollen. eDNA-spørsmålet fikk blant annet en eDNA-artikkel om en
  annen organisme, men gir ikke grunn til å anta at primere eller deteksjonsgrense
  for lakselus er dekket.
- Begge kontrollspørsmålene utenfor domenet ble avvist som MØRKT uten treff
  (L2 0,9740 og 0,9825).

Dette er et red-team-signal for bruksgrensen: avstandsterskelen avviser
åpenbart uvedkommende spørsmål, men skiller ikke alltid tematisk nærliggende
bakgrunn fra kildebelegg for en spesifikk metode. Kildeoppdagelse kan vise slike
treff med tydelig avgrensning; direkte svar eller metodepåstander trenger egne
relevansetiketter og holdout-kontroller. Målingen brukte lokal `boker.db`, så den
sier ikke noe om Mistral-produksjonsutdraget.

Proben fant samtidig at artikkelen «Precision Feeding Technology» ikke hadde
ernæringstema i den gjeldende eksporten. Jeg sammenlignet gjeldende tematermer med
et foreløpig tillegg av `feeding` mot bare utviklingsdelen av temafasiten: 49
merkede artikler av 78 ga null endrede prediksjoner. Presisjon, gjenfinning og
eksakt temasett var uendret (77,6 %, 84,3 % og 59,2 %). Dette er ingen støtte for
å endre ordlisten: utviklingsdelen inneholder ikke eksempelet som utløste
hypotesen. Ordlisten står derfor uendret; legg til et uavhengig vurdert
utviklingseksempel før en slik profilendring vurderes. Holdout er ikke brukt.

## Neste trinn

1. Lag en håndvurdert, balansert søkepakke med de fire store temaene, noen små
   nisjer, nabospørsmål og spørsmål uten dekning.
2. Kjør pakken mot dagens utdrag og annoter treffene blindt på dokumentnivå.
3. Bruk resultatet til å velge sortering og synlighetsregler for en kildeoppdagelsesflate.
4. Først etter stabil retrieval-måling: vurder egen faktasvarflyt eller
   metodeorientert visning.

Produksjonshelserutene `/health/live` og `/health/ready` svarte 401 ved siste
kontroll. Derfor er produksjonsutdraget og den faktiske brukerreisen der ikke
verifisert i denne gjennomgangen.
