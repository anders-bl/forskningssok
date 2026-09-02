# nefrokalsinose-sok

Entitet-sentrisk litteratursøk for oppdrettsfisk-patologi — vertikal #4 av samme mal som
`bruktmarked` / `teknisk-enhets-sok` / `rollesok` (skjelettet: `vertikal-sok-mal`). Bygget
for Ulven (marinbiolog, firma skanner 500 fisk/t med ultralyd) — svimmel av støy i eget
litteratursøk, ville ha hard empiri, tverrfaglig, om nefrokalsinose hos oppdrettsfisk:
faser, miljøfaktorer, regenerasjon etter sjøsetting, livsløp.

Full scoping, domenepresisering og «hvorfor akkurat disse valgene»: plattformwikien,
`prosjekt/idebank/28-nefrokalsinose-litteratursok`.

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python cli.py "nephrocalcinosis smolt seawater transfer" -n 10
venv/bin/python cli.py --lignende 10.1111/jfd.70099   # relasjonelt: nærmeste i cachen
venv/bin/python -m pytest -q
```

## Arkitektur — de fire trinnene

| Trinn | Modul | Kilde |
|---|---|---|
| Resolve | `resolve.py` (kopi, uændret) — brukt KUN for eksakt-tittel-flagg, se under | `vertikal-sok-mal` |
| Aggreger | `adapters/europe_pmc.py` — spørretid + 24t TTL-cache | Europe PMC (EU, EMBL-EBI) |
| Ranger | `ranking.py` — domene-nærhet-bånd + (ferskhet, siteringer) | `rank.py` (kopi, uendret) |
| Strukturer | `schemas.py:PaperDossier` | — |

**Pluss ett lag mer enn malen spesifiserer:** `bank.py` — sqlite-vec-cache av
abstract-embeddinger (bge-m3, husets delte embedder), for `--lignende`-søk. Dette er den
konkrete gjenbruken av husets kunnskapsbank-mønster (`bøker/fag_bank.py` +
`fag_sok.py`: embed → sqlite-vec → avstand-rangert søk) — **ikke** `bøker/hoster.py`
sin CC-lisens-gate, som løser et annet problem (permanent redistribuerbar korpus).
`bank.py` er en privat, TTL-ånds cache av API-metadata (abstract, ikke fulltekst) for
ett verktøys søk — samme juridiske klasse som ADR-004, ikke bok-banken.

### Hvorfor `resolve.py` IKKE styrer hovedsøket

`resolve.py` sin kandidat-gren matcher på SUBSTRENG — riktig for et navn («Ola Hansen»),
feil for en emnesetning mot lange papirtitler («nephrocalcinosis smolt seawater
transfer» er verken substreng av eller inneholder noen ekte tittel). Europe PMCs egen
relevans-søk ER resolve-steget for oppdagelses-søk her. `resolve()` brukes derfor kun
til å oppdage det ene ekte tilfellet den passer: spørringen er ORDRETT en tittel
(Ulven limer inn en kjent tittel). Se kommentaren i `cli.py:sok_og_ranger`.

## Kildevalg — hvorfor Europe PMC, ikke arXiv

Vurdert eksplisitt (Anders spurte om husets arXiv-maskineri, `bøker/arxiv_harvest.py`
m.fl., kunne gjenbrukes som KILDE — ikke bare mønster):

- **Feil domene.** arXiv dekker math/cs/physics/q-bio — fiskeveterinær-patologi
  publiseres i `Journal of Fish Diseases`/`Aquaculture`/PubMed-indekserte tidsskrifter,
  ikke arXiv. Live-søk 2026-09-02 traff 0 relevante treff der.
- **Feil bruksklasse.** `bøker/hoster.py`/`oai_harvest.py` sin CC-BY/SA/CC0-gate løser
  «bygg en permanent, redistribuerbar bok-bank» — de fleste veterinær-tidsskrift-artikler
  er verken CC-lisensiert eller trenger å være det for et privat søkeverktøy. Husets EGEN
  målte tabell i `oai_harvest.py` (2026-08-23) viser **Europe PMCs OAI-endepunkt er dødt
  (404)**, og de fleste akademiske OAI-kilder gir 0 % CC-utbytte — CC-gaten ville
  strupt nesten alt reelt innhold i dette domenet.
- **Hva SOM overføres:** embed/chunk/sqlite-vec-mønsteret (`hoster.py`, `fag_bank.py`) og
  husets delte bge-m3-embedder (`silverbullet/ops/semantisk_sok.py:embed`) — se `bank.py`.

**Europe PMC (EU, EMBL-EBI)** er i stedet primærkilden: REST-søk, ingen nøkkel, og
`citedByCount` + `isOpenAccess` følger med i selve kjernesvaret — den planlagte
OpenAlex-siteringsberikelsen (spec'et som «andreklipp») er derfor IKKE bygget i v1, den
var overflødig. Live-verifisert 2026-09-02: `"nephrocalcinosis salmon"` → 201 treff,
inkl. Pharmaq Analytiq / Journal of Fish Diseases-funn direkte relevante for domenet.

## Ranking — ADR-013s pending-prinsipp på et nytt korpus

Se `ranking.py`-docstringen. Kort: `arkitektur/adr-013-rangering-konfidens-ferskhet`s
«un-anriket ≠ verdiløst» blir her «et ferskt, lite-sitert papir ≠ et dårlig papir» —
domene-nærhet (norske fagmiljøer: Havforskningsinstituttet, Veterinærinstituttet, NMBU,
Nofima, Pharmaq + kjerne-fagtidsskrifter) rangeres FØR siteringstall, ellers ville et
2026-Havforskningsinstituttet-funn (0 sitater, for nytt) begravd seg selv under et
2015-MIT-funn (50 sitater) i et helt annet fagfelt.

## Ikke gjort (bevisst, v1)

- **Evidensnivå-klassifisering** (systematisk oversikt > studie > case-rapport) —
  krever NLP over fulltekst, ikke bygget. `PaperDossier` har ikke feltet ennå.
- **DisCoCat-typet sitasjonsgraf** (typede morfismer: støtter/motsier/bygger-på) —
  eksplisitt utsatt, samme datamangel-felle (få eksempler mot 1024 dim) som
  `konsepter/discocat-operator` selv fant på wiki-grafen. `bank.py` er ren
  distribusjonell likhet, første søyle, ikke tredje.
- **Betalte kilder** (Web of Science, Scopus) — først når firmaet faktisk bestiller.
- **Fulltekst-mining** — kun abstract i v1.
- **Integrasjon mot firmaets ultralyd-skanndata** — eget, mye større prosjekt.

## Tips for domeneavgrensning

Et bart `nephrocalcinosis`-søk treffer mest human-medisin (nyrestein hos mennesker
dominerer literaturvolumet). Legg til artstermer for oppdrettsdomenet, f.eks.
`"nephrocalcinosis salmon"` eller `"nephrocalcinosis aquaculture smolt"` — ærlig
uten-gjetning-prinsippet betyr at verktøyet ikke stille legger til artsfilter du ikke ba om.

## Testet

15/15 tester (`pytest -q`), alle mocket/offline unntatt live-verifiseringen i denne
README-en. Dekker: parsing av ekte Europe PMC-felt, TTL-cache (ingen dobbelt HTTP-kall),
kilde-feil ≠ stille tomt resultat, ADR-013-banding (ferskt+domenenært slår
eldre+høyt-sitert+urelatert), embed-cache er idempotent og skiller nær fra fjern
(`--lignende`), og at en emnesøk-med-treff aldri feilrapporteres som «ingen treff».
