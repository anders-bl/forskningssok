#!/usr/bin/env python3
# entrypoint: manuell (Anders), FØR en AVTALT Ulven-demo-økt — aldri launchd RunAtLoad.
#   Kjør: venv/bin/python3 ops/ollama_tunnel.py start|stop|status
"""ops/ollama_tunnel.py — FDR-106 fase 1: start/stopp den utgående SSH reverse-tunnelen
som lar prod-noden nå Anders' Mac sin Ollama for Ulvens syntese-fortelling.

**Bevisst IKKE en launchd-tjeneste (RunAtLoad).** FDR-106 svart hatt #1: Anders' Mac
(base-M5, 24 GB) har MÅLT gjentatte ganger kritisk minnepress ved lokal modellast
alene (konsepter/lokal-ki-hardware) — en stående tunnel som gjør Macen til PROD-backend
uten forvarsel kan kollidere med et helt vanlig øktkveld-arbeidsmønster. Suksesskriterium
`fase1-avtalt-ikke-stende` krever eksplisitt at fase 1 brukes til AVTALTE demo-økter,
ikke stående trafikk. Derfor: et script Anders selv starter/stopper, ikke en daemon som
alltid kjører.

## Mekanisme

Utgående-initiert (`ssh -R`, aldri `-L` eller en inngående port på hjemme-/kontornettet):
Anders' Mac åpner en tilkobling UT til Netcup-noden og ber noden lytte på en lokal port
(127.0.0.1:TUNNEL_PORT_NODE) som videresender til Ollama på Macen (127.0.0.1:11434).
`GatewayPorts no` (noden sin sshd, verifisert 2026-09-20) + `permitlisten` på selve
tunnel-nøkkelen sikrer at den forwardede porten ALDRI er nåbar fra utsiden av noden —
kun prosesser SOM ALLEREDE KJØRER PÅ noden (forskningssok) kan nå den.

Nøkkelen (`~/.ssh/lauvasdata-tunnel/ollama-tunnel-fase1`) er dedikert til akkurat dette,
aldri gjenbrukt: `command=` tvinger et harmløst echo i stedet for skall ved et vanlig
SSH-login-forsøk, `restrict` fjerner all annen kapabilitet (pty/X11/agent-forwarding)
og lar KUN `permitlisten` mot nøyaktig denne porten stå igjen.

## Wiring på node-siden (Anders' hånd, IKKE gjort av dette scriptet)

Selve nøkkelen må legges til `root@159.195.20.82:~/.ssh/authorized_keys` FØR `start`
kan virke — se `linje_for_authorized_keys()` under, som skriver ut den eksakte linja.
Dette scriptet rører ALDRI noden sin `authorized_keys` selv (samme grense som resten av
FDR-106-arbeidet 2026-09-20 — en agent legger ikke til en ny stående nøkkel på et
produksjonssystem uten et menneske som ser linja FØR den lander).

`OLLAMA_TUNNEL_URL=http://127.0.0.1:{TUNNEL_PORT_NODE}` må settes i forskningssok sitt
kjøremiljø på noden FOR den avtalte økten (Dokploy-env, midlertidig — ikke en permanent
env-var, se svart hatt #1 over) for at `syntese_fortelling.kall_llm()` faktisk skal ta
tunnel-veien.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

NODE = "root@159.195.20.82"
NOKKEL = Path.home() / ".ssh" / "lauvasdata-tunnel" / "ollama-tunnel-fase1"
TUNNEL_PORT_NODE = 18711  # verifisert ledig på noden 2026-09-20
OLLAMA_PORT_MAC = 11434
PID_FIL = Path.home() / ".config" / "lauvasdata" / "ollama_tunnel_fase1.pid"


def linje_for_authorized_keys() -> str:
    """Den eksakte linja som må legges til på noden — printet, ALDRI skrevet dit av
    dette scriptet. `command=` gjør et vanlig SSH-login-forsøk med denne nøkkelen
    harmløst (echo, ikke skall) i stedet for å stole på at ingen noensinne prøver —
    dette ALENE er det som hindrer skall, uavhengig av forwarding-innstillingene.

    RETTET 2026-09-20: `restrict,permitlisten="127.0.0.1:{PORT}"` (den opprinnelige,
    "riktige ifølge sshd(8)"-varianten) ga `Warning: remote port forwarding failed`
    + server-siden logget `Server has disabled port forwarding` — verifisert direkte
    mot ekte noden (`ssh -vv`), ikke antatt. Isolerte variabelen: et HELT urestriktert
    nøkkel-forsøk mot SAMME node fungerte (ekte HTTP 200 gjennom tunnelen), så noden
    selv støtter reverse-forwarding fint — feilen sitter i selve `restrict`+
    `permitlisten`-kombinasjonen på denne OpenSSH 9.6-builden, ikke i noden generelt.
    Løsning: dropp `restrict`-snarveien, list de granulære flaggene eksplisitt UTEN
    `no-port-forwarding` (den er nettopp den som kolliderte med permitlisten) og stol
    på `permitlisten` alene til å begrense HVILKEN forwarding som er lov. `command=`
    dekker skall-blokkeringen uavhengig av dette. IKKE fullt så smalt som den
    opprinnelige planen (permitlisten kan i teorien ikke narrowes ned fra "ingen andre
    port-forwarding-typer i det hele tatt" når no-port-forwarding er fraværende — se
    kommentar i selve linja), men fortsatt ingen skall, ingen X11/agent-forwarding, og
    `GatewayPorts no` på noden hindrer uansett at NOE forwardet blir eksternt nåbart."""
    pub = NOKKEL.with_suffix(".pub")
    innhold = pub.read_text().strip()
    felt = innhold.split()
    type_, key = felt[0], felt[1]
    return (
        f'no-pty,no-agent-forwarding,no-X11-forwarding,no-user-rc,'
        f'permitlisten="127.0.0.1:{TUNNEL_PORT_NODE}",'
        f'command="echo lauvasdata-ollama-tunnel-fase1: tunnel-only key, no shell access" '
        f'{type_} {key} lauvasdata-ollama-tunnel-fase1'
    )


def _autossh_kommando() -> list[str]:
    """Ren funksjon — testbar uten å faktisk starte en prosess. `-N`: ingen ekstern
    kommando kjøres over forbindelsen (den er KUN en tunnel). `-o ServerAliveInterval=30
    -o ServerAliveCountMax=3`: oppdag en død forbindelse innen ~90s i stedet for å bli
    hengende stille. `AUTOSSH_GATETIME=0` (env, ikke argv) trengs også — se `start()`."""
    return [
        "autossh", "-M", "0", "-N",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-i", str(NOKKEL),
        "-R", f"127.0.0.1:{TUNNEL_PORT_NODE}:127.0.0.1:{OLLAMA_PORT_MAC}",
        NODE,
    ]


def start() -> int:
    if not NOKKEL.exists():
        print(f"⊘ Tunnel-nøkkelen finnes ikke: {NOKKEL}", file=sys.stderr)
        return 2
    if _kjorer():
        print(f"Tunnelen kjører allerede (PID {_les_pid()}).")
        return 0
    import os
    env = dict(os.environ)
    env["AUTOSSH_GATETIME"] = "0"  # ikke krev 30s oppetid før første restart-forsøk teller
    p = subprocess.Popen(
        _autossh_kommando(), env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    PID_FIL.parent.mkdir(parents=True, exist_ok=True)
    PID_FIL.write_text(str(p.pid))
    print(f"Tunnel startet (PID {p.pid}). Node-side: sett OLLAMA_TUNNEL_URL="
          f"http://127.0.0.1:{TUNNEL_PORT_NODE} i forskningssok sitt miljø for økten.")
    print("Husk å kjøre `stop` når den avtalte økten er ferdig — se FDR-106 svart hatt #1.")
    return 0


def stop() -> int:
    pid = _les_pid()
    if pid is None:
        print("Ingen kjørende tunnel (ingen PID-fil).")
        return 0
    import os
    import signal
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Sendte SIGTERM til PID {pid}.")
    except ProcessLookupError:
        print(f"PID {pid} kjørte ikke lenger (ryddet opp).")
    PID_FIL.unlink(missing_ok=True)
    return 0


def status() -> int:
    if _kjorer():
        print(f"Tunnel KJØRER (PID {_les_pid()}, node-port 127.0.0.1:{TUNNEL_PORT_NODE}).")
        return 0
    print("Tunnel kjører IKKE.")
    return 1


def _les_pid() -> int | None:
    if not PID_FIL.exists():
        return None
    try:
        return int(PID_FIL.read_text().strip())
    except ValueError:
        return None


def _kjorer() -> bool:
    pid = _les_pid()
    if pid is None:
        return False
    import os
    try:
        os.kill(pid, 0)  # signal 0: sjekk eksistens, dreper ingenting
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _positiv_kontroll() -> list[str]:
    feil = []
    kommando = _autossh_kommando()
    if "-N" not in kommando:
        feil.append("D1: -N (ingen ekstern kommando) mangler — tunnelen ville tillatt shell")
    if f"127.0.0.1:{TUNNEL_PORT_NODE}:127.0.0.1:{OLLAMA_PORT_MAC}" not in kommando:
        feil.append("D2: -R skal binde BEGGE sider KUN til 127.0.0.1 (aldri 0.0.0.0) "
                     "— manglende/feil binding ville gjort porten nåbar utenfra noden")
    if str(NOKKEL) not in kommando:
        feil.append("D3: dedikert nøkkel mangler i kommandoen — ville falt tilbake på default")
    return feil


def selvtest() -> bool:
    feil = _positiv_kontroll()
    print(f"{'✓' if not feil else '✗'} autossh-kommando bygget riktig (4 sjekker)")
    for f in feil:
        print(f"  [STOPP] {f}")
    if NOKKEL.exists():
        try:
            print(f"  authorized_keys-linje (kopier denne til noden manuelt):\n"
                  f"    {linje_for_authorized_keys()}")
        except Exception as e:
            feil.append(f"D5: kunne ikke bygge authorized_keys-linja: {e}")
    else:
        print(f"  ⊘ Nøkkel ikke generert ennå ({NOKKEL}) — D5 hoppet over")
    ok = not feil
    print(f"\n{'✓ SELVTEST BESTÅTT' if ok else '[STOPP] SELVTEST FEILET'}")
    return ok


def main() -> int:
    if "--selvtest" in sys.argv:
        return 0 if selvtest() else 1
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("kommando", choices=["start", "stop", "status", "authorized-keys-linje"])
    args = p.parse_args()
    if args.kommando == "authorized-keys-linje":
        print(linje_for_authorized_keys())
        return 0
    return {"start": start, "stop": stop, "status": status}[args.kommando]()


if __name__ == "__main__":
    sys.exit(main())
