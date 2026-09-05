#!/usr/bin/env python3
"""cli.py — forskningssok: entitet-sentrisk litteratursøk for oppdrettsfisk-patologi.

Vertikal #4 (prosjekt/idebank/28-nefrokalsinose-litteratursok), samme mal som
bruktsøk/teknisk-enhets-søk/rollesøk. Ærlig tomt-prinsipp: ingen treff → sier det,
gjetter aldri.

Kjør:
  python3 cli.py "nephrocalcinosis smolt seawater transfer"
  python3 cli.py --lignende 10.1111/jfd.70099
  python3 cli.py --gap 10.1111/jfd.70099   # citation-gap-testen, se citation_gap.py
"""
import argparse
import sys
import time

from adapters import core as core_adapter
from adapters.europe_pmc import cache_alder as europe_pmc_cache_alder, sok
from bank import hent, lagre, lignende
from citation_gap import gap_kandidater
import domeneprofil
from dedup import dedupliser
from ranking import arts_naer, domene_naer, ranger
from resolve import resolve
from schemas import PaperDossier


def sok_og_ranger(query: str, page_size: int = 20) -> tuple[list[PaperDossier], str | None, dict]:
    """Europe PMC ER resolve-steget for oppdagelses-søk (fritekst-relevans mot en
    hel korpusindeks) — resolve.py sin substreng-kandidat-gren passer et NAVN (kort
    streng), ikke en emnesetning mot lange papirtitler, og ville feilaktig meldt
    «ingen treff» der Europe PMC ga 200+. Derfor: resolve() brukes her KUN til å
    flagge det ene ekte tilfellet den er laget for — spørringen ER en tittel, ordrett
    (Ulven limer inn en kjent tittel/DOI-lignende streng). Alt annet er kandidater,
    alltid, rangert av ranking.py.

    Europe PMC er PÅKREVD kilde — en feil der forplantes uendret (uendret oppførsel).
    CORE er en TILLEGGSKILDE (institusjonsarkiv/gråtekst Europe PMC ikke indekserer,
    se adapters/core.py) — en CORE-feil skal ikke ta ned et ellers fungerende søk, men
    skal heller ikke skjules: returnerte `kilder`-dict rapporterer om den lyktes, samme
    transparens-prinsipp som citation_gap.py sin `referanse_kilde`.

    Tredje returverdi er REVISJONEN, ikke lenger bare `kilder` (kontraktendring
    2026-09-05). Den gamle dicten ligger uendret under nøkkelen `kilder`; resten er nytt.

    Kaller IKKE `lagre()` selv — cache/embed for fremtidig --lignende-søk er kallerens
    ansvar (synkront i CLI-en, som en fire-and-forget BackgroundTask i api.py). Denne
    funksjonen kalte lagre() synkront FØR return til 2026-09-04: embed_fn kan ta opptil
    120s (ekte AI-proxy-kall), så HVER fersk /api/sok-request satt og ventet på en
    caching-bivirkning ingen bruker faktisk trengte for å se resultatet sitt — reell
    årsak til at søk så ut som de hang, og til at overlappende (reload-utløste) søk
    kappløp mot samme cache-rader (se bank.py sin lagre()-fiks samme kveld)."""
    # Cache-alderen leses FØR søket, ellers ville sok() alt ha skrevet en fersk rad og
    # svaret blitt «0 sekunder gammel» for hvert eneste søk — et tall som alltid ser likt
    # ut måler ingenting.
    alder = europe_pmc_cache_alder(query, page_size)
    start = time.perf_counter()

    epmc = sok(query, page_size=page_size)
    kilder = {"europe_pmc": True, "core": True}
    kjerne = []
    try:
        kjerne = core_adapter.sok(query, limit=page_size)
    except RuntimeError:
        kilder["core"] = False
    kandidater = dedupliser(epmc + kjerne)
    rangert = ranger(kandidater)
    resultat = resolve(query, rangert, tekst=lambda p: p.tittel)
    eksakt_id = resultat.eksakt.id if resultat.eksakt else None

    # Revisjonssporet (idébank #29 §Kritikk C/D): bibliotekar-fagmiljøet ber eksplisitt om
    # å få dokumentert HVERT filtreringslag per spørring, ikke bare resultatet. Uten dette
    # kunne verktøyet svare «20 treff» der sannheten var «CORE var nede, Europe PMC svarte
    # fra en 22 timer gammel cache, og fire dubletter ble slått sammen» — tre forskjeller
    # som alle endrer hvordan et menneske skal lese lista.
    return rangert, eksakt_id, {
        "kilder": kilder,
        "treff_per_kilde": {"europe_pmc": len(epmc), "core": len(kjerne)},
        "etter_dedup": len(kandidater),
        "dubletter_fjernet": len(epmc) + len(kjerne) - len(kandidater),
        "cache_alder_s": round(alder) if alder is not None else None,
        "profil": domeneprofil.NAVN,
        "baand": {
            "domene_naer": sum(1 for p in rangert if domene_naer(p)),
            "arts_naer": sum(1 for p in rangert if arts_naer(p)),
        },
        "ms": round((time.perf_counter() - start) * 1000),
    }


def _print_revisjon(r: dict) -> None:
    """Hva som FAKTISK kjørte for dette søket. «20 treff» kan bety fire ulike ting, og
    forskjellen endrer hvordan lista skal leses."""
    tpk = r["treff_per_kilde"]
    alder = r["cache_alder_s"]
    fersk = "ekte kall" if alder is None else f"cache, {alder // 60} min gammel"
    print(f"— revisjon: Europe PMC {tpk['europe_pmc']} treff ({fersk}) · "
          f"CORE {tpk['core']} treff{'' if r['kilder']['core'] else ' (UTILGJENGELIG)'} · "
          f"{r['dubletter_fjernet']} dubletter slått sammen · "
          f"{r['baand']['domene_naer']} domene-nære, {r['baand']['arts_naer']} artsnære · "
          f"profil «{r['profil']}» · {r['ms']} ms")


def _print_papirer(papirer: list[PaperDossier], antall: int, query: str, eksakt_id: str | None):
    if not papirer:
        print(f"Ingen treff for «{query}» — ikke gjettet, faktisk tomt.")
        return
    print(f"{len(papirer)} kandidater for «{query}» (viser {min(antall, len(papirer))}):\n")
    for p in papirer[:antall]:
        flagg = "★" if domene_naer(p) else " "
        eksakt = " 🎯 eksakt titteltreff" if p.id == eksakt_id else ""
        aa = p.aar or "?"
        sit = p.siteringstall if p.siteringstall is not None else "?"
        oa = "OA" if p.open_access else "  "
        print(f"[{flagg}][{oa}] {aa} · {sit} siteringer · {p.tidsskrift}{eksakt}")
        print(f"    {p.tittel}")
        if p.abstract:
            print(f"    {p.abstract[:220].strip()}…")
        print(f"    id={p.id}  {p.kilde_url}")
        print()


def main():
    ap = argparse.ArgumentParser(
        description=f"Litteratursøk (Europe PMC) — profil: {domeneprofil.NAVN}")
    ap.add_argument("query", nargs="*",
                    help=f"søkestreng, f.eks. '{domeneprofil.PROFIL['sok_eksempel']}'")
    ap.add_argument("-n", "--antall", type=int, default=10, help="maks treff å vise")
    ap.add_argument("--lignende", metavar="ID", help="vis cachede papirer semantisk nærmest DOI/PMID")
    ap.add_argument("--gap", metavar="ID", help="citation-gap-testen: cachede naboer IKKE i papirets egen referanseliste")
    a = ap.parse_args()

    if a.gap:
        papir = hent(a.gap)
        if not papir:
            print(f"{a.gap} er ikke cachet ennå — søk det opp først (--lignende krever samme).")
            return
        if not papir["pmid"] and not papir["doi"]:
            print(f"{a.gap} mangler både PMID og DOI i cachen — ingen referanse-kilde tilgjengelig.")
            return
        try:
            resultat = gap_kandidater(a.gap, papir["kilde_kode"] or "MED", papir["pmid"],
                                      k=a.antall, kilde_aar=papir["aar"])
        except RuntimeError as e:
            print(f"Feil mot Europe PMC /references: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"«{papir['tittel']}» ({papir['aar'] or '?'}) siterer "
              f"{resultat['siterte_antall']} kilder selv.")
        # Modulen har rapportert referanse_kilde siden den ble bygget, men CLI-en skrev
        # den aldri ut — transparens-prinsippet gjaldt returverdien og ikke flaten noen
        # faktisk leser. Fanget da EBIs /references hadde ligget nede i tre døgn og
        # utskriften ikke røpet at hele svaret kom fra OpenAlex.
        print(f"Referanselisten kom fra: {resultat['referanse_kilde']}")
        d = resultat.get("referanse_dekning")
        if d:
            print(f"⚠ Delvis dekning: {d['hentet']} hentet av {d['oppgitt_av_utgiver']} "
                  f"oppgitt av utgiver — gap-listen kan være for lang.")
        print(f"\n{len(resultat['naboer'])} semantiske naboer i cachen, "
              f"{len(resultat['gap'])} av dem IKKE i referanselisten (kandidater, ikke en dom):\n")
        for g in resultat["gap"]:
            print(f"[{g['avstand']:.3f}] {g['aar'] or '?'} · {g['tidsskrift']}")
            print(f"    {g['tittel']}")
            print(f"    {g['kilde_url']}\n")
        ferske = resultat.get("publisert_etter") or []
        if ferske:
            print(f"— og {len(ferske)} nabo(er) publisert ETTER {papir['aar']}, som papiret "
                  f"umulig kunne sitert. Ikke et gap; les dem som «dette har kommet siden»:\n")
            for g in ferske:
                print(f"[{g['avstand']:.3f}] {g['aar']} · {g['tittel']}")
        return

    if a.lignende:
        naboer = lignende(a.lignende, k=a.antall)
        if not naboer:
            print(f"Ingen cachede naboer for {a.lignende} — enten ikke søkt opp ennå, "
                  f"eller uten abstract å embedde.")
            return
        print(f"{len(naboer)} nærmeste i cachen til {a.lignende}:\n")
        for n in naboer:
            print(f"[{n['avstand']:.3f}] {n['aar'] or '?'} · {n['tidsskrift']}")
            print(f"    {n['tittel']}")
            print(f"    {n['kilde_url']}\n")
        return

    if not a.query:
        ap.error("oppgi en søkestreng, eller --lignende ID")
    query = " ".join(a.query)
    try:
        papirer, eksakt_id, revisjon = sok_og_ranger(query, page_size=max(a.antall, 20))
    except RuntimeError as e:
        print(f"Feil mot Europe PMC: {e}", file=sys.stderr)
        sys.exit(1)
    lagre(papirer)  # cache/embed for fremtidig --lignende-søk — CLI-en kan trygt vente
    if not revisjon["kilder"]["core"]:
        print("(CORE utilgjengelig akkurat nå — viser kun Europe PMC-treff)\n", file=sys.stderr)
    _print_papirer(papirer, a.antall, query, eksakt_id)
    _print_revisjon(revisjon)


if __name__ == "__main__":
    main()
