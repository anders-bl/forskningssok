"""embed_renhet.py — er cache.db embeddet av ÉN modell? En smal detektor med selvkontroll.

Risikoen `bank.py` dokumenterer: bge-m3 (lokal) og mistral-embed (ai-proxy, prod) er BEGGE
1024-dim, men IKKE samme vektorrom. En `cache.db` som er blandet — noen rader fra den ene
modellen, noen fra den andre — er STILLE korrupt: alle skjema-sjekker passerer (riktig
dimensjon), men semantisk søk returnerer søppel, fordi to vektorer fra ulike rom ikke er
sammenlignbare. Nøyaktig felle-familien der formen er riktig og innholdet er feil modell.

**Selvkontrollen er det som gjør detektoren robust:** samme tekst gjennom samme modell gir
en identisk (deterministisk) vektor, altså avstand ~0. Så vi re-embedder et cachet papirs
egen tekst med DEN NÅVÆRENDE embedderen og måler avstanden til den LAGREDE vektoren:

- avstand ~0  → den lagrede vektoren kom fra den samme modellen vi kjører nå (ren).
- avstand ~1  → den lagrede vektoren kom fra en ANNEN modell (blandet, eller cachen ble
  laget lokalt og kopiert inn i prod — den ene tingen bank.py sier ALDRI gjør).

Kontrollen kan ikke bli falsk-grønn: en detektor som re-embedder feil tekst, eller en
embedder som er nede, gir stor avstand og felles, ikke en stille pass.
"""
import struct

TERSKEL = 0.05  # L2 på (tilnærmet) enhetsvektorer. Identisk modell gir < 0.01 (float-støy);
                # en annen modell gir ~1.4 (ortogonal). 0.05 er godt under gapet, valgt før
                # måling og bekreftet live 2026-09-05 (bge-m3 re-embed-støy målt < 0.001).


def _floats(raa: bytes) -> list[float]:
    """Deserialiser sqlite-vec sin serialize_float32 (rå little-endian float32-blokk)."""
    return list(struct.unpack(f"<{len(raa) // 4}f", raa))


def _l2(a: list[float], b: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def sjekk_renhet(*, embed_fn=None, db_path=None, n: int = 5) -> dict:
    """Re-embedder n cachede papirer og måler avstand til deres lagrede vektor.

    Returnerer {sjekket, maks_avstand, snitt_avstand, ren, avvik}. `ren` er False så snart
    ETT papir avviker over terskelen — én rad fra feil modell er nok til at cachen er
    blandet. `avvik` lister de papirene som avvek, med avstand."""
    import bank
    from paths import DB
    db_path = db_path or DB
    embed_fn = embed_fn or bank._hus_embed()

    db = bank._db(db_path)
    rader = db.execute("""
        SELECT p.rowid, p.tittel, p.abstract, v.embedding
        FROM papers p JOIN paper_vec v ON v.chunk_id = p.rowid
        WHERE p.abstract IS NOT NULL AND p.abstract != ''
        LIMIT ?""", (n,)).fetchall()
    db.close()

    if not rader:
        # Ingen embeddede papirer å sjekke er IKKE «ren» — det er UMÅLT. En tom cache kan
        # ikke bevise at embedderen stemmer (samme «0 er ikke en måling»-linje som ellers).
        return {"sjekket": 0, "maks_avstand": None, "snitt_avstand": None,
                "ren": None, "avvik": []}

    # Samme tekst-format som bank.embed_manglende bruker: "tittel. abstract".
    tekster = [f"{t}. {a}" for _, t, a, _ in rader]
    friske = embed_fn(tekster)

    avvik, avstander = [], []
    for (rowid, tittel, _, raa), frisk in zip(rader, friske):
        d = _l2(_floats(raa), list(frisk))
        avstander.append(d)
        if d > TERSKEL:
            avvik.append({"rowid": rowid, "tittel": (tittel or "")[:60], "avstand": round(d, 4)})

    return {
        "sjekket": len(rader),
        "maks_avstand": round(max(avstander), 4),
        "snitt_avstand": round(sum(avstander) / len(avstander), 4),
        "ren": max(avstander) <= TERSKEL,
        "avvik": avvik,
    }
