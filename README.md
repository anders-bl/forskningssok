# forskningssok

Entitet-sentrisk litteratursøk — vertikal #4 av samme mal som `bruktmarked` /
`teknisk-enhets-sok` / `rollesok` (skjelettet: `vertikal-sok-mal`). Omdøpt 2026-09-02 fra
`nefrokalsinose-sok`: arkitekturen var alt ~90 % domeneagnostisk, navnet løy ikke lenger om
det (se [[prosjekt/idebank/29-forskningssok-rammeverk]]). **Siden 2026-09-04 er den siste
tideler også ute av koden:** fagfeltet er en datafil (`profiler/*.toml`), valgt med
`FORSKNINGSSOK_PROFIL`, og ingen Python-modul i repoet bærer et fagfelt-spesifikt ord i
kjørende kode. Denne INSTANSEN er fortsatt fiskehelse-scopet — det er profilen som er valgt,
ikke en begrensning i koden. Se §Domeneprofilen som datafil.

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

✅ **Live-verifisert 2026-09-04** — men ikke slik det var planlagt. EBIs `/references`
svarte fortsatt 503 «temporarily unavailable due to maintenance» to dager etter at dette
ble kalt et vedlikeholdsvindu; det er ikke et vindu lenger, og OpenAlex-fallbacken er i
praksis den eneste armen som kjører. Gap-testen ble kjørt mot ekte data via den, og
fungerer: 6 cachede naboer, 5 gap, referanselisten parset korrekt.

### Kilde-union + dekningsforbehold (lagt til 2026-09-04)

Verifiseringen avslørte et problem verifiseringen selv var i ferd med å gå glipp av.
Fallbacken *fungerte* — men den var UFULLSTENDIG: for `10.1111/jfd.70099` kjente OpenAlex
13 referanser, mens Crossref (Wileys egen deposit) oppga 20. UI-et skrev «Papiret siterer
13 kilder selv» som et faktum.

Det er ikke en kosmetisk feil. **En for kort referanseliste gjør gap-testen systematisk
for snill mot seg selv:** hver referanse kilden ikke kjenner, blir en nabo som feilaktig
framstår som «ikke sitert» — et falskt gap. Nøyaktig den feilen proben er bygget for å
avsløre hos Elicit/Consensus/Undermind.

To grep, begge nødvendige:

1. **Union, ikke valg** (`adapters/crossref.py` + `citation_gap._forén`). En referanse
   kjent av én kilde er en referanse. Nøkkelen er DOI når den finnes, normalisert tittel
   ellers — samme to-trinns identitet som selve matchingen, så ingen telles dobbelt.
   Målt: 13 → 20, altså nøyaktig utgiverens eget tall, og de 5 gjenværende gapene holdt
   seg (funnene var ekte — nå også forsvarlige). Crossref er aldri alene nok, siden mange
   utgivere ikke deponerer referanselister offentlig, og feiler derfor stille: en manglende
   supplering velter aldri et svar primærkilden alt har levert.
2. **Dekningsforbehold** når listen fortsatt er kortere enn `reference-count` fra
   utgiverens egen deposit. Da står det i UI-et OG i den eksporterte rapporten hvor mange
   som mangler, og at listen derfor er *for lang, ikke for kort*. Verifisert live på
   `10.1016/j.aquaculture.2022.738104`: 63 av 72. Forbeholdet forsvinner når det ikke
   gjelder — et permanent «kan være ufullstendig» ville blitt lest som støy.

**Sidefunn verdt å merke:** Crossref-supplementet gjorde tre eksisterende gap-tester
nettverksavhengige uten at noe sa fra. De gikk grønt fordi maskinen tilfeldigvis hadde
internett, og `test_europe_pmc_svarer_normalt_bruker_ikke_openalex` sluttet i praksis å
verifisere det navnet lover. Lukket med en autouse-fixture som gjør at ingen test i fila
kan nå nettet uten å overstyre den eksplisitt.

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

### Deploy — Dockerfile + docker-compose.yml (lagt til 2026-09-04)

Samme mønster som `stromkontrol` (privat-pilot-app på Dokploy): `Dockerfile`
(`python:3.14-slim`, `uvicorn api:app`), `docker-compose.yml` (volum `/data`,
`dokploy-network: external`, ingen Traefik-labels i fila — Domains-fanen i
Dokploy-UI-et står for ruting/middleware). `.dockerignore` utelater `venv/`/`.git/`
(uten den kopierte `COPY . .` inn en hel Mac-kompilert venv og full git-historikk —
fanget under bygging, bildet gikk fra å dra med seg venv til en ren 72 MB).

**`paths.py`** samler `cache.db`-stien ETT sted (`FORSKNINGSSOK_DB`-env, default
uendret repo-rot-sti) — `bank.py` og alle tre `adapters/*.py` beregnet denne
uavhengig av hverandre før dette, en reell fare for en "halvveis persistert" cache
ved Dokploy-volum (noen treff overlever redeploy, andre forsvinner stille).

**Live-verifisert med ekte `docker build`/`docker run`, ikke bare lest kode:**
bygget for både `linux/arm64` (min Mac) og `linux/amd64` (Netcup-noden er AMD EPYC).
Kjørte containeren med et volum montert på `/data` og en mock ai-proxy-server på
verten (`host.docker.internal`) — et ekte søk mot Europe PMC/CORE returnerte 3
papirer, embeddet via mock-en (verifiserte `wiki_id="forskningssok"` i requesten),
cachet til det monterte volumet (37 papirer, 4.5 MB), og overlevde en `/api/status`-
sjekk etterpå. Full kjede fra container til ekte kilder til (mocket) embed til disk,
ikke bare «bildet bygger».

DNS er allerede satt (Anders, deSEC) — `forskningssok.lauvasdata.no` → `159.195.20.82`,
verifisert identisk med `stromkontrol.lauvasdata.no`.

**Live siden 2026-09-04.** Deployet, DNS + TLS + ruting verifisert med ekte
Let's Encrypt-sertifikat (`ops/autorisering_smoketest.py --dry-run` i lauvasdata:
9 ok, 0 feil). Ett reelt driftsfunn underveis: Domains-fanens innstillinger var
lagret i Dokploy-panelet men aldri skrevet til den kjørende containeren («lagret,
ikke deployet») — `docker inspect` viste kun Basic Auth-labelen, ingen
`traefik.http.routers.*` — løst med en eksplisitt redeploy.

### To tilgangsmiddlewares, kun én aktiv om gangen

`docker-compose.yml` definerer BEGGE, Dokploys Domains-fane refererer kun den ene:

- **`forskningssok-auth@docker`** (Basic Auth, delt statisk credential) — live nå.
  Fungerer uten portal-konto, for enhver som har credentialet.
- **`forskningssok-forwardauth@docker`** (ekte portal-SSO, lagt til 2026-09-04) —
  Traefik spør `/api/auth/forward` FØR proxy, samme endepunkt ADR-042 bruker for
  wiki-instanser. Ingen credentials for en innlogget, grantet bruker. Krever en
  ekte portal-konto med `app_access="forskningssok"` — Ulvens Basic Auth-lenke
  slutter å virke for ham inntil invitasjonen hans faktisk er fullført.

  **En kjent felle traff oss live ved første bytte** (`konsepter/kjente-feller`
  §Auth/ForwardAuth, dokumentert allerede 2026-06-22): `address` MÅ peke internt
  på backend-containeren (`http://lauvasdata-portal-xaxnqv-backend-1:8000/...`),
  ALDRI på det offentlige `api.lauvasdata.no`. Peker den offentlig, ruter Traefik
  forespørselen gjennom seg selv på nytt, og det andre hoppet overskriver
  `X-Forwarded-Host` til `api.lauvasdata.no` — endepunktet finner da ingen app og
  svarer 403 «Ukjent app-host». Fikset til intern adresse, live-verifisert
  etterpå. **Restrisiko:** containernavnets Dokploy-suffiks (`xaxnqv`) kan endre
  seg ved en full gjenskaping av portal-appen — samme feil dukker opp igjen om
  det skjer, sjekk `docker ps | grep backend` på nytt da.

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

## Ett arbeidsrom med skuff — modusbryteren er borte (2026-09-04)

Fram til nå var «Les» og «Skriv» to modi bak en bryter i toppbaren, og et sitat kunne
bare havne i en notatliste. Anders' brief var at flaten «ikke er så oversiktlig»: søk og
treff til venstre, lesevindu i midten, en dokumentbehandler som **kommer opp under** når
man siterer og kan trekkes opp og redigeres direkte i, og relevans til høyre som blir
varmere over tid.

Skallet er derfor nå ETT: tre paneler over en skuff. Skuffen er kollapset til en
44px-linje til du trenger den, spretter opp av seg selv når du siterer, og dras til
ønsket høyde i grepet på toppkanten. Poenget med at den ligger under og ikke bak en
bryter: et sitat kan lande i dokumentet uten at du forlater papiret du leser.

### Sitat ↔ dokument: ett lager, valgfritt medlemskap

Hybriden Anders valgte framfor både «alt inn i dokumentet» og «dokumentet er opt-in».
`sitater.utkast_id` er nullbar:

- Er et dokument åpent når du siterer, festes sitatet til det med én gang.
- Er det ikke det, blir sitatet **løst** — synlig i skuffens «Løse»-linse, festbart senere.
- «Løsne» setter kolonnen tilbake til NULL. `slett_sitat` er den ENESTE veien til faktisk
  tap, og må velges eksplisitt. Å slette et dokument etterlater sitatene, ikke sletter dem.

De tre linsene i skuffen (I dokumentet / Løse / Alle) er tre spørringer mot samme rad —
ingen av dem kopierer noe, et sitat har én identitet uansett hvilken linse du ser det
gjennom.

### Varme — to lag, synlig adskilt

«Relevansen blir varmere og varmere» er implementert som to lag som slås sammen i ett
panel men aldri blandes til ett tall, fordi de to er ulike slags påstander:

| Lag | Kilde | Hukommelse | Skala i UI |
|---|---|---|---|
| **varig** | `bank.varme` — akkumulert av det du gjør | overlever dokumentbytte og omstart | relativ (mot listas maks) |
| **nå** | `bank.lignende_tekst` mot dokumentteksten | glemmer alt ved dokumentbytte | absolutt (`1 - avstand/2`) |

Vekter: sitert 6, festet til dokument 4, åpnet 1. Sitering (og festing) sprer 30 % av sin
egen vekt til papirets fem nærmeste semantiske naboer — det er grunnen til at panelet kan
løfte fram noe du **aldri har åpnet**: ukjent, men i selskap med noe du brukte. Åpning
sprer ikke, og telles én gang per papir per økt; ellers hadde panelet målt navigasjon i
stedet for interesse. Ingen forfall: varmen synker aldri av seg selv, et ubrukt papir blir
kaldt relativt, ikke absolutt.

Kortet navngis av den **sterkeste** handlingen, ikke den siste (`HENDELSE_RANG`).

**Tre ekte feil fanget live under bygging** (chrome-devtools mot ekte cache, ikke antatt
riktig) — alle tre var tilfeller av at flaten sa noe annet enn dataen:

1. *«nå»-laget var maks-normalisert.* Tolv kandidater lå på avstand 0.955–1.002 — ~5 %
   spredning — og normaliseringen tegnet dem ALLE som nesten fulle stolper. Panelet
   påstod «alt er brennhett» der sannheten var «alt ligger middels nær, og omtrent like
   nær». Byttet til absolutt skala: en flat gruppe ser nå flat ut.
2. *Fargerampen gikk gjennom grått.* Rett RGB-lerp kald→varm treffer rgb(175,152,140) på
   midten, en avmettet grå som forsvant mot `--surface` — altså nettopp de halvfulle
   stolpene, som er de vanligste. HSL-interpolasjon løste det ikke: endepunktene ligger
   ~180° fra hverandre, «korteste vei» er tvetydig, og implementasjonen valgte veien om
   magenta. Løst med et eksplisitt mellomstopp (`--lunken`) og to korte RGB-segmenter.
3. *Kortet sa «du har lest det» om et papir jeg nettopp hadde sitert* — `siste_hendelse`
   ble overskrevet av en sidelasts «apnet». Derav `sterkeste_hendelse`.

### Lagring og deling

Skuffen eksporterer dokumentet slik det står — brødteksten din **pluss** sitatene festet
til det, med full kildehenvisning — via `/api/rapport/dokument` (`rapport.dokument_blokker`,
den femte malen). Markdown og PDF fra samme Blokk-liste som resten, «Kopier» legger
Markdown på utklippstavlen, «Del» sender PDF-en til systemets egen delingsmeny
(`navigator.share`) med nedlasting som fallback. Verktøyet laster ingenting opp noe sted
— deling er at DU sender filen.

Dette er den eneste malen som blander egen prosa med sitert kildetekst, og skillet er
derfor bygget inn i blokk-typene (`p` mot `sitat` + kildelinje): en delt PDF må aldri
kunne leses som om du selv skrev det du siterte.

### To feil i skuffen, funnet etter at den var «ferdig» (2026-09-04)

- **Slettedialogen løy.** «Sitatene du har lagret blir liggende som løse» — men
  `slett_utkast` rørte ikke `sitater`, så `utkast_id` pekte på en rad som ikke fantes.
  Sitatet forsvant dermed fra BEGGE arbeidslinsene: «Løse» spør på `IS NULL`, «I
  dokumentet» på en id ingen kan velge. Synlig bare under «Alle». Løsningen skjer nå i
  `bank.slett_utkast`, der invarianten hører hjemme — ikke ved at frontend husker å rydde.
- **Sitat-telleren i toppbaren frøs** så snart du byttet til «Løse»-linsen, fordi den ble
  satt som en bivirkning av «I dokumentet»-linsens henting. Nå har den sin egen.

Og én ytelsessak: «nå»-laget koster en full embedding av utkastteksten (bge-m3 lokalt,
ai-proxy i Dokploy). Autolagringen fyrer også når bare tittelen endret seg, så den ber nå
om varme med `{tvungen: false}` og hopper over hentingen når teksten er uendret. Alt annet
(sitering, festing, fanebytte) endrer det VARIGE laget og må tvinge en henting.

## Domeneprofilen som datafil (2026-09-04)

```bash
# standard — uendret oppførsel for Ulven-instansen
venv/bin/uvicorn api:app --port 8420

# et annet fagfelt: navn i profiler/, eller absolutt sti til en .toml utenfor repoet
FORSKNINGSSOK_PROFIL=/sti/til/mitt-fagfelt.toml venv/bin/uvicorn api:app --port 8420
```

Profilen eier fagmiljøer, fagtidsskrifter, målobjekt-termer, homonym-kollisjoner,
forskningsakser — **og UI-tekstene**. Det siste er poenget: verdiene ble samlet i
`domeneprofil.py` alt 2026-09-02, men ni steder i `frontend/index.html` sa fortsatt «laks»
rett ut, og `rapport.py` skrev det inn i eksporterte PDF-er. Det er de stedene et
profilbytte garantert ville glemt — og de ville ikke feilet, bare påstått feil fagfelt.
Flaten leser dem nå fra `/api/profil`.

**Bevist, ikke påstått.** `tests/test_domeneprofil_generisk.py` laster
`tests/fixtures/annetfagfelt.toml` — bygningsakustikk, valgt fordi det deler null vokabular
med lakseoppdrett — og sjekker at fiske-oppførselen faktisk FORSVINNER: et laksepapir er
ikke lenger domene-nært, aksenavnene skifter, båndingen snur rekkefølgen, og merketeksten i
en eksportert rapport følger med. Å lese koden og ikke se ordet «laks» beviser ingenting om
hva den gjør.

Én av testene er en detektor (`test_ingen_python_modul_navngir_fagfeltet_i_kjorende_kode`):
den parser AST-en til hver modul og feller fagfelt-ord i strengliteraler, men lar
docstrings og kommentarer stå — de er institusjonell hukommelse om HVORFOR en mekanisme
finnes, og skal nevne det konkrete tilfellet den ble bygget for. **Positiv kontroll kjørt:**
en plantet literal i `scoping.py` ble felt med fil og linjenummer, og detektoren gikk grønt
igjen da den ble fjernet. Tolv grønne tester på første kjøring er ellers nettopp når en
detektor skal mistenkes for ikke å måle noe.

Verifisert live side ved side: to instanser, samme kode, ulik profil — `★ / ⚠ art? /
«nephrocalcinosis salmon»` mot `◆ / ⚠ rom? / «reverberation time classroom»`, med akser,
«Om»-panel og søke-eksempel byttet i takt.

⚠ **Det finnes ingen andre ekte profiler enn fiskehelse.** Akustikkprofilen er en
testfixtur, ikke et fagfelt noen bruker. Mekanismen er verifisert; at et VILKÅRLIG fagfelt
gir gode treff er ikke — kildene (Europe PMC, CORE) er biomedisinsk tunge, og et fagfelt
utenfor den dekningen vil merke det uansett hvor generisk profil-laget er.

## Overvåking — hva som dekker hva (2026-09-04)

Fire lag, og de ser ulike ting. Kartlagt før noe nytt ble bygget, i stedet for å legge en
fjerde sjekk oppå tre eksisterende:

| lag | hvem | ser |
|---|---|---|
| crash-loop | `silverbullet/ops/container_helse.py`, cron på noden hvert 10. min | at containeren restarter — dekker enhver container, også denne |
| HTTP oppe/nede | Uptime Kuma | at URL-en svarer |
| **feil inne i appen** | GlitchTip (`GLITCHTIP_DSN`) | 500-er og degradering mens containeren er frisk og HTTP er 200 |
| kilde-nåbarhet | «Om»-panelet via `/api/status` | om Europe PMC/OpenAlex/CORE/Crossref svarer NÅ |

Det tredje laget var hullet: Anders traff en ekte feil 2026-09-04 (sitering feilet fordi
embeddingen falt) mens containeren var frisk og forsiden svarte 200. Verken restart-telling
eller en HTTP-sjekk kan se det.

### Scoping av feilsporing — ikke alt som skjer er en alarm

Taksonomien er bokbankens (`modernnetworkobservability` §The art of alerts): event →
notification → alert → incident. `_skal_rapporteres` er porten:

- **Vær** (502/503/504 — kilden er nede): slippes IKKE gjennom. EBI lå nede i dagevis i
  september; uten porten ville hvert brukersøk blitt en hendelse.
- **Forventet avvisning** (400/404/422): brukerinput, ikke en bug. Slippes ikke gjennom.
- **Vår feil** (500, ufangede unntak): slippes gjennom.
- **Fanget degradering**: porten ser den ikke, så den rapporteres EKSPLISITT der den skjer
  (`_rapporter_degradering`). En feilende embedder gjør varme-panelet og «Lignende» stille
  tomme mens appen svarer 200 — en `except` uten rapportering er hvordan det ble usynlig.

### Uptime Kuma — `/health/ready`, offentlig

Helsesjekken følger husstandarden (`konsepter/helsesjekk`, arvet fra `ny-tjeneste-mal`),
ikke et endepunkt oppfunnet her. Første utkast VAR oppfunnet, og det var
`reimplementer-i-stedet-for-gjenbruk` (`misc/feilantagelser` 2026-08-29): standarden i
`rollesok/app/health.py` var bedre på tre punkter jeg ikke hadde tenkt på.

| sti | spør | konsument |
|---|---|---|
| `/health/live` | lever prosessen? Aldri disk, aldri nett | Docker HEALTHCHECK |
| `/health/ready` | kan vi ta trafikk? **Asserterer på innhold** | Uptime Kuma |
| `/health` | full detalj, bak `X-Internal-Key` | mennesker |

`/ready` er den som betyr noe: den svarer **503 hvis cachen er tom**, ikke bare hvis
endepunktet er nede. Det er FDR-065-lærdommen — *en monitor mot skallet melder grønt i
nedetid*. En tom cache kan ikke besvare et eneste søk.

⚠ **`/api/status` er IKKE en monitor-sti.** Den gjør fem utgående kall (Europe PMC,
OpenAlex, CORE, Crossref, EBI-referanser) for å svare på «er kildene nåbare nå». Hvert 60.
sekund blir det 7 200 kall til fire tredjeparter i døgnet, for å svare på et spørsmål om
VÅR tjeneste.

**Oppsett (valgt 2026-09-04: unnta stien fra auth, så Kuma slipper en hemmelighet):**

1. Dokploy → forskningssok → Domains: legg til en path-basert regel som unntar
   `/health` fra `forskningssok-auth`-middlewaren. I Traefik-termer er det en egen router
   med `PathPrefix(\`/health\`)`, høyere `priority` enn hovedruteren, og TOM
   `middlewares`-liste.
2. Redeploy — Domains-innstillinger er «lagret, ikke deployet» til containeren startes på
   nytt (se §Deploy).
3. Verifiser at unntaket faktisk traff:
   `curl -s -o /dev/null -w "%{http_code}\n" https://forskningssok.lauvasdata.no/health/ready`
   → **200** (ikke 401). Får du 401, traff ikke regelen.
4. Uptime Kuma: HTTP(s)-monitor mot `https://forskningssok.lauvasdata.no/health/ready`,
   forventet status 200, intervall 300 s. Ingen legitimasjon nødvendig.

**Hva stien lekker offentlig:** kun `{"status": "pass"}`. Ingen tall, intet profilnavn,
intet tjenestenavn — de bor bak `X-Internal-Key` på `/health`. Testdekket
(`test_helse_lekker_ingen_tall_uten_noekkel`), fordi et offentlig endepunkt som stille
begynner å lekke er en regresjon ingen ville lagt merke til.

## Tips for domeneavgrensning

Et bart `nephrocalcinosis`-søk treffer mest human-medisin (nyrestein hos mennesker
dominerer literaturvolumet). Legg til artstermer for oppdrettsdomenet, f.eks.
`"nephrocalcinosis salmon"` eller `"nephrocalcinosis aquaculture smolt"` — ærlig
uten-gjetning-prinsippet betyr at verktøyet ikke stille legger til artsfilter du ikke ba om.
Se også §Species-trap-motvekt over — treff utenfor målarten flagges, ikke filtreres.

## Testet

151/151 tester (`pytest -q`), alle mocket/offline unntatt live-verifiseringen i denne
README-en. Dekker: embedder-valget (AI_PROXY_URL → ai-proxy, ellers lokal bge-m3 — se
§Embedder), delt DB-sti på tvers av bank.py/adapters (§Deploy), parsing av ekte Europe
PMC/OpenAlex/CORE-felt (inkl. lisens/OA-status),
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
