#!/usr/bin/env python3
"""scivis_feltmodning.py -- prototype (lek-lense, brukerinitiert), bygget 2026-10-07.

Innspill #3 fra SciVis-dykket for Ulven (party-line ulven-scivis-innspill-20261007):
en stablet tidslinje som viser hvordan evidens-SAMMENSETNINGEN i et korpus endrer seg
over aar -- "modner feltet?". Case-rapporter tidlig og systematiske oversikter sent er et
felt som modnes; en flat vegg av "Ukjent design" er et felt som fortsatt er anekdotisk
(eller et korpus der heuristikken ikke ser nok).

Hvorfor en EGEN prototype og ikke bare gjenbruk dossier_innsikt.tidslinje(): den teller
papirer per aar uten evidens-lag. Her er hele poenget lagdelingen -- og den aerlige
delingen evidensniva.py insisterer paa: NLM-indeksert design ("noen har staatt inne for
det") vises massivt, monster-gjenkjent design ("var heuristikk paa forfatternes egne ord")
vises skravert, og "Ukjent design" er sin egen daempede baand -- aldri skjult, aldri lest
som "lavt evidensniva". Nivaa-rekkefolge og -navn importeres fra evidensniva.NIVAAER, saa
denne fila ikke blir en andre, drivende kopi av hierarkiet.

Offline: leser kun cache.db (ingen eksterne kall), saa den kjorer uendret om nett/Ollama
er nede. Figuren er metadata-avledet -- den er IKKE en kvalitetsdom og IKKE en paastand om
studiedesign ut over hva evidensniva allerede badger. Krever derfor ikke et ekte
Review-sett (til forskjell fra maaleytelsesfigurer som sens/spes).

  venv/bin/python scivis_feltmodning.py --output data/scivis_feltmodning.html
"""
from __future__ import annotations

import argparse
import html
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

from evidensniva import NIVAAER, evidensniva

_HER = Path(__file__).resolve().parent
_CACHE = _HER / "cache.db"
_UKJENT = "Ukjent design"

# Baand-rekkefolge nederst->opp: sterkeste evidens oeverst i stabelen, ukjent i bunn som
# et noeytralt gulv. NIVAAER er sortert sterkest->svakest; vi snur for tegne-rekkefolgen.
_NIVAA_NAVN: list[str] = [navn for navn, _ in NIVAAER]
_BAAND: list[str] = [_UKJENT] + list(reversed(_NIVAA_NAVN))

# Hue per baand (HSL-grader): ukjent graa, saa en gradient fra svak (varm) til sterk (kald
# gronn). Rent presentasjon -- ingen datapaastand, samme avgjorelse som farge i et hvilket
# som helst galleri.
_HUE: dict[str, int] = {_UKJENT: 0}
for _i, _navn in enumerate(reversed(_NIVAA_NAVN)):
    _HUE[_navn] = 20 + int(_i * (150 / max(1, len(_NIVAA_NAVN) - 1)))


def last_papirer(db: Path = _CACHE) -> list[dict]:
    """Alle cachede papirer med et aarstall -- hele det akkumulerte soekerommet."""
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    try:
        rader = c.execute(
            "select tittel, abstract, pubtyper, aar from papers "
            "where aar is not null and aar > 1900"
        ).fetchall()
    finally:
        c.close()
    return [dict(r) for r in rader]


def _pubtyper(rad: dict) -> tuple[str, ...]:
    felt = (rad.get("pubtyper") or "").strip()
    return tuple(p for p in felt.split(";") if p) if felt else ()


def bygg_lag(papirer: list[dict]) -> dict[int, dict[str, dict[str, int]]]:
    """aar -> baandnavn -> {"nlm": n, "monster": n, "ukjent": n}.

    Kilden (nlm/monster/ukjent) beholdes per baand slik at tegningen kan vise den ulike
    epistemiske vekten evidensniva.py krever -- ikke bare hvilket nivaa, men hvor paastanden
    kommer fra.
    """
    ut: dict[int, dict[str, dict[str, int]]] = defaultdict(
        lambda: {b: {"nlm": 0, "monster": 0, "ukjent": 0} for b in _BAAND}
    )
    for p in papirer:
        try:
            aar = int(p["aar"])
        except (TypeError, ValueError):
            continue
        navn, kilde = evidensniva(p.get("tittel") or "", p.get("abstract") or "", _pubtyper(p))
        baand = navn if navn in _BAAND else _UKJENT
        nokkel = kilde if kilde in ("nlm", "monster") else "ukjent"
        ut[aar][baand][nokkel] += 1
    return dict(ut)


def _fyll(baand: str, kilde: str) -> str:
    hue = _HUE.get(baand, 0)
    if baand == _UKJENT:
        return "#d4d4d8"  # noeytralt gulv, ingen metning
    lys = 42 if kilde == "nlm" else 62
    return f"hsl({hue} 55% {lys}%)"


def normaliser_andeler(
    lag: dict[int, dict[str, dict[str, int]]],
) -> dict[int, dict[str, dict[str, float]]]:
    """Normaliser hvert aar separat slik at korpusstorrelse ikke styrer andelsvisningen."""
    ut: dict[int, dict[str, dict[str, float]]] = {}
    for aar, baand in lag.items():
        total = sum(n for kilder in baand.values() for n in kilder.values())
        ut[aar] = {
            navn: {
                kilde: (100.0 * antall / total if total else 0.0)
                for kilde, antall in kilder.items()
            }
            for navn, kilder in baand.items()
        }
    return ut


def tegn_svg(
    lag: dict[int, dict[str, dict[str, int]]], *, andel: bool = False
) -> tuple[str, int]:
    """Stablet SVG i antall eller normalisert andel per aar."""
    aar_sortert = sorted(lag)
    if not aar_sortert:
        return "<p>Ingen papirer med aarstall i korpuset.</p>", 0
    totaler = {a: sum(v2 for b in lag[a].values() for v2 in b.values()) for a in aar_sortert}
    viste_lag = normaliser_andeler(lag) if andel else lag
    maks = 100 if andel else max(totaler.values()) or 1

    pad_v, pad_h, bredde_soyle, mellomrom, hoyde = 24, 52, 30, 10, 360
    bredde = pad_h + len(aar_sortert) * (bredde_soyle + mellomrom) + pad_v
    full_h = hoyde + 58

    def y(n: float) -> float:
        return pad_v + hoyde * (1 - n / maks)

    deler: list[str] = []
    # y-akse hjelpelinjer
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        ly = pad_v + hoyde * (1 - frac)
        akseverdi = f"{round(frac * 100)}%" if andel else str(round(frac * maks))
        deler.append(
            f'<line x1="{pad_h}" y1="{ly:.1f}" x2="{bredde - pad_v}" y2="{ly:.1f}" '
            f'stroke="#e4e4e7" stroke-width="1"/>'
            f'<text x="{pad_h - 8}" y="{ly + 4:.1f}" font-size="10" fill="#71717a" '
            f'text-anchor="end">{akseverdi}</text>'
        )
    for i, aar in enumerate(aar_sortert):
        x = pad_h + i * (bredde_soyle + mellomrom)
        akk = 0  # nederst
        for baand in _BAAND:
            for kilde in ("ukjent", "monster", "nlm"):
                n = lag[aar][baand][kilde]
                verdi = viste_lag[aar][baand][kilde]
                if not n:
                    continue
                y0, y1 = y(akk + verdi), y(akk)
                skravur = ' stroke="#fff" stroke-width="0.6" stroke-dasharray="2 2"' if kilde == "monster" else ""
                prosent = 100 * n / totaler[aar] if totaler[aar] else 0
                tittel = f"{aar} -- {baand} ({kilde}): {n} av {totaler[aar]} ({prosent:.1f}%)"
                deler.append(
                    f'<rect x="{x}" y="{y0:.1f}" width="{bredde_soyle}" height="{max(0.0, y1 - y0):.1f}" '
                    f'fill="{_fyll(baand, kilde)}"{skravur}><title>{html.escape(tittel)}</title></rect>'
                )
                akk += verdi
        deler.append(
            f'<text x="{x + bredde_soyle / 2:.1f}" y="{full_h - 30}" font-size="10" '
            f'fill="#52525b" text-anchor="middle" transform="rotate(35 {x + bredde_soyle / 2:.1f} {full_h - 30})">'
            f'<title>{aar}: N={totaler[aar]}</title>{aar}</text>'
        )
    svg = (
        f'<svg viewBox="0 0 {bredde} {full_h}" width="100%" '
        f'preserveAspectRatio="xMidYMid meet" role="img" '
        f'aria-label="Stablet tidslinje: {"andel" if andel else "antall"} per aar">'
        + "".join(deler)
        + "</svg>"
    )
    return svg, maks


def _tegnforklaring() -> str:
    rader: list[str] = []
    for baand in reversed(_BAAND):
        if baand == _UKJENT:
            rader.append(
                f'<span class="sw" style="background:{_fyll(baand, "ukjent")}"></span>'
                f'{html.escape(baand)} (ingen design-signal -- aldri lest som lavt nivaa)'
            )
        else:
            rader.append(
                f'<span class="sw" style="background:{_fyll(baand, "nlm")}"></span>'
                f'{html.escape(baand)} <em>(mettet = NLM-indeksert; skravert/lysere = var monster-heuristikk)</em>'
            )
    return '<div class="legend">' + "".join(f"<div>{r}</div>" for r in rader) + "</div>"


def bygg_html(lag: dict[int, dict[str, dict[str, int]]], tittel: str, n_papirer: int) -> str:
    antall_svg, _ = tegn_svg(lag)
    andel_svg, _ = tegn_svg(lag, andel=True)
    grunnlag = " ".join(
        "<tr>"
        f"<td>{aar}</td>"
        f"<td>{sum(n for band in aar_lag.values() for n in band.values())}</td>"
        "</tr>"
        for aar, aar_lag in sorted(lag.items())
    )
    return f"""<!doctype html>
<html lang="no"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(tittel)}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ font: 15px/1.5 system-ui, sans-serif; margin: 0; padding: 24px; color: #18181b; background: #fafafa; }}
  .wrap {{ max-width: 920px; margin: 0 auto; }}
  h1 {{ font-size: 1.3rem; margin: 0 0 4px; }}
  .sub {{ color: #52525b; font-size: 0.85rem; margin: 0 0 20px; }}
  .kort {{ background: #fff; border: 1px solid #e4e4e7; border-radius: 12px; padding: 20px; }}
  .valg {{ display: flex; gap: 8px; margin: 0 0 14px; }}
  .valg button {{ border: 1px solid #a1a1aa; background: #fff; color: #27272a; border-radius: 6px; padding: 7px 11px; font: inherit; cursor: pointer; }}
  .valg button[aria-pressed="true"] {{ background: #27272a; border-color: #27272a; color: #fff; }}
  .valg button:focus-visible {{ outline: 3px solid #2563eb; outline-offset: 2px; }}
  .visning[hidden] {{ display: none; }}
  .legend {{ margin-top: 18px; display: grid; gap: 6px; font-size: 0.8rem; color: #3f3f46; }}
  .legend em {{ color: #71717a; font-style: normal; }}
  .sw {{ display: inline-block; width: 14px; height: 14px; border-radius: 3px; margin-right: 8px; vertical-align: -2px; }}
  .merk {{ margin-top: 18px; padding: 12px 14px; background: #fef9c3; border: 1px solid #fde68a; border-radius: 8px; font-size: 0.8rem; color: #713f12; }}
  .merk b {{ font-weight: 600; }}
  details {{ margin-top: 16px; font-size: 0.85rem; }}
  summary {{ cursor: pointer; }}
  table {{ margin-top: 8px; border-collapse: collapse; }}
  th, td {{ padding: 4px 12px 4px 0; text-align: left; border-bottom: 1px solid #e4e4e7; }}
</style></head>
<body><div class="wrap">
  <h1>{html.escape(tittel)}</h1>
  <p class="sub">{n_papirer} cachede papirer med aarstall. Bytt mellom korpusvolum og evidensmerker som andel av hvert aars treff.</p>
  <div class="kort">
    <div class="valg" role="group" aria-label="Visningsmaate">
      <button id="andel-knapp" type="button" aria-pressed="true" aria-controls="andel-visning">Andel per aar</button>
      <button id="antall-knapp" type="button" aria-pressed="false" aria-controls="antall-visning">Antall per aar</button>
    </div>
    <div id="andel-visning" class="visning">{andel_svg}<p>Hver soyle summerer til 100 %. Hold over et lag for antall og prosent. Tallet N per aar er tilgjengelig ved a holde over aarstallet. Les sma N med varsomhet.</p></div>
    <div id="antall-visning" class="visning" hidden>{antall_svg}<p>Hoyden viser antall cachede papirer per aar. Hold over et lag for antall og prosent.</p></div>
    {_tegnforklaring()}
  </div>
  <details><summary>Se antall cachede papirer per aar</summary><table><thead><tr><th>Aar</th><th>N</th></tr></thead><tbody>{grunnlag}</tbody></table></details>
  <p class="merk"><b>[OBS]</b> Metadata-avledet. Andelene viser bare sammensetningen av aarets cachede treff, ikke om et fagfelt faktisk modnes. Evidensniva er et merke basert paa NLM-indeksering eller ord forfatterne brukte, ALDRI en kvalitetsdom eller verifisert studiedesign. Et papir uten design-signal er "Ukjent design", aldri "lavt evidensniva". Prototype/lek-lense -- brukerinitiert, ikke en produksjonsflate.</p>
</div>
<script>
  const andelKnapp = document.getElementById("andel-knapp");
  const antallKnapp = document.getElementById("antall-knapp");
  const andelVisning = document.getElementById("andel-visning");
  const antallVisning = document.getElementById("antall-visning");
  andelKnapp.addEventListener("click", () => {{
    andelVisning.hidden = false;
    antallVisning.hidden = true;
    andelKnapp.setAttribute("aria-pressed", "true");
    antallKnapp.setAttribute("aria-pressed", "false");
  }});
  antallKnapp.addEventListener("click", () => {{
    andelVisning.hidden = true;
    antallVisning.hidden = false;
    andelKnapp.setAttribute("aria-pressed", "false");
    antallKnapp.setAttribute("aria-pressed", "true");
  }});
</script>
</body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--db", type=Path, default=_CACHE, help="sti til cache.db")
    ap.add_argument("--output", type=Path, default=_HER / "data" / "scivis_feltmodning.html",
                    help="utdata-HTML (default: data/scivis_feltmodning.html)")
    ap.add_argument("--tittel", type=str, default="Evidensmerker over tid",
                    help="overskrift (fagfeltnoeytral som default)")
    a = ap.parse_args()

    if not a.db.is_file():
        print(f"[STOPP] fant ikke {a.db}", file=sys.stderr)
        return 1
    papirer = last_papirer(a.db)
    lag = bygg_lag(papirer)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(bygg_html(lag, a.tittel, len(papirer)), encoding="utf-8")

    klassifisert = sum(
        v["nlm"] + v["monster"]
        for aar in lag.values() for navn, v in aar.items() if navn != _UKJENT
    )
    print(f"{len(papirer)} papirer over {len(lag)} aar -- {klassifisert} med design-signal, "
          f"{len(papirer) - klassifisert} ukjent design.")
    print(f"Skrevet: {a.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
