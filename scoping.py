"""scoping.py — akse-dekning for Skriv-modus «Omfang»-fanen.

Ulvens forskningsakser (idébank #28: faser/miljøfaktorer/regenerasjon; idébank #30:
lever/ultralyd-validering lagt til). Dette er BEVISST den kjedelige, enkle versjonen —
nøkkelord-tilstedeværelse, ikke en semantisk klassifikator — samme designvalg som
multisok gjorde eksplisitt («tenk kjedelig + enkelt», Anders 2026-07-26): en akse-
dekningsindikator er et scoping-HJELPEMIDDEL, ikke en dom, og trenger ikke mer presisjon
enn det. Terskelen (2+ nøkkelord = full stolpe) er en ukalibrert heuristikk — dokumentert
som det, ikke fremstilt som målt presisjon.

Ærlighets-prinsippet gjelder også her: LAV dekning betyr «du har ikke skrevet/søkt om
dette ennå», ALDRI «forskningen mangler» — samme distinksjon citation_gap.py insisterer på.
"""
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
_FULL_VED_ANTALL = 2  # 2+ distinkte nøkkelord i teksten = full stolpe — ukalibrert, se moduldocstring


def akse_dekning(tekst: str) -> dict[str, float]:
    """tekst → {akse: 0.0-1.0}. Tom/kort tekst gir alle akser 0.0 (ærlig, ikke en feil)."""
    t = (tekst or "").lower()
    ut = {}
    for akse, ord in AKSER.items():
        treff = sum(1 for o in ord if o in t)
        ut[akse] = round(min(1.0, treff / _FULL_VED_ANTALL), 2)
    return ut
