#!/usr/bin/env python3
"""scivis_siteringsgap.py -- prototype (lek-lense, brukerinitiert), bygget 2026-10-07.

Innspill #1 fra SciVis-dykket for Ulven (party-line ulven-scivis-innspill-20261007),
gjort synlig: for ETT fokuspapir, hvilke av dets naermeste SEMANTISKE naboer siterer det
faktisk, og hvilke gjor det IKKE? De siste er siteringsgap-kandidater -- den ene proben
citation_gap.py sin docstring noterer at spesialiserte verktoy (Elicit/Consensus/Undermind)
feiler systematisk: de "finner" stort sett bare det kildepapiret alt siterer.

Samme idé som husets ormehull_*.py (naer i embedding, fjern i lenkegraf) og citation_gap.py,
men som ETT bilde: et ego-nett der eiker til allerede-siterte naboer er heltrukne og eiker
til naere-men-usiterte naboer er stiplet. Eikelengde ~ embedding-avstand (naermere = kortere).

Offline, bevisst: naboene kommer fra bank.lignende() (leser lagrede vektorer i cache.db, ingen
ai-proxy-kall), og "sitert"-settet fra den cachede SS-referanselista (graf-ref). Verifisert
med dod proxy. Dekningsgrense som MAA leses aerlig: kun de papirene som alt har en hentet
referanseliste (maalt 2026-10-07: 18 stk) kan fungere som fokus -- for andre er fravaer av en
kant "ukjent", ikke "bevist ikke sitert". Et gap er en KANDIDAT aa undersoke, aldri en feil.

Krever ikke et ekte Review-sett; star paa cachet metadata + embeddinger som alt er hentet.

  venv/bin/python scivis_siteringsgap.py --output data/scivis_siteringsgap.html
  venv/bin/python scivis_siteringsgap.py --doi 10.3389/fphys.2023.1226068
"""
from __future__ import annotations

import argparse
import html
import json
import math
import os
import sqlite3
import sys
from pathlib import Path

_HER = Path(__file__).resolve().parent
_CACHE = _HER / "cache.db"
_MAKS_NABO = 12


def _norm(doi: str | None) -> str:
    return (doi or "").strip().lower().replace("https://doi.org/", "")


def referanse_sett(db: Path) -> dict[str, set[str]]:
    """fokus-DOI -> sett av DOI-er fokuset FAKTISK siterer (fra cachet SS graf-ref).

    Kun papirer med en ikke-tom referanseliste tas med -- fravaer her betyr "ikke hentet",
    ikke "siterer ingenting", og de to maa ikke forveksles i en gap-paastand.
    """
    c = sqlite3.connect(db)
    try:
        rader = c.execute(
            "select key, respons from semantic_scholar_cache where key like 'graf-ref%'"
        ).fetchall()
    finally:
        c.close()
    ut: dict[str, set[str]] = {}
    for key, respons in rader:
        fokus = _norm(key.split("DOI:")[-1])
        data = (json.loads(respons) or {}).get("data") or []
        sitert = {
            _norm(((rad.get("citedPaper") or {}).get("externalIds") or {}).get("DOI"))
            for rad in data
        }
        sitert.discard("")
        if sitert:
            ut[fokus] = sitert
    return ut


def _naboer(fokus: str, k: int):
    import bank  # lokal import: holder nettfri moduldrift tydelig og lazy

    return bank.lignende(fokus, k=k)


def _med_tittel(db: Path) -> set[str]:
    c = sqlite3.connect(db)
    try:
        return {_norm(r[0]) for r in c.execute("select doi from papers where doi is not null and doi != ''")}
    finally:
        c.close()


def velg_fokus(refs: dict[str, set[str]], titler: set[str]) -> str:
    """Fokuset med best balanse sitert/gap blant naermeste naboer -- gir et bilde som viser
    BEGGE eiketypene, ikke et degenerert ego-nett med bare den ene."""
    best: tuple[int, int, str] | None = None
    for src in refs:
        try:
            nb = _naboer(src, _MAKS_NABO + 4)
        except Exception:
            continue
        sit = gap = 0
        for x in nb:
            nid = _norm(x.get("id") or x.get("doi"))
            if nid == src or nid not in titler:
                continue
            if nid in refs[src]:
                sit += 1
            else:
                gap += 1
        kort = (min(sit, gap), sit + gap, src)
        if best is None or kort > best:
            best = kort
    if best is None:
        raise SystemExit("[STOPP] ingen fokuskandidat med cachet referanseliste funnet.")
    return best[2]


def bygg_egonett(fokus: str, refs: dict[str, set[str]], db: Path) -> dict:
    titler = _med_tittel(db)
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    try:
        frad = c.execute("select tittel, aar, tidsskrift from papers where lower(doi)=?", (fokus,)).fetchone()
    finally:
        c.close()
    sitert = refs.get(fokus, set())
    naboer = []
    for x in _naboer(fokus, _MAKS_NABO + 6):
        nid = _norm(x.get("id") or x.get("doi"))
        if nid == fokus or nid not in titler or not (x.get("tittel")):
            continue
        naboer.append({
            "doi": nid,
            "tittel": x.get("tittel") or nid,
            "aar": x.get("aar") or "",
            "tidsskrift": x.get("tidsskrift") or "",
            "avstand": float(x.get("avstand") or 0.0),
            "sitert": nid in sitert,
        })
        if len(naboer) >= _MAKS_NABO:
            break
    return {
        "fokus_doi": fokus,
        "fokus_tittel": (frad["tittel"] if frad else fokus),
        "fokus_aar": (frad["aar"] if frad else ""),
        "naboer": naboer,
        "n_sitert": sum(1 for n in naboer if n["sitert"]),
        "n_gap": sum(1 for n in naboer if not n["sitert"]),
    }


def _kort(tekst: str, n: int = 38) -> str:
    tekst = " ".join((tekst or "").split())
    return tekst if len(tekst) <= n else tekst[: n - 1] + "…"


def tegn_svg(nett: dict) -> str:
    naboer = nett["naboer"]
    if not naboer:
        return "<p>Ingen naboer med tittel i cachen for dette fokuset.</p>"
    b, h = 900, 620
    cx, cy = b / 2, h / 2
    av = [n["avstand"] for n in naboer]
    lo, hi = min(av), max(av)
    rmin, rmax = 120, 250

    def radius(a: float) -> float:
        return rmin if hi == lo else rmin + (rmax - rmin) * (a - lo) / (hi - lo)

    deler: list[str] = []
    n = len(naboer)
    for i, nb in enumerate(naboer):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        r = radius(nb["avstand"])
        x, y = cx + r * math.cos(ang), cy + r * math.sin(ang)
        if nb["sitert"]:
            strek, farge, prikk = 'stroke="#15803d" stroke-width="2.2"', "#15803d", "#15803d"
        else:
            strek, farge, prikk = 'stroke="#ea580c" stroke-width="2" stroke-dasharray="5 4"', "#ea580c", "#ea580c"
        tt = html.escape(f'{nb["tittel"]} ({nb["aar"]}) -- L2={nb["avstand"]:.3f} -- '
                         f'{"sitert" if nb["sitert"] else "IKKE sitert (gap)"}')
        deler.append(f'<line x1="{cx:.0f}" y1="{cy:.0f}" x2="{x:.1f}" y2="{y:.1f}" {strek}><title>{tt}</title></line>')
        deler.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{prikk}"><title>{tt}</title></circle>')
        hoyre = math.cos(ang) >= 0
        lx = x + (10 if hoyre else -10)
        anc = "start" if hoyre else "end"
        etikett = html.escape(f'{_kort(nb["tittel"])} ({nb["aar"]})')
        deler.append(
            f'<text x="{lx:.1f}" y="{y + 3:.1f}" font-size="10.5" fill="{farge}" '
            f'text-anchor="{anc}">{etikett}</text>'
        )
    # fokus-node
    deler.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="9" fill="#1e293b"/>')
    deler.append(
        f'<text x="{cx:.0f}" y="{cy + 26:.0f}" font-size="12" font-weight="600" fill="#0f172a" '
        f'text-anchor="middle">{html.escape(_kort(nett["fokus_tittel"], 52))}</text>'
    )
    deler.append(
        f'<text x="{cx:.0f}" y="{cy + 42:.0f}" font-size="10" fill="#64748b" '
        f'text-anchor="middle">fokus ({html.escape(str(nett["fokus_aar"]))})</text>'
    )
    return (f'<svg viewBox="0 0 {b} {h}" width="100%" preserveAspectRatio="xMidYMid meet" '
            f'role="img" aria-label="Siteringsgap ego-nett">' + "".join(deler) + "</svg>")


def _gap_liste(nett: dict) -> str:
    gap = [n for n in nett["naboer"] if not n["sitert"]]
    if not gap:
        return "<p>Ingen gap-kandidater blant naermeste naboer.</p>"
    rader = "".join(
        f'<tr><td>{html.escape(_kort(g["tittel"], 70))}</td><td>{html.escape(str(g["aar"]))}</td>'
        f'<td>{html.escape(_kort(g["tidsskrift"], 28))}</td><td>{g["avstand"]:.3f}</td></tr>'
        for g in sorted(gap, key=lambda x: x["avstand"])
    )
    return (f'<table><thead><tr><th>Naer, men ikke sitert (gap-kandidat)</th><th>Aar</th>'
            f'<th>Tidsskrift</th><th>L2</th></tr></thead><tbody>{rader}</tbody></table>')


def bygg_html(nett: dict, tittel: str) -> str:
    return f"""<!doctype html>
<html lang="no"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(tittel)}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ font: 15px/1.5 system-ui, sans-serif; margin: 0; padding: 24px; color: #18181b; background: #fafafa; }}
  .wrap {{ max-width: 960px; margin: 0 auto; }}
  h1 {{ font-size: 1.3rem; margin: 0 0 4px; }}
  .sub {{ color: #52525b; font-size: 0.85rem; margin: 0 0 16px; }}
  .kort {{ background: #fff; border: 1px solid #e4e4e7; border-radius: 12px; padding: 14px; }}
  .legend {{ display: flex; gap: 24px; flex-wrap: wrap; font-size: 0.82rem; margin: 14px 2px 0; color: #3f3f46; }}
  .legend i {{ display: inline-block; width: 26px; height: 0; vertical-align: middle; margin-right: 8px; }}
  .sit i {{ border-top: 2.5px solid #15803d; }}
  .gap i {{ border-top: 2.5px dashed #ea580c; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 0.82rem; }}
  th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid #ececef; }}
  th {{ color: #52525b; font-weight: 600; }}
  td:last-child, th:last-child {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .merk {{ margin-top: 18px; padding: 12px 14px; background: #fef9c3; border: 1px solid #fde68a; border-radius: 8px; font-size: 0.8rem; color: #713f12; }}
  .merk b {{ font-weight: 600; }}
</style></head>
<body><div class="wrap">
  <h1>{html.escape(tittel)}</h1>
  <p class="sub">Fokuspapirets {len(nett['naboer'])} naermeste semantiske naboer:
     <b>{nett['n_sitert']}</b> er faktisk sitert, <b>{nett['n_gap']}</b> er naere men IKKE sitert (gap-kandidater).
     Eikelengde ~ embedding-avstand (naermere senter = likere).</p>
  <div class="kort">{tegn_svg(nett)}
    <div class="legend"><span class="sit"><i></i>Sitert (i hentet referanseliste)</span>
      <span class="gap"><i></i>Naer, men ikke sitert -- gap-kandidat</span></div>
  </div>
  {_gap_liste(nett)}
  <p class="merk"><b>[OBS]</b> Nabolag = embedding-likhet (bge-m3, L2). "Ikke sitert" betyr "ikke i
  den CACHEDE referanselista" -- bare papirer med hentet liste kan vaere fokus; ellers er fravaer av
  kant ukjent, ikke bevist. Et gap er en KANDIDAT aa undersoke (kan vaere bevisst utelatt, nyere enn
  fokuset, eller irrelevant), aldri en feil. Prototype/lek-lense, brukerinitiert.</p>
</div></body></html>
"""


def main() -> int:
    # Dokumentert nettfri drift: naboene leses fra lagrede vektorer, ikke fra ai-proxy.
    os.environ.setdefault("HTTP_PROXY", "")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=_CACHE, help="sti til cache.db")
    ap.add_argument("--doi", type=str, default=None, help="fokus-DOI (default: best sitert/gap-balanse)")
    ap.add_argument("--output", type=Path, default=_HER / "data" / "scivis_siteringsgap.html",
                    help="utdata-HTML (default: data/scivis_siteringsgap.html)")
    ap.add_argument("--tittel", type=str, default="Siteringsgap -- naere naboer du (ikke) siterer",
                    help="overskrift (fagfeltnoeytral default)")
    a = ap.parse_args()

    if not a.db.is_file():
        print(f"[STOPP] fant ikke {a.db}", file=sys.stderr)
        return 1
    refs = referanse_sett(a.db)
    if not refs:
        print("[STOPP] ingen cachet referanseliste (graf-ref) funnet -- kjor en dossier-siteringsgraf forst.",
              file=sys.stderr)
        return 1
    titler = _med_tittel(a.db)
    fokus = _norm(a.doi) if a.doi else velg_fokus(refs, titler)
    if fokus not in refs:
        print(f"[STOPP] {fokus} har ingen cachet referanseliste; velg et av: {', '.join(list(refs)[:5])} ...",
              file=sys.stderr)
        return 1
    nett = bygg_egonett(fokus, refs, a.db)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(bygg_html(nett, a.tittel), encoding="utf-8")
    print(f"Fokus: {fokus} -- {nett['n_sitert']} sitert, {nett['n_gap']} gap-kandidater blant "
          f"{len(nett['naboer'])} naermeste naboer.")
    print(f"Skrevet: {a.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
