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

# Matcher [#<id>] — id-en er alltid papers.id (sqlite radnøkkel), ALDRI DOI/tittel, fordi
# det er det eneste feltet som er garantert unikt og til stede for hvert cachet papir
# (DOI mangler for en god del CORE-treff).
_REF_MØNSTER = re.compile(r"\[#([\w./-]+)\]")

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
    papirer = list(hent_fra_cache(emne, db_path))

    utstyr_query = domeneprofil.PROFIL.get("sok_utstyr")
    if utstyr_query:
        papirer += hent_fra_cache(utstyr_query, db_path)

    unike: dict = {}
    for p in papirer:
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
    kildeliste = "\n\n".join(
        f"[#{p['id']}] {p.get('tittel', '(uten tittel)')} — "
        f"{p.get('forfattere', 'Ukjent forfatter')} ({p.get('aar', 'u.å.')}), "
        f"kilde={p.get('kilde', '?')}\n"
        f"Abstract: {p.get('abstract') or '(ingen abstract tilgjengelig)'}"
        for p in papirer
    )

    return f"""Du er en forskningsassistent som skal skrive en SAMMENHENG-FORTELLING om: "{emne}"

STRENGE REGLER (brudd gjør outputen ubrukelig og blir fjernet mekanisk etterpå):
1. Bruk KUN fakta fra kildelisten under. Aldri fra egen forhåndskunnskap.
2. HVER setning som hevder noe faktisk MÅ avsluttes med kildereferansen i formatet
   [#<id>], hentet ORDRETT fra listen under (flere kilder: [#12][#47]).
3. Mangler god kildedekning for et poeng, skriv det ærlig
   ("Ingen kilder i utvalget dekker dette") — ikke fyll ut med antakelser.
4. Dikt ALDRI opp en [#id] som ikke står i kildelisten. Den blir oppdaget og fjernet.

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
    signalet om hvilket miljø vi kjører i."""
    import os
    if os.environ.get("AI_PROXY_URL"):
        return _kall_llm_ai_proxy(prompt)
    return _kall_llm_lokal_ollama(prompt)


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
                                     num_predict=6000, timeout=600)
    return svar["message"]["content"]


def lag_referanseliste(papirer: list[dict]) -> str:
    return "\n".join(
        f"[#{p['id']}] {p.get('forfattere', 'Ukjent forfatter')} ({p.get('aar', 'u.å.')}). "
        f"{p.get('tittel', '(uten tittel)')}. "
        + (f"DOI: {p['doi']}" if p.get("doi") else "(ingen DOI)")
        for p in papirer
    )


def lag_syntese_fortelling(emne: str, db_path: Path = DB) -> str:
    """Hovedfunksjon: hent kilder → prompt → kall LLM → verifiser kilder → returner."""
    papirer = hent_kandidater(emne, db_path)
    if not papirer:
        return (f"Ingen kilder i cachen for «{emne}».\n"
                 f'Kjør først: python3 cli.py "{emne}" --oppdater')

    prompt = bygg_prompt(emne, papirer)
    rått_svar = kall_llm(prompt)
    renset, avvist = verifiser_kilder(rått_svar, papirer)

    ut = [renset]
    if avvist:
        ut.append(
            f"\n---\n[ADVARSEL: {len(avvist)} kildehenvisning(er) fantes ikke i "
            f"kildesettet og ble fjernet: {', '.join(avvist)}]"
        )
    ut.append(f"\n---\n## Kildeliste ({len(papirer)} kilder)\n{lag_referanseliste(papirer)}")
    return "\n".join(ut)


def main():
    parser = argparse.ArgumentParser(description="LLM-syntese-fortelling over et emne, kildetro")
    parser.add_argument("--emne", type=str, required=True,
                         help="Emnet syntesen skal handle om")
    parser.add_argument("--db", type=str, default=str(DB), help="Database-sti")
    args = parser.parse_args()
    print(lag_syntese_fortelling(args.emne, Path(args.db)))


if __name__ == "__main__":
    main()