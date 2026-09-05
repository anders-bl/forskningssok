"""sti.py — korteste vei mellom to vilkårlige papirer i cachen.

Mønsteret er lånt fra **Inciteful sin «Literature Connector»** (idébank #29 §Mønstre verdt
å stjele, punkt 3): gitt to papirer som tilsynelatende ikke har noe med hverandre å gjøre,
vis kjeden som binder dem sammen. Ingen av de fem referansehåndtererne i lag 1 gjør noe i
nærheten — de er arkivskap og vet ikke at to poster handler om det samme.

**Og her skiller vår seg fra Inciteful sin, på en måte som må sies rett ut: deres sti går
langs SITERINGER, vår går langs BETYDNING.** Inciteful svarer «A siterte B som siterte C».
Vi svarer «A ligner B som ligner C» — samme sqlite-vec-graf `lignende()` alt bruker, ny
spørring, ingen ny arkitektur. De to besvarer ulike spørsmål: en siteringssti er en påstand
om hva forfatterne faktisk leste, en semantisk sti er en påstand om hva som handler om det
samme. Å kalle vår for en siteringssti ville vært å låne en autoritet den ikke har.

Vi KAN ikke bygge siteringsvarianten på dagens data uansett: referanselister hentes
on-demand per papir (`citation_gap.py`), aldri lagret som en graf. Det er en ærlig grense,
ikke en mangel som skjules.

**Grafen er en kNN-graf, og det har en konsekvens verdt å kjenne:** hver node har kun sine
`k` nærmeste som kanter. Finnes ingen sti, er svaret «ingen sti innenfor k=…», ikke
«papirene er urelaterte» — en høyere k ville kunne funnet en. Svaret sier derfor alltid
hvilken k som ble brukt.
"""
import heapq
from pathlib import Path

import bank
from paths import DB


def _papir_kort(rad: dict) -> dict:
    return {"id": rad["id"], "tittel": rad["tittel"], "tidsskrift": rad["tidsskrift"],
            "aar": rad["aar"], "doi": rad["doi"], "kilde_url": rad["kilde_url"]}


def finn_sti(fra_id: str, til_id: str, *, k: int = 6, maks_hopp: int = 6,
             db_path: Path = DB) -> dict:
    """Korteste semantiske sti mellom to cachede papirer.

    Dijkstra med embedding-avstand som kantvekt — ikke bredde-først. Færrest hopp og
    korteste vei er ikke det samme: to hopp på 0.95 hver er en svakere forbindelse enn
    tre hopp på 0.3, og det er STYRKEN i kjeden Ulven skal kunne vurdere. Vi rapporterer
    begge tall og lar ham dømme.

    Returnerer alltid en dict — aldri et unntak for «fant ingenting». `sti` er tom med en
    lesbar `grunn`, fordi et tomt resultat her har flere ulike, ikke-utskiftbare årsaker:
    ikke cachet, ingen vektor (papiret manglet abstract), eller genuint ingen vei.
    """
    fra = bank.hent(fra_id, db_path=db_path)
    til = bank.hent(til_id, db_path=db_path)
    if not fra or not til:
        mangler = fra_id if not fra else til_id
        return {"sti": [], "grunn": f"{mangler} er ikke cachet — søk det opp først", "k": k}
    if fra_id == til_id:
        return {"sti": [_papir_kort(fra)], "hopp": 0, "total_avstand": 0.0, "k": k,
                "grunn": "samme papir"}

    # Et papir uten abstract har ingen vektor, og er dermed en isolert node — ikke en node
    # med få naboer. Skilles ut FØR søket, ellers ville svaret blitt «ingen sti funnet» og
    # sett ut som en påstand om avstand der problemet er manglende data.
    for pid, p in ((fra_id, fra), (til_id, til)):
        if not p.get("abstract"):
            return {"sti": [], "k": k,
                    "grunn": f"{pid} har ikke abstract, altså ingen vektor — den er en "
                             f"isolert node i grafen, ikke et papir som ligger langt unna"}

    kø: list[tuple[float, int, str, list[str]]] = [(0.0, 0, fra_id, [fra_id])]
    beste: dict[str, float] = {fra_id: 0.0}
    kanter: dict[tuple[str, str], float] = {}
    besokt = 0

    while kø:
        kost, hopp, node, vei = heapq.heappop(kø)
        if node == til_id:
            papirer = [bank.hent(i, db_path=db_path) for i in vei]
            return {
                "sti": [_papir_kort(p) for p in papirer if p],
                "hopp": len(vei) - 1,
                "total_avstand": round(kost, 4),
                "ledd": [{"fra": vei[i], "til": vei[i + 1],
                          "avstand": round(kanter[(vei[i], vei[i + 1])], 4)}
                         for i in range(len(vei) - 1)],
                "besokt": besokt, "k": k,
            }
        if kost > beste.get(node, float("inf")) or hopp >= maks_hopp:
            continue
        besokt += 1
        # band=False: se bank._naboer_fra_rader. Banding er presentasjon; her trenger vi
        # topologi, og en bånd-sortert kutt-liste er en annen graf.
        for n in bank.lignende(node, k=k, band=False, db_path=db_path):
            ny_kost = kost + n["avstand"]
            kanter[(node, n["id"])] = n["avstand"]
            if ny_kost < beste.get(n["id"], float("inf")):
                beste[n["id"]] = ny_kost
                heapq.heappush(kø, (ny_kost, hopp + 1, n["id"], vei + [n["id"]]))

    return {"sti": [], "besokt": besokt, "k": k,
            "grunn": f"ingen sti innenfor k={k} og {maks_hopp} hopp — en høyere k ville "
                     f"kunne funnet en, så dette er ikke en påstand om at papirene er urelaterte"}
