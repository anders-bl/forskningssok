"""dokumenter.py — egne PDF-er inn i det samme korpuset.

Hullet dette lukker: de fleste Europe PMC-treff er IKKE open access (nesten alle treff i
kalibreringen 2026-09-04 var `isOpenAccess: N`). For dem har leseflaten kun abstractet,
og en forsker som faktisk HAR papiret gjennom institusjonstilgang har ingen vei til å
lese eller sitere det her. Det er Zotero sin egen brukssituasjon, og den var det største
gjenstående produkt-gapet før Ulven ser verktøyet.

**Designvalget som gjør resten gratis:** en dratt-inn PDF blir en ekte rad i `papers`,
ikke en sidevogn med egne visninger. Da virker sitering, «Lignende», ambient relevans,
banding, varme og alle fire rapportmalene på den fra første sekund — ingen av dem trengte
en linje ny kode for å se den. En parallell dokument-modell ville krevd at hver av dem
lærte om en andre entitetstype.

**DOI-en i PDF-en er identiteten, ikke filnavnet.** Drar Ulven inn PDF-en av et papir han
alt fant i verktøyet, skal fulltekst FESTE SEG på den eksisterende raden — ikke lage en
dublett med samme innhold under et annet navn. Filnavn er ubrukelig som identitet
(`s41598-024-1234-5.pdf`, `Downloads (3).pdf`), DOI-en inne i dokumentet er ikke.

**Det finnes ingen OCR her, og det sies høyt.** En skannet PDF har intet tekstlag; pypdf
returnerer da tom streng. Den tomheten lagres som det den er (`tegn: 0`) og flaten sier
«ingen tekst kunne hentes ut», fordi et stille tomt leseflate-panel ville sett nøyaktig ut
som et papir uten innhold — samme «ærlig tomt»-krav som resten av verktøyet.
"""
import hashlib
import re
import sqlite3
import time
from pathlib import Path

from paths import DB
from schemas import PaperDossier

# 60 MB. Et skannet, bildetungt tidsskriftpapir kan bli titalls megabyte; en hel bok
# hører ikke hjemme i et papir-korpus. Grensen er en volum-vakt, ikke en formatdom.
MAKS_BYTES = 60 * 1024 * 1024

# PDF-ene bor ved siden av cache.db, ALDRI i den. To grunner: sqlite blir treg og
# vanskelig å sikkerhetskopiere med titalls MB blobs, og paths.DB peker allerede på
# Dokploy-volumet — så filene arver persistensen uten en andre volum-beslutning.
#
# «vedlegg», ikke «dokumenter»: mappa lander ved siden av denne modulen i lokal utvikling,
# der paths.DB er repo-rota. En katalog `dokumenter/` rett ved `dokumenter.py` ville vært
# en navneromspakke med samme navn som modulen — import-rekkefølgen i CPython lar .py-fila
# vinne, så det ville virket, men det er en felle å legge igjen for neste leser.
MAPPE = DB.parent / "vedlegg"

# DOI-syntaks per Crossref sin egen anbefalte regex. Sluttmatchen trimmes etterpå:
# PDF-tekst limer ofte DOI-en inntil neste setning eller et linjeskift-artefakt.
_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.IGNORECASE)

# Kun de første sidene. En DOI i referanselista på side 12 er en ANNEN artikkels DOI —
# å plukke den ville festet fulltekst på feil papir, den verste feilen denne modulen kan
# gjøre. Forsidens DOI er dokumentets egen.
_DOI_SIDER = 3


def _mappe() -> Path:
    MAPPE.mkdir(parents=True, exist_ok=True)
    return MAPPE


def fil_sti(doc_id: str) -> Path:
    return _mappe() / f"{doc_id}.pdf"


def finn_doi(tekst: str) -> str | None:
    """Første DOI i teksten, med etterhengt tegnsetting trimmet bort."""
    m = _DOI_RE.search(tekst or "")
    if not m:
        return None
    # «10.1111/jfd.70099.» og «…70099,» er samme DOI som «…70099». Punktum er lovlig
    # INNE i en DOI, så vi kan ikke bare strippe det — kun i enden, der det er
    # setningstegn fra brødteksten rundt.
    return m.group(0).rstrip(".,;:)]}’'\"").lower()


def les_pdf(data: bytes) -> dict:
    """Tekst + sidetall + PDF-ens egen metadata. Kaster ValueError på noe som ikke er PDF.

    Feilende sider hoppes over, de andre beholdes: en enkelt korrupt side i et ellers
    lesbart dokument skal ikke koste hele fulltekten."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
    import io

    try:
        leser = PdfReader(io.BytesIO(data))
        sider = list(leser.pages)
    except (PdfReadError, OSError, ValueError) as e:
        raise ValueError(f"kunne ikke leses som PDF: {e}") from e

    biter = []
    for side in sider:
        try:
            biter.append(side.extract_text() or "")
        except Exception:
            biter.append("")  # se docstring: én dårlig side felle ikke dokumentet
    tekst = "\n\n".join(b.strip() for b in biter if b.strip())

    meta = leser.metadata or {}
    return {
        "tekst": tekst,
        "sider": len(sider),
        "forside": "\n".join(biter[:_DOI_SIDER]),
        # PDF-metadata er notorisk upålitelig (LaTeX-maler legger igjen «untitled»,
        # Word legger igjen forfatterens filnavn). Den brukes KUN som siste utvei for
        # tittel, aldri til å overstyre et papir vi alt har ekte metadata for.
        "meta_tittel": (meta.get("/Title") or "").strip(),
        "meta_forfatter": (meta.get("/Author") or "").strip(),
    }


def _tabell(db: sqlite3.Connection) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS dokumenter(
        id TEXT PRIMARY KEY, paper_id TEXT NOT NULL, filnavn TEXT NOT NULL,
        sider INTEGER, tegn INTEGER, tekst TEXT, opprettet REAL NOT NULL)""")


def _oppslag_papir(doi: str, oppslag_fn) -> PaperDossier | None:
    """Ekte metadata for en DOI vi ikke har cachet, hvis kilden svarer.

    Uten dette ville et papir opprettet fra en PDF båret PDF-metadataens tittel — og den
    tittelen ville deretter sett ut som ekte kildedata for alt nedstrøms (rapporter,
    BibTeX, sitatbanken). Feiler oppslaget, faller vi tilbake på lokal metadata og MERKER
    raden LOKAL, så forskjellen er lesbar i stedet for skjult."""
    if oppslag_fn is None:
        from adapters import europe_pmc
        oppslag_fn = europe_pmc.sok
    try:
        traff = oppslag_fn(f'DOI:"{doi}"', 5)
    except Exception:
        return None  # kilden nede er ikke en grunn til å avvise brukerens egen fil
    for p in traff or []:
        if (p.doi or "").lower() == doi.lower():
            return p
    return None


def lagre(filnavn: str, data: bytes, *, paper_id: str | None = None,
          oppslag_fn=None, embed_fn=None, db_path: Path = DB) -> dict:
    """Tar imot en PDF, knytter den til et papir, returnerer dokumentraden.

    Knytningen i prioritert rekkefølge — først den brukeren selv peker på, så
    dokumentets egen DOI, og bare til slutt en ny lokal identitet:

    1. `paper_id` oppgitt (Ulven trykket «legg ved» på et åpent papir) — han vet best.
    2. DOI funnet på forsiden og ALT cachet → fulltekst fester seg på den raden.
    3. DOI funnet, ikke cachet → slå den opp hos kilden for ekte metadata, cache den.
    4. Ingen DOI → `lokal:<sha256[:16]>`. Innholdets hash, ikke filnavnet: samme PDF
       lastet opp to ganger blir samme dokument, ikke to.
    """
    if not data:
        raise ValueError("tom fil")
    if len(data) > MAKS_BYTES:
        raise ValueError(f"filen er {len(data)//1024//1024} MB — grensen er "
                         f"{MAKS_BYTES//1024//1024} MB")

    lest = les_pdf(data)
    doc_id = hashlib.sha256(data).hexdigest()[:16]

    import bank
    doi = finn_doi(lest["forside"])
    lokal_tittel = lest["meta_tittel"] or Path(filnavn).stem

    if paper_id and bank.hent(paper_id, db_path=db_path):
        knyttet, hvordan = paper_id, "valgt"
    elif doi and bank.hent(doi, db_path=db_path):
        knyttet, hvordan = doi, "doi-i-cache"
    else:
        hentet = _oppslag_papir(doi, oppslag_fn) if doi else None
        if hentet:
            bank.lagre([hentet], embed_fn=embed_fn, db_path=db_path)
            knyttet, hvordan = hentet.id, "doi-slatt-opp"
        else:
            # Ingen ekte metadata finnes. Raden opprettes likevel — uten den kan
            # dokumentet verken siteres eller nås av «Lignende» — men den merkes LOKAL
            # og har tomt abstract, aldri en oppdiktet et. Fulltekstens FØRSTE avsnitt
            # ville vært en fristende «abstract», og det er nøyaktig plassholder-som-
            # verdi-fella README allerede dokumenterer for «Not Available».
            ny = PaperDossier(
                pmid=None, doi=doi, tittel=lokal_tittel, forfattere=lest["meta_forfatter"],
                tidsskrift="", aar=None, abstract="", siteringstall=None,
                open_access=False, kilde_url=f"lokal:{doc_id}", kilde="lokal",
                kilde_kode="LOKAL")
            bank.lagre([ny], embed_fn=embed_fn, db_path=db_path)
            knyttet = ny.id
            hvordan = "lokal-doi" if doi else "lokal"

    fil_sti(doc_id).write_bytes(data)
    db = bank._db(db_path)
    _tabell(db)
    db.execute("""INSERT OR REPLACE INTO dokumenter(id,paper_id,filnavn,sider,tegn,tekst,opprettet)
                  VALUES (?,?,?,?,?,?,?)""",
               (doc_id, knyttet, filnavn, lest["sider"], len(lest["tekst"]),
                lest["tekst"], time.time()))
    db.commit()
    db.close()

    return {"id": doc_id, "paper_id": knyttet, "filnavn": filnavn,
            "sider": lest["sider"], "tegn": len(lest["tekst"]),
            "knyttet_via": hvordan, "doi_funnet": doi,
            # Eksplisitt felt, ikke noe klienten skal utlede av `tegn == 0`. Se
            # modulens docstring: stillhet her er ikke til å skille fra et tomt papir.
            "tekstlag": bool(lest["tekst"])}


def hent(doc_id: str, *, db_path: Path = DB) -> dict | None:
    db = bank_db(db_path)
    rad = db.execute("""SELECT id,paper_id,filnavn,sider,tegn,tekst,opprettet
                        FROM dokumenter WHERE id=?""", (doc_id,)).fetchone()
    db.close()
    if not rad:
        return None
    n = ("id", "paper_id", "filnavn", "sider", "tegn", "tekst", "opprettet")
    return dict(zip(n, rad))


def for_papir(paper_id: str, *, db_path: Path = DB) -> list[dict]:
    """Alle PDF-er knyttet til ett papir — flertall med vilje: supplement, korrigendum
    og hovedartikkel hører til samme verk."""
    db = bank_db(db_path)
    rader = db.execute("""SELECT id,paper_id,filnavn,sider,tegn,opprettet FROM dokumenter
                          WHERE paper_id=? ORDER BY opprettet""", (paper_id,)).fetchall()
    db.close()
    n = ("id", "paper_id", "filnavn", "sider", "tegn", "opprettet")
    return [dict(zip(n, r)) for r in rader]


def liste(*, db_path: Path = DB) -> list[dict]:
    db = bank_db(db_path)
    rader = db.execute("""SELECT d.id,d.paper_id,d.filnavn,d.sider,d.tegn,d.opprettet,p.tittel
                          FROM dokumenter d LEFT JOIN papers p ON p.id=d.paper_id
                          ORDER BY d.opprettet DESC""").fetchall()
    db.close()
    n = ("id", "paper_id", "filnavn", "sider", "tegn", "opprettet", "tittel")
    return [dict(zip(n, r)) for r in rader]


def slett(doc_id: str, *, db_path: Path = DB) -> bool:
    """Fjerner dokumentet. Papirraden og sitatene fra den blir stående med vilje: et
    sitat Ulven har skrevet en kommentar til er HANS arbeid, ikke en avledning av fila.
    Kaster han PDF-en, skal notatene overleve — samme grunn som at sitater overlever et
    slettet utkast."""
    db = bank_db(db_path)
    _tabell(db)
    n = db.execute("DELETE FROM dokumenter WHERE id=?", (doc_id,)).rowcount
    db.commit()
    db.close()
    sti = fil_sti(doc_id)
    if sti.exists():
        sti.unlink()
    return bool(n)


def bank_db(db_path: Path):
    """bank._db + dokument-tabellen. Egen hjelper fordi lesefunksjonene her kan treffe
    en cache.db skrevet før denne modulen fantes — samme idempotente migrasjonsmønster
    som bank.py bruker for sine egne senere kolonner."""
    import bank
    db = bank._db(db_path)
    _tabell(db)
    return db
