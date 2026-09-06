"""Husstandard: ingen emoji (prosesser/husstandard-ingen-emoji). ASCII der det passer,
egen maskingenerert SVG ellers (Anders 2026-09-06). Denne testen er repoets egen vakt,
siden silverbullet/ops/emoji_lint.py kun ser sitt eget repo.

Hvorfor det betyr noe her spesielt: PDF-motoren (typst) har en emoji-fallback-font, så
et U+26A0-varseltegn i en profil-datafil ble stille til et fargeikon i en kundevendt rapport (sett
2026-09-06). Profilen er data, og data er nettopp det en kode-lint aldri ser.

README.md er bevisst utelatt: den er legacy med markører fra før standarden, migreres
ved berøring (samme regel som lauvasdata-kjernekoden).
"""
import io
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ROT = Path(__file__).resolve().parent.parent

# Emoji-presentasjon + dingbats/diverse symboler (U+2600-27BF) + supplerende. INGEN unntak:
# husstandard-siden og silverbullets emoji_lint unntar hake/kryss (U+2713/2717) og
# stjerne/rombe, men Anders 2026-09-06: «ikke overhodet». Dette repoet bruker ingen av dem.
_EMOJI = re.compile("[\u2600-\u27bf\u2b00-\u2bff\U0001F000-\U0001FAFF\ufe0f]")

FILER = (
    [ROT / "frontend" / "index.html", ROT / "rapport_mal.typ", ROT / "CLAUDE.md"]
    + sorted(ROT.glob("*.py")) + sorted((ROT / "adapters").glob("*.py"))
    + sorted((ROT / "profiler").glob("*.toml")) + sorted((ROT / "tests" / "fixtures").glob("*.toml"))
    + sorted((ROT / "tests").glob("*.py"))
)


@pytest.mark.parametrize("fil", FILER, ids=lambda p: str(p.relative_to(ROT)))
def test_ingen_emoji_i_kilde_eller_profil(fil):
    tekst = fil.read_text(encoding="utf-8")
    treff = [(i + 1, m.group()) for i, l in enumerate(tekst.splitlines()) for m in _EMOJI.finditer(l)]
    assert not treff, f"{fil.relative_to(ROT)}: {treff[:5]}"


def test_detektoren_feller_plantet_tegn_og_godtar_hake():
    """Positiv kontroll: en detektor som er grønn på første kjøring skal mistenkes for
    ikke å måle noe. Varseltrekant (U+26A0), emoji-presentasjon (U+1F600), stjerne
    (U+2605), hake (U+2713) og variasjonsvelger (U+FE0F) skal alle felles; norske
    bokstaver og ASCII-tagger skal ikke."""
    for tegn in (chr(0x26A0), chr(0x1F600), chr(0x2605), chr(0x2713), chr(0x2717), chr(0x2B50), chr(0xFE0F)):
        assert _EMOJI.search("x" + tegn + "y"), hex(ord(tegn))
    for tegn in ("å", "[OBS]", "*", "->"):
        assert not _EMOJI.search("x" + tegn + "y"), tegn


def test_pdf_med_profilmerker_inneholder_ingen_emoji():
    """Skjæringspunktet: profilens merke går inn i rapporten, og typst ville rendret et
    emoji-tegn med fallback-fonten uten å klage. Leses tilbake med pypdf."""
    from pypdf import PdfReader
    import domeneprofil
    from rapport import Blokk, til_pdf_bytes, kildesamling_blokker
    papir = {"id": "1", "tittel": "Kidney stones in humans", "forfattere": "Doe J", "tidsskrift": "Nature",
             "aar": 2024, "abstract": "no target species here", "siteringstall": 0, "open_access": False,
             "kilde_url": "https://example.org/1", "doi": None}
    blokker = kildesamling_blokker([papir], tittel="T")
    tekst = "".join(s.extract_text() for s in PdfReader(io.BytesIO(til_pdf_bytes(blokker, tittel="T"))).pages)
    assert domeneprofil.PROFIL["art"]["merke"] in tekst          # merket er MED, som ASCII
    assert not _EMOJI.search(tekst)


def test_alle_blokktyper_og_tom_tekst_kompilerer():
    from rapport import Blokk, til_pdf_bytes
    blokker = [Blokk(t, "x") for t in ("h1", "h2", "h3", "meta", "p", "sitat", "lenke", "ukjent")]
    blokker += [Blokk("p", ""), Blokk("sitat", None)]  # type: ignore[arg-type]
    assert til_pdf_bytes(blokker, tittel="").startswith(b"%PDF")
