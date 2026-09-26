# Oppgave: mistral-kalibrering for bank-bakgrunn i prod

Avgrenset oppfølgingsoppgave. Åpner codex' fail-closed (`6b25844`) så Ulven får
bankbakgrunn i PROD. Ikke en blokker for å lande `integrasjon/bank-full` lokalt.

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
- Mistral-utdraget bygges i prod-miljøet: `bank_utdrag.bygg()` med `AI_PROXY_URL` satt
  (embedder = mistral-embed; lagres ved siden av cache.db på det monterte volumet).
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
5. Koble inn i `bank_bakgrunn.py` `kal`-valget: bruk `mistral_kalibrering` når
   `bank_utdrag.embed_modell() == "mistral-embed"` og en kalibrering finnes; ellers
   stående fail-closed.

## Drepbare kontroller (ellers er terskelen feilkalibrert)

- Setnings-lengde, ikke tittel: korte 3-4-ords queries faller utenfor kalibreringen og
  gir kunstig høy avstand (dokumentert artefakt i `bok_kalibrering`).
- Dekket domene -> `skarpt`: en spørring i fiskehelse-utdragets tetteste tema MÅ lande
  skarpt (analog til bok-bankens "kubernetes"-kontroll). Ligger den på grensen er
  terskelen feil, ikke banken tynn.
- Off-domene -> `MORKT`: en spørring klart utenfor fiskehelse MÅ lande MORKT. Faller
  den ikke i MORKT, slipper terskelen søppel inn.

## Akseptkriterier

- `mistral_kalibrering` finnes som ÉN kilde; ingen kopiert terskel.
- Query-settet er committet med spørringen ved siden av hvert tall (re-målbart).
- Begge drepbare kontroller (dekket->skarpt, off-domene->MORKT) passerer.
- `bank_bakgrunn` bruker mistral-kalibreringen i prod; fail-closed står når ingen
  kalibrering finnes.

## Forbehold

- Snill mot ai-proxy: minimal live-prøving, bruk fixtures der mulig, respekter
  rate-limits (kalibrering er et bulk-embed - ett pass, ikke en løkke).
- Alternativet (kjøre bge-m3 ende-til-ende i prod) er et større infra-valg, ikke
  denne avgrensede oppgaven.

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
