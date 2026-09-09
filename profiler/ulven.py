"""ulven.py — profil for Ulven (Lumic, fiskehelse + ultralyd + lever).

En «profil» er en samling domene-spesifikke synonymer og forhåndslasta søk.
Brukes til å utvide brukerens søk med relevante termer de kanskje ikke tenker på,
og til å tilby «ferdige søk» som starter forskningsprosessen.

Profilen aktiveres når brukeren:
  - skriver «ulven» i søkefeltet (aktivert med en gang)
  - eller velger «Fiskehelse-profil» fra en meny (fremtidig UI)

Mønster: samme som «smartsyntese» sin tverrfaglige utvidelse, men her er det
DOMENE-spesifikke synonymer, ikke disiplin-overskridende.
"""

# Synonymer som utvider brukerens søk automatisk
# Når bruker søker på "lever", søker vi egentlig på:
#   "lever OR hepatic OR hepatitt OR levervev OR hepatocytter"
SYNONYMER = {
    "lever": [
        "hepatic",
        "hepatitt",
        "levervev",
        "hepatocytter",
        "hepatocyte",
        "liver",
    ],
    "ultralyd": [
        "ultrasound",
        "sonografi",
        "echography",
        "ultrasonography",
        "B-mode",
    ],
    "laks": [
        "Salmo salar",
        "oppdrettslaks",
        "atlantic salmon",
        "laksefisk",
        "salmonid",
    ],
    "fiskehelse": [
        "fish health",
        "aquatic pathology",
        "fiskepatologi",
        "fish disease",
        "aquaculture health",
    ],
    "nyre": [
        "renal",
        "kidney",
        "nefrokalsinose",
        "nephrocalcinosis",
        "nyrevev",
    ],
    "ultralyd-bilde": [
        "echogenicity",
        "hyperechoic",
        "hypoechoic",
        "bildekvalitet",
        "image quality",
    ],
}

# Forhåndsdefinerte søk som gir Ulven en god start
FORHAANDSSOK = [
    {
        "navn": "Lever + ultralyd hos laks",
        "query": "laks lever ultralyd",
        "beskrivelse": "Grunnleggende søk for ikke-invasiv levervurdering",
    },
    {
        "navn": "Nefrokalsinose + ultralyd",
        "query": "laks nyre nefrokalsinose ultralyd",
        "beskrivelse": "Oppdager nyrestein tidlig med ultralyd",
    },
    {
        "navn": "Fiskehelse + avbildning",
        "query": "fiskehelse ultralyd avbildning ikke-invasiv",
        "beskrivelse": "Oversikt over ikke-invasive metoder",
    },
    {
        "navn": "Norske studier (gråtekst)",
        "query": "laks lever ultralyd site:ntnu.no OR site:nmbu.no OR site:uit.no",
        "beskrivelse": "Masteroppgaver og PhD-er fra norske institusjoner",
    },
    {
        "navn": "Internasjonale studier",
        "query": "salmon liver ultrasound aquaculture",
        "beskrivelse": "Internasjonal forskning på laksehelse",
    },
]

# Kilder som er spesielt relevante for fiskehelse
PRIORITERTE_KILDER = [
    "Aquaculture",
    "Journal of Fish Diseases",
    "Diseases of Aquatic Organisms",
    "Aquaculture Research",
    "Fish & Shellfish Immunology",
    "Reviews in Aquaculture",
    "NTNU Open",
    "NMBU Åpen",
    "Havforskningsinstituttet",
    "Veterinærinstituttet",
]


def utvid_sok(query: str) -> str:
    """Utvid brukerens søk med domene-spesifikke synonymer.

    Eksempel:
        "laks lever" → "laks OR Salmo salar OR oppdrettslaks lever OR hepatic OR liver"

    Bruker OR mellom synonymer (samme konsept), AND mellom ulike konsepter.
    """
    import re

    # Tokeniser queryen (enkle ord, ikke fraser)
    ord = re.findall(r"\w+", query.lower())

    utvida = []
    for o in ord:
        if o in SYNONYMER:
            # Legg til orig + synonymer med OR
            alternativer = [o] + SYNONYMER[o]
            utvida.append(f"({' OR '.join(alternativer)})")
        else:
            utvida.append(o)

    return " AND ".join(utvida)


def get_profil_info() -> dict:
    """Returnerer profil-metadata for UI-en."""
    return {
        "navn": "Fiskehelse (Ulven/Lumic)",
        "beskrivelse": "Spesialisert på ultralyd av lever og nyre hos oppdrettsfisk",
        "antall_synonymer": len(SYNONYMER),
        "antall_forhandssok": len(FORHAANDSSOK),
        "prioriterte_kilder": PRIORITERTE_KILDER,
    }