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
