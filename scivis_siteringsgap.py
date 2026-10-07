#!/usr/bin/env python3
"""scivis_siteringsgap.py -- prototype (lek-lense, brukerinitiert), bygget 2026-10-07.

Innspill #1 fra SciVis-dykket for Ulven (party-line ulven-scivis-innspill-20261007),
gjort synlig: for ETT fokuspapir, hvilke av dets naermeste SEMANTISKE naboer er i
referanselista, mulige gap-kandidater eller uavklarte pa grunn av manglende dekning?
Bare fravaer i en komplett DOI-dekket liste gir siteringsgap-kandidater -- den ene proben
citation_gap.py sin docstring noterer at spesialiserte verktoy (Elicit/Consensus/Undermind)
feiler systematisk: de "finner" stort sett bare det kildepapiret alt siterer.

Samme idé som husets ormehull_*.py (naer i embedding, fjern i lenkegraf) og citation_gap.py,
men som ETT bilde: et ego-nett med egne uttrykk for sitert, mulig gap og uavklart status.
Eikelengde ~ embedding-avstand (naermere = kortere).

Offline, bevisst: naboene kommer fra bank.lignende() (leser lagrede vektorer i cache.db, ingen
ai-proxy-kall), og "sitert"-settet fra den cachede SS-referanselista (graf-ref). Semantic
Scholar-paginering og referanser uten DOI gjores synlige: fravaer i ufullstendig dekning er
"ukjent", ikke "ikke sitert". Et gap er en KANDIDAT aa undersoke, aldri en feil.

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
from dataclasses import dataclass
from pathlib import Path

_HER = Path(__file__).resolve().parent
_CACHE = _HER / "cache.db"
_MAKS_NABO = 12


@dataclass(frozen=True)
class Referanseliste:
    doi_er: frozenset[str]
    antall_cachet: int
    neste_offset: int | None
    antall_uten_doi: int

    @property
    def komplett(self) -> bool:
        return self.neste_offset is None and self.antall_uten_doi == 0


def _norm(doi: str | None) -> str:
    return (doi or "").strip().lower().replace("https://doi.org/", "")


def _aarstall(verdi) -> int | None:
    try:
        return int(verdi)
    except (TypeError, ValueError):
        return None


def referanse_sett(db: Path) -> dict[str, Referanseliste]:
    """fokus-DOI -> cachet SS-side, med pagineringsstatus.

    Kun papirer med en ikke-tom referanseliste tas med -- fravaer her betyr "ikke hentet",
    ikke "siterer ingenting". `next` betyr at Semantic Scholar har flere sider; da kan
    fravaer fra den cachede siden ikke klassifiseres som et gap.
    """
    c = sqlite3.connect(db)
    try:
        rader = c.execute(
            "select key, respons from semantic_scholar_cache where key like 'graf-ref%'"
        ).fetchall()
    finally:
        c.close()
    ut: dict[str, Referanseliste] = {}
    for key, respons in rader:
        fokus = _norm(key.split("DOI:")[-1])
        payload = json.loads(respons) or {}
        data = payload.get("data") or []
        sitert = {
            _norm(((rad.get("citedPaper") or {}).get("externalIds") or {}).get("DOI"))
            for rad in data
        }
        sitert.discard("")
        if data:
            uten_doi = sum(
                not _norm(
                    ((rad.get("citedPaper") or {}).get("externalIds") or {}).get("DOI")
                )
                for rad in data
            )
            ut[fokus] = Referanseliste(
                doi_er=frozenset(sitert),
                antall_cachet=len(data),
                neste_offset=payload.get("next"),
                antall_uten_doi=uten_doi,
            )
    return ut


def _naboer(fokus: str, k: int, db: Path):
    import bank  # lokal import: holder nettfri moduldrift tydelig og lazy

    return bank.lignende(fokus, k=k, db_path=db)


def _med_tittel(db: Path) -> set[str]:
    c = sqlite3.connect(db)
    try:
        return {_norm(r[0]) for r in c.execute("select doi from papers where doi is not null and doi != ''")}
    finally:
        c.close()


def velg_fokus(
    refs: dict[str, Referanseliste], titler: set[str], db: Path
) -> str:
    """Velg best balanserte komplett DOI-dekkede fokus hvis en finnes."""
    best: tuple[int, int, str] | None = None
    komplette = [src for src, ref in refs.items() if ref.komplett]
    kandidater = komplette or list(refs)
    for src in kandidater:
        nb = _naboer(src, _MAKS_NABO + 4, db)
        sit = gap = usikker = 0
        for x in nb:
            nid = _norm(x.get("id") or x.get("doi"))
            if nid == src or nid not in titler:
                continue
            if nid in refs[src].doi_er:
                sit += 1
            elif refs[src].komplett:
                gap += 1
            else:
                usikker += 1
        kort = (min(sit, gap if refs[src].komplett else usikker), sit + gap + usikker, src)
        if best is None or kort > best:
            best = kort
    if best is None:
        raise SystemExit("[STOPP] ingen fokuskandidat med cachet referanseliste funnet.")
    return best[2]


def bygg_egonett(fokus: str, refs: dict[str, Referanseliste], db: Path) -> dict:
    titler = _med_tittel(db)
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    try:
        frad = c.execute("select tittel, aar, tidsskrift from papers where lower(doi)=?", (fokus,)).fetchone()
    finally:
        c.close()
    referanser = refs[fokus]
    fokus_aar = _aarstall(frad["aar"]) if frad else None
    naboer = []
    for x in _naboer(fokus, _MAKS_NABO + 6, db):
        nid = _norm(x.get("id") or x.get("doi"))
        if nid == fokus or nid not in titler or not (x.get("tittel")):
            continue
        nabo_aar = _aarstall(x.get("aar"))
        ukjent_grunner = []
        if nid in referanser.doi_er:
            status = "sitert"
        elif (
            fokus_aar is not None
            and nabo_aar is not None
            and nabo_aar > fokus_aar
        ):
            status = "nyere"
        else:
            if referanser.neste_offset is not None:
                ukjent_grunner.append(
                    f"flere referansesider finnes fra offset {referanser.neste_offset}"
                )
            if referanser.antall_uten_doi:
                ukjent_grunner.append(
                    f"{referanser.antall_uten_doi} referanser i cachen mangler DOI"
                )
            if fokus_aar is None or nabo_aar is None:
                ukjent_grunner.append("publikasjonsaar mangler")
            elif nabo_aar == fokus_aar:
                ukjent_grunner.append("samme publikasjonsaar; rekkefolgen er ukjent")
            status = "ukjent" if ukjent_grunner else "gap"
        naboer.append({
            "doi": nid,
            "tittel": x.get("tittel") or nid,
            "aar": x.get("aar") or "",
            "tidsskrift": x.get("tidsskrift") or "",
            "avstand": float(x.get("avstand") or 0.0),
            "status": status,
            "sitert": status == "sitert",
            "ukjent_grunn": "; ".join(ukjent_grunner),
        })
        if len(naboer) >= _MAKS_NABO:
            break
    return {
        "fokus_doi": fokus,
        "fokus_tittel": (frad["tittel"] if frad else fokus),
        "fokus_aar": (frad["aar"] if frad else ""),
        "naboer": naboer,
        "n_sitert": sum(1 for n in naboer if n["sitert"]),
        "n_gap": sum(1 for n in naboer if n["status"] == "gap"),
        "n_ukjent": sum(1 for n in naboer if n["status"] == "ukjent"),
        "n_nyere": sum(1 for n in naboer if n["status"] == "nyere"),
        "referanseliste_komplett": referanser.komplett,
        "referanser_cachet": referanser.antall_cachet,
        "referanser_neste_offset": referanser.neste_offset,
        "referanser_uten_doi": referanser.antall_uten_doi,
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
        if nb["status"] == "sitert":
            strek, farge, prikk = 'stroke="#15803d" stroke-width="2.2"', "#15803d", "#15803d"
        elif nb["status"] == "gap":
            strek, farge, prikk = 'stroke="#ea580c" stroke-width="2" stroke-dasharray="5 4"', "#ea580c", "#ea580c"
        elif nb["status"] == "nyere":
            strek, farge, prikk = 'stroke="#2563eb" stroke-width="2" stroke-dasharray="7 3 2 3"', "#2563eb", "#2563eb"
        else:
            strek, farge, prikk = 'stroke="#71717a" stroke-width="2" stroke-dasharray="2 4"', "#71717a", "#71717a"
        status_tekst = {
            "sitert": "sitert",
            "gap": "ikke i komplett referanseliste (gap-kandidat)",
            "ukjent": f'ukjent: {nb["ukjent_grunn"]}',
            "nyere": "publisert etter fokuspapirets aar; ikke gap",
        }[nb["status"]]
        tt = html.escape(f'{nb["tittel"]} ({nb["aar"]}) -- L2={nb["avstand"]:.3f} -- '
                         f'{status_tekst}')
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
    gap = [n for n in nett["naboer"] if n["status"] == "gap"]
    if not gap:
        return "<p>Ingen gap-kandidater blant naermeste naboer.</p>"
    rader = "".join(
        f'<tr><td>{html.escape(_kort(g["tittel"], 70))}</td><td>{html.escape(str(g["aar"]))}</td>'
        f'<td>{html.escape(_kort(g["tidsskrift"], 28))}</td><td>{g["avstand"]:.3f}</td></tr>'
        for g in sorted(gap, key=lambda x: x["avstand"])
    )
    return (f'<table><thead><tr><th>Ikke i komplett referanseliste (gap-kandidat)</th><th>Aar</th>'
            f'<th>Tidsskrift</th><th>L2</th></tr></thead><tbody>{rader}</tbody></table>')


def _usikker_liste(nett: dict) -> str:
    usikker = [n for n in nett["naboer"] if n["status"] == "ukjent"]
    if not usikker:
        return ""
    rader = "".join(
        f'<tr><td>{html.escape(_kort(n["tittel"], 70))}</td><td>{html.escape(str(n["aar"]))}</td>'
        f'<td>{html.escape(n["ukjent_grunn"])}</td><td>{n["avstand"]:.3f}</td></tr>'
        for n in sorted(usikker, key=lambda x: x["avstand"])
    )
    return (
        '<h2>Uavklarte naboer</h2>'
        '<p>Disse kan ikke kalles gap med dagens kildegrunnlag.</p>'
        f'<table><thead><tr><th>Nabo</th><th>Aar</th><th>Grunn</th><th>L2</th></tr></thead><tbody>{rader}</tbody></table>'
    )


def _nyere_liste(nett: dict) -> str:
    nyere = [n for n in nett["naboer"] if n["status"] == "nyere"]
    if not nyere:
        return ""
    rader = "".join(
        f'<tr><td>{html.escape(_kort(n["tittel"], 70))}</td><td>{html.escape(str(n["aar"]))}</td>'
        f'<td>{n["avstand"]:.3f}</td></tr>'
        for n in sorted(nyere, key=lambda x: x["avstand"])
    )
    return (
        '<h2>Publisert etter fokuspapiret</h2>'
        '<p>Aarsfeltet i kildene plasserer disse etter fokuspapiret, sa de er ikke gap-kandidater.</p>'
        f'<table><thead><tr><th>Nabo</th><th>Aar</th><th>L2</th></tr></thead><tbody>{rader}</tbody></table>'
    )


def bygg_html(nett: dict, tittel: str) -> str:
    if nett["referanseliste_komplett"]:
        referanse_status = "komplett ifolge cachet API-respons"
    else:
        grunner = []
        if nett["referanser_neste_offset"] is not None:
            grunner.append(
                f'flere sider fra offset {nett["referanser_neste_offset"]} er ikke cachet'
            )
        if nett["referanser_uten_doi"]:
            grunner.append(
                f'{nett["referanser_uten_doi"]} cachede oppforinger mangler DOI'
            )
        referanse_status = "; ".join(grunner)
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
  .ukjent i {{ border-top: 2.5px dotted #71717a; }}
  .nyere i {{ border-top: 2.5px dashed #2563eb; }}
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
     <b>{nett['n_sitert']}</b> er i cachet referanseliste, <b>{nett['n_gap']}</b> mangler i komplett liste (gap-kandidater),
     <b>{nett['n_ukjent']}</b> er uavklarte, og <b>{nett['n_nyere']}</b> ble publisert etter fokuspapiret.
     Eikelengde ~ embedding-avstand (naermere senter = likere).</p>
  <div class="kort">{tegn_svg(nett)}
    <div class="legend"><span class="sit"><i></i>Sitert (i hentet referanseliste)</span>
      <span class="gap"><i></i>Ikke i komplett referanseliste -- gap-kandidat</span>
      <span class="ukjent"><i></i>Ukjent -- referansedekning eller tidsrekkefolge er ufullstendig</span>
      <span class="nyere"><i></i>Publisert etter fokuspapiret -- ikke gap</span></div>
  </div>
  {_gap_liste(nett)}
  {_usikker_liste(nett)}
  {_nyere_liste(nett)}
  <p>Cachet referanseliste: {nett['referanser_cachet']} oppforinger; {referanse_status}.</p>
  <p class="merk"><b>[OBS]</b> Nabolag = embedding-likhet (bge-m3, L2). Semantic Scholar deler lange referanselister i sider, og noen oppforinger mangler DOI. Bare full DOI-dekning og et eldre publikasjonsaar gir gap-kandidater; ufullstendig dekning eller samme aar gir "ukjent". Et gap er en KANDIDAT aa undersoke (kan vaere bevisst utelatt eller irrelevant), aldri en feil. Prototype/lek-lense, brukerinitiert.</p>
</div></body></html>
"""


def main() -> int:
    # Dokumentert nettfri drift: naboene leses fra lagrede vektorer, ikke fra ai-proxy.
    os.environ.setdefault("HTTP_PROXY", "")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=_CACHE, help="sti til cache.db")
    ap.add_argument("--doi", type=str, default=None, help="fokus-DOI (default: best komplette referansegrunnlag)")
    ap.add_argument("--output", type=Path, default=_HER / "data" / "scivis_siteringsgap.html",
                    help="utdata-HTML (default: data/scivis_siteringsgap.html)")
    ap.add_argument("--tittel", type=str, default="Siteringsgap -- naere naboer i referanselisten",
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
    fokus = _norm(a.doi) if a.doi else velg_fokus(refs, titler, a.db)
    if fokus not in refs:
        print(f"[STOPP] {fokus} har ingen cachet referanseliste; velg et av: {', '.join(list(refs)[:5])} ...",
              file=sys.stderr)
        return 1
    nett = bygg_egonett(fokus, refs, a.db)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(bygg_html(nett, a.tittel), encoding="utf-8")
    print(f"Fokus: {fokus} -- {nett['n_sitert']} i cache, {nett['n_gap']} gap-kandidater, "
          f"{nett['n_ukjent']} uavklarte, {nett['n_nyere']} nyere blant "
          f"{len(nett['naboer'])} naermeste naboer.")
    print(f"Skrevet: {a.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
