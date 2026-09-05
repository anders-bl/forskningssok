"""konformans.py — følger et /health-svar husstandarden? En smal, bærbar validator.

Målt 2026-09-05: husstandarden (`konsepter/helsesjekk` §Responsformat) har spesifisert
`version` og `releaseId` siden juni, og INGEN app i huset sender dem — forskningssøk er
første implementasjon. En standard uten en konformans-sjekk binder ikke (samme «doktrine
binder ikke, mekanisme binder»-linje). Dette er sjekken.

Bevisst bærbar: den validerer et PAYLOAD, ikke et endepunkt, så den kan brukes både som
regresjonsvakt på forskningssøks eget /health OG pekes på en hvilken som helst app i huset.

Semantikken er standardens, ikke vår (og den er lett å bomme på — se
`versjon.py:helsefelt()`):
- `version` = tjenestens PUBLIKE/MAJOR-versjon, altså API-kontrakten. Full semver («1.0.0»)
  her er et AVVIK: det gjør en bakoverkompatibel patch til en synlig kontraktendring.
- `releaseId` = den EKSAKTE utgaven (produktversjon + byggnummer), så den peker på én kode.

Kontrollen er to-armet i testene: en konform payload gir INGEN avvik (positiv), en med
full-semver `version` eller manglende `releaseId` gir avvik (negativ). En validator som
bare kan si «ok» er en no-op-vakt.
"""

GYLDIG_STATUS = {"pass", "warn", "fail"}


def sjekk_detalj(payload: dict) -> list[str]:
    """Avvik fra standarden for DETALJ-varianten (bak X-Internal-Key). Tom liste = konform."""
    avvik = []
    status = payload.get("status")
    if status not in GYLDIG_STATUS:
        avvik.append(f"status «{status}» er ikke pass/warn/fail")

    if "checks" not in payload:
        avvik.append("mangler «checks» (detalj-varianten skal bære komponent-sjekker)")
    elif not isinstance(payload["checks"], dict):
        avvik.append("«checks» er ikke et objekt")

    ver = payload.get("version")
    if ver is None:
        avvik.append("mangler «version»")
    elif "." in str(ver):
        avvik.append(f"«version» = «{ver}» er full semver — standarden vil ha MAJOR alene "
                     f"(API-kontrakten). Byggdetaljen hører i releaseId.")

    rid = payload.get("releaseId")
    if not rid:
        avvik.append("mangler «releaseId» (den eksakte utgaven)")
    elif ver is not None and str(rid) == str(ver):
        avvik.append("«releaseId» er lik «version» — den skal identifisere den EKSAKTE "
                     "utgaven, ikke gjenta major")
    return avvik


def sjekk_offentlig(payload: dict) -> list[str]:
    """Avvik for det OFFENTLIGE svaret (uten nøkkel). Det skal si status og INGENTING mer —
    et endepunkt som stille begynner å lekke tall/versjon er en regresjon ingen merker."""
    avvik = []
    if payload.get("status") not in GYLDIG_STATUS:
        avvik.append(f"status «{payload.get('status')}» er ikke pass/warn/fail")
    ekstra = set(payload) - {"status"}
    if ekstra:
        avvik.append(f"lekker felt utover status: {sorted(ekstra)} — det offentlige svaret "
                     f"skal ikke røpe version/releaseId/checks/tall")
    return avvik
