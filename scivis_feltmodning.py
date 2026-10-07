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


def tegn_svg(lag: dict[int, dict[str, dict[str, int]]]) -> tuple[str, int]:
    """Stablet soylediagram som inline SVG. Returnerer (svg, maks_hoeyde_i_papirer)."""
    aar_sortert = sorted(lag)
    if not aar_sortert:
        return "<p>Ingen papirer med aarstall i korpuset.</p>", 0
    totaler = {a: sum(v2 for b in lag[a].values() for v2 in b.values()) for a in aar_sortert}
    maks = max(totaler.values()) or 1

    pad_v, pad_h, bredde_soyle, mellomrom, hoyde = 24, 52, 30, 10, 360
    bredde = pad_h + len(aar_sortert) * (bredde_soyle + mellomrom) + pad_v
    full_h = hoyde + 58

    def y(n: int) -> float:
        return pad_v + hoyde * (1 - n / maks)

    deler: list[str] = []
    # y-akse hjelpelinjer
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        ly = pad_v + hoyde * (1 - frac)
        deler.append(
            f'<line x1="{pad_h}" y1="{ly:.1f}" x2="{bredde - pad_v}" y2="{ly:.1f}" '
            f'stroke="#e4e4e7" stroke-width="1"/>'
            f'<text x="{pad_h - 8}" y="{ly + 4:.1f}" font-size="10" fill="#71717a" '
            f'text-anchor="end">{int(round(frac * maks))}</text>'
        )
    for i, aar in enumerate(aar_sortert):
        x = pad_h + i * (bredde_soyle + mellomrom)
        akk = 0  # nederst
        for baand in _BAAND:
            for kilde in ("ukjent", "monster", "nlm"):
                n = lag[aar][baand][kilde]
                if not n:
                    continue
                y0, y1 = y(akk + n), y(akk)
                skravur = ' stroke="#fff" stroke-width="0.6" stroke-dasharray="2 2"' if kilde == "monster" else ""
                tittel = f"{aar} -- {baand} ({kilde}): {n}"
                deler.append(
                    f'<rect x="{x}" y="{y0:.1f}" width="{bredde_soyle}" height="{max(0.0, y1 - y0):.1f}" '
                    f'fill="{_fyll(baand, kilde)}"{skravur}><title>{html.escape(tittel)}</title></rect>'
                )
                akk += n
        deler.append(
            f'<text x="{x + bredde_soyle / 2:.1f}" y="{full_h - 30}" font-size="10" '
            f'fill="#52525b" text-anchor="middle" transform="rotate(35 {x + bredde_soyle / 2:.1f} {full_h - 30})">{aar}</text>'
        )
    svg = (
        f'<svg viewBox="0 0 {bredde} {full_h}" width="100%" '
        f'preserveAspectRatio="xMidYMid meet" role="img" '
        f'aria-label="Stablet tidslinje: evidensnivaa-sammensetning per aar">'
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
    svg, _ = tegn_svg(lag)
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
  .legend {{ margin-top: 18px; display: grid; gap: 6px; font-size: 0.8rem; color: #3f3f46; }}
  .legend em {{ color: #71717a; font-style: normal; }}
  .sw {{ display: inline-block; width: 14px; height: 14px; border-radius: 3px; margin-right: 8px; vertical-align: -2px; }}
  .merk {{ margin-top: 18px; padding: 12px 14px; background: #fef9c3; border: 1px solid #fde68a; border-radius: 8px; font-size: 0.8rem; color: #713f12; }}
  .merk b {{ font-weight: 600; }}
</style></head>
<body><div class="wrap">
  <h1>{html.escape(tittel)}</h1>
  <p class="sub">{n_papirer} cachede papirer med aarstall. Hoyden er antall papirer per aar; lagene er evidensniva-badge, stablet.</p>
  <div class="kort">{svg}{_tegnforklaring()}</div>
  <p class="merk"><b>[OBS]</b> Metadata-avledet. evidensniva er en badge paa ord forfatterne selv brukte
  (eller NLMs indeksering), ALDRI en kvalitetsdom eller en verifisert paastand om studiedesign.
  Et papir uten design-signal er "Ukjent design", aldri "lavt evidensniva". Prototype/lek-lense --
  brukerinitiert, ikke en produksjonsflate.</p>
</div></body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--db", type=Path, default=_CACHE, help="sti til cache.db")
    ap.add_argument("--output", type=Path, default=_HER / "data" / "scivis_feltmodning.html",
                    help="utdata-HTML (default: data/scivis_feltmodning.html)")
    ap.add_argument("--tittel", type=str, default="Feltmodning -- evidensnivaa over tid",
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
