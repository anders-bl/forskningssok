"""domeneprofil.py — fagfeltet som DATA i en fil, ikke som konstanter i Python.

Historikken i to trinn, fordi bare det andre innløser løftet:

1. **2026-09-02** samlet dette modulen verdiene ETT sted (Svart hatt-funn: `ranking.py`s
   domeneliste og `scoping.py`s akser var hardkodet inline hver for seg). Det gjorde
   profilbytte til én fils jobb — men fila var fortsatt Python, og ni steder i
   `frontend/index.html` sa fortsatt «laks» rett ut. README-ens egen dom sto uendret:
   *«generisk i navn før det er generisk i kode»*.
2. **2026-09-04** flyttet verdiene til `profiler/*.toml` og la UI-tekstene inn i samme
   fil. Ingen Python-modul i repoet bærer nå et fagfelt-spesifikt ord, og flaten leser
   merker, forklaringer og søke-eksempel fra profilen via `/api/profil`.

Verifisert, ikke antatt: `tests/test_domeneprofil_generisk.py` laster en profil fra et
helt annet fagfelt og sjekker at ingen fiske-term lekker gjennom noen av veiene. Det er
den eneste prøven som faktisk kan felle påstanden «domeneagnostisk» — å lese koden og
ikke se ordet «laks» beviser ingenting om hva den GJØR.

Valg av profil: `FORSKNINGSSOK_PROFIL` = enten et navn i `profiler/` («fiskehelse») eller
en absolutt sti til en .toml utenfor repoet. Default er «fiskehelse», altså uendret
oppførsel for Ulven-instansen. Samme env-var-mønster som `paths.py` bruker for DB-stien.

`ranking.py`/`scoping.py` re-eksporterer fortsatt de gamle navnene — kun kilden endret.
"""
import os
import tomllib
from pathlib import Path

PROFILKATALOG = Path(__file__).resolve().parent / "profiler"
STANDARD_PROFIL = "fiskehelse"


def _profilsti() -> Path:
    valgt = os.environ.get("FORSKNINGSSOK_PROFIL", STANDARD_PROFIL)
    sti = Path(valgt)
    # Absolutt sti slipper å ligge i repoet — en konsument kan holde sitt eget fagfelt
    # utenfor, uten en fork. Et bart navn slås opp i profiler/.
    return sti if sti.is_absolute() else PROFILKATALOG / f"{valgt}.toml"


def last_profil(sti: Path | None = None) -> dict:
    """Leser og VALIDERER en profil. En profil som mangler et felt skal feile ved oppstart
    med fagfeltets navn i feilmeldingen — ikke stille gi tomme lister, som ville sett ut
    som «ingen treff i dette fagfeltet» i hver eneste flate og vært umulig å skille fra
    et ærlig tomt søk."""
    sti = sti or _profilsti()
    if not sti.exists():
        raise RuntimeError(
            f"domeneprofil «{sti}» finnes ikke. Sett FORSKNINGSSOK_PROFIL til et navn i "
            f"{PROFILKATALOG} eller en absolutt sti til en .toml-fil.")
    with sti.open("rb") as f:
        p = tomllib.load(f)

    mangler = [n for n in ("navn", "kort", "sok_standard") if not p.get(n)]
    for seksjon, felt in (("domene", ("fagmiljoer", "fagtidsskrifter")), ("art", ("termer",))):
        if seksjon not in p:
            mangler.append(seksjon)
            continue
        mangler += [f"{seksjon}.{k}" for k in felt if not p[seksjon].get(k)]
    if not p.get("akser"):
        mangler.append("akser")
    if mangler:
        raise RuntimeError(f"domeneprofil «{sti}» mangler påkrevde felt: {', '.join(mangler)}")
    return p


PROFIL = last_profil()

NAVN: str = PROFIL["navn"]
FAGMILJOER: tuple[str, ...] = tuple(PROFIL["domene"]["fagmiljoer"])
FAGTIDSSKRIFTER: tuple[str, ...] = tuple(PROFIL["domene"]["fagtidsskrifter"])
ARTSTERMER: tuple[str, ...] = tuple(PROFIL["art"]["termer"])
ARTSKOLLISJONER: tuple[str, ...] = tuple(PROFIL["art"].get("kollisjoner", []))
MESH_TERMER: tuple[str, ...] = tuple(PROFIL["art"].get("mesh_termer", []))
AKSER: dict[str, tuple[str, ...]] = {k: tuple(v) for k, v in PROFIL["akser"].items()}

# Bakoverkompatibelt alias: navnet var fagfelt-spesifikt («NORSKE_») på en konstant som
# ikke er det. Beholdt fordi ranking.py re-eksporterer det og eldre importer finnes.
NORSKE_FAGMILJOER = FAGMILJOER


def domene_naer_tekst(tekst: str) -> bool:
    """Substreng-match mot forfatter-affiliasjon + tidsskriftnavn — se ranking.py:domene_naer
    for hvorfor (forfatter-affiliasjon/tidsskrift, ikke generisk siteringstall)."""
    t = (tekst or "").lower()
    return any(m in t for m in FAGMILJOER + FAGTIDSSKRIFTER)


def arts_naer_tekst(tekst: str) -> bool:
    """Nevner tittel+abstract MÅLOBJEKTET i det hele tatt? Species-trap-funn fra Svart
    hatt-gjennomgangen 2026-09-02, live observert: et bart nøkkelordsøk på
    «nephrocalcinosis» treffer mest human-nyrestein-litteratur (langt større publiserings-
    volum, se README §Tips for domeneavgrensning) — ren embedding-avstand har INGEN
    art-/domenefilter, så et menneske-CYP24A1-funn kan rangere høyt blant fiskepapirer kun
    på tekstlig nærhet. Dette er et FRAVÆR/NÆRVÆR-signal, ikke en klassifikator — et
    papir UTEN treff her blir ALDRI filtrert bort, kun flagget (samme ærlighets-prinsipp:
    et menneske-sammenligningsstudie kan være legitimt relevant, avgjørelsen er brukerens).

    Kollisjonsfrasene fjernes FØR sjekken; hvilke de er, er profilens sak, ikke kodens —
    hvert fagfelt har sine egne homonymer, og det er nettopp den kunnskapen som gjorde
    denne funksjonen fiskespesifikk før profilen ble en datafil."""
    t = (tekst or "").lower()
    for frase in ARTSKOLLISJONER:
        t = t.replace(frase, "")
    return any(m in t for m in ARTSTERMER)


def arts_naer_mesh(mesh: tuple[str, ...] | str | None) -> bool | None:
    """MeSH-basert arts-svar, eller None når papiret ikke er MeSH-indeksert.

    TRE utfall, ikke to — og det er hele poenget: «ikke indeksert» er en annen tilstand
    enn «indeksert og ikke om målarten». Preprints, CORE-treff og tidsskrifter utenfor
    MEDLINE har ingen MeSH i det hele tatt (målt: 41 av 55 cachede papirer), og å svare
    False for dem ville vært å utlede fravær av indeksering til fravær av art."""
    if not mesh:
        return None
    termer = mesh.split("|") if isinstance(mesh, str) else list(mesh)
    termer = [t for t in termer if t]
    if not termer:
        return None
    lav = {t.lower() for t in termer}
    return any(m.lower() in lav for m in MESH_TERMER)


def for_frontend() -> dict:
    """Det flaten trenger for å slutte å hardkode fagfeltet: merker, hva de betyr,
    søke-eksempel og «Om»-teksten. Termlistene sendes IKKE — de er store, brukes bare
    server-side, og en klient som fikk dem ville invitert til å reimplementere
    matchingen i JS med subtilt andre regler."""
    art = PROFIL.get("art", {})
    domene = PROFIL.get("domene", {})
    return {
        "navn": NAVN,
        "kort": PROFIL["kort"],
        "sok_standard": PROFIL["sok_standard"],
        "sok_eksempel": PROFIL.get("sok_eksempel", PROFIL["sok_standard"]),
        "domene_merke": domene.get("merke", "★"),
        "domene_merke_betyr": domene.get("merke_betyr", "domene-nær"),
        "art_merke": art.get("merke", "⚠"),
        "art_merke_betyr": art.get("merke_betyr", "nevner ikke målobjektet"),
        "art_merke_utdypet": art.get("merke_utdypet", ""),
        "akser": list(AKSER),
        "om_domeneprofil": (PROFIL.get("om", {}).get("domeneprofil") or "").strip(),
    }
