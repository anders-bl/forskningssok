# Oppfolgingsplan for bankkorpuset

Status: arbeidsplan, kontrollert 2026-10-03. Ingen profil- eller retrieval-endringer
er gjort. Ingen nye modellkall er kjort i denne oppfolgingen.

Dette dokumentet gjor funnene i [bruksmulighetskartet](bank-korpus-bruksmuligheter.md)
og [Mistral-kalibreringsoppgaven](mistral-bank-kalibrering-oppgave.md)
om til tre spor med tydelige leveranser, avhengigheter og stoppunkter.

## 1. Blind evaluering

### Hva som allerede finnes

Kalibreringsoppgaven beskriver allerede kravene til et forsvarlig oppsett:
frys sporsmal og fasit for maling, hold tidligere pilotsporsmal utenfor blind
holdout, fa to fagkyndige til a merke treff blindt, og rapporter per
bruksomrade. Denne oppfolgingen erstatter ikke den protokollen.

Den faktiske koden bruker bankutdrag som bakgrunn i forskningssyntesen. Jeg
fant ikke en selvstendig bank-sokerute. Evalueringen bor derfor starte med
syntesebakgrunn som forste brukerreise. En mulig framtidig kildeoppdagelsesflate
ma fa sin egen del og egne akseptgrenser for den testes.

### Arbeidsrekkefolge

1. Frys dette oppsettet og sporsmalsfilen i Git for forste modellkall.
2. Lag sporsmal etter brukerbehov og faktatype, ikke ved a parafrasere gamle
   evalueringssporsmal. Bruk kategoriene direkte dekning, delvis bakgrunn,
   naerliggende men utilstrekkelig dekning, og forventet ingen dekning.
3. La en fagkyndig kontrollere at hvert sporsmal er realistisk, at onsket
   kildegrunnlag faktisk dekker sporsmalet, og at negative kontroller ikke
   utilsiktet har et svar i korpuset. Registrer fasit og begrunnelse for sok.
4. Skill utviklingssett fra holdout etter tema og faktatype. Hold
   paraphraser av samme faktum i samme del. Pilotsporsmalene fra september og
   allerede malte sporsmal fra retrieval-probene kan vaere kjente sanity-kontroller,
   men ikke blind holdout.
5. Kjor frosset sok mot en identifisert korpus-snapshot og modell. Bevar ra
   foresporsler, ra treff og metadata per sporsmal. Ikke juster terskel eller
   rangering etter at holdout-resultatene er sett.
6. To vurderere merker treffene uavhengig og uten synlige avstander,
   modellnavn eller arm. Skill relevans som svargrunnlag fra relevans som
   lesetips. Uenighet beholdes og avgjores med begrunnelse.
7. Kjor en blind sammenligning av syntese med bank av/pa pa samme sporsmal og
   ovrige kilder. Vurder pastander, kildestotte, irrelevante bankkilder og om
   bankmaterialet faktisk forbedrer svaret. Ikke la flyt eller sprakkvalitet
   erstatte faktasjekken.
8. Rapporter alle saker enkeltvis, ogsa tomme og feilede kjoringer. Skill
   "bestatt", "feilet" og "kunne ikke males". En kjoring uten bevart radata er
   ikke et maleresultat.

Eksisterende protokoll krever ogsa eksakt korpus- og retrieval-identitet,
modellidentitet, faktiske parametere og ra svar. Produksjonsstatus er fortsatt
uverifisert: lokal `bank_utdrag.db` mangler, og produksjonens health-ruter har
tidligere svart 401. En lokal maling kan derfor ikke omtales som produksjonsmaling.

### Avgrensning for forste runde

- Forste runde maler retrieval-egnethet og syntesens kildebruk for den
  implementerte bakgrunnsreisen.
- Ingen terskelendring, profilendring eller produksjonsaktivering folger
  automatisk av resultatet.
- Hvis fasit ikke kan etableres av to fagkyndige, eller korpusidentiteten ikke
  kan festes, stoppes den aktuelle malingen som "kunne ikke males".
- Vurderinger av om banken skal brukes til metodefinn eller direkte svar er
  egne beslutninger; de kan ikke utledes fra at det finnes semantiske treff.

## 2. Gjenbruksrettigheter for Mattilsynets fiskeforrapport

### Kontrollert offentlig materiale

Mattilsynets [rapportside for 2022](https://mattilsynet.no/for/overvakingsprogram-for-fiskefor/overvakingsprogram-for-fiskefor-2022)
og [Havforskningsinstituttets egen rapportpost (Rapport fra havforskningen
2023-36)](https://www.hi.no/hi/nettrapporter/rapport-fra-havforskningen-2023-36)
viser rapporten som utgitt av HI pa oppdrag fra Mattilsynet. HI sin PDF sier
"Distribusjon: Apen". Posten lenker til PDF-en [Program for overvaking av fiskefor: arsrapport for prover
innsamlet i 2022](https://mattilsynet-xp7prod.enonic.cloud/_/attachment/inline/00b36682-5c14-49b4-b874-26d484769c3d:91a86d753a98b59afebfd3b43e4b95e9617c719c/Rapport_%20Overv%C3%A5kingsprogram%20for%20fiskef%C3%B4r%202022.pdf).
PDF-en oppgir Havforskningsinstituttet som rapportutgiver og Mattilsynet som
oppdragsgiver. Forsiden sier distribusjon "Apen".

Jeg fant ingen lisens- eller gjenbruksbetingelse pa rapportsiden eller i
PDF-teksten i verken Mattilsynets eller HI sin kopi ved sok etter opphavsrett,
lisens, rettigheter, Creative Commons, CC BY og kopiering.
"Apen" distribusjon dokumenterer at rapporten er tilgjengelig, men avklarer
ikke i seg selv vilkarene for a kopiere hele eller deler av teksten inn i et
annet korpus. Rettighetsstatus for innlemming er derfor fortsatt uavklart.

### Overordnede styringssignaler kontrollert 2026-10-03

Mattilsynet har tre fagdepartementer: Landbruks- og matdepartementet (LMD),
Naerings- og fiskeridepartementet (NFD) og Helse- og omsorgsdepartementet
(HOD). LMD har etatsstyringsansvaret; HOD og NFD har faglig etatsstyring pa
sine omrader, ifolge [HODs etatsside](https://www.regjeringen.no/no/dep/hod/organiseringen-av-helse-og-omsorgsdepartementet/etater-og-virksomheter-under-helse--og-omsorgsdepartementet/underliggende-etater/mattilsynet/id279765/).
Havforskningsinstituttet ligger under NFD, ifolge [NFDs etatsside](https://www.regjeringen.no/no/dep/nfd/org/etater-og-virksomheter-under-narings--og-fiskeridepartementet/Subordinate-agencies-and-institutions/havforskningsinstituttet-/id115321/).

Den viktigste tverrgaende teksten jeg fant er [Digitaliseringsrundskrivet,
punkt 1.2](https://www.regjeringen.no/no/dokumenter/digitaliseringsrundskrivet/id3103320/).
Det krever oversikt over data og registrering i Felles datakatalog i angitte
tilfeller, og sier at tilgjengeliggjoring skal folge viderebruksreglene. Det
anbefaler at offentlig produsert tekst ved publisering har bruksvilkar som
apner for innhosting og gjenbruk til sprak-teknologiske formal; vilkarene bor
vaere videre enn for andre gjenbruksformer. Regjeringens [retningslinjer for
offentlige data](https://www.regjeringen.no/no/dokumenter/retningslinjer-ved-tilgjengeliggjoring-av-offentlige-data/id2536870/)
ber i tillegg om tydelige bruksvilkar og peker pa CC BY 4.0 eller NLOD som
standardlisenser.

For rapportens konkrete avsendere sjekket jeg ogsa 2026-styringsdokumentene:
[LMDs tildelingsbrev til Mattilsynet](https://www.regjeringen.no/contentassets/f3630965333e4af2a5f1007dbdc0bad9/statsbudsjett-2026-tildelingsbrev-til-mattilsynet.pdf)
har ikke treff pa "gjenbruk", "apne data" eller "sprakteknologi". [NFDs
tildelingsbrev til HI](https://www.regjeringen.no/contentassets/76a9cd4d079d415dbd6d7faa0ebae0e9/hi-tildelingsbrev-2026.pdf)
har et delmal om a gjore relevante data tilgjengelige og teller datasett,
nedlasting og datasiteringer; det har ikke treff pa "gjenbruk", "apne data"
eller "sprakteknologi". Brevene gir dermed en tydelig generell retning mot
tilgjengelige data, men ingen spesifikk lisens eller rapporttillatelse for
denne teksten.

Tolkning for dette tilfellet: det finnes et godt grunnlag for a be etatene
oppgi eller fastsette klare gjenbruksvilkar, og Digitaliseringsrundskrivet
navngir uttrykkelig sprak-teknologisk bruk. Men rundskrivets ordlyd er en
anbefaling pa tekstvilkar, og de generelle dataforingene beviser ikke alene
hvem som har opphavsretten eller om denne bestemte rapporten kan kopieres inn
i korpuset. Be derfor HI som rapportutgiver/rettighetsforvalter og Mattilsynet
som oppdragsgiver om en eksplisitt avklaring. Hvis de ikke kan avgjore det,
be dem rute sporsmalet til rettighetshaver eller sine respektive departementer
(LMD for Mattilsynets etatsstyring, NFD for HI; HOD/NFD for Mattilsynet dersom
fagansvaret er relevant).

### Tryggeste neste handling

Sporr forst HI, som forfatterinstitusjon og utgiver, og Mattilsynet, som
oppdragsgiver. Bruk HIs [generelle postmottak](https://www.hi.no/hi/om-oss/kontaktinformasjon)
(`post@hi.no`) og Mattilsynets [felles postmottak](https://www.mattilsynet.no/kontakt-oss/kontaktinformasjon)
(`postmottak@mattilsynet.no`); be dem rute foresporselen til den som forvalter
publiseringsavtalen/rettighetene, og be de to etatene samordne svaret. For
rettighetstillatelse er disse operative kontaktpunktene mer direkte enn a
starte hos departementene. LMD er Mattilsynets etatsstyrer og NFD HI sin eier;
departementene er eskalering dersom etatene ikke vet hvem som kan klarere
rapporten.

Be om skriftlig svar pa om rapporttekst kan lagres og indekseres i et internt
forskningskorpus, hvilke utdragslengder som eventuelt kan vises, om resultatet
kan brukes i genererte synteser, og hvilke krav som gjelder for attribusjon,
videre distribusjon og sletting.

Utkast til henvendelse, ikke sendt:

> Hei. Vi vurderer a bruke rapporten "Program for overvaking av fiskefor,
> arsrapport for prover innsamlet i 2022" i et avgrenset, internt
> forskningssoksystem. Kan dere avklare hvem som forvalter gjenbruksrettighetene,
> og om folgende er tillatt: (1) lagring av rapporttekst i et tilgangsstyrt
> korpus, (2) indeksering med embeddings, (3) visning av korte, kildebelagte
> tekstutdrag, og (4) bruk av utdrag som bakgrunn i genererte forskningsutkast?
> Oppgi gjerne tillatt utdragslengde, attribusjonskrav, viderebruksbegrensninger
> og eventuell lisens. Hvis rettighetene ligger hos Havforskningsinstituttet,
> ber vi om riktig kontaktpunkt.

Fram til skriftlig svar er registrert bor rapporten holdes utenfor nye
korpuseksporter. En kildehenvisning eller lenke til rapporten kan vurderes
separat fra kopiering av innhold; dagens inntaksregel og eierbeslutning gjelder.
Jeg har ikke sendt henvendelsen.

## 3. Korpusdekning og sokeflate

### Korpusfunn som pavirker utformingen

Versjonert uttrekk har 4 732 biter fordelt pa 68 dokumenter. Dokumenttelling,
ikke bit-telling, bor vaere grunnenheten i grensesnittet. En velferdsveileder
star for 813 biter, sa ratt antall treff vil ellers overdrive bredden.

Temaetikettene er ujevne: infeksjon, immunitet, miljo og velferd har flest
dokumenter; flere temaer har bare ett til fire. Artsmerkingen er 14 mal, 47
naer, 6 annet og 1 uten niva. Dette stotter en kildeoppdagelsesflate med synlig
dekning og proveniens, men ikke et lofte om at alle temaer eller metoder er
godt dekket.

Den lokale BGE-proben fra 2026-10-03 fant at naerliggende sok kan gi skarpe
avstander uten a dekke den konkrete metoden i sporsmalet. Derfor ma flaten vise
at et semantisk treff er en kandidat til lesning; avstand er ikke et
dekningstempel.

### Konkret MVP-kontrakt

- Read-only sok over godkjent, versjonert uttrekk.
- Treff grupperes per unikt dokument. Vis antall dokumenter separat fra antall
  treffbiter.
- Hvert dokument viser tittel, kilde/proveniens, eventuell verifiserbar
  original-URL, tema, artsniva og hvorfor utdraget matcher.
- Ukjent eller manglende artsniva vises eksplisitt; systemet lager ikke
  original-URL fra ufullstendig metadata.
- Brukeren kan se at et treff er tematisk naert uten at det hevdes a svare pa
  sporsmalet. Sma temaer far synlig dokumentantall.
- Tomt treff og "ingen direkte dekning funnet" er gyldige utfall.
- Ingen generering, skriving til sitatbank eller automatisk innlemming av
  treff i utkast i MVP-en.
- Sokefraser logges bare dersom eksisterende personvern- og cachekontrakt for
  sok dekker det.

### Verifikasjon for bygging

1. Bekreft om brukerreisen faktisk onskes, og om den bare skal vise kilder eller
   ogsa stotte videre lesning.
2. Bekreft produksjonsuttrekk, proveniensfelter og tilgangskontroll. Lokal
   manifestkontroll er ikke bevis pa produksjonslikhet.
3. Bruk den blinde retrieval-pakken fra spor 1 til a male toppresultater,
   dokumentdeduplisering, avvisning av nabotreff og tomtreff.
4. Gjor MVP-en forst etter at rettighetsfilteret kan skjule kilder som ikke kan
   vises, og etter at sokets faktiske API-flate og tilgangsmodell er bekreftet.

## Apne avhengigheter

| Punkt | Status | Neste eier/handling |
|---|---|---|
| Godkjenne brukerreise og risikoniva | Venter | Anders velger om forste evalueringsrunde kun dekker syntesebakgrunn |
| Faglig fasit og blind merking | Venter | To fagkyndige vurderere etter at sporsmalssettet er frosset |
| Mattilsynet/HI sine gjenbruksvilkar | Uavklart | Menneskelig avsender sender utkastet og legger svaret i repoet |
| Produksjonsuttrekk og runtime | Ikke verifisert | Eier med produksjonstilgang bekrefter snapshot, modell og tilgang |
| Kildeoppdagelsesflate | Forslag | Produktarbeid etter evaluerings- og rettighetsporter |

Ingen av disse apne punktene er grunnlag for profilendring eller bredere
produksjonsbruk. Nar avhengighetene er lost, registreres maledata i egne,
committede forsoksfiler med radata og identiteter etter evidenskravene i
arbeidsomradets AGENTS.md.
