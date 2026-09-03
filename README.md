# forskningssok

Entitet-sentrisk litteratursøk — vertikal #4 av samme mal som `bruktmarked` /
`teknisk-enhets-sok` / `rollesok` (skjelettet: `vertikal-sok-mal`). Omdøpt 2026-09-02 fra
`nefrokalsinose-sok`: arkitekturen var alt ~90 % domeneagnostisk (kun `ranking.py`s
domeneliste er fiskespesifikk — se [[prosjekt/idebank/29-forskningssok-rammeverk]]), navnet
løy om det. **Denne INSTANSEN er fortsatt fiskehelse-scopet** — domeneprofilen er ikke
trukket ut som egen injiserbar fil ennå (§Neste steg), så repoet er generisk i navn før det
er generisk i kode. Ikke et løfte om at andre fagfelt fungerer i dag.

Bygget for Ulven (marinbiolog, firma skanner 500 fisk/t med ultralyd) — svimmel av støy i
eget litteratursøk, ville ha hard empiri, tverrfaglig, om nefrokalsinose hos oppdrettsfisk:
faser, miljøfaktorer, regenerasjon etter sjøsetting, livsløp.

Full scoping, domenepresisering og «hvorfor akkurat disse valgene»:
plattformwikien, `prosjekt/idebank/28-nefrokalsinose-litteratursok` (opprinnelig scope) og
`prosjekt/idebank/29-forskningssok-rammeverk` (generaliseringen, denne omdøpingen, og
kildevalgene under).

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python cli.py "nephrocalcinosis smolt seawater transfer" -n 10
venv/bin/python cli.py --lignende 10.1111/jfd.70099   # relasjonelt: nærmeste i cachen
venv/bin/python cli.py --gap 10.1111/jfd.70099        # citation-gap-testen, se under
venv/bin/python -m pytest -q
```

## Citation-gap-testen (`citation_gap.py`)

Aaron Tays fleksibilitets-probe (idébank #29): *«finn papirer som burde vært sitert av X,
men ikke er det.»* Spesialiserte forskningsverktøy (Elicit, Consensus, Undermind, AI2
Paperfinder) feilet denne testen systematisk i uavhengige tester — den skiller ekte
relasjonelt søk fra et pent rangert ekko av det som uansett siteres. `--gap ID` henter
papirets faktiske referanseliste (Europe PMC `/references`) og viser hvilke av `bank.py`s
semantiske naboer som IKKE står der — kandidater for menneskelig vurdering, ikke en dom
(samme ærlighets-prinsipp som resten av verktøyet).

⚠ **`/references`-delressursen er IKKE live-verifisert mot ekte data ennå** — EBIs
endepunkt var i et vedlikeholdsvindu («temporarily unavailable due to maintenance», 503)
under hele byggingen 2026-09-02 14:34–14:38 UTC, bekreftet live gjentatte ganger, mens
`/search` var oppe hele tiden. `RuntimeError`-disiplinen ble likevel live-verifisert:
kjøring mot ekte 503 gir en tydelig feilmelding, ikke et stille «0 gap» som ville sett ut
som «alt er sitert». Parsingen følger EBIs dokumenterte reference-schema (se
`adapters/europe_pmc.py:referanser` sin docstring) — kjør `--gap` på nytt når
vedlikeholdsvinduet er over for å bekrefte feltene faktisk stemmer.

## Arkitektur — de fire trinnene

| Trinn | Modul | Kilde |
|---|---|---|
| Resolve | `resolve.py` (kopi, uændret) — brukt KUN for eksakt-tittel-flagg, se under | `vertikal-sok-mal` |
| Aggreger | `adapters/europe_pmc.py` (påkrevd) + `adapters/core.py` (tilleggskilde, se under) — spørretid + 24t TTL-cache | Europe PMC (EU, EMBL-EBI) + CORE |
| Ranger | `ranking.py` — domene-nærhet-bånd + (ferskhet, siteringer) | `rank.py` (kopi, uendret) |
| Strukturer | `schemas.py:PaperDossier` | — |

**Pluss ett lag mer enn malen spesifiserer:** `bank.py` — sqlite-vec-cache av
abstract-embeddinger (bge-m3, husets delte embedder), for `--lignende`-søk. Dette er den
konkrete gjenbruken av husets kunnskapsbank-mønster (`bøker/fag_bank.py` +
`fag_sok.py`: embed → sqlite-vec → avstand-rangert søk) — **ikke** `bøker/hoster.py`
sin CC-lisens-gate, som løser et annet problem (permanent redistribuerbar korpus).
`bank.py` er en privat, TTL-ånds cache av API-metadata (abstract, ikke fulltekst) for
ett verktøys søk — samme juridiske klasse som ADR-004, ikke bok-banken.

### Embedder — lokalt vs. Dokploy (lagt til 2026-09-04)

`bank.py`s embedder er miljø-avhengig, ikke ett fast valg: **lokalt** (Anders' Mac)
brukes fortsatt husets delte bge-m3-embedder (`silverbullet/ops/semantisk_sok.py`) via
en `sys.path`-import — den kaller til slutt en Ollama-instans på `localhost`/hjemme-
flåtenoden, uoppnåelig fra en Dokploy-container på Netcup. **Sett `AI_PROXY_URL`**
(kun i Dokploy-miljøet) og `bank.py` bytter i stedet til `ai-proxy`s `/embed`
(mistral-embed, EU-direkte, nås internt på `dokploy-network` — samme mønster
smartsok/wiki allerede bruker der). `AI_PROXY_WIKI_ID` (default `"forskningssok"`)
brukes kun til kost-attribusjon i ai-proxy, ikke autentisering — nettverksisolasjon
(kun containere på `dokploy-network` når endepunktet) ER auth-grensen.

**Begge er 1024-dim (ingen skjema-endring), men IKKE samme vektor-rom** — bge-m3 og
mistral-embed er målt ulike fordelinger. `cache.db` må derfor være embed-modell-REN:
ALDRI kopiere en lokal `cache.db` inn i prod-volumet (de er allerede strukturelt
atskilt — lokal fil er gitignored, prod starter tomt). Prod-deploy koster småbeløp i
ekte Mistral-API-bruk (mistral-embed er billig — se `ai-proxy/main.py`s prisliste),
ikke lenger gratis som lokal Ollama.

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

## Tredje kilde — CORE (institusjonsarkiv/gråtekst)

`adapters/core.py` — institusjonelle open-access-repositorier (masteroppgaver, ph.d.-
avhandlinger), den klassen norsk gråtekst Europe PMC aldri indekserer. Slått sammen med
Europe PMC i selve søket (`cli.py:sok_og_ranger`, lagt til 2026-09-02 — adapteren var
bygget og live-verifisert en økt tidligere, men sto ubrukt inntil da). Europe PMC er
PÅKREVD kilde (feil der stanser søket); CORE er en TILLEGGSKILDE — en CORE-feil
degraderer synlig via `kilder`-feltet i `/api/sok`-responsen, tar aldri ned et ellers
fungerende søk. `dedup.py` fjerner dubletter på tvers av kildene (DOI FØRST, normalisert
tittel som fallback — samme funn kan finnes både Europe PMC-indeksert og som
institusjonsarkiv-kopi).

## Ranking — ADR-013s pending-prinsipp på et nytt korpus

Se `ranking.py`-docstringen. Kort: `arkitektur/adr-013-rangering-konfidens-ferskhet`s
«un-anriket ≠ verdiløst» blir her «et ferskt, lite-sitert papir ≠ et dårlig papir» —
domene-nærhet (norske fagmiljøer: Havforskningsinstituttet, Veterinærinstituttet, NMBU,
Nofima, Pharmaq + kjerne-fagtidsskrifter) rangeres FØR siteringstall, ellers ville et
2026-Havforskningsinstituttet-funn (0 sitater, for nytt) begravd seg selv under et
2015-MIT-funn (50 sitater) i et helt annet fagfelt.

**Species-trap-motvekt** (lagt til 2026-09-02, Svart hatt-funn): ren embedding-avstand har
ingen art-/domenefilter — et menneske-nyrestein-funn (delt nøkkelord «nephrocalcinosis»)
kan rangere høyt blant fiskefunn kun på tekstlig nærhet, observert live med et ekte
CYP24A1-funn. `arts_naer()` bånd papirer som nevner målarten (laks/oppdrettsfisk) over de
som ikke gjør det — FLAGGER, filtrerer aldri bort. Se `domeneprofil.py:arts_naer_tekst`.

Denne bandingen gjaldt opprinnelig kun hovedsøket (`ranking.py:ranger`) — `bank.py`s
relasjonelle paneler (`--lignende`, «Lignende»-fanen, citation-gap, og FDR-038s ambient
Relevans-panel i Skriv-modus) viste samme `arts_naer`-flagg, men i ren avstand-rekkefølge,
så et artsfjernt treff kunne likevel ligge ØVERST med bare et advarselsikon ved siden av
(idébank #30s navngitte gap). Lukket 2026-09-02 (natt): `bank.py:_naboer_fra_rader()`
bånder nå (domene_naer, arts_naer, avstand) i alle fire paneler, samme prinsipp som
hovedsøket — ingen kandidat fjernes, kun rekkefølgen endres. Frontend viser et ★ (samme
symbol som hovedsøkets resultatliste) for domene_naer, slik at omordningen er synlig,
ikke en stille overraskelse mot avstand-tallet ved siden av. Live-verifisert mot ekte
cachede papirer i kjørende app (chrome-devtools): et CORE-treff med lavere avstand enn et
Journal of Fish Diseases-treff ble korrekt vist ETTER det domene-nære treffet.

## Ikke gjort (bevisst, v1)

- **Ekte evidensnivå-KLASSIFISERING** (en rangeringsakse: systematisk oversikt > studie >
  case-rapport) — krever NLP over fulltekst, ikke bygget. Det som FINNES (lagt til
  2026-09-02): `evidensniva.py` — et mønster-badge for visning (signalord forfattere selv
  bruker: «systematic review», «case report» …), aldri brukt til å filtrere/rangere. Se
  modulens egen docstring for hvorfor det IKKE er det samme som ekte klassifisering.
- **DisCoCat-typet sitasjonsgraf** (typede morfismer: støtter/motsier/bygger-på) —
  eksplisitt utsatt, samme datamangel-felle (få eksempler mot 1024 dim) som
  `konsepter/discocat-operator` selv fant på wiki-grafen. `bank.py` er ren
  distribusjonell likhet, første søyle, ikke tredje.
- **Betalte kilder** (Web of Science, Scopus) — først når firmaet faktisk bestiller.
- **Fulltekst-mining** — kun abstract i v1.
- **Integrasjon mot firmaets ultralyd-skanndata** — eget, mye større prosjekt.

## Lisens/tilgang — hvorfor ikke «koble til bruktsøk»

Opprinnelig idé (idébank #28): koble til `bruktsøk`/`bruktmarked` for pris/lisens på
litteratur Ulven vil kjøpe. Undersøkt 2026-09-02: bruktmarked er ISBN-baserte fysiske
varer (Speider/FDR-029: Open Library-oppslag → Bokbörsen/Aurelia-priser) — journalartikler
har DOI, ikke ISBN, og omsettes ikke der. Strukturelt feil domene, ikke koblet til.

Det som faktisk finnes: `adapters/openalex.py:tilgang()` leser lisens/fri-PDF/utgiver fra
DET SAMME OpenAlex-kallet `konsepter()` allerede gjør (ingen ekstra HTTP) — ekte
SPDX-aktig lisensstreng (f.eks. `cc-by-nc-nd`), direkte fri-PDF-lenke når den finnes,
utgivernavn, og oa_status. **Ingen prisdata finnes noe sted i OpenAlex** — `/api/tilgang`
returnerer ærlig fravær (aldri en gjettet pris), med en `doi.org`-lenke til utgiveren når
ingen åpen kopi er funnet.

## «Om»-panelet — metodikk/transparens i selve UI-et (lagt til 2026-09-04)

Gul/svart hatt-gjennomgang med Ulven som bruker fant ett konkret gap: alt over (kilder,
hva verktøyet aldri gjør, domeneprofilen) sto kun i denne README-en — en bruker som
eksplisitt krever «hard empiri» møter et black-box-inntrykk i UI-et selv om rangeringen
faktisk er lesbar Python. `frontend/index.html` fikk en «ℹ️ Om»-knapp i toppbaren som
åpner et modalvindu med samme innhold destillert: kilde-nåbarhet (live, via `/api/status`
— nå med CORE lagt til der, ikke bare Europe PMC/OpenAlex), hva som ALDRI gjøres (ingen
syntese, ingen fulltekst-mining, flagger/omordner men filtrerer aldri), domeneprofilen
eksplisitt, og hvor dataen faktisk lever (lokal sqlite, ingen deling ennå).

**Ekte rendrings-bug fanget og fikset under bygging** (chrome-devtools, ikke antatt
riktig): modalens `hidden`-attributt ble overstyrt av `.om-overlay{ display:flex }` —
klasse-selektoren og UA-stilarkets `[hidden]`-regel har lik spesifisitet, og siden
forfatterstilen kommer sist i kaskaden vant `display:flex` uansett attributt. Fikset med
en eksplisitt `.om-overlay[hidden]{ display:none }`-regel (høyere spesifisitet).
Live-verifisert: skjult ved last, åpner med kilde-status synlig, lukkes med
Escape/bakgrunnsklikk/×-knapp.

## Tips for domeneavgrensning

Et bart `nephrocalcinosis`-søk treffer mest human-medisin (nyrestein hos mennesker
dominerer literaturvolumet). Legg til artstermer for oppdrettsdomenet, f.eks.
`"nephrocalcinosis salmon"` eller `"nephrocalcinosis aquaculture smolt"` — ærlig
uten-gjetning-prinsippet betyr at verktøyet ikke stille legger til artsfilter du ikke ba om.
Se også §Species-trap-motvekt over — treff utenfor målarten flagges, ikke filtreres.

## Testet

148/148 tester (`pytest -q`), alle mocket/offline unntatt live-verifiseringen i denne
README-en. Dekker: embedder-valget (AI_PROXY_URL → ai-proxy, ellers lokal bge-m3 — se
§Embedder), parsing av ekte Europe PMC/OpenAlex/CORE-felt (inkl. lisens/OA-status),
TTL-cache (ingen dobbelt HTTP-kall — `tilgang()` og `konsepter()` deler cache-nøkkel),
kilde-feil ≠ stille tomt resultat (verifisert BÅDE mocket og mot en ekte 503 live for alle
tre kilder), fler-kilde-dedup (DOI/tittel på tvers av Europe PMC+CORE), ADR-013-banding
(ferskt+domenenært+artsnært slår eldre+høyt-sitert+urelatert/annen-art) — nå bevist i
BÅDE hovedsøket OG `bank.py`s relasjonelle paneler (en artsfjern/domene-fjern nabo som er
NÆRMERE i ren avstand plasseres likevel etter, se §Species-trap-motvekt), embed-cache er
idempotent og skiller nær fra fjern (`--lignende`), citation-gap-matching (DOI- og
tittel-match ekskluderer korrekt, whitespace/tegnsetting-robust, PMID-løse DOI-papirer
faller korrekt til OpenAlex uten unødvendig 422), emnesøk-med-treff feilrapporteres aldri
som «ingen treff», slett av sitater/utkast gir ærlig 404 på ukjent id, fire rapportmaler
(kildesamling/sitatnotater/citation-gap/omfang) i både Markdown og PDF, species-trap-caset
fra 2026-09-02 reprodusert som regresjonstest, og evidensniva-mønstre gjenkjennes/degraderer
ærlig til «Ukjent design» uten treff.
