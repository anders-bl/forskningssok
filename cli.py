#!/usr/bin/env python3
"""cli.py — nefrokalsinose-sok: entitet-sentrisk litteratursøk for oppdrettsfisk-patologi.

Vertikal #4 (prosjekt/idebank/28-nefrokalsinose-litteratursok), samme mal som
bruktsøk/teknisk-enhets-søk/rollesøk. Ærlig tomt-prinsipp: ingen treff → sier det,
gjetter aldri.

Kjør:
  python3 cli.py "nephrocalcinosis smolt seawater transfer"
  python3 cli.py --lignende 10.1111/jfd.70099
"""
import argparse
import sys

from adapters.europe_pmc import sok
from bank import lagre, lignende
from ranking import domene_naer, ranger
from resolve import resolve
from schemas import PaperDossier


def sok_og_ranger(query: str, page_size: int = 20) -> tuple[list[PaperDossier], str | None]:
    """Europe PMC ER resolve-steget for oppdagelses-søk (fritekst-relevans mot en
    hel korpusindeks) — resolve.py sin substreng-kandidat-gren passer et NAVN (kort
    streng), ikke en emnesetning mot lange papirtitler, og ville feilaktig meldt
    «ingen treff» der Europe PMC ga 200+. Derfor: resolve() brukes her KUN til å
    flagge det ene ekte tilfellet den er laget for — spørringen ER en tittel, ordrett
    (Ulven limer inn en kjent tittel/DOI-lignende streng). Alt annet er kandidater,
    alltid, rangert av ranking.py."""
    kandidater = sok(query, page_size=page_size)
    rangert = ranger(kandidater)
    lagre(rangert)  # cache/embed for fremtidig --lignende-søk, feiler stille aldri kritisk
    resultat = resolve(query, rangert, tekst=lambda p: p.tittel)
    eksakt_id = resultat.eksakt.id if resultat.eksakt else None
    return rangert, eksakt_id


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
    ap = argparse.ArgumentParser(description="Nefrokalsinose-litteratursøk (Europe PMC).")
    ap.add_argument("query", nargs="*", help="søkestreng, f.eks. 'nephrocalcinosis smolt seawater transfer'")
    ap.add_argument("-n", "--antall", type=int, default=10, help="maks treff å vise")
    ap.add_argument("--lignende", metavar="ID", help="vis cachede papirer semantisk nærmest DOI/PMID")
    a = ap.parse_args()

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
        papirer, eksakt_id = sok_og_ranger(query, page_size=max(a.antall, 20))
    except RuntimeError as e:
        print(f"Feil mot Europe PMC: {e}", file=sys.stderr)
        sys.exit(1)
    _print_papirer(papirer, a.antall, query, eksakt_id)


if __name__ == "__main__":
    main()
