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


def hent_kandidater(emne: str, db_path: Path = DB) -> list[dict]:
    """Ekte kilder for emnet, PLUSS utstyrs-/teknisk-litteratur hvis profilen definerer
    et eget søk for det (PROFIL["sok_utstyr"] — valgfritt felt, ikke et påkrevd som
    sok_standard, fordi ikke alle fagfelt har et eget utstyrsspor). Samme cache, ingen
    egen database — et dossier om f.eks. øye-skanning skal kunne trekke på BÅDE
    biologi-treff og avbildningsutstyr-treff samtidig."""
    papirer = list(hent_fra_cache(emne, db_path))

    utstyr_query = domeneprofil.PROFIL.get("sok_utstyr")
    if utstyr_query:
        papirer += hent_fra_cache(utstyr_query, db_path)

    unike: dict = {}
    for p in papirer:
        unike[p["id"]] = p
    return list(unike.values())


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


def kall_llm(prompt: str) -> str:
    """Det ENESTE stedet i denne fila som snakker med en ekstern modell. Bevisst
    NotImplementedError til leverandør/nøkkel er valgt (2026-09-10) — bytt ut kroppen
    med et ekte API-kall når det skjer. Alt annet i denne fila (henting, prompt,
    etterkontroll) er allerede ferdig og testet uavhengig av HVA som står her."""
    raise NotImplementedError(
        "Ingen LLM-nøkkel er koblet til ennå — se dossier.py sin modul-docstring. "
        "Sett inn et ekte API-kall i kall_llm() når leverandør er valgt."
    )


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
