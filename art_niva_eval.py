#!/usr/bin/env python3
"""art_niva_eval.py — måler art_niva.klassifiser mot den håndleste fasiten.

Fasiten (tests/fixtures/art_fasit.json) er lest og merket av én modell (Claude), FØR noen
regel ble kjørt mot den; den er ikke en uavhengig menneskelig fasit, og usikre tilfeller er
holdt utenfor. Halvparten (`utvikling`) kan brukes til å justere termlistene; `holdout`
(hash-delt på id) leses av en enkelt sluttmåling og skal ikke ligge til grunn for justering.

  python art_niva_eval.py                # bare utviklingsdelen
  python art_niva_eval.py --holdout      # sluttmåling, en gang
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import art_niva
import domeneprofil
import tema

FASIT = Path(__file__).resolve().parent / "tests" / "fixtures" / "art_fasit.json"
NIVAER = art_niva.NIVAER


def last(del_: str) -> list[dict]:
    return [g for g in json.loads(FASIT.read_text(encoding="utf-8")) if g["del"] == del_]


def maal(g: dict, hva: str) -> str:
    if hva == "gammel":   # ja/nei-testen: flagget = «artsnær» = antatt målobjekt
        return "maal" if domeneprofil.arts_naer_tekst(f"{g['tittel']} {g['tekst']}") else "ingen"
    if hva == "gammel-tittel":
        return "maal" if domeneprofil.arts_naer_tekst(g["tittel"]) else "ingen"
    return art_niva.klassifiser(g["tittel"], g["tekst"], g["mesh"]).niva


def rapport(gull: list[dict]) -> dict:
    ut = {}
    for hva in ("gammel", "gammel-tittel", "ny"):
        pred = [maal(g, hva) for g in gull]
        tp = sum(p == "maal" and g["niva"] == "maal" for p, g in zip(pred, gull))
        fp = sum(p == "maal" and g["niva"] != "maal" for p, g in zip(pred, gull))
        fn = sum(p != "maal" and g["niva"] == "maal" for p, g in zip(pred, gull))
        ut[hva] = {"maal_presisjon": tp / (tp + fp) if tp + fp else None,
                   "maal_gjenfinning": tp / (tp + fn) if tp + fn else None, "tp": tp, "fp": fp, "fn": fn}
        if hva == "ny":
            ut["ny"]["nivaa_riktig"] = sum(p == g["niva"] for p, g in zip(pred, gull)) / len(gull)
            ut["ny"]["forvekslinger"] = Counter((g["niva"], p) for p, g in zip(pred, gull) if p != g["niva"])
    return ut


def tema_rapport(gull: list[dict]) -> dict:
    """Mikro-snitt over alle (artikkel, tema)-par + hver artikkels eksakte mengde. Bare artikler
    merket med tema i fasiten (fiskerelaterte) telles."""
    tp = fp = fn = eksakt = n = 0
    per = Counter()
    for g in gull:
        if "tema" not in g:
            continue
        n += 1
        gold = set(g["tema"])
        pred = {f.tema for f in tema.klassifiser(g["tittel"], g["tekst"])}
        tp += len(gold & pred); fp += len(pred - gold); fn += len(gold - pred)
        eksakt += gold == pred
        for t in gold - pred:
            per[("mistet", t)] += 1
        for t in pred - gold:
            per[("falsk", t)] += 1
    return {"n": n, "presisjon": tp / (tp + fp) if tp + fp else None, "gjenfinning": tp / (tp + fn) if tp + fn else None,
            "eksakt": eksakt / n if n else None, "tp": tp, "fp": fp, "fn": fn, "per": per}


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--holdout", action="store_true")
    a.add_argument("--feil", action="store_true", help="skriv ut hver feilklassifisering (kun utvikling)")
    args = a.parse_args()
    del_ = "holdout" if args.holdout else "utvikling"
    gull = last(del_)
    r = rapport(gull)
    print(f"{del_}: {len(gull)} artikler, fasit {dict(Counter(g['niva'] for g in gull))}")
    for hva in ("gammel", "gammel-tittel", "ny"):
        x = r[hva]
        print(f"  {hva:14} maal: presisjon {x['maal_presisjon']:.0%} gjenfinning {x['maal_gjenfinning']:.0%}"
              f"  (tp {x['tp']} fp {x['fp']} fn {x['fn']})")
    print(f"  ny, alle fire nivå riktig: {r['ny']['nivaa_riktig']:.0%}")
    for (fasit, pred), n in sorted(r["ny"]["forvekslinger"].items(), key=lambda x: -x[1]):
        print(f"    fasit {fasit:6} -> ny {pred:6} x{n}")
    tr = tema_rapport(gull)
    print(f"  temaer ({tr['n']} artikler): presisjon {tr['presisjon']:.0%} gjenfinning {tr['gjenfinning']:.0%}"
          f" eksakt mengde {tr['eksakt']:.0%} (tp {tr['tp']} fp {tr['fp']} fn {tr['fn']})")
    if args.feil and not args.holdout:
        for (hva, t), c in sorted(tr["per"].items(), key=lambda x: -x[1])[:14]:
            print(f"    {hva:6} {t:13} x{c}")
    if args.feil and not args.holdout:
        for g in gull:
            f = art_niva.klassifiser(g["tittel"], g["tekst"], g["mesh"])
            if f.niva != g["niva"]:
                print(f"  [{g['niva']}->{f.niva} {f.kilde} {list(f.bevis)}] {g['tittel'][:90]}")


if __name__ == "__main__":
    main()
