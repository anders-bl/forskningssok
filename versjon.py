"""versjon.py — hvilken utgave er dette, og hvilken KODE kjører den faktisk.

To tall, fordi de svarer på to ulike spørsmål:

`VERSJON` er semantisk og settes for hånd. Den sier hva utgaven BETYR — at sitering ble
mulig, at egne PDF-er kom inn — og den er det Anders og Ulven snakker om.

`BYGG` er en hash over kildefilene, beregnet ved import. Den sier hvilken kode som
faktisk kjører, og den er det en feilrapport trenger. **En versjon som bare er semantisk,
lyver**: ingen husker å bumpe den, og «v1.0.0» sitter da på tjue ulike utgaver. Et
bygg-tall ingen kan glemme å oppdatere er det eneste som holder.

Hvorfor ikke git-sha, som ville vært det åpenbare: `.dockerignore` ekskluderer `.git/`,
så et `git rev-parse` i containeren har ingenting å lese. Det ville gitt tom streng i
PRODUKSJON og riktig svar lokalt — verste kombinasjon, siden feilen først viser seg der
den betyr noe. En build-ARG ville fungert, men krever at hver deploy husker å sende den,
og Dokploy-panelet er ikke en fil vi kan lese eller teste. Innholdshashen krever ingen
av delene og er sann i begge miljøer.
"""
import hashlib
from pathlib import Path

VERSJON = "1.0.0"

# Anders, 2026-09-05. Ikke et slagord om produktet — en påminnelse om at ferdig ikke
# finnes, festet til nettopp det tallet som later som det motsatte.
TAGLINE = "Vi er alle en versjon fram til vi dør."

_ROT = Path(__file__).resolve().parent

# Kun det som faktisk kjører. Testene er ikke i imaget (se .dockerignore), så å ta dem med
# ville gitt ulikt byggnummer lokalt og i prod for samme kjørende kode — altså nøyaktig
# den forvirringen tallet finnes for å fjerne.
_FILER = ("*.py", "adapters/*.py", "profiler/*.toml", "frontend/index.html")


def _bygg() -> str:
    try:
        stier = sorted(
            p for m in _FILER for p in _ROT.glob(m)
            if p.is_file() and p.name != "versjon.py")
        h = hashlib.sha256()
        for p in stier:
            # Filnavnet hashes med innholdet: en fil som BYTTER NAVN uten at innholdet
            # endres er en annen utgave, og uten navnet ville de to hashet likt.
            h.update(p.relative_to(_ROT).as_posix().encode())
            h.update(p.read_bytes())
        return h.hexdigest()[:8]
    except OSError:
        # Et byggnummer er diagnostikk. At det ikke kan beregnes skal aldri hindre appen
        # i å starte — da ville sporingsmekanismen tatt ned det den skulle spore.
        return "ukjent"


# versjon.py er utelatt fra hashen over. Ellers ville enhver endring HER — inkludert en
# ren VERSJON-bump — endret byggnummeret uten at en eneste kjørende linje ble annerledes.
BYGG = _bygg()


def info() -> dict:
    return {"versjon": VERSJON, "bygg": BYGG, "tagline": TAGLINE}
