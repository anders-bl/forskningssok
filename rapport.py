"""rapport.py — rapportmaler: strukturerte Markdown-eksporter av et papirutvalg, klare
til å limes inn i e-post/dokument eller sendes til en kollega/Lumic-teamet uten at de
selv må åpne verktøyet.

Første mal (2026-09-02, idébank #29 §Gul hatt-gjennomgang): kildesamling — et utvalg
cachede papirer (typisk et søkeresultat eller en emne-utforskning) som ett lesbart
dokument, gruppert på domene-nærhet — samme ADR-013-prinsipp som selve søkerangeringen,
ikke en ny idé oppfunnet for rapporten. Ærlighets-prinsippet gjelder eksporten også:
rapporten hevder ALDRI å være uttømmende, kun hva verktøyet faktisk fant og når.

Input er bank.hent()-formede dict-er (id, tittel, forfattere, tidsskrift, aar, doi,
abstract, siteringstall, open_access, kilde_url, kilde_kode) — samme form api.py
allerede serialiserer overalt, ingen ny type å holde synkronisert.
"""
import time

from domeneprofil import domene_naer_tekst

_UTDRAG_LENGDE = 400


def _naer(p: dict) -> bool:
    return domene_naer_tekst(f"{p.get('forfattere', '')} {p.get('tidsskrift', '')}")


def _seksjon(p: dict) -> str:
    aar = p.get("aar") or "?"
    sit = p.get("siteringstall")
    sit_tekst = f"{sit} siteringer" if sit is not None else "siteringstall ukjent"
    oa = " · Open Access" if p.get("open_access") else ""
    lenke = p.get("kilde_url") or (f"https://doi.org/{p['doi']}" if p.get("doi") else "")
    linjer = [
        f"### {p.get('tittel') or 'Uten tittel'}",
        f"*{p.get('forfattere') or 'Forfatter ukjent'}* — "
        f"{p.get('tidsskrift') or 'Tidsskrift ukjent'}, {aar} · {sit_tekst}{oa}",
    ]
    if lenke:
        linjer.append(f"<{lenke}>")
    abstract = (p.get("abstract") or "").strip()
    if abstract:
        utdrag = abstract[:_UTDRAG_LENGDE]
        if len(abstract) > _UTDRAG_LENGDE:
            utdrag += "…"
        linjer.append(f"> {utdrag}")
    return "\n\n".join(linjer)


def kildesamling(papirer: list[dict], *, tittel: str = "Kildesamling") -> str:
    """Grupperer papirer på domene-nærhet FØRST (nordisk fagmiljø/kjerne-fagtidsskrift),
    resten samlet under egen seksjon — ikke rangert på nytt her, rekkefølgen INNENFOR
    hver gruppe er den input-listen allerede hadde (typisk ranking.py sin)."""
    dato = time.strftime("%Y-%m-%d")
    if not papirer:
        return f"# {tittel}\n\n*Generert av forskningssok, {dato} — ingen papirer i utvalget.*\n"
    naere = [p for p in papirer if _naer(p)]
    naere_id = {p.get("id") for p in naere}
    andre = [p for p in papirer if p.get("id") not in naere_id]
    delar = [
        f"# {tittel}",
        f"*Generert av forskningssok, {dato} — {len(papirer)} papirer. "
        f"Et utgangspunkt for videre vurdering, ikke en uttømmende litteraturgjennomgang.*",
    ]
    if naere:
        delar.append("## Nordisk fagmiljø / kjerne-fagtidsskrift")
        delar.extend(_seksjon(p) for p in naere)
    if andre:
        delar.append("## Øvrige treff")
        delar.extend(_seksjon(p) for p in andre)
    return "\n\n".join(delar) + "\n"
