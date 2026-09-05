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
import re
import json
from pathlib import Path
import time
from dataclasses import dataclass
from io import BytesIO
from xml.sax.saxutils import escape as _xml_escape

import domeneprofil
from domeneprofil import arts_naer_tekst, domene_naer_tekst
from evidensniva import evidensniva

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
    niva, niva_kilde = evidensniva(p.get("tittel", ""), p.get("abstract", ""),
                                    tuple((p.get("pubtyper") or "").split("|")) if p.get("pubtyper") else ())
    if niva != "Ukjent design":
        niva += " (NLM-indeksert)" if niva_kilde == "nlm" else " (mønstergjenkjent)"
    # Merketeksten kommer fra profilen, ikke fra denne fila: dette er en EKSPORTERT
    # streng, altså den som følger med ut av huset i en delt PDF. Sto den hardkodet som
    # «laks/oppdrettsfisk», ville en bruker i et annet fagfelt delt en rapport som
    # påstår feil fagfelt — uten at noe feilet noe sted.
    varsel = "" if arts_naer_tekst(f"{p.get('tittel', '')} {p.get('abstract', '')}") \
        else f" · {domeneprofil.PROFIL['art'].get('merke', '⚠')} {domeneprofil.PROFIL['art'].get('merke_betyr', 'nevner ikke målobjektet')} — sjekk før bruk"
    if niva != "Ukjent design" or varsel:
        merknad = niva if niva != "Ukjent design" else ""
        ut.append(Blokk("p", f"{merknad}{varsel}".strip(" ·")))
    abstract = (p.get("abstract") or "").strip()
    if abstract:
        utdrag = abstract[:_UTDRAG_LENGDE]
        if len(abstract) > _UTDRAG_LENGDE:
            utdrag += "…"
        ut.append(Blokk("sitat", utdrag))
    return ut


def referanseliste_blokker(papirer: list[dict], *, stil: str = "vancouver") -> list[Blokk]:
    """En formatert «Referanser»-seksjon (citeproc, valgt stil). Dette er signatur-poleringen:
    en journal-standard referanseliste, ikke hjemmelaget «forfatter — tidsskrift, år»."""
    if not papirer:
        return []
    blokker = [Blokk("h2", "Referanser"),
               Blokk("meta", f"Formatert i {stil.upper()}-stil.")]
    for linje in render_referanser(papirer, stil=stil):
        blokker.append(Blokk("p", linje))
    return blokker


def kildesamling_blokker(papirer: list[dict], *, tittel: str = "Kildesamling",
                         stil: str = "vancouver", med_referanser: bool = True) -> list[Blokk]:
    """Grupperer papirer på domene-nærhet FØRST (nordisk fagmiljø/kjerne-fagtidsskrift) —
    samme ADR-013-prinsipp som selve søkerangeringen. Rekkefølgen INNENFOR hver gruppe er
    den input-listen allerede hadde (typisk ranking.py sin). Avsluttes med en formatert
    Referanser-seksjon i valgt stil (`stil`)."""
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
    if med_referanser:
        blokker.extend(referanseliste_blokker(papirer, stil=stil))
    return blokker


def kildesamling(papirer: list[dict], *, tittel: str = "Kildesamling",
                 stil: str = "vancouver") -> str:
    """Bakoverkompatibel Markdown-shortcut — se kildesamling_blokker() for PDF-veien."""
    return til_markdown(kildesamling_blokker(papirer, tittel=tittel, stil=stil))


# ---------- Sitasjonseksport: BibTeX/RIS — «hvordan får jeg dette inn i Zotero?» ----------
#
# Anders 2026-09-02: manuell sitasjonsformatering er fortsatt uløst selv med et
# referanseverktøy i hånden (bekreftet i research-runden samme kveld). Svaret er IKKE å
# formatere pen tekst Ulven likevel må lime inn manuelt — det er å gi ham en fil hans eget
# verktøy (Zotero/EndNote — begge dominerer forskerlandskapet) leser NATIVT. RIS er formatet
# begge er bygget rundt (Research Information Systems); BibTeX for LaTeX-arbeidsflyt. Ikke
# Blokk-baserte som resten av rapport.py (ingen overskrift/avsnitt-struktur å gjenbruke) —
# egen, flat gren, men samme prinsipp: rene data-transformasjoner, ingen IO her.

def _forfatterliste(forfattere: str) -> list[str]:
    """Kildene formaterer forfattere ulikt (Europe PMC: «Etternavn AB, Etternavn2 CD»
    kommaseparert; OpenAlex: «Fornavn Etternavn; Fornavn2 Etternavn2» semikolon-separert)
    — bevisst enkel: velger skilletegn ut fra hva som faktisk finnes, omformaterer ALDRI
    navnerekkefølgen. Dokumentert begrensning, ikke skjult."""
    forfattere = (forfattere or "").strip()
    if not forfattere:
        return []
    sep = ";" if ";" in forfattere else ","
    return [f.strip() for f in forfattere.split(sep) if f.strip()]


def _bib_nokkel(p: dict, brukt: set[str]) -> str:
    forfattere = _forfatterliste(p.get("forfattere", ""))
    etternavn = re.sub(r"[^a-z0-9]", "", (forfattere[0].split()[0] if forfattere else "ukjent").lower())
    base = f"{etternavn}{p.get('aar') or 'uaar'}"
    nokkel, i = base, 2
    while nokkel in brukt:
        nokkel = f"{base}{i}"
        i += 1
    brukt.add(nokkel)
    return nokkel


def _bib_escape(s) -> str:
    """Minimal, ikke uttømmende — unngår å KNEKKE .bib-syntaksen (ubalanserte klammer),
    ikke en full LaTeX-spesialtegn-escaper."""
    return str(s or "").replace("{", "").replace("}", "")


def til_bibtex(papirer: list[dict]) -> str:
    brukt: set[str] = set()
    poster = []
    for p in papirer:
        nokkel = _bib_nokkel(p, brukt)
        felt = [
            ("author", " and ".join(_forfatterliste(p.get("forfattere", "")))),
            ("title", p.get("tittel", "")),
            ("journal", p.get("tidsskrift", "")),
            ("year", str(p.get("aar") or "")),
            ("doi", p.get("doi") or ""),
            ("url", p.get("kilde_url") or ""),
        ]
        linjer = ",\n".join(f"  {navn} = {{{_bib_escape(verdi)}}}" for navn, verdi in felt if verdi)
        poster.append(f"@article{{{nokkel},\n{linjer}\n}}")
    return "\n\n".join(poster) + ("\n" if poster else "")


def til_csl_json(papirer: list[dict]) -> str:
    """CSL-JSON — det formatet som faktisk gir «boilerplate som fyller ut mekanisk».

    BibTeX og RIS er utvekslingsformater: de flytter data mellom programmer. CSL-JSON er
    inngangen til Citation Style Language, som er MOTOREN Zotero, Mendeley, Paperpile og
    Pandoc alle bruker for å RENDRE en referanse — med 10 000+ ferdige tidsskriftstiler
    (APA, Vancouver, Harvard, per-tidsskrift). Å skrive vår egen malmotor ville vært en
    dårligere kopi av tjue års korpus.

    Feltnavnene er CSL-spesifikasjonens, ikke våre: `container-title` (ikke journal),
    `page`, `volume`, `issue`, `issued.date-parts`. Forfattere splittes i family/given
    fordi en stil som krever «Dalum, A. S.» ikke kan utlede det fra én streng.

    Felter vi ikke har utelates HELT i stedet for å settes til tom streng: en CSL-prosessor
    som ser `"page": ""` renderer «s. » med et tomt tall, mens et fraværende felt får
    stilen til å hoppe over leddet. Samme ærlighets-prinsipp som resten av huset — et
    fravær skal se ut som et fravær.
    """
    return json.dumps([_csl_post(p) for p in papirer], ensure_ascii=False, indent=2) + "\n"


def _csl_post(p: dict) -> dict:
    """Ett papir → én CSL-JSON-post. Delt mellom eksporten (til_csl_json) og
    citeproc-rendringen (render_referanser), så feltmappingen har ÉN sannhet."""
    post: dict = {
        "id": p.get("id") or p.get("doi") or p.get("pmid") or "ukjent",
        "type": "article-journal",
        "title": p.get("tittel") or "",
    }
    forf = []
    for navn in _forfatterliste(p.get("forfattere", "")):
        # Europe PMC gir «Dalum AS» — etternavn først, initialer sist og uten punktum.
        deler = navn.split()
        if len(deler) >= 2:
            forf.append({"family": " ".join(deler[:-1]), "given": deler[-1]})
        elif deler:
            forf.append({"literal": deler[0]})
    if forf:
        post["author"] = forf
    for csl, felt in (("container-title", "tidsskrift"), ("volume", "volum"),
                       ("issue", "hefte"), ("page", "sider"), ("DOI", "doi"),
                       ("ISSN", "issn"), ("URL", "kilde_url"), ("abstract", "abstract")):
        verdi = p.get(felt)
        if verdi:
            post[csl] = str(verdi)
    if p.get("aar"):
        post["issued"] = {"date-parts": [[int(p["aar"])]]}
    if p.get("pmid"):
        post["PMID"] = str(p["pmid"])
    return post


# ── Ekte siterings-rendring: CSL-JSON → formatert referanse via citeproc ─────────────
# Dette er skillet mellom «ser hjemmelaget ut» og «ser ut som noe man betaler for». Vi
# skriver IKKE en malmotor (rapport.py sa alt hvorfor: en dårligere kopi av tjue års
# tidsskriftstil-korpus). Vi kjører CSL-JSON-en vi alt bygger gjennom citeproc — samme
# motor Zotero og Pandoc bruker — med en ferdig .csl-stil.
STIL_DIR = Path(__file__).resolve().parent / "csl_stiler"


def _referanse_prosa(p: dict) -> str:
    """Fallback hvis citeproc/stilen svikter: en enkel, ærlig linje. En rapport skal ALDRI
    krasje på formatering — en litt kjedeligere referanse er bedre enn en 500."""
    forf = p.get("forfattere") or "Forfatter ukjent"
    aar = p.get("aar") or "u.å."
    ts = p.get("tidsskrift") or ""
    doi = f" doi:{p['doi']}" if p.get("doi") else ""
    return f"{forf} ({aar}). {p.get('tittel') or 'Uten tittel'}. {ts}.{doi}".strip()


def render_referanser(papirer: list[dict], *, stil: str = "vancouver") -> list[str]:
    """Formaterte referanser i valgt stil (vancouver/apa/harvard). Én streng per papir, i
    rekkefølge. Faller tilbake til _referanse_prosa hvis citeproc eller stilen svikter."""
    if not papirer:
        return []
    sti = STIL_DIR / f"{stil}.csl"
    if not sti.exists():
        return [_referanse_prosa(p) for p in papirer]
    try:
        from citeproc import (CitationStylesStyle, CitationStylesBibliography,
                              Citation, CitationItem, formatter)
        from citeproc.source.json import CiteProcJSON
        poster = []
        for i, p in enumerate(papirer):
            post = _csl_post(p)
            post["id"] = f"ref-{i}"  # citeproc krever unike id-er
            poster.append(post)
        style = CitationStylesStyle(str(sti), validate=False)
        bib = CitationStylesBibliography(style, CiteProcJSON(poster), formatter.plain)
        for i in range(len(poster)):
            bib.register(Citation([CitationItem(f"ref-{i}")]))
        rendret = [str(item).strip() for item in bib.bibliography()]
        # citeproc kan i sjeldne tilfeller droppe en post den ikke klarer — fyll ut med
        # fallback så antallet stemmer med papirlista (ellers ville referanse 4 pekt feil).
        if len(rendret) != len(papirer):
            return [_referanse_prosa(p) for p in papirer]
        return rendret
    except Exception:
        return [_referanse_prosa(p) for p in papirer]


def _ris_post(p: dict) -> str:
    linjer = ["TY  - JOUR"]
    linjer += [f"AU  - {f}" for f in _forfatterliste(p.get("forfattere", ""))]
    for tag, felt in (("TI", "tittel"), ("JO", "tidsskrift"), ("PY", "aar"),
                       ("VL", "volum"), ("IS", "hefte"), ("SP", "sider"), ("SN", "issn"),
                       ("DO", "doi"), ("UR", "kilde_url"), ("AB", "abstract")):
        verdi = p.get(felt)
        if verdi:
            linjer.append(f"{tag}  - {verdi}")
    linjer.append("ER  - ")
    return "\n".join(linjer)


def til_ris(papirer: list[dict]) -> str:
    return "\n\n".join(_ris_post(p) for p in papirer) + ("\n" if papirer else "")


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


# ---------- Mal 6: boilerplate fra sitatbanken — «relasjonelle sitater åpnet samlet» ----------

def boilerplate_blokker(kildepapir: dict, relaterte: list[dict],
                         sitater_per_papir: dict[str, list[dict]],
                         *, tittel: str | None = None) -> list[Blokk]:
    """Et arbeidsdokument bygget av ETT papir pluss dets semantiske naboer i sitatbanken.

    Dette er det Anders beskrev som «relasjonelle sitater åpnet samlet i en boilerplate som
    fyller ut mekanisk alt som trengs». Alt som KAN utledes er utledet: overskriftene,
    kildehenvisningene, referanselisten, rekkefølgen. Det eneste tomme er der du skal
    tenke — og de stedene er merket, ikke usynlige.

    Nabolaget er IKKE en påstand om at papirene hører sammen faglig. Det er
    embedding-avstand mellom abstracts, og avstanden står i dokumentet så leseren kan
    bedømme den selv. Samme kontrakt som «Lignende»-fanen: kandidater, ikke en dom."""
    ktittel = kildepapir.get("tittel") or "Uten tittel"
    blokker = [Blokk("h1", tittel or f"Arbeidsnotat — {ktittel}")]
    blokker.append(Blokk("meta",
        f"Generert av forskningssok, {_dato()}. Bygget av ETT papir og "
        f"{len(relaterte)} semantisk nærmeste papirer DU HAR SITERT. Nabolaget er "
        f"embedding-avstand mellom abstracts, ikke en faglig dom — avstanden står ved hver "
        f"kilde. Ingenting her er AI-generert prosa; alle sitater er ordrett dine egne utdrag."))

    alle = [kildepapir] + relaterte
    for i, p in enumerate(alle):
        pid = p.get("id") or p.get("paper_id") or ""
        avstand = p.get("avstand")
        blokker.append(Blokk("h2", p.get("tittel") or "Uten tittel"))
        merknad = _kildelinje({
            "paper_forfattere": p.get("forfattere"), "paper_aar": p.get("aar"),
            "paper_tittel": None, "paper_tidsskrift": p.get("tidsskrift"),
            "paper_doi": p.get("doi"),
        })
        if i == 0:
            merknad += "  ·  utgangspunkt"
        elif avstand is not None:
            merknad += f"  ·  avstand {avstand:.3f}"
        blokker.append(Blokk("meta", merknad))

        for s in sorted(sitater_per_papir.get(pid, []), key=lambda x: x.get("opprettet", 0)):
            blokker.append(Blokk("sitat", s.get("tekst", "")))
            if (s.get("kommentar") or "").strip():
                blokker.append(Blokk("p", f"Kommentar: {s['kommentar']}"))
        blokker.append(Blokk("p", "*Din lesning:*"))

    blokker.append(Blokk("h2", "Å skrive ut"))
    blokker.append(Blokk("p", "*Hva sier de sammen? Hvor er de uenige? Hva mangler?*"))

    blokker.append(Blokk("h2", "Referanser"))
    for p in alle:
        blokker.append(Blokk("p", _kildelinje({
            "paper_forfattere": p.get("forfattere"), "paper_aar": p.get("aar"),
            "paper_tittel": p.get("tittel"), "paper_tidsskrift": p.get("tidsskrift"),
            "paper_doi": p.get("doi"),
        })))
    blokker.append(Blokk("meta",
        "Referansene over er husets eget format. Trenger du APA, Vancouver eller en "
        "tidsskriftspesifikk stil: hent samme utvalg som CSL-JSON (format=csl) og kjør det "
        "gjennom en hvilken som helst citeproc — det er samme motor Zotero og Pandoc bruker, "
        "med over 10 000 ferdige stiler."))
    return blokker


# ---------- Mal 5: dokumentet — egen tekst + festede sitater, det som faktisk deles ----------

def dokument_blokker(utkast: dict, sitater: list[dict], *, tittel: str | None = None) -> list[Blokk]:
    """Den ENESTE malen som blander brukerens egen prosa med sitert kildetekst. Derfor
    er skillet mellom dem bygget inn i blokk-typene («p» for din tekst, «sitat» +
    kildelinje for det som er hentet), ikke overlatt til leserens hukommelse: en delt PDF
    må aldri kunne leses som om du selv skrev det du siterte.

    Sitatene snus til ELDSTE først her (bank leverer nyeste først) — et dokument leses
    ovenfra, og rekkefølgen du fanget dem i er den eneste rekkefølgen verktøyet vet noe
    om. Ingen forsøk på å gjette hvor i brødteksten de hører hjemme."""
    tittel = tittel or utkast.get("tittel") or "Uten tittel"
    blokker = [Blokk("h1", tittel)]
    n = len(sitater)
    blokker.append(Blokk("meta", f"Skrevet i forskningssok, eksportert {_dato()} — "
                                  f"{n} sitat{'' if n == 1 else 'er'} festet til dokumentet."))

    innhold = (utkast.get("innhold") or "").strip()
    if innhold:
        for avsnitt in [a.strip() for a in innhold.split("\n") if a.strip()]:
            blokker.append(Blokk("p", avsnitt))
    else:
        blokker.append(Blokk("meta", "(Ingen brødtekst skrevet ennå.)"))

    if not sitater:
        return blokker

    blokker.append(Blokk("h2", "Kilder sitert"))
    for s in sorted(sitater, key=lambda x: x.get("opprettet", 0)):
        blokker.append(Blokk("sitat", s.get("tekst", "")))
        blokker.append(Blokk("p", _kildelinje(s)))
        if (s.get("kommentar") or "").strip():
            blokker.append(Blokk("p", f"Kommentar: {s['kommentar']}"))
    return blokker


def _kildelinje(sitat: dict) -> str:
    """Én lesbar henvisning per sitat. Feltene som mangler droppes stille — en
    henvisning uten årstall er fortsatt sann; en oppdiktet «(u.å.)»-konvensjon ville
    vært verktøyet som fyller ut på forfatterens vegne."""
    deler = []
    forfattere = (sitat.get("paper_forfattere") or "").split(",")
    if forfattere and forfattere[0].strip():
        deler.append(forfattere[0].strip() + (" et al." if len(forfattere) > 1 else ""))
    if sitat.get("paper_aar"):
        deler.append(f"({sitat['paper_aar']})")
    if sitat.get("paper_tittel"):
        # Punktum kun hvis tittelen ikke alt ender på skilletegn — Europe PMC leverer
        # mange titler med punktum bakt inn, og «… Considerations..» så ut som en feil
        # i det eksporterte dokumentet (målt live 2026-09-04).
        tit = sitat["paper_tittel"].rstrip()
        deler.append(tit if tit.endswith((".", "?", "!")) else tit + ".")
    if sitat.get("paper_tidsskrift"):
        deler.append(f"*{sitat['paper_tidsskrift']}*.")
    if sitat.get("paper_doi"):
        deler.append(f"doi:{sitat['paper_doi']}")
    return " ".join(deler) or "Ukjent kilde"


def dokument(utkast: dict, sitater: list[dict], *, tittel: str | None = None) -> str:
    return til_markdown(dokument_blokker(utkast, sitater, tittel=tittel))


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
    # Et forbehold som MÅ stå i den delte filen, ikke bare på skjermen: en ufullstendig
    # referanseliste gjør gap-listen for lang, og en leser som får rapporten videre har
    # ingen annen måte å vite det på.
    dekning = gap_resultat.get("referanse_dekning")
    if dekning:
        blokker.append(Blokk("meta",
            f"⚠ Forbehold: referanselisten som ble hentet har {dekning['hentet']} av de "
            f"{dekning['oppgitt_av_utgiver']} referansene utgiveren selv oppgir. De "
            f"{dekning['oppgitt_av_utgiver'] - dekning['hentet']} ukjente kan være blant "
            f"kandidatene under — listen er altså trolig for lang, ikke for kort."))
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

    # Naboer utgitt ETTER kildepapiret er verken gap eller sitert; de er en tredje ting.
    # Uten denne seksjonen ville de falt i «allerede sitert» nedenfor bare fordi de ikke
    # sto i gap-listen — en stille feilklassifisering innført samme dag som årsskillet.
    ferske = gap_resultat.get("publisert_etter") or []
    if ferske:
        blokker.append(Blokk("h2", "Publisert etter kildepapiret — kunne ikke vært sitert"))
        blokker.append(Blokk("p", "Ikke et gap: kildepapiret er eldre enn disse. Les dem som "
                                  "«dette har kommet siden», ikke som noe forfatteren overså."))
        for n in ferske:
            blokker.append(Blokk("p", f"{n.get('tittel') or 'Uten tittel'} — "
                                       f"{n.get('tidsskrift') or '?'}, {n.get('aar') or '?'} "
                                       f"· avstand {n.get('avstand', 0):.3f}"))

    fersk_id = {n.get("id") for n in ferske}
    sitert = [n for n in naboer if n.get("id") not in gap_id and n.get("id") not in fersk_id]
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


# ---------- Konvergens-rapport: de fem flettet til produktets signatur-leveranse ----------
#
# Nordstjernen (Anders 2026-09-05): en forskningsplattform som spytter ut fine
# boilerplate-rapporter en betalende kunde åpner. Denne malen er der brikkene MØTES —
# kildesamling + citation-gap + omfang + verifisering + proveniens — en kombinasjon ingen
# konkurrent bunter. rapport.py forblir nettverksfri: den TAR de ferdig-beregnede bitene
# inn (api.py gjør søket/gap/omfang), assembler dokumentet, og er ærlig om det som mangler.

def _proveniens_linje(revisjon: dict) -> str:
    """«Hard empiri» gjort synlig: hvilke kilder, cache-alder, dedup — Ulvens salgsargument."""
    tpk = revisjon.get("treff_per_kilde", {})
    alder = revisjon.get("cache_alder_s")
    fersk = "ekte kall" if alder is None else f"cache {alder // 60} min gammel"
    kilder = revisjon.get("kilder", {})
    core = "" if kilder.get("core", True) else " (CORE utilgjengelig)"
    return (f"Proveniens: Europe PMC {tpk.get('europe_pmc', '?')} treff ({fersk}), "
            f"CORE {tpk.get('core', 0)} treff{core}, "
            f"{revisjon.get('dubletter_fjernet', 0)} dubletter slått sammen. "
            f"Profil «{revisjon.get('profil', '?')}».")


def konvergens_blokker(query: str, papirer: list[dict], *, gap_papir: dict | None = None,
                       gap: dict | None = None, omfang: dict[str, float] | None = None,
                       revisjon: dict | None = None, verifisering: dict | None = None,
                       stil: str = "vancouver", tittel: str | None = None) -> list[Blokk]:
    """Én forskningsrapport for `query`, bygget av de ferdig-beregnede bitene. Hver seksjon
    er ærlig om fravær: mangler gap-papiret, står seksjonen ikke; er verifisering ikke
    tilgjengelig (Mistral-abonnement), sies det rett ut i stedet for å utelates stille."""
    tittel = tittel or f"Forskningsrapport: {query}"
    b = [Blokk("h1", tittel),
         Blokk("meta", f"av Lauvasdata · forskningssok · {_dato()}")]
    if revisjon:
        b.append(Blokk("meta", _proveniens_linje(revisjon)))
    b.append(Blokk("p", f"Et strukturert utgangspunkt for spørringen «{query}» — kildene, "
                        f"hva litteraturen mangler, dekningen, og formaterte referanser. "
                        f"Et hjelpemiddel for videre vurdering, ikke en uttømmende gjennomgang."))

    # 1. Kilder (gruppert på domene-nærhet, uten egen referanseliste — samlet til slutt)
    b.append(Blokk("h2", f"Kilder ({len(papirer)})"))
    naere = [p for p in papirer if domene_naer_tekst(f"{p.get('forfattere', '')} {p.get('tidsskrift', '')}")]
    naere_id = {p.get("id") for p in naere}
    if naere:
        b.append(Blokk("h3", "Nordisk fagmiljø / kjerne-fagtidsskrift"))
        for p in naere:
            b.extend(_kildesamling_papir_blokker(p))
    andre = [p for p in papirer if p.get("id") not in naere_id]
    if andre:
        b.append(Blokk("h3", "Øvrige treff"))
        for p in andre:
            b.extend(_kildesamling_papir_blokker(p))

    # 2. Hva litteraturen mangler (citation-gap) — differensieringen (Aaron Tay-proben)
    if gap and gap_papir:
        b.append(Blokk("h2", "Hva litteraturen mangler (citation-gap)"))
        b.append(Blokk("p", f"For «{(gap_papir.get('tittel') or '')[:80]}»: papiret siterer "
                            f"{gap.get('siterte_antall', 0)} kilder (via "
                            f"{gap.get('referanse_kilde', 'ukjent')}). "
                            f"{len(gap.get('gap', []))} semantiske naboer i korpuset er IKKE i "
                            f"den referanselisten — kandidater å vurdere, ikke en dom."))
        for g in (gap.get("gap") or [])[:8]:
            b.append(Blokk("p", f"· {g.get('tittel') or 'Uten tittel'} "
                                f"({g.get('aar') or '?'}, avstand {g.get('avstand', 0):.3f})"))

    # 3. Omfang — akse-dekning
    if omfang:
        b.append(Blokk("h2", "Omfang — dekning per forskningsakse"))
        b.append(Blokk("meta", "Nøkkelord-basert hjelpemiddel over kildenes tekst, ikke en semantisk dom."))
        for akse, dekning in omfang.items():
            merke = "godt dekket" if dekning >= 1.0 else ("tynt/ikke nevnt" if dekning == 0 else "delvis")
            b.append(Blokk("p", f"· {akse}: {round(dekning * 100)} % ({merke})"))

    # 4. Verifisering — ærlig om at kapabiliteten finnes men kan være gated
    b.append(Blokk("h2", "Verifisering av påstander"))
    if verifisering and verifisering.get("tilgjengelig"):
        b.append(Blokk("p", "Marker en påstand i verktøyet og trykk «Verifiser» for et "
                            "EU-web-verifisert verdikt med kilder (FDR-028)."))
    else:
        b.append(Blokk("p", "Påstands-verifisering (web-kilder, EU-direkte) er en kapabilitet "
                            "i verktøyet, men er ikke aktivert i dette miljøet ennå. Rapporten "
                            "gjør derfor ingen verifiserte påstander — kildene over står for seg selv."))

    # 5. Referanser — den formaterte bibliografien (signatur-poleringen)
    b.extend(referanseliste_blokker(papirer, stil=stil))
    return b


def konvergens(query: str, papirer: list[dict], **kw) -> str:
    return til_markdown(konvergens_blokker(query, papirer, **kw))
