#!/usr/bin/env python3
"""syntese_fortelling.py — LLM-generert SAMMENHENG-FORTELLING over et emne, bygget PÅ
ekte kilder.

Forskjell fra dossier.py:
- dossier.py: fem adskilte seksjoner (Hard vitenskap/Hull/Trygt-kjedelig/Frontier/Gammel tro)
- syntese_fortelling.py: ÉN sammenhengende fortelling som vever kildene sammen ("slik henger
  disse funnene sammen") — Ulvens formvalg 2026-09-11 (prosjekt/forskningssok-smartsyntese-for-ulven).

Samme jernregel som dossier: HVER påstand bærer en kildereferanse [#id] hentet ordrett fra
det faktiske kildesettet. verifiser_kilder() sjekker hver referanse mekanisk etterpå og
fjerner alt som ikke finnes — samme etterprøvbarhet som dossier.py.

Bygget 2026-09-11 etter Ulvens formvalg (Anders: "Han virket mest interessert i en
sammenheng/fortelling, men flere syntese-former har gjerne verdi."). Brukerinitiert-only,
ALDRI kjørt automatisk — dette gjør ekte, kostbare LLM-kall.

kall_llm() er BEVISST det eneste stedet som snakker med en ekstern modell — ingen nøkkel
er koblet til ennå (leverandørvalg utsatt til Anders har bestemt seg). Resten av pipelinen
(henting → prompt → etterkontroll) er ferdig og testbar uavhengig av det.

Bruk:
  python3 syntese_fortelling.py --emne "fiskeøye-skanning identifikasjon"
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import domeneprofil  # noqa: E402
from ai_assistent import hent_fra_cache  # noqa: E402
from paths import DB  # noqa: E402
from art_niva import klassifiser as art_niva  # noqa: E402
from domeneprofil import domene_naer_tekst  # noqa: E402
from ranking import ranger_cachede  # noqa: E402

# Matcher [#<id>] — id-en er cachet papers.id. I praksis kan dette være DOI eller
# kilde-URL for enkelte adaptere; den må alltid samsvare ordrett med cachet kilde-ID.
# Fang hele innholdet mellom [# og ] slik at en modell som setter inn DOI/URL i
# stedet for papers.id blir synlig og kan avvises, ikke stille overses.
_REF_MØNSTER = re.compile(r"\[#([^\]]+)\]")
_UTTRYKKELIG_KILDEHULL = "Ingen kilder i utvalget dekker dette"

# Samme kapping som dossier.py — et to-ords emne kan treffe hundrede av løst relaterte
# cachede papirer. Målt live 2026-09-11: «nephrocalcinosis salmon» alene ga 205 treff;
# pluss sok_utstyr ga 612 totalt. Et ukappet kall sendte 612 kilder til lokal Ollama og
# sprengte konteksten stille. Kappingen er det som gjør et syntese-kall mulig.
MAKS_KILDER = 25


def hent_kandidater(emne: str, db_path: Path = DB) -> list[dict]:
    """Ekte kilder for emnet, PLUSS utstyrs-/teknisk-litteratur hvis profilen definerer
    et eget søk for det (PROFIL["sok_utstyr"]). Samme cache, ingen egen database.

    Kappet til MAKS_KILDER — emne-treff beholder prioritet over utstyr-treff fordi de
    settes inn FØRST i unike-dicten, og et Python-dict bevarer innsettingsrekkefølge."""
    emnepapirer = ranger_cachede(list(hent_fra_cache(emne, db_path)), emne)

    utstyr_query = domeneprofil.PROFIL.get("sok_utstyr")
    utstyrpapirer = ranger_cachede(list(hent_fra_cache(utstyr_query, db_path)), utstyr_query) if utstyr_query else []

    unike: dict = {}
    for p in emnepapirer + utstyrpapirer:
        unike[p["id"]] = p
    return list(unike.values())[:MAKS_KILDER]


def bygg_prompt(emne: str, papirer: list[dict]) -> str:
    """Bygg LLM-prompten for SAMMENHENG-FORTELLING.

    Forskjell fra dossier.py::bygg_prompt:
    - Ikke fem adskilte seksjoner
    - Én sammenhengende fortelling som vever kildene sammen
    - Fokus på "hvordan henger disse funnene sammen" — mekanismer, årsakssammenhenger,
      tverrfaglige broer

    Instruksen i punkt 1-4 er en avtale med modellen, ikke en garanti —
    verifiser_kilder() er garantien."""
    def kildeblokk(p: dict) -> str:
        domenetekst = f"{p.get('forfattere') or ''} {p.get('tidsskrift') or ''}"
        niva = art_niva(p.get('tittel'), p.get('abstract'), p.get('mesh')).niva
        art = niva == "maal"
        domene = domene_naer_tekst(domenetekst)
        kategori = "DIREKTE_KANDIDAT" if art else "ANALOGI_ELLER_BAKGRUNN"
        if p.get("kilde") == "bok-bank" and not art:
            # Bankens bakgrunn er kuratert kontekst, ikke funn for målobjektet: egen
            # merkelapp så modellen (og en leser av prompten) ser hvor den kom fra.
            kategori = "BANK_BAKGRUNN"
        return (
            f"[{kategori}] [#{p['id']}] {p.get('tittel', '(uten tittel)')} — "
            f"{p.get('forfattere', 'Ukjent forfatter')} ({p.get('aar', 'u.å.')}), "
            f"kilde={p.get('kilde', '?')}\n"
            f"Artsnivå={niva} Domenenær={domene}\n"
            f"Abstract: {p.get('abstract') or '(ingen abstract tilgjengelig)'}"
        )

    direkte = [p for p in papirer if art_niva(p.get('tittel'), p.get('abstract'), p.get('mesh')).niva == "maal"]
    analogier = [p for p in papirer if p not in direkte]
    kildeliste = (
        "DIREKTE_KANDIDATER — kan brukes som direkte evidens for målobjektet:\n"
        + ("\n\n".join(kildeblokk(p) for p in direkte) or "(ingen)\n")
        + "\n\nANALOGI_ELLER_BAKGRUNN — kan ikke brukes som direkte evidens for målobjektet:\n"
        + ("\n\n".join(kildeblokk(p) for p in analogier) or "(ingen)")
    )

    return f"""Du er en forskningsassistent som skal skrive en SAMMENHENG-FORTELLING om: "{emne}"

STRENGE REGLER (brudd gjør outputen ubrukelig og blir fjernet mekanisk etterpå):
1. Bruk KUN fakta fra kildelisten under. Aldri fra egen forhåndskunnskap.
2. HVER setning som hevder noe faktisk MÅ avsluttes med kildereferansen i formatet
   [#<id>], hentet ORDRETT fra listen under (flere kilder: [#12][#47]).
3. Mangler god kildedekning for et poeng, skriv det ærlig
   ("Ingen kilder i utvalget dekker dette") — ikke fyll ut med antakelser.
4. Dikt ALDRI opp en [#id] som ikke står i kildelisten. Den blir oppdaget og fjernet.
5. En kilde med Artsnivå annet enn maal er ikke direkte evidens for målarten
   (naer = annen eller uspesifisert art, annet = organisme utenfor fagområdet,
   ingen = ingen organisme nevnt). Bruk den bare
   som eksplisitt merket analogi eller bakgrunn, og skriv hva som er overført og hva som
   ikke er dokumentert hos målobjektet. Ikke bruk humanmedisin eller andre arter som om
   de var forsøk på målobjektet.
6. En påstand om målobjektets sykdom, fysiologi eller behandling kan bare støttes av
   en DIREKTE_KANDIDAT. Hvis bare ANALOGI_ELLER_BAKGRUNN dekker poenget, skriv at det
   er en hypotese eller et kunnskapshull; ikke presenter det som et funn.
7. Når et poeng ikke har dekning, skal du skrive kun "Ingen kilder i utvalget dekker
   dette". Ikke skriv en udokumentert faktasetning først og legg kunnskapshullet etterpå.
8. Hold hver faktapåstand i én kort setning. Avslutt hver slik setning med én eller
   flere kildereferanser, eller bruk kunnskapshullet alene på egen linje.

FORM: Skriv ÉN sammenhengende fortelling som vever disse kildene sammen. Ikke fem
adskilte seksjoner. Fortellingen skal svare på:
- Hvordan henger disse funnene sammen?
- Hvilke mekanismer eller årsakssammenhenger tegner seg?
- Hvor er det tverrfaglige broer (f.eks. humanmedisin som kaster lys over fiskehelse)?
- Hvor er det hull eller motstridende funn?

Strukturér fortellingen naturlig (ikke merk seksjoner eksplisitt), men la den ha en
klar begynnelse (hvem/hva), midt (mekanismer/sammenhenger), og slutt (hull/frontier).

KILDER:
{kildeliste}
"""


def bygg_reparasjons_prompt(emne: str, papirer: list[dict], fortelling: str) -> str:
    """Bygg ett avgrenset reparasjonskall for manglende sitatdekning.

    Reparasjonen får samme kildeliste og artsregler som førstegenereringen, men skal
    ikke utvide innholdet. Den kan bare sette inn en gyldig referanse når kilden faktisk
    dekker setningen, eller fjerne/sette igjen et eksplisitt kunnskapshull.
    """
    return bygg_prompt(emne, papirer) + f"""

REPARASJONSMODUS:
Revider teksten under uten å legge til nye fakta eller nye kilder. Behold bare påstander
som kan støttes av kildelisten. Hver faktapåstand skal stå i én kort setning med gyldig
[#id] på slutten. Hvis en påstand ikke kan støttes, erstatt hele påstanden med nøyaktig:
Ingen kilder i utvalget dekker dette
Returner kun den reviderte fortellingen, uten kildeliste og uten forklaring på endringene.

TEKST SOM SKAL REPARERES:
{fortelling}
"""


def verifiser_kilder(fortelling_tekst: str, papirer: list[dict]) -> tuple[str, list[str]]:
    """Mekanisk etterkontroll — stol ALDRI på at LLM-en fulgte instruksen i bygg_prompt().
    Enhver [#id] som ikke finnes i det faktiske kildesettet er et konfabulert sitat og
    MÅ fjernes, ikke bare flagges — en lesbar men uverifiserbar påstand er verre enn en
    synlig hullete én. Returnerer (renset_tekst, avviste_id-er)."""
    kjente = {str(p["id"]) for p in papirer}
    avvist: list[str] = []

    def _sjekk(match: re.Match) -> str:
        if match.group(1) not in kjente:
            avvist.append(match.group(1))
            return "[KILDE IKKE VERIFISERT — PÅSTAND FJERNET]"
        return match.group(0)

    renset = _REF_MØNSTER.sub(_sjekk, fortelling_tekst)
    return renset, avvist


def evaluer_kvalitet(fortelling_tekst: str, papirer: list[dict]) -> dict:
    """Mål mekanisk kvalitet i fortellingens narrativdel.

    Dette er en gate- og observasjonsmåling, ikke en semantisk sannhetsdom. Den kan
    oppdage manglende kildemerking, ukjente kilde-ID-er, ubrukt kildemateriale og
    manglende eksterne lenker. Om en sitert kilde faktisk støtter hele påstanden,
    krever fortsatt menneskelig eller modellbasert innholdsvurdering.

    Kildelisten etter ``---`` tas ikke med i setningsmålingen. En eksplisitt
    ``Ingen kilder ...``-setning telles som synlig kunnskapshull, ikke som en vanlig
    kildebelagt påstand.
    """
    narrativ = fortelling_tekst.split("\n---", 1)[0]
    enheter: list[str] = []
    for avsnitt in narrativ.splitlines():
        linje = avsnitt.strip()
        if not linje or linje.startswith("#") or linje.startswith("["):
            continue
        enheter.extend(del_i_setninger(linje))

    kjente = {str(p["id"]) for p in papirer}
    brukte: set[str] = set()
    ugyldige: list[str] = []
    dekket = 0
    eksplisitte_hull = 0
    mangler = 0
    for enhet in enheter:
        refs = _REF_MØNSTER.findall(enhet)
        if refs:
            gyldige = [ref for ref in refs if ref in kjente]
            if gyldige:
                dekket += 1
                brukte.update(gyldige)
            for ref in refs:
                if ref not in kjente and ref not in ugyldige:
                    ugyldige.append(ref)
        elif _UTTRYKKELIG_KILDEHULL.lower() in enhet.lower():
            dekket += 1
            eksplisitte_hull += 1
        else:
            mangler += 1

    # lag_referanseliste viser DOI som ekstern peker når URL mangler, derfor teller
    # begge som etterprøvbar kildehenvisning.
    med_lenke = sum(bool(p.get("kilde_url") or p.get("doi")) for p in papirer)
    antall = len(enheter)
    return {
        "faktiske_enheter": antall,
        "dekket_enheter": dekket,
        "mangler_kilde_enheter": mangler,
        "eksplisitte_kildehull": eksplisitte_hull,
        "sitatdekning": dekket / antall if antall else 1.0,
        "ugyldige_kilde_ider": ugyldige,
        "listede_kilder": len(papirer),
        "brukte_kilder": len(brukte),
        "ubrukte_kilder": len(kjente - brukte),
        "kilder_med_ekstern_lenke": med_lenke,
        "lenkedekning": med_lenke / len(papirer) if papirer else 1.0,
    }


def del_i_setninger(tekst: str) -> list[str]:
    """Del en narrativ linje grovt i setninger for observasjonsmålingen."""
    return [bit.strip() for bit in re.split(r"(?<=[.!?])\s+(?=[A-ZÆØÅ])", tekst) if bit.strip()]


# Lokal Ollama-modell — samme som dossier.py bruker (gpt-oss:agent, num_ctx=16384)
OLLAMA_MODELL = "gpt-oss:agent"

# Prod-modell — kun brukt via ai-proxy (se _kall_llm_ai_proxy). Rollen er registrert i
# ai-proxy sin ROLE_ROUTE (magistral-medium-latest, EU-direkte Mistral, 2026-09-11).
# Vi gjenbruker samme rolle som dossier.py — samme oppgave (syntese), annen form.
AI_PROXY_ROLLE = "dossier-syntese"
AI_PROXY_WIKI_ID = "forskningssok"


def tilgjengelig() -> bool:
    """Er syntese-fortelling tilgjengelig for en WEB-bruker (Ulven)? Samme spørsmål og
    samme svar som dossier.tilgjengelig() — Ulven når kun forskningssok gjennom den
    deployede flaten, aldri Anders' Mac, så «tilgjengelig for ham» betyr «AI_PROXY_URL er
    satt» selv om kall_llm() TEKNISK sett også fungerer lokalt via Ollama. Flaten spør
    FØR den viser knappen, samme mønster."""
    import os
    return bool(os.environ.get("AI_PROXY_URL"))


def kall_llm(prompt: str) -> str:
    """Det ENESTE stedet i denne fila som avgjør HVOR en modell nås. Ruten speiler
    embedder-splitten husets øvrige kode allerede bruker (bank._hus_embed,
    verifiser.py::tilgjengelig) — samme "AI_PROXY_URL satt → Dokploy-prod, usatt →
    Anders' Mac"-gate, ikke funnet opp her: prod har ingen lokal Ollama, Anders' Mac har
    ingen ai-proxy-nettverkstilgang (dokploy-network-isolert, se ai-proxy sin egen
    modul-docstring). AI_PROXY_URL er dermed IKKE bare en konfigurasjonsdetalj, den ER
    signalet om hvilket miljø vi kjører i.

    FDR-106 fase 1, lagt til 2026-09-20: en TREDJE, valgfri rute. `OLLAMA_TUNNEL_URL`
    satt (KUN for en AVTALT demo-økt, aldri stående — svart hatt #1: Anders' Mac har
    målt kritisk minnepress ved samtidig øktarbeid+modellast, se konsepter/lokal-ki-
    hardware) rutes FØRST, selv i prod der AI_PROXY_URL alltid er satt — ellers ville
    denne veien aldri blitt nådd der Ulven faktisk er. Feiler tunnelen, faller vi
    AUTOMATISK videre til ai-proxy (obligatorisk fallback, FDR-106 §Foreslått funksjon)
    — Ulven skal ALDRI se en feilmelding fordi Anders' Mac var av eller nett var nede."""
    import os
    if os.environ.get("OLLAMA_TUNNEL_URL"):
        try:
            return _kall_llm_tunnel(prompt)
        except RuntimeError as e:
            import sys
            print(f"[OBS] Ollama-tunnel feilet, faller til ai-proxy: {e}", file=sys.stderr)
    if os.environ.get("AI_PROXY_URL"):
        return _kall_llm_ai_proxy(prompt)
    return _kall_llm_lokal_ollama(prompt)


def _kall_llm_tunnel(prompt: str, *, post_fn=None) -> str:
    """FDR-106 fase 1: prod-noden når Anders' Mac sin Ollama via en UTGÅENDE-initiert
    SSH reverse-tunnel — aldri en inngående port på hjemme-/kontornettverket i noen
    fase (se selve FDR-en for hvorfor: Cloudflare/Tailscale/ngrok forkastet som
    US-tunnelbroker, suverenitets-nedgradering på en flate som bærer Ulvens spørringer).

    `OLLAMA_TUNNEL_URL` peker på den FORWARDEDE porten PÅ NODEN SELV
    (`http://127.0.0.1:<port>`, aldri en ekstern adresse) — `GatewayPorts no` +
    `permitlisten` på tunnel-nøkkelen sikrer at porten aldri er nåbar utenfra noden,
    kun fra prosesser som allerede kjører der. Samme kall-form som _ollama_port.py sin
    kall_dommer() (rå /api/chat, ikke ai-proxy sitt /complete-endepunkt — ingen ai-proxy
    på den andre siden av denne tunnelen)."""
    import os
    import httpx

    url = os.environ["OLLAMA_TUNNEL_URL"]
    post = post_fn or httpx.post
    try:
        r = post(url.rstrip("/") + "/api/chat", json={
            "model": OLLAMA_MODELL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_ctx": 16384, "num_predict": 6000, "temperature": 0.2},
        }, timeout=600)
    except httpx.HTTPError as e:
        raise RuntimeError(f"Ollama-tunnel utilgjengelig: {e}") from e
    if r.status_code != 200:
        raise RuntimeError(f"Ollama-tunnel /api/chat feiler ({r.status_code}): {r.text[:200]}")
    try:
        data = r.json()
    except ValueError as e:
        raise RuntimeError(f"Ollama-tunnel returnerte ugyldig JSON: {e}") from e
    return data["message"]["content"]


def _kall_llm_ai_proxy(prompt: str, *, post_fn=None) -> str:
    """Prod-veien: ai-proxy sitt generiske /complete (FDR-019 byttbar-upstream), samme
    kall-mønster som verifiser.py (synkron httpx, forskningssok-disiplinen — CLAUDE.md).
    `post_fn` injiseres i test, samme grunn som verifiser.py sin (suiten er nettverksfri)."""
    import os
    import httpx

    url = os.environ["AI_PROXY_URL"]
    post = post_fn or httpx.post
    try:
        # 600s: syntese over MAKS_KILDER kilder er ikke et live UI-kall som må svare
        # raskt — samme begrunnelse som den lokale Ollama-veiens timeout.
        r = post(url.rstrip("/") + "/complete", json={
            "wiki_id": AI_PROXY_WIKI_ID,
            "role": AI_PROXY_ROLLE,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4000,
        }, timeout=600)
    except httpx.HTTPError as e:
        raise RuntimeError(f"ai-proxy utilgjengelig: {e}") from e
    if r.status_code != 200:
        raise RuntimeError(f"ai-proxy /complete feiler ({r.status_code}): {r.text[:200]}")
    try:
        data = r.json()
    except ValueError as e:
        raise RuntimeError(f"ai-proxy returnerte ugyldig JSON: {e}") from e
    return data["content"]


def _kall_llm_lokal_ollama(prompt: str, model: str = OLLAMA_MODELL) -> str:
    """Dev-veien (Anders' Mac): lokal Ollama via husets delte port
    (`silverbullet/ops/_ollama_port.py`) — samme mønster som evaluer.py::_hus_dommer,
    lat sys.path-import fordi porten kun er nåbar på Anders' Mac. Gratis, ingen
    abonnement.

    sjekk_dommer() FØR selve kallet, samme disiplin porten selv krever: en død/manglende
    Ollama skal gi en tydelig feilmelding her, ikke en stack trace to nivåer ned i httpx."""
    import sys
    sys.path.insert(0, str(Path.home() / "prosjekter" / "silverbullet" / "ops"))
    import _ollama_port

    feil = _ollama_port.sjekk_dommer(model)
    if feil:
        raise RuntimeError(f"Lokal Ollama ({model}) ikke klar: {feil}")

    # num_ctx=16384: et syntese med mange kilder (hver med tittel+abstract) kan fort
    # passere Ollamas 4096-standard, som trunkerer STILLE. Fortsatt ikke ubegrenset —
    # mange nok kilder kan fortsatt trunkere; ikke antatt trygt for et vilkårlig stort
    # korpus.
    #
    # num_predict=6000: samme budsjett som dossier.py — "thinking"-modeller bruker en
    # STOR, variabel andel av num_predict på skjult resonnering FØR den skriver selve
    # svaret. 2500 ga fire ekte setninger og stoppet midt i ordet (målt 2026-09-11).
    # timeout=600 (ikke portens 180s-default): et 6000-tokens generation-budsjett på
    # lokal maskinvare uten dedikert GPU-akselerasjon overskrider ofte 180s.
    svar = _ollama_port.kall_dommer(model, prompt, temperature=0.2, num_ctx=16384,
                                     num_predict=6000, timeout=600,
                                     consumer="forskningssok.syntese_fortelling")
    return svar["message"]["content"]


def lag_referanseliste(papirer: list[dict]) -> str:
    return "\n".join(
        f"[#{p['id']}] {p.get('forfattere', 'Ukjent forfatter')} ({p.get('aar', 'u.å.')}). "
        f"{p.get('tittel', '(uten tittel)')}. "
        + (f"DOI: {p['doi']}. " if p.get("doi") else "")
        + (f"URL: {p['kilde_url']}" if p.get("kilde_url") else "(ingen ekstern lenke)")
        + (f" [bok-bank, avstand {p['bank_avstand']}{' ' + p['bank_band'] if p.get('bank_band') else ''}]" if p.get("kilde") == "bok-bank" else "")
        for p in papirer
    )


def lag_syntese_fortelling(emne: str, db_path: Path = DB, *, bank_bakgrunn: bool | None = None) -> str:
    """Hovedfunksjon: hent kilder → prompt → kall LLM → verifiser kilder → returner.

    `bank_bakgrunn=True` legger bok-bankens nærmeste chunks til som BAKGRUNN (se
    bank_bakgrunn.py); uten boker.db/utdrag eller embedder fortsetter syntesen uten bank og
    sier hvorfor i utdata, aldri stille. None (standard) = automatisk: på bare når et
    bygd bank_utdrag.db finnes, altså når noen bevisst har satt banken opp der syntesen kjører.
    Uten utdrag er oppførselen uendret, så prod endres ikke av selve koden."""
    papirer = hent_kandidater(emne, db_path)
    if not papirer:
        return (f"Ingen kilder i cachen for «{emne}».\n"
                 f'Kjør først: python3 cli.py "{emne}" --oppdater')

    bank_notat = ""
    if bank_bakgrunn is None:
        import bank_bakgrunn as bb  # lokal import: modulen er valgfri
        bank_bakgrunn = bb.utdrag_finnes()
    if bank_bakgrunn:
        import bank_bakgrunn as bb  # lokal import: modulen er valgfri
        bakgrunn, bank_status = bb.hent_bakgrunn(emne)
        papirer = papirer + bakgrunn
        bank_notat = (
            f"[BANK-BAKGRUNN: {bank_status['antall']} bankposter lagt til"
            f" (beste avstand {bank_status['beste_avstand']}, {bank_status['forkastet_morkt']} forkastet som MØRKT)]"
            if bank_status["tilgjengelig"] and bakgrunn else
            f"[BANK-BAKGRUNN: ikke brukt — {bank_status['arsak'] or 'ingen treff'}]"
        )

    prompt = bygg_prompt(emne, papirer)
    rått_svar = kall_llm(prompt)
    renset, avvist = verifiser_kilder(rått_svar, papirer)
    kvalitetsmåling = evaluer_kvalitet(renset, papirer)

    # Én brukerinitiert syntese kan få ett ekstra reparasjonskall. Det hindrer at en
    # kjent sitatbrist bare blir en passiv advarsel, men unngår også retry-loop og beholder
    # førsteutkastet dersom reparasjonen ikke faktisk forbedrer målingen.
    if kvalitetsmåling["mangler_kilde_enheter"]:
        reparert_rått = kall_llm(bygg_reparasjons_prompt(emne, papirer, renset))
        reparert, reparert_avvist = verifiser_kilder(reparert_rått, papirer)
        reparert_måling = evaluer_kvalitet(reparert, papirer)
        if reparert_måling["mangler_kilde_enheter"] < kvalitetsmåling["mangler_kilde_enheter"]:
            renset = reparert
            avvist = reparert_avvist
            kvalitetsmåling = reparert_måling

    ut = [renset]
    if avvist:
        ut.append(
            f"\n---\n[ADVARSEL: {len(avvist)} kildehenvisning(er) fantes ikke i "
            f"kildesettet og ble fjernet: {', '.join(avvist)}]"
        )
    if kvalitetsmåling["mangler_kilde_enheter"]:
        ut.append(
            "\n---\n[ADVARSEL: "
            f"{kvalitetsmåling['mangler_kilde_enheter']} faktiske setning(er) mangler "
            "verifiserbar kildehenvisning; syntesen er ikke kvalitetssikret]"
        )
    if bank_notat:
        ut.append(f"\n---\n{bank_notat}")
    ut.append(f"\n---\n## Kildeliste ({len(papirer)} kilder)\n{lag_referanseliste(papirer)}")
    return "\n".join(ut)


def main():
    parser = argparse.ArgumentParser(description="LLM-syntese-fortelling over et emne, kildetro")
    parser.add_argument("--emne", type=str, required=True,
                         help="Emnet syntesen skal handle om")
    parser.add_argument("--db", type=str, default=str(DB), help="Database-sti")
    parser.add_argument("--bank", action="store_true",
                         help="Legg bok-bankens nærmeste chunks til som BAKGRUNN (lokalt; se bank_bakgrunn.py)")
    args = parser.parse_args()
    print(lag_syntese_fortelling(args.emne, Path(args.db), bank_bakgrunn=args.bank))


if __name__ == "__main__":
    main()
