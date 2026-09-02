"""rapport.py — rapportmaler: strukturerte eksporter av et utvalg, klare til å limes
inn i e-post/dokument eller sendes til en kollega/Lumic-teamet uten at de selv må åpne
verktøyet. To format fra samme data: Markdown (rask, limes rett inn) og PDF (Ulven ba
eksplisitt om dette 2026-09-02 — noe som ser ut som et dokument, ikke en tekstfil).

Arkitektur: hver mal bygger en liste `Blokk`-er (typet innhold: overskrift, avsnitt,
sitat, lenke) — IKKE en ferdig streng. `til_markdown()`/`til_pdf_bytes()` er de eneste
to stedene som vet hvordan en Blokk-liste blir tekst/PDF. Uten dette laget ville hver ny
mal (nå fire, flere kommer) måtte implementere BÅDE Markdown- og PDF-rendering selv —
firedoblet flate for samme feilklasse. Malene under er derfor rene, testbare
data-transformasjoner: input inn, Blokk-liste ut, aldri IO/nettverk selv (samme
separasjon som api.py alt bruker — bank.py/scoping.py henter, rapport.py formaterer).

Ærlighets-prinsippet gjelder alle malene: ingen rapport hevder å være uttømmende, kun
hva verktøyet faktisk fant og når.
"""
import time
from dataclasses import dataclass
from io import BytesIO
from xml.sax.saxutils import escape as _xml_escape

from domeneprofil import domene_naer_tekst

_UTDRAG_LENGDE = 400


@dataclass(frozen=True)
class Blokk:
    type: str  # "h1" | "h2" | "h3" | "meta" | "p" | "sitat" | "lenke"
    tekst: str


def _dato() -> str:
    return time.strftime("%Y-%m-%d")


# ---------- Rendering: samme Blokk-liste, to formater ----------

def til_markdown(blokker: list[Blokk]) -> str:
    ut = []
    for b in blokker:
        if b.type == "h1":
            ut.append(f"# {b.tekst}")
        elif b.type == "h2":
            ut.append(f"## {b.tekst}")
        elif b.type == "h3":
            ut.append(f"### {b.tekst}")
        elif b.type == "meta":
            ut.append(f"*{b.tekst}*")
        elif b.type == "sitat":
            ut.append(f"> {b.tekst}")
        elif b.type == "lenke":
            ut.append(f"<{b.tekst}>")
        else:
            ut.append(b.tekst)
    return "\n\n".join(ut) + "\n"


def til_pdf_bytes(blokker: list[Blokk], *, tittel: str = "") -> bytes:
    """Reportlab Platypus — ren Python, ingen systembinær (weasyprint/wkhtmltopdf
    ville krevd Cairo/Pango installert utenfor venv, samme fallgruve som
    `gjør det åpenbare riktig`-disiplinen advarer mot). Paragraph-tekst er reportlabs
    egen mini-XML-markup — ALL brukertekst må escapes FØR den limes inn, ellers knekker
    en tittel med `&`/`<` i seg rendering stille."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    sitat_stil = ParagraphStyle(
        "Sitat", parent=styles["Normal"], leftIndent=12 * mm,
        textColor=colors.HexColor("#5A5A56"), fontName="Helvetica-Oblique", spaceAfter=4,
    )
    meta_stil = ParagraphStyle(
        "Meta", parent=styles["Normal"], textColor=colors.HexColor("#5A5A56"),
        fontName="Helvetica-Oblique", fontSize=9, spaceAfter=10,
    )
    lenke_stil = ParagraphStyle("Lenke", parent=styles["Normal"], fontSize=8, spaceAfter=6)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=tittel or "Rapport",
                             topMargin=20 * mm, bottomMargin=20 * mm,
                             leftMargin=20 * mm, rightMargin=20 * mm)
    story = []
    for b in blokker:
        tekst = _xml_escape(b.tekst)
        if b.type == "h1":
            story.append(Paragraph(tekst, styles["Title"]))
        elif b.type == "h2":
            story.append(Spacer(1, 8))
            story.append(Paragraph(tekst, styles["Heading2"]))
        elif b.type == "h3":
            story.append(Spacer(1, 4))
            story.append(Paragraph(tekst, styles["Heading3"]))
        elif b.type == "meta":
            story.append(Paragraph(tekst, meta_stil))
        elif b.type == "sitat":
            story.append(Paragraph(f"«{tekst}»", sitat_stil))
        elif b.type == "lenke":
            href = _xml_escape(b.tekst)
            story.append(Paragraph(f'<link href="{href}" color="#2E5C47">{tekst}</link>', lenke_stil))
        else:
            story.append(Paragraph(tekst, styles["Normal"]))
    doc.build(story)
    return buf.getvalue()


# ---------- Mal 1: kildesamling — et papirutvalg som ett dokument ----------

def _kildesamling_papir_blokker(p: dict) -> list[Blokk]:
    aar = p.get("aar") or "?"
    sit = p.get("siteringstall")
    sit_tekst = f"{sit} siteringer" if sit is not None else "siteringstall ukjent"
    oa = " · Open Access" if p.get("open_access") else ""
    lenke = p.get("kilde_url") or (f"https://doi.org/{p['doi']}" if p.get("doi") else "")
    ut = [
        Blokk("h3", p.get("tittel") or "Uten tittel"),
        Blokk("p", f"{p.get('forfattere') or 'Forfatter ukjent'} — "
                   f"{p.get('tidsskrift') or 'Tidsskrift ukjent'}, {aar} · {sit_tekst}{oa}"),
    ]
    if lenke:
        ut.append(Blokk("lenke", lenke))
    abstract = (p.get("abstract") or "").strip()
    if abstract:
        utdrag = abstract[:_UTDRAG_LENGDE]
        if len(abstract) > _UTDRAG_LENGDE:
            utdrag += "…"
        ut.append(Blokk("sitat", utdrag))
    return ut


def kildesamling_blokker(papirer: list[dict], *, tittel: str = "Kildesamling") -> list[Blokk]:
    """Grupperer papirer på domene-nærhet FØRST (nordisk fagmiljø/kjerne-fagtidsskrift) —
    samme ADR-013-prinsipp som selve søkerangeringen. Rekkefølgen INNENFOR hver gruppe er
    den input-listen allerede hadde (typisk ranking.py sin)."""
    blokker = [Blokk("h1", tittel)]
    if not papirer:
        blokker.append(Blokk("meta", f"Generert av forskningssok, {_dato()} — ingen papirer i utvalget."))
        return blokker
    blokker.append(Blokk("meta", f"Generert av forskningssok, {_dato()} — {len(papirer)} papirer. "
                                  f"Et utgangspunkt for videre vurdering, ikke en uttømmende litteraturgjennomgang."))
    naere = [p for p in papirer if domene_naer_tekst(f"{p.get('forfattere', '')} {p.get('tidsskrift', '')}")]
    naere_id = {p.get("id") for p in naere}
    andre = [p for p in papirer if p.get("id") not in naere_id]
    if naere:
        blokker.append(Blokk("h2", "Nordisk fagmiljø / kjerne-fagtidsskrift"))
        for p in naere:
            blokker.extend(_kildesamling_papir_blokker(p))
    if andre:
        blokker.append(Blokk("h2", "Øvrige treff"))
        for p in andre:
            blokker.extend(_kildesamling_papir_blokker(p))
    return blokker


def kildesamling(papirer: list[dict], *, tittel: str = "Kildesamling") -> str:
    """Bakoverkompatibel Markdown-shortcut — se kildesamling_blokker() for PDF-veien."""
    return til_markdown(kildesamling_blokker(papirer, tittel=tittel))


# ---------- Mal 2: sitatnotater — hele leseloggen som ett dokument ----------

def sitatnotater_blokker(sitater: list[dict], *, tittel: str = "Sitatnotater") -> list[Blokk]:
    """sitater = bank.hent_sitater()-formede dict-er (id, paper_id, tekst, kommentar,
    opprettet, paper_tittel, paper_doi) — allerede nyeste-først fra bank.py."""
    blokker = [Blokk("h1", tittel)]
    if not sitater:
        blokker.append(Blokk("meta", f"Generert av forskningssok, {_dato()} — ingen sitater lagret ennå."))
        return blokker
    blokker.append(Blokk("meta", f"Generert av forskningssok, {_dato()} — {len(sitater)} sitater, nyeste først."))
    for s in sitater:
        blokker.append(Blokk("h3", s.get("paper_tittel") or "Uten papirtittel"))
        tidspunkt = time.strftime("%Y-%m-%d %H:%M", time.localtime(s.get("opprettet", 0)))
        doi_del = f" · doi:{s['paper_doi']}" if s.get("paper_doi") else ""
        blokker.append(Blokk("p", f"{tidspunkt}{doi_del}"))
        blokker.append(Blokk("sitat", s.get("tekst", "")))
        if (s.get("kommentar") or "").strip():
            blokker.append(Blokk("p", f"Kommentar: {s['kommentar']}"))
    return blokker


def sitatnotater(sitater: list[dict], *, tittel: str = "Sitatnotater") -> str:
    return til_markdown(sitatnotater_blokker(sitater, tittel=tittel))


# ---------- Mal 3: citation-gap-rapport — Aaron Tay-proben som delbart dokument ----------

def gap_rapport_blokker(kilde_papir: dict, gap_resultat: dict, *, tittel: str | None = None) -> list[Blokk]:
    """kilde_papir = bank.hent()-formet dict for papiret gap-testen kjøres PÅ.
    gap_resultat = citation_gap.gap_kandidater()s retur ({siterte_antall,
    referanse_kilde, naboer, gap})."""
    kilde_tittel = kilde_papir.get("tittel") or "Uten tittel"
    blokker = [Blokk("h1", tittel or f"Citation-gap: {kilde_tittel}")]
    naboer = gap_resultat.get("naboer", [])
    gap = gap_resultat.get("gap", [])
    gap_id = {g.get("id") for g in gap}
    blokker.append(Blokk("meta",
        f"Generert av forskningssok, {_dato()} — «{kilde_tittel}» siterer "
        f"{gap_resultat.get('siterte_antall', 0)} kilder selv (kilde: "
        f"{gap_resultat.get('referanse_kilde', 'ukjent')}). {len(gap)} av {len(naboer)} "
        f"semantiske naboer i cachen er IKKE i den listen. Dette er kandidater for "
        f"menneskelig vurdering, ALDRI en påstand om at noe faktisk mangler i litteraturen."))
    if gap:
        blokker.append(Blokk("h2", "Kandidater — ikke sitert av kildepapiret"))
        for g in gap:
            blokker.append(Blokk("h3", g.get("tittel") or "Uten tittel"))
            blokker.append(Blokk("p", f"{g.get('tidsskrift') or 'Tidsskrift ukjent'}, "
                                       f"{g.get('aar') or '?'} · avstand {g.get('avstand', 0):.3f}"))
            if g.get("kilde_url"):
                blokker.append(Blokk("lenke", g["kilde_url"]))
    else:
        blokker.append(Blokk("p", "Ingen kandidater — alle semantiske naboer i cachen er allerede sitert."))
    sitert = [n for n in naboer if n.get("id") not in gap_id]
    if sitert:
        blokker.append(Blokk("h2", "Allerede sitert av kildepapiret (til referanse)"))
        for n in sitert:
            blokker.append(Blokk("p", f"{n.get('tittel') or 'Uten tittel'} — "
                                       f"{n.get('tidsskrift') or '?'}, {n.get('aar') or '?'}"))
    return blokker


def gap_rapport(kilde_papir: dict, gap_resultat: dict, *, tittel: str | None = None) -> str:
    return til_markdown(gap_rapport_blokker(kilde_papir, gap_resultat, tittel=tittel))


# ---------- Mal 4: omfang-rapport — akse-dekning for et utkast + forslag fra cachen ----------

def omfang_rapport_blokker(akser: dict[str, float], forslag: dict[str, list[dict]],
                            *, tittel: str = "Omfang-rapport") -> list[Blokk]:
    """akser = scoping.akse_dekning()s retur. forslag = {akse: [bank.lignende_tekst()-
    treff]} — KUN for akser under full dekning (api.py avgjør terskel og henter fra
    egen cache, rapport.py formaterer bare det som blir gitt inn, se moduldocstring)."""
    blokker = [Blokk("h1", tittel),
               Blokk("meta", f"Generert av forskningssok, {_dato()} — nøkkelord-basert dekning "
                             f"(en scoping-HJELPEMIDDEL, ikke en semantisk dom — se scoping.py).")]
    for akse, dekning in akser.items():
        blokker.append(Blokk("h2", f"{akse} — {round(dekning * 100)} %"))
        if dekning >= 1.0:
            blokker.append(Blokk("p", "Godt dekket i teksten."))
            continue
        blokker.append(Blokk("p", "Tynt dekket eller ikke nevnt ennå." if dekning == 0
                                   else "Delvis dekket."))
        kandidater = forslag.get(akse) or []
        if kandidater:
            blokker.append(Blokk("p", "Kandidater fra din egen cache som kan dekke aksen:"))
            for k in kandidater:
                blokker.append(Blokk("p", f"· {k.get('tittel') or 'Uten tittel'} "
                                           f"({k.get('aar') or '?'}, {k.get('tidsskrift') or '?'})"))
    return blokker


def omfang_rapport(akser: dict[str, float], forslag: dict[str, list[dict]],
                    *, tittel: str = "Omfang-rapport") -> str:
    return til_markdown(omfang_rapport_blokker(akser, forslag, tittel=tittel))
