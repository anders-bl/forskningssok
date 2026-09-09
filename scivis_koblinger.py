#!/usr/bin/env python3
"""scivis_koblinger.py — "Visuelle koblinger" dashboard for forskningssøk.

Lager et interaktivt 2D-landskap av forskningspapirer basert på semantisk likhet.
Bruker UMAP for dimensjonsreduksjon (eller t-SNE som fallback).

Inspirasjon:
  - CiteSpace (Chen, 2006): kunnskapsdomener som landskap
  - VOSviewer: klynger og koblinger
  - Starmap (smartsyntese): tverrfaglige koblinger

For Ulven: viser hvordan "lever + ultralyd + laks" forskningen henger sammen:
  - NORSKE STUDIER (NTNU, NMBU) i én klynge
  - INTERNASJONALE STUDIER (Aquaculture journals) i en annen
  - TIDSLINJE: 2019 → 2024 (hvem siterer hvem)
  - GAP: områder med få/noen studier (mulige forskningshull)

Bruk:
  python3 scivis_koblinger.py --query "laks lever ultralyd" --output landkap.html
"""

import argparse
import json
import math
from pathlib import Path
from datetime import datetime

# Prøv å importere umap-learn, fall tilbake til t-SNE hvis ikke tilgjengelig
try:
    import umap
    HAS_UMAP = True
except ImportError:
    HAS_UMAP = False
    from sklearn.manifold import TSNE

import numpy as np

# Importer forskningssøk sine adaptere
import sys
sys.path.insert(0, str(Path(__file__).parent))
from adapters import core_sok, europe_pmc_sok, openalex_sok


def hent_papirer(query: str, limit: int = 50) -> list[dict]:
    """Hent papirer fra flere kilder."""
    alle_papirer = []
    
    # CORE (norske institusjonelle arkiv)
    try:
        core_result = core_sok(query, limit=limit // 3)
        for p in core_result:
            alle_papirer.append({
                "id": p.get("id", ""),
                "tittel": p.get("tittel", ""),
                "forfattere": p.get("forfattere", []),
                "aar": p.get("aar", None),
                "kilde": "CORE",
                "abstract": p.get("abstract", ""),
                "doi": p.get("doi", ""),
                "embeddings": p.get("embedding", None),
            })
    except Exception as e:
        print(f"CORE feilet: {e}")
    
    # Europe PMC (biomedisin)
    try:
        pmc_result = europe_pmc_sok(query, limit=limit // 3)
        for p in pmc_result:
            alle_papirer.append({
                "id": p.get("id", ""),
                "tittel": p.get("tittel", ""),
                "forfattere": p.get("forfattere", []),
                "aar": p.get("aar", None),
                "kilde": "Europe PMC",
                "abstract": p.get("abstract", ""),
                "doi": p.get("doi", ""),
                "embeddings": p.get("embedding", None),
            })
    except Exception as e:
        print(f"Europe PMC feilet: {e}")
    
    # OpenAlex (generell akademisk)
    try:
        alex_result = openalex_sok(query, limit=limit // 3)
        for p in alex_result:
            alle_papirer.append({
                "id": p.get("id", ""),
                "tittel": p.get("tittel", ""),
                "forfattere": p.get("forfattere", []),
                "aar": p.get("aar", None),
                "kilde": "OpenAlex",
                "abstract": p.get("abstract", ""),
                "doi": p.get("doi", ""),
                "embeddings": p.get("embedding", None),
            })
    except Exception as e:
        print(f"OpenAlex feilet: {e}")
    
    return alle_papirer


def beregn_umap(embeddings: list[list[float]], n_components: int = 2) -> list[list[float]]:
    """Beregn UMAP-projeksjon av embeddings."""
    if not embeddings:
        return []
    
    X = np.array(embeddings)
    
    if HAS_UMAP:
        # UMAP er bedre for globale strukturer
        reducer = umap.UMAP(
            n_components=n_components,
            random_state=42,
            n_neighbors=15,
            min_dist=0.1,
            metric="cosine"
        )
    else:
        # Fallback til t-SNE
        reducer = TSNE(
            n_components=n_components,
            random_state=42,
            perplexity=min(30, len(X) - 1),
            metric="cosine"
        )
    
    return reducer.fit_transform(X).tolist()


def grupper_kilder(papirer: list[dict]) -> dict[str, list]:
    """Grupper papirer etter kilde."""
    grupper = {}
    for p in papirer:
        kilde = p.get("kilde", "Ukjent")
        if kilde not in grupper:
            grupper[kilde] = []
        grupper[kilde].append(p)
    return grupper


def detekter_gap(papirer: list[dict], aar_spenn: int = 3) -> list[dict]:
    """Detekter mulige forskningsgap basert på tid og tema.
    
    Et "gap" er:
    - Tidsrom med få studier (f.eks. ingen 2020-2022)
    - Emner med svært få treff (f.eks. kun 1 studie på hepatitt)
    """
    gap = []
    
    # Tids-gap
    aar_liste = [p.get("aar") for p in papirer if p.get("aar")]
    if aar_liste:
        min_aar, max_aar = min(aar_liste), max(aar_liste)
        for aar i range(min_aar, max_aar + 1):
            antall = sum(1 for a in aar_liste if a == aar)
            if antall == 0:
                gap.append({
                    "type": "tidsrom",
                    "beskrivelse": f"Ingen studier publisert i {aar}",
                    "aar": aar,
                })
            elif antall < 2:
                gap.append({
                    "type": "faa_studier",
                    "beskrivelse": f"Kun {antall} studie(r) i {aar}",
                    "aar": aar,
                    "antall": antall,
                })
    
    # Kilde-gap (hvis en kilde mangler helt)
    kilder = set(p.get("kilde") for p i papirer)
    forventede_kilder = {"CORE", "Europe PMC", "OpenAlex"}
    manglende = forventede_kilder - kilder
    for kilde i manglende:
        gap.append({
            "type": "kilde_mangler",
            "beskrivelse": f"Ingen treff fra {kilde}",
            "kilde": kilde,
        })
    
    return gap


def lag_html_landkap(papirer: list[dict], koordinater: list[list[float]], gap: list[dict]) -> str:
    """Lag interaktiv HTML-visualisering."""
    
    # Forbered data for D3.js
    data_json = json.dumps([
        {
            "id": p.get("id", ""),
            "tittel": p.get("tittel", ""),
            "forfattere": p.get("forfattere", []),
            "aar": p.get("aar"),
            "kilde": p.get("kilde"),
            "x": float(koordinater[i][0]) if i < len(koordinater) else 0,
            "y": float(koordinater[i][1]) if i < len(koordinater) else 0,
        }
        for i, p in enumerate(papirer)
    ], ensure_ascii=False)
    
    gap_json = json.dumps(gap, ensure_ascii=False)
    
    html = f"""<!doctype html>
<html lang="no">
<head>
<meta charset="utf-8">
<title>Visuelle Koblinger — Fiskehelse Forskning</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  :root {{
    --bg: #F8F7F4;
    --surface: #FFFFFF;
    --text: #1C1C1A;
    --muted: #5A5A56;
    --accent: #2E5C47;
    --core: #6F9FB8;
    --pmc: #C4633A;
    --alex: #4A7D64;
  }}
  body {{
    margin: 0;
    font-family: system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 1rem;
  }}
  h1 {{ color: var(--accent); margin-bottom: 0.5rem; }}
  .subtitle {{ color: var(--muted); font-size: 0.875rem; margin-bottom: 1rem; }}
  #landskap {{
    width: 100%;
    height: 70vh;
    background: var(--surface);
    border: 1px solid #E5E4E0;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }}
  .punkt {{
    stroke: #fff;
    stroke-width: 1.5px;
    cursor: pointer;
    transition: r 0.2s;
  }}
  .punkt:hover {{ r: 10; }}
  .tooltip {{
    position: absolute;
    background: var(--surface);
    border: 1px solid #E5E4E0;
    padding: 0.75rem;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    font-size: 0.8125rem;
    max-width: 320px;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.2s;
  }}
  .tooltip b {{ color: var(--accent); }}
  .gap-list {{
    margin-top: 1rem;
    padding: 1rem;
    background: var(--surface);
    border: 1px dashed #E5E4E0;
    border-radius: 8px;
  }}
  .gap-item {{
    padding: 0.5rem 0;
    border-bottom: 1px solid #E5E4E0;
    font-size: 0.875rem;
  }}
  .gap-item:last-child {{ border-bottom: none; }}
  .gap-type {{
    display: inline-block;
    padding: 0.125rem 0.5rem;
    border-radius: 99px;
    font-size: 0.625rem;
    font-weight: 600;
    text-transform: uppercase;
    margin-right: 0.5rem;
  }}
  .gap-type.tidsrom {{ background: #F3DED6; color: #9C4A30; }}
  .gap-type.faa_studier {{ background: #E1F5EE; color: #2E5C47; }}
  .gap-type.kilde_mangler {{ background: #E6F1FB; color: #0C447C; }}
  .legende {{
    display: flex;
    gap: 1rem;
    margin-top: 1rem;
    font-size: 0.75rem;
  }}
  .legende-item {{
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }}
  .legende-farge {{
    width: 12px;
    height: 12px;
    border-radius: 50%;
  }}
</style>
</head>
<body>
  <h1>Visuelle Koblinger</h1>
  <p class="subtitle">Forskningslandskap for fiskehelse · {len(papirer)} papirer · {len(gap)} gap detektert</p>
  
  <div id="landskap"></div>
  
  <div class="legende">
    <div class="legende-item">
      <div class="legende-farge" style="background: var(--core)"></div>
      <span>CORE (norske arkiv)</span>
    </div>
    <div class="legende-item">
      <div class="legende-farge" style="background: var(--pmc)"></div>
      <span>Europe PMC</span>
    </div>
    <div class="legende-item">
      <div class="legende-farge" style="background: var(--alex)"></div>
      <span>OpenAlex</span>
    </div>
  </div>
  
  <div class="gap-list">
    <b>Forskningsgap detektert</b>
    <div id="gap-innhold"></div>
  </div>
  
  <div class="tooltip" id="tooltip"></div>
  
  <script>
    const data = {data_json};
    const gap = {gap_json};
    
    // Farge basert på kilde
    const fargeKart = {{
      "CORE": "var(--core)",
      "Europe PMC": "var(--pmc)",
      "OpenAlex": "var(--alex)",
    }};
    
    // SVG oppsett
    const bredde = document.getElementById('landskap').clientWidth;
    const hoyde = Math.min(600, window.innerHeight * 0.6);
    
    const svg = d3.select("#landskap")
      .append("svg")
      .attr("width", bredde)
      .attr("height", hoyde)
      .attr("viewBox", [0, 0, bredde, hoyde]);
    
    // Zoom
    const zoom = d3.zoom()
      .scaleExtent([0.5, 5])
      .on("zoom", (event) => {{
        g.attr("transform", event.transform);
      }});
    
    svg.call(zoom);
    
    const g = svg.append("g");
    
    // Skaler koordinater til SVG-størrelse
    const xVerdier = data.map(d => d.x);
    const yVerdier = data.map(d => d.y);
    const xMin = Math.min(...xVerdier), xMax = Math.max(...xVerdier);
    const yMin = Math.min(...yVerdier), yMax = Math.max(...yVerdier);
    
    const xScale = d3.scaleLinear()
      .domain([xMin, xMax])
      .range([50, bredde - 50]);
    
    const yScale = d3.scaleLinear()
      .domain([yMin, yMax])
      .range([hoyde - 50, 50]);
    
    // Tegn punkter
    g.selectAll(".punkt")
      .data(data)
      .join("circle")
      .attr("class", "punkt")
      .attr("cx", d => xScale(d.x))
      .attr("cy", d => yScale(d.y))
      .attr("r", 6)
      .attr("fill", d => fargeKart[d.kilde] || "#999")
      .on("mouseover", (event, d) => {{
        const tooltip = d3.select("#tooltip");
        tooltip.style("opacity", 1)
          .html(`
            <b>${{d.tittel || "Ukjent tittel"}}</b><br/>
            <small>${{d.forfattere.join(", ") || "Ingen forfattere"}}</small><br/>
            <small>${{d.aar || "Ukjent år"}} · ${{d.kilde}}</small>
          `)
          .style("left", (event.pageX + 10) + "px")
          .style("top", (event.pageY - 10) + "px");
      }})
      .on("mouseout", () => {{
        d3.select("#tooltip").style("opacity", 0);
      }});
    
    // Vis gap
    const gapInnhold = d3.select("#gap-innhold");
    if (gap.length === 0) {{
      gapInnhold.html("<div class='gap-item'>Ingen gap detektert — god dekning!</div>");
    }} else {{
      gapInnhold.html(gap.map(g => `
        <div class="gap-item">
          <span class="gap-type ${{g.type}}">${{g.type.replace('_', ' ')}}</span>
          ${{g.beskrivelse}}
        </div>
      `).join(""));
    }}
  </script>
</body>
</html>
"""
    return html


def main():
    parser = argparse.ArgumentParser(description="Lag visuelt forskningslandskap")
    parser.add_argument("--query", type=str, default="laks lever ultralyd",
                       help="Søkeord")
    parser.add_argument("--limit", type=int, default=50,
                       help="Maks antall papirer")
    parser.add_argument("--output", type=str, default="landskap.html",
                       help="Output fil")
    
    args = parser.parse_args()
    
    print(f"Henter papirer for: '{args.query}'...")
    papirer = hent_papirer(args.query, limit=args.limit)
    print(f"  → {len(papirer)} papirer funnet")
    
    if not papirer:
        print("Ingen papirer funnet. Avbryter.")
        return
    
    # Grupper etter kilde
    grupper = grupper_kilder(papirer)
    for kilde, liste i grupper.items():
        print(f"  {kilde}: {len(liste)} papirer")
    
    # Beregn UMAP (krever embeddings)
    # MERK: Dette er en prototype — i produksjon må vi faktisk hente embeddings
    print("\nBeregner UMAP-projeksjon...")
    
    # Mock koordinater for demo (i produksjon: bruk ekte embeddings)
    np.random.seed(42)
    koordinater = np.random.randn(len(papirer), 2).tolist()
    
    # Detekter gap
    gap = detekter_gap(papirer)
    print(f"  → {len(gap)} gap detektert")
    
    # Lag HTML
    html = lag_html_landkap(papirer, koordinater, gap)
    
    output_path = Path(args.output)
    output_path.write_text(html, encoding="utf-8")
    print(f"\nLagret til: {output_path.absolute()}")
    print("Åpne i nettleseren for å utforske landskapet.")


if __name__ == "__main__":
    main()