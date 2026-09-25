"""art_niva.py — fire-nivå svar på «hva handler dette om», med bevis.

Bygget fordi `domeneprofil.arts_naer_tekst` er en ja/nei-test over ÉN liste der generelle
ord («fish», «aquaculture») står ved siden av selve målarten. Målt 2026-09-25 mot en
håndlest fasit på bank-utdraget: 22 av 32 tittel-treff var falske (sjøpølse, krabbe,
østers ble «artsnære»), og regel 6 i syntese-prompten (påstander om målobjektet bare fra
direkte kilder) ble dermed svakere enn den så ut.

Nivåene, fra nærmest til fjernest målobjektet (navn og lister bor i profilen, `[art.niva]`):
  maal  — målobjektet selv
  naer  — samme fagområde, annen eller uspesifisert art
  annet — organismer utenfor fagområdet (skalldyr, pattedyr, mennesker)
  ingen — ingen av dem nevnt

Samme prinsipp som resten av huset: dette er et SIGNAL som merkes, aldri et filter, og hver
avgjørelse bærer sitt bevis (hvilken kilde og hvilke termer), så en leser kan si «feil»
uten å gjette. MeSH har tre utfall (ikke indeksert er noe annet enn indeksert og ikke
om arten), samme kontrakt som `arts_naer_mesh`.

Ingen fagfelt-ord her: alt kommer fra profilen (`tests/test_domeneprofil_generisk.py`).
"""
import re
from dataclasses import dataclass, field
from functools import lru_cache

import domeneprofil

NIVAER = ("maal", "naer", "annet", "ingen")
# En enkelt omtale av målarten i en tekst om noe annet er ikke «handler om målarten».
MIN_MAAL_I_TEKST = 2
# ...og målartens andel av alle organisme-treff i teksten må være høy nok. En oversikt om
# akvakultur generelt kan nevne laks fire ganger uten å handle om laks.
MIN_MAAL_ANDEL = 0.3


@dataclass(frozen=True)
class ArtFunn:
    niva: str
    kilde: str                      # "mesh" | "tittel" | "tekst" | "mesh-gulv" | "ingen" | "legacy"
    bevis: tuple[str, ...] = ()
    tellinger: dict = field(default_factory=dict)


def _monster(termer: list[str]) -> re.Pattern | None:
    """Korte termer (<5 tegn) må være hele ord («eel», «cod»); lengre matcher ordstart så
    «salmonid» og «trouts» treffer. Aldri substring midt i et ord («cod» i «encoded»)."""
    if not termer:
        return None
    deler = []
    for t in sorted(set(termer), key=len, reverse=True):
        kropp = re.escape(t.lower())
        deler.append(rf"(?<!\w){kropp}(?!\w)" if len(t) < 5 else rf"(?<!\w){kropp}")
    return re.compile("|".join(deler))


@lru_cache(maxsize=8)
def _sett(profil_id: int):
    """Kompilerte mønstre per profil-objekt. Nøkkel = id() slik at en test som bytter
    domeneprofil.PROFIL ikke får tilbake cachede mønstre fra forrige profil."""
    niva = (domeneprofil.PROFIL.get("art") or {}).get("niva")
    if not niva:
        return None
    return {n: _monster(niva.get(n, [])) for n in ("maal", "naer", "annet")}, \
        {m.lower() for m in niva.get("mesh_maal", [])}, {g.lower() for g in niva.get("generisk", [])}


def _tell(monster: re.Pattern | None, tekst: str) -> list[str]:
    return monster.findall(tekst) if monster else []


def _fjern_kollisjoner(tekst: str) -> str:
    t = (tekst or "").lower()
    for frase in domeneprofil.ARTSKOLLISJONER:
        t = t.replace(frase, "")
    return t


def _mesh_liste(mesh) -> list[str] | None:
    if not mesh:
        return None
    termer = mesh.split("|") if isinstance(mesh, str) else list(mesh)
    termer = [t for t in termer if t]
    return termer or None


def klassifiser(tittel: str | None, tekst: str | None = "", mesh=None) -> ArtFunn:
    sett = _sett(id(domeneprofil.PROFIL))
    if sett is None:   # profil uten [art.niva]: gammel ja/nei-oppførsel, tydelig merket
        treff = domeneprofil.arts_naer_tekst(f"{tittel or ''} {tekst or ''}")
        return ArtFunn("maal" if treff else "ingen", "legacy")
    monstre, mesh_maal, generisk = sett

    t_tittel = _fjern_kollisjoner(tittel)
    t_tekst = _fjern_kollisjoner(f"{tittel or ''} {tekst or ''}")
    tit = {n: _tell(monstre[n], t_tittel) for n in ("maal", "naer", "annet")}
    kropp = {n: _tell(monstre[n], t_tekst) for n in ("maal", "naer", "annet")}
    tellinger = {n: len(v) for n, v in kropp.items()}

    mesh_termer = _mesh_liste(mesh)
    if mesh_termer:
        spesifikke = [m for m in mesh_termer if m.lower() in mesh_maal]
        if spesifikke:
            return ArtFunn("maal", "mesh", tuple(spesifikke[:5]), tellinger)

    if tit["maal"]:
        return ArtFunn("maal", "tittel", tuple(dict.fromkeys(tit["maal"]))[:5], tellinger)
    n_tot = len(kropp["maal"]) + len(kropp["naer"]) + len(kropp["annet"])
    if (len(kropp["maal"]) >= MIN_MAAL_I_TEKST and len(kropp["maal"]) >= len(kropp["annet"])
            and len(kropp["maal"]) / n_tot >= MIN_MAAL_ANDEL):
        return ArtFunn("maal", "tekst", tuple(dict.fromkeys(kropp["maal"]))[:5], tellinger)
    spesifikke_naer = [t for t in tit["naer"] if t not in generisk]
    if spesifikke_naer:
        return ArtFunn("naer", "tittel", tuple(dict.fromkeys(spesifikke_naer))[:5], tellinger)
    if tit["annet"]:
        return ArtFunn("annet", "tittel", tuple(dict.fromkeys(tit["annet"]))[:5], tellinger)
    if tit["naer"]:
        return ArtFunn("naer", "tittel", tuple(dict.fromkeys(tit["naer"]))[:5], tellinger)
    n_naer = len(kropp["naer"]) + len(kropp["maal"])
    if n_naer and n_naer >= len(kropp["annet"]):
        return ArtFunn("naer", "tekst", tuple(dict.fromkeys(kropp["naer"] + kropp["maal"]))[:5], tellinger)
    if kropp["annet"]:
        return ArtFunn("annet", "tekst", tuple(dict.fromkeys(kropp["annet"]))[:5], tellinger)
    if mesh_termer and domeneprofil.arts_naer_mesh(mesh_termer):
        return ArtFunn("naer", "mesh-gulv", tuple(mesh_termer[:3]), tellinger)
    return ArtFunn("ingen", "ingen", (), tellinger)
