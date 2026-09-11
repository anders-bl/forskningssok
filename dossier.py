#!/usr/bin/env python3
"""dossier.py — LLM-generert dybdedossier over et emne, bygget PÅ ekte kilder.

Utvidelse av ai_assistent.py sitt prinsipp ("hver påstand har en kilde-knapp"), ikke et
brudd på det: ai_assistent.py sin egen docstring sier "Ingen AI-generering av fakta —
kun strukturering". Her får en LLM lov til å skrive SAMMENHENGENDE prosa (noe ren
mønstergjenkjenning ikke kan), men under samme jernregel — hver påstand skal bære en
kildereferanse [#id] hentet ordrett fra det faktiske kildesettet. En LLM følger ikke
instrukser 100 % av tiden, så vi stoler ALDRI på det: verifiser_kilder() sjekker hver
referanse mekanisk mot kildelisten etterpå og fjerner alt som ikke finnes — samme
etterprøvbarhet som test_hvert_funn_baerer_kildepapiret håndhever for
detekter_hovedfunn() i ai_assistent.py.

Bygget 2026-09-10 etter Ulven-samtalen (Anders ba om «dossier/review-artikkel» —
hard vitenskap / hull / trygt-kjedelig / frontier / gammel akseptert tro). Skrevet
brukerinitiert-only (samme FDR-057-ånd som lauvasdatas smartsøk-FORSKNING-kanal),
ALDRI kjørt automatisk — dette gjør ekte, kostbare LLM-kall.

kall_llm() er BEVISST det eneste stedet i denne fila som snakker med en ekstern
modell — ingen nøkkel er koblet til ennå (leverandørvalg utsatt til Anders har
bestemt seg). Resten av pipelinen (henting → prompt → etterkontroll) er ferdig og
testbar uavhengig av det.

Bruk:
  python3 dossier.py --emne "fiskeøye-skanning identifikasjon"
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import domeneprofil  # noqa: E402
from ai_assistent import hent_fra_cache  # noqa: E402
from paths import DB  # noqa: E402

SEKSJONER = ("Hard vitenskap", "Hull i forskningen", "Trygt og kjedelig", "Frontier",
             "Gammel akseptert tro")

# Matcher [#<id>] — id-en er alltid papers.id (sqlite radnøkkel), ALDRI DOI/tittel, fordi
# det er det eneste feltet som er garantert unikt og til stede for hvert cachet papir
# (DOI mangler for en god del CORE-treff).
_REF_MØNSTER = re.compile(r"\[#([\w./-]+)\]")


# hent_fra_cache() gjør per-ORD OR-matching uten rangering (ai_assistent.py, delt kode) —
# et to-ords emne kan derfor treffe hundrede av løst relaterte cachede papirer, IKKE bare
# de faktisk relevante. Målt live 2026-09-11 (samme dag): «nephrocalcinosis salmon» alene
# ga 205 treff i en cache fylt av en hel økts live-søk; pluss sok_utstyr ga 612 totalt. Et
# ukappet dossier-kall sendte 612 kilder til lokal Ollama (num_ctx=16384) — konteksten
# sprengte stille, og gpt-oss brukte HELE num_predict-budsjettet på sin egen "thinking"-
# kanal (bekreftet: /api/chat returnerer et eget message.thinking-felt), null tegn igjen
# til selve svaret. Kappingen under er derfor ikke en optimalisering, den er det som gjør
# et dossier-kall mulig i det hele tatt med en lokal modell.
MAKS_KILDER = 25


def hent_kandidater(emne: str, db_path: Path = DB) -> list[dict]:
    """Ekte kilder for emnet, PLUSS utstyrs-/teknisk-litteratur hvis profilen definerer
    et eget søk for det (PROFIL["sok_utstyr"] — valgfritt felt, ikke et påkrevd som
    sok_standard, fordi ikke alle fagfelt har et eget utstyrsspor). Samme cache, ingen
    egen database — et dossier om f.eks. øye-skanning skal kunne trekke på BÅDE
    biologi-treff og avbildningsutstyr-treff samtidig.

    Kappet til MAKS_KILDER (se konstantens egen kommentar for hvorfor) — emne-treff
    beholder prioritet over utstyr-treff fordi de settes inn FØRST i unike-dicten under,
    og et Python-dict bevarer innsettingsrekkefølge."""
    papirer = list(hent_fra_cache(emne, db_path))

    utstyr_query = domeneprofil.PROFIL.get("sok_utstyr")
    if utstyr_query:
        papirer += hent_fra_cache(utstyr_query, db_path)

    unike: dict = {}
    for p in papirer:
        unike[p["id"]] = p
    return list(unike.values())[:MAKS_KILDER]


def bygg_prompt(emne: str, papirer: list[dict]) -> str:
    """Bygg LLM-prompten. Instruksen i punkt 1-4 er en avtale med modellen, ikke en
    garanti — verifiser_kilder() er garantien."""
    kildeliste = "\n\n".join(
        f"[#{p['id']}] {p.get('tittel', '(uten tittel)')} — "
        f"{p.get('forfattere', 'Ukjent forfatter')} ({p.get('aar', 'u.å.')}), "
        f"kilde={p.get('kilde', '?')}\n"
        f"Abstract: {p.get('abstract') or '(ingen abstract tilgjengelig)'}"
        for p in papirer
    )

    seksjons_beskrivelser = "\n".join(f"## {s}" for s in SEKSJONER)

    return f"""Du er en forskningsassistent som skal skrive et dybdedossier om: "{emne}"

STRENGE REGLER (brudd gjør outputen ubrukelig og blir fjernet mekanisk etterpå):
1. Bruk KUN fakta fra kildelisten under. Aldri fra egen forhåndskunnskap.
2. HVER setning som hevder noe faktisk MÅ avsluttes med kildereferansen i formatet
   [#<id>], hentet ORDRETT fra listen under (flere kilder: [#12][#47]).
3. Mangler god kildedekning for en seksjon, skriv det ærlig
   ("Ingen kilder i utvalget dekker dette") — ikke fyll ut med antakelser.
4. Dikt ALDRI opp en [#id] som ikke står i kildelisten. Den blir oppdaget og fjernet.

Strukturer svaret i nøyaktig disse seksjonene:
{seksjons_beskrivelser}

Hard vitenskap = godt replikert på tvers av flere uavhengige kilder, bred enighet.
Hull i forskningen = uenighet, motstridende funn, eller emner ingen kilde dekker.
Trygt og kjedelig = gammelt, høyt sitert, ingen som lenger utfordrer det.
Frontier = nytt, lite sitert, aktivt i bevegelse — der feltet faktisk er i dag.
Gammel akseptert tro = eldre konsensus som nyere/høyere sitert arbeid har nyansert
  eller motsagt — KUN hvis kildelisten faktisk viser en slik motsigelse, ellers
  skriv "Ingen motsigelse funnet i utvalget" under denne seksjonen.

KILDER:
{kildeliste}
"""


def verifiser_kilder(dossier_tekst: str, papirer: list[dict]) -> tuple[str, list[str]]:
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

    renset = _REF_MØNSTER.sub(_sjekk, dossier_tekst)
    return renset, avvist


OLLAMA_MODELL = "gpt-oss:agent"

# Prod-modell — kun brukt via ai-proxy (se _kall_llm_ai_proxy). Rollen er registrert i
# ai-proxy sin ROLE_ROUTE (magistral-medium-latest, EU-direkte Mistral, 2026-09-11).
AI_PROXY_ROLLE = "dossier-syntese"
AI_PROXY_WIKI_ID = "forskningssok"


def tilgjengelig() -> bool:
    """Er dossier-generering tilgjengelig for en WEB-bruker (Ulven)? Samme spørsmål og
    samme svar som verifiser.py::tilgjengelig() — Ulven når kun forskningssok gjennom den
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
        # 600s: dossier-syntese over MAKS_KILDER kilder er ikke et live UI-kall som må
        # svare raskt — samme begrunnelse som den lokale Ollama-veiens timeout.
        r = post(url.rstrip("/") + "/complete", json={
            "wiki_id": AI_PROXY_WIKI_ID,
            "role": AI_PROXY_ROLLE,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4000,
        }, timeout=600)
    except httpx.HTTPError as e:
        raise RuntimeError(f"ai-proxy utilgjengelig: {e}") from e
    if r.status_code != 200:
        raise RuntimeError(f"ai-proxy /complete feilet ({r.status_code}): {r.text[:200]}")
    try:
        data = r.json()
    except ValueError as e:
        raise RuntimeError(f"ai-proxy returnerte ugyldig JSON: {e}") from e
    return data["content"]


def _kall_llm_lokal_ollama(prompt: str, model: str = OLLAMA_MODELL) -> str:
    """Dev-veien (Anders' Mac, "gøy å prøve med noen lokalt kjørende llm", 2026-09-11):
    lokal Ollama via husets delte port (`silverbullet/ops/_ollama_port.py`) — samme
    mønster som evaluer.py::_hus_dommer, lat sys.path-import fordi porten kun er nåbar
    på Anders' Mac. Gratis, ingen abonnement. Bytt OLLAMA_MODELL til f.eks.
    "devstral:agent" for å sammenligne kvalitet — begge er allerede pullet.

    sjekk_dommer() FØR selve kallet, samme disiplin porten selv krever: en død/manglende
    Ollama skal gi en tydelig feilmelding her, ikke en stack trace to nivåer ned i httpx."""
    import sys
    sys.path.insert(0, str(Path.home() / "prosjekter" / "silverbullet" / "ops"))
    import _ollama_port

    feil = _ollama_port.sjekk_dommer(model)
    if feil:
        raise RuntimeError(f"Lokal Ollama ({model}) ikke klar: {feil}")

    # num_ctx=16384: et dossier med mange kilder (hver med tittel+abstract) kan fort
    # passere Ollamas 4096-standard, som trunkerer STILLE (se _ollama_port sin egen
    # advarsel om nettopp dette). Fortsatt ikke ubegrenset — mange nok kilder kan
    # fortsatt trunkere; ikke antatt trygt for et vilkårlig stort korpus.
    #
    # num_predict=6000, ikke 2500: gpt-oss (og enhver "thinking"-modell, se _ollama_port-
    # svarets eget message.thinking-felt) bruker en STOR, variabel andel av num_predict på
    # skjult resonnering FØR den skriver selve svaret — samme budsjett, delt kanal. Målt
    # live 2026-09-11 med 2500: en 25-kilders MAKS_KILDER-prompt ga fire ekte, kildekoblede
    # setninger og stoppet midt i ordet «magnesium». Ikke en prompt-lengde-feil (den var
    # innenfor num_ctx) — ren token-budsjett-sult i tenke-kanalen.
    # timeout=600 (ikke portens 180s-default): et 6000-tokens generation-budsjett på lokal
    # maskinvare uten dedikert GPU-akselerasjon overskrider ofte 180s — målt live
    # 2026-09-11 (httpcore.ReadTimeout ved default). Et dossier er en bakgrunnsjobb, ikke
    # et live UI-kall som må svare raskt.
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


def lag_dossier(emne: str, db_path: Path = DB) -> str:
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
    parser = argparse.ArgumentParser(description="LLM-dossier over et emne, kildetro")
    parser.add_argument("--emne", type=str, required=True,
                         help="Emnet dossieret skal handle om")
    parser.add_argument("--db", type=str, default=str(DB), help="Database-sti")
    args = parser.parse_args()
    print(lag_dossier(args.emne, Path(args.db)))


if __name__ == "__main__":
    main()
