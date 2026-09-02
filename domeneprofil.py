"""domeneprofil.py — Ulvens fagfelt (norsk oppdrettslaks-patologi) som DATA, ikke kode.

README har lenge sagt at repoet er «generisk i navn før det er generisk i kode» — dette
er innløsningen av det løftet, ikke en ny idé: `ranking.py`s domene-nærhet-liste og
`scoping.py`s forskningsakser var begge hardkodet inline, flagget som et Svart hatt-funn
i gjennomgangen 2026-09-02. Samlet ETT sted nå — bytter man fagfelt (et annet firma, en
annen fiskesykdom), er DENNE fila det eneste som skal endres, ikke `ranking.py`/
`scoping.py`/`rapport.py` sin logikk.

`ranking.py` og `scoping.py` re-eksporterer fortsatt `domene_naer`/`AKSER` for bakover-
kompatibilitet med eksisterende imports (api.py, cli.py, tester) — kun VERDIENE flyttet.
"""

NORSKE_FAGMILJOER = (
    "havforskningsinstitutt", "veterinærinstitutt", "veterinaerinstitutt",
    "nmbu", "norwegian university of life sciences", "nofima", "pharmaq",
)
FAGTIDSSKRIFTER = (
    "journal of fish diseases", "aquaculture", "diseases of aquatic organisms",
    "journal of fish biology", "fish and shellfish immunology",
)

AKSER: dict[str, tuple[str, ...]] = {
    "Faser": ("stage", "phase", "progression", "fase", "stadium", "utvikling"),
    "Miljøfaktorer": ("co2", "co₂", "hypercapnia", "hyperkapni", "temperature", "temperatur",
                       "salinity", "salinitet", "environment", "miljø", "vannkjemi", "tetthet"),
    "Regenerasjon": ("seawater transfer", "smolt", "sjøsetting", "regenerat", "recovery",
                      "post-smolt", "ferskvann"),
    "Lever": ("liver", "hepat", "lever"),
    "Ultralyd-validering": ("ultrasound", "ultrasonograph", "echograph", "ultralyd",
                             "imaging", "diagnos", "skann"),
}


def domene_naer_tekst(tekst: str) -> bool:
    """Substreng-match mot forfatter-affiliasjon + tidsskriftnavn — se ranking.py:domene_naer
    for hvorfor (forfatter-affiliasjon/tidsskrift, ikke generisk siteringstall)."""
    t = (tekst or "").lower()
    return any(m in t for m in NORSKE_FAGMILJOER + FAGTIDSSKRIFTER)
