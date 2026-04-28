"""
=============================================================
 PPA Archival Survey — Interactive Dashboard Generator
 Works in Google Colab or any Jupyter environment.
 Upload your CSV → generates a standalone HTML dashboard.
=============================================================

COLUMN EXPECTATIONS (matches PPA survey format):
  Col 0  : Survey Number
  Col 1  : Room Location
  Col 2  : Rack Number
  Col 3  : Shelf Number
  Col 4  : Stack / Bundle Number
  Col 5  : Title
  Col 6  : Date  (free text, year extracted via regex)
  Col 7  : Project Name
  Col 8  : Place
  Col 9  : Custodianship
  Col 10 : Format        (Bound / Unbound)
  Col 11 : Covering Material  (Paper / Hardcover / Leather / Missing)
  Col 12 : Media         (Print / MS / Print and MS)
  Col 13 : Dimensions
  Col 14 : Number of Pages
  Col 15 : Fold-outs     (Yes / No)
  Col 16 : Binding Condition    (0-2)
  Col 17 : Weak / Fragile       (0-2)
  Col 18 : Distortion           (0-2)
  Col 19 : Tears / Losses       (0-2)
  Col 20 : Media Obscured       (0-2)
  Col 21 : Handling Difficulty  (0-2)
  Col 22 : Condition Category   (A / B / C)
"""

# ── 1. INSTALL / IMPORTS ─────────────────────────────────────────────────────
import csv
import re
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

# ── 2. FILE UPLOAD (Colab) ───────────────────────────────────────────────────
def upload_csv():
    """Upload a CSV file in Google Colab and return its path."""
    try:
        from google.colab import files
        print("📂  Click 'Choose Files' and select your survey CSV …")
        uploaded = files.upload()
        filename = list(uploaded.keys())[0]
        print(f"✅  Uploaded: {filename}")
        return filename
    except ImportError:
        # Running outside Colab — just provide the path manually
        path = input("Enter path to your CSV file: ").strip()
        return path


# ── 3. PARSE CSV ─────────────────────────────────────────────────────────────
def parse_survey_csv(filepath: str) -> list[dict]:
    """
    Parse the PPA-style archival survey CSV.
    Returns a list of record dicts for every row whose first column is numeric.
    """
    records = []
    with open(filepath, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            if not row[0].strip().isdigit():
                continue  # skip header / blank / label rows

            def safe(col, default=""):
                return row[col].strip() if len(row) > col else default

            def safe_int(col):
                v = safe(col)
                return int(v) if v.isdigit() else None

            records.append({
                "id":           safe(0),
                "room":         safe(1),
                "rack":         safe(2),
                "shelf":        safe(3),
                "stack":        safe(4),
                "title":        safe(5),
                "date_raw":     safe(6),
                "project":      safe(7),
                "place":        safe(8),
                "custody":      safe(9),
                "format":       safe(10),
                "material":     safe(11),
                "media":        safe(12),
                "dimensions":   safe(13),
                "pages":        safe_int(14),
                "foldouts":     safe(15),
                "binding":      safe_int(16),
                "fragile":      safe_int(17),
                "distortion":   safe_int(18),
                "tears":        safe_int(19),
                "obscured":     safe_int(20),
                "handling":     safe_int(21),
                "condition":    safe(22),
            })
    return records


# ── 4. COMPUTE ANALYTICS ─────────────────────────────────────────────────────
def analyse(records: list[dict]) -> dict:
    total = len(records)
    assessed = [r for r in records if r["condition"] in ("A", "B", "C")]

    # --- Places (collapse known variants) ---
    place_map = {"Pune": "Poona", "Ahmednage": "Ahmednagar", "Ahmednager": "Ahmednagar"}
    places = Counter()
    for r in records:
        p = place_map.get(r["place"], r["place"])
        if p:
            places[p] += 1

    # Top 5 + Others
    top_places = places.most_common(5)
    others_count = sum(v for k, v in places.items() if k not in dict(top_places))
    place_labels = [k for k, v in top_places] + (["Others"] if others_count else [])
    place_values = [v for k, v in top_places] + ([others_count] if others_count else [])

    # --- Decades ---
    decade_counter = Counter()
    for r in records:
        years = re.findall(r'\b(1[6-9]\d{2}|20\d{2})\b', r["date_raw"])
        if years:
            decade = (int(years[0]) // 10) * 10
            decade_counter[decade] += 1

    sorted_decades = sorted(decade_counter)
    decade_labels = [f"{d}s" for d in sorted_decades]
    decade_values = [decade_counter[d] for d in sorted_decades]

    # --- Covering material ---
    materials = Counter(r["material"] for r in records if r["material"])
    mat_labels = list(materials.keys())
    mat_values = list(materials.values())

    # --- Media ---
    media_counter = Counter(r["media"] for r in records if r["media"])
    media_labels = list(media_counter.keys())
    media_values = list(media_counter.values())

    # --- Fold-outs ---
    fo = Counter(r["foldouts"] for r in records if r["foldouts"] in ("Yes", "No"))
    fo_yes = fo.get("Yes", 0)
    fo_no  = fo.get("No",  0)

    # --- Condition overall ---
    cond = Counter(r["condition"] for r in assessed)
    cond_a = cond.get("A", 0)
    cond_b = cond.get("B", 0)
    cond_c = cond.get("C", 0)

    # --- Condition by decade ---
    cond_decade = defaultdict(Counter)
    for r in records:
        if r["condition"] not in ("A", "B", "C"):
            continue
        years = re.findall(r'\b(1[6-9]\d{2}|20\d{2})\b', r["date_raw"])
        if years:
            decade = (int(years[0]) // 10) * 10
            cond_decade[decade][r["condition"]] += 1

    cd_decades = sorted(cond_decade)
    cd_labels  = [f"{d}s" for d in cd_decades]
    cd_a = [cond_decade[d].get("A", 0) for d in cd_decades]
    cd_b = [cond_decade[d].get("B", 0) for d in cd_decades]
    cd_c = [cond_decade[d].get("C", 0) for d in cd_decades]

    # --- Damage vectors (avg) ---
    def avg_score(field):
        vals = [r[field] for r in records if r[field] is not None]
        return round(sum(vals) / len(vals), 2) if vals else 0

    damage = {
        "Binding":    avg_score("binding"),
        "Fragile":    avg_score("fragile"),
        "Distortion": avg_score("distortion"),
        "Handling":   avg_score("handling"),
        "Tears":      avg_score("tears"),
        "Obscured":   avg_score("obscured"),
    }

    # --- Pages ---
    pages_list = [r["pages"] for r in records if r["pages"] is not None]
    avg_pages = round(sum(pages_list) / len(pages_list)) if pages_list else 0
    min_pages = min(pages_list) if pages_list else 0
    max_pages = max(pages_list) if pages_list else 0

    # --- Date span ---
    all_years = []
    for r in records:
        yy = re.findall(r'\b(1[6-9]\d{2}|20\d{2})\b', r["date_raw"])
        all_years.extend(map(int, yy))
    year_span = f"{min(all_years)}–{max(all_years)}" if all_years else "N/A"

    return {
        "total":          total,
        "assessed":       len(assessed),
        "year_span":      year_span,
        "avg_pages":      avg_pages,
        "min_pages":      min_pages,
        "max_pages":      max_pages,
        "place_labels":   place_labels,
        "place_values":   place_values,
        "decade_labels":  decade_labels,
        "decade_values":  decade_values,
        "mat_labels":     mat_labels,
        "mat_values":     mat_values,
        "media_labels":   media_labels,
        "media_values":   media_values,
        "fo_yes":         fo_yes,
        "fo_no":          fo_no,
        "cond_a":         cond_a,
        "cond_b":         cond_b,
        "cond_c":         cond_c,
        "cd_labels":      cd_labels,
        "cd_a":           cd_a,
        "cd_b":           cd_b,
        "cd_c":           cd_c,
        "damage":         damage,
    }


# ── 5. BUILD HTML ─────────────────────────────────────────────────────────────
def build_html(d: dict, title: str = "Archival Survey Dashboard") -> str:
    """Render a fully self-contained HTML dashboard from the analytics dict."""

    damage_bars_html = ""
    max_damage = 2.0
    color_map = {
        "Binding":    ("#c0312b", "#fbeaea"),
        "Fragile":    ("#c0312b", "#fbeaea"),
        "Distortion": ("#ba7517", "#fdf3e3"),
        "Handling":   ("#ba7517", "#fdf3e3"),
        "Tears":      ("#5a9e7c", "#e6f3ec"),
        "Obscured":   ("#5a9e7c", "#e6f3ec"),
    }
    for name, score in sorted(d["damage"].items(), key=lambda x: -x[1]):
        pct = round(score / max_damage * 100, 1)
        bar_color, _ = color_map.get(name, ("#888", "#eee"))
        damage_bars_html += f"""
        <div class="risk-bar-wrap">
          <div class="risk-label"><span>{name}</span><span class="risk-score">{score} / 2</span></div>
          <div class="risk-track"><div class="risk-fill" style="width:{pct}%; background:{bar_color};"></div></div>
        </div>"""

    # JSON-encode arrays for Chart.js
    jdl   = json.dumps(d["decade_labels"])
    jdv   = json.dumps(d["decade_values"])
    jpl   = json.dumps(d["place_labels"])
    jpv   = json.dumps(d["place_values"])
    jml   = json.dumps(d["mat_labels"])
    jmv   = json.dumps(d["mat_values"])
    jmedl = json.dumps(d["media_labels"])
    jmedv = json.dumps(d["media_values"])
    jcdl  = json.dumps(d["cd_labels"])
    jcda  = json.dumps(d["cd_a"])
    jcdb  = json.dumps(d["cd_b"])
    jcdc  = json.dumps(d["cd_c"])

    dmg_labels = json.dumps(list(d["damage"].keys()))
    dmg_values = json.dumps(list(d["damage"].values()))

    assessed_pct = round(d["assessed"] / d["total"] * 100) if d["total"] else 0
    b_or_c       = d["cond_b"] + d["cond_c"]
    b_or_c_pct   = round(b_or_c / d["assessed"] * 100) if d["assessed"] else 0
    cond_a_pct   = round(d["cond_a"] / d["assessed"] * 100, 1) if d["assessed"] else 0
    cond_b_pct   = round(d["cond_b"] / d["assessed"] * 100, 1) if d["assessed"] else 0
    cond_c_pct   = round(d["cond_c"] / d["assessed"] * 100, 1) if d["assessed"] else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #f5f4f0;
    color: #1a1a18;
    padding: 2rem;
    line-height: 1.6;
  }}
  h1 {{ font-size: 20px; font-weight: 500; margin-bottom: 4px; }}
  .sub {{ font-size: 13px; color: #666; margin-bottom: 2rem; }}
  .section-label {{
    font-size: 10px; font-weight: 600; letter-spacing: 0.1em;
    text-transform: uppercase; color: #999;
    margin: 2rem 0 0.75rem;
  }}
  .metric-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 1rem; }}
  .metric {{
    background: #fff; border-radius: 10px;
    border: 0.5px solid rgba(0,0,0,0.1);
    padding: 1rem 1.1rem;
  }}
  .metric-label {{ font-size: 11px; color: #888; margin-bottom: 4px; }}
  .metric-value {{ font-size: 24px; font-weight: 500; color: #111; }}
  .metric-sub {{ font-size: 11px; color: #aaa; margin-top: 2px; }}
  .chart-row {{ display: grid; gap: 14px; margin-bottom: 14px; }}
  .chart-row-2 {{ grid-template-columns: 1fr 1fr; }}
  .chart-row-3 {{ grid-template-columns: 2fr 1fr; }}
  .chart-card {{
    background: #fff; border-radius: 12px;
    border: 0.5px solid rgba(0,0,0,0.1);
    padding: 1rem 1.2rem;
  }}
  .chart-title {{ font-size: 13px; font-weight: 500; margin-bottom: 3px; }}
  .chart-sub {{ font-size: 11px; color: #888; margin-bottom: 12px; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 10px; font-size: 11px; color: #555; }}
  .legend-item {{ display: flex; align-items: center; gap: 5px; }}
  .legend-swatch {{ width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }}
  .risk-bar-wrap {{ margin-bottom: 10px; }}
  .risk-label {{ display: flex; justify-content: space-between; font-size: 12px; color: #555; margin-bottom: 4px; }}
  .risk-score {{ font-weight: 500; }}
  .risk-track {{ background: #f0ede8; border-radius: 3px; height: 8px; overflow: hidden; }}
  .risk-fill {{ height: 100%; border-radius: 3px; }}
  .cond-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 8px; }}
  .cond-block {{ border-radius: 8px; padding: 0.7rem; text-align: center; }}
  .cond-letter {{ font-size: 26px; font-weight: 500; }}
  .cond-count {{ font-size: 13px; margin-top: 2px; }}
  .cond-pct {{ font-size: 10px; margin-top: 2px; opacity: 0.8; }}
  .cond-bar-wrap {{ margin-top: 12px; }}
  .cond-bar-label {{ font-size: 11px; color: #888; margin-bottom: 4px; }}
  .cond-bar-track {{ background: #f0ede8; border-radius: 3px; height: 8px; display: flex; overflow: hidden; }}
  .cond-bar-seg {{ height: 100%; }}
  footer {{ margin-top: 2.5rem; font-size: 11px; color: #bbb; text-align: center; }}
  @media (max-width: 700px) {{
    .metric-grid {{ grid-template-columns: 1fr 1fr; }}
    .chart-row-2, .chart-row-3 {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>

<h1>{title}</h1>
<p class="sub">IB Lower Floor collection &mdash; auto-generated from survey CSV</p>

<p class="section-label">Collection summary</p>
<div class="metric-grid">
  <div class="metric">
    <div class="metric-label">Total records</div>
    <div class="metric-value">{d["total"]}</div>
    <div class="metric-sub">Survey items</div>
  </div>
  <div class="metric">
    <div class="metric-label">Fully assessed</div>
    <div class="metric-value">{d["assessed"]}</div>
    <div class="metric-sub">{assessed_pct}% of collection</div>
  </div>
  <div class="metric">
    <div class="metric-label">Date span</div>
    <div class="metric-value" style="font-size:17px;">{d["year_span"]}</div>
    <div class="metric-sub">Years of origin</div>
  </div>
  <div class="metric">
    <div class="metric-label">Avg pages / item</div>
    <div class="metric-value">{d["avg_pages"]}</div>
    <div class="metric-sub">Range {d["min_pages"]}–{d["max_pages"]}</div>
  </div>
</div>

<p class="section-label">Temporal distribution</p>
<div class="chart-card">
  <div class="chart-title">Records by decade of origin</div>
  <div class="chart-sub">Volume peaks and tails reveal collection density and acquisition periods</div>
  <div style="position:relative;width:100%;height:220px;">
    <canvas id="decadeChart" role="img" aria-label="Bar chart of records by decade"></canvas>
  </div>
</div>

<p class="section-label">Geographic &amp; physical breakdown</p>
<div class="chart-row chart-row-2">
  <div class="chart-card">
    <div class="chart-title">Records by place of origin</div>
    <div class="chart-sub">Top locations — administrative provenance distribution</div>
    <div class="legend" id="place-legend"></div>
    <div style="position:relative;width:100%;height:200px;">
      <canvas id="placeChart" role="img" aria-label="Pie chart of place of origin"></canvas>
    </div>
  </div>
  <div class="chart-card">
    <div class="chart-title">Covering material</div>
    <div class="chart-sub">Among fully assessed items</div>
    <div class="legend" id="mat-legend"></div>
    <div style="position:relative;width:100%;height:200px;">
      <canvas id="materialChart" role="img" aria-label="Doughnut chart of covering material"></canvas>
    </div>
  </div>
</div>

<p class="section-label">Condition analysis</p>
<div class="chart-row chart-row-3">
  <div class="chart-card">
    <div class="chart-title">Condition grade by decade</div>
    <div class="chart-sub">A (good) / B (fair) / C (poor) — assessed items only</div>
    <div class="legend">
      <span class="legend-item"><span class="legend-swatch" style="background:#5a9e7c;"></span>A – Good</span>
      <span class="legend-item"><span class="legend-swatch" style="background:#ba7517;"></span>B – Fair</span>
      <span class="legend-item"><span class="legend-swatch" style="background:#c0312b;"></span>C – Poor</span>
    </div>
    <div style="position:relative;width:100%;height:220px;">
      <canvas id="condDecadeChart" role="img" aria-label="Stacked bar chart of condition by decade"></canvas>
    </div>
  </div>
  <div class="chart-card">
    <div class="chart-title">Overall condition split</div>
    <div class="chart-sub">{d["assessed"]} items fully graded</div>
    <div class="cond-grid">
      <div class="cond-block" style="background:#e6f3ec;">
        <div class="cond-letter" style="color:#2a7a4f;">A</div>
        <div class="cond-count" style="color:#2a7a4f;">{d["cond_a"]}</div>
        <div class="cond-pct" style="color:#3d8c60;">{cond_a_pct}%</div>
      </div>
      <div class="cond-block" style="background:#fdf3e3;">
        <div class="cond-letter" style="color:#8a5a00;">B</div>
        <div class="cond-count" style="color:#8a5a00;">{d["cond_b"]}</div>
        <div class="cond-pct" style="color:#a36c00;">{cond_b_pct}%</div>
      </div>
      <div class="cond-block" style="background:#fbeaea;">
        <div class="cond-letter" style="color:#9b2222;">C</div>
        <div class="cond-count" style="color:#9b2222;">{d["cond_c"]}</div>
        <div class="cond-pct" style="color:#b53030;">{cond_c_pct}%</div>
      </div>
    </div>
    <div class="cond-bar-wrap">
      <div class="cond-bar-label">{b_or_c_pct}% require intervention (B or C)</div>
      <div class="cond-bar-track">
        <div class="cond-bar-seg" style="width:{cond_a_pct}%;background:#5a9e7c;border-radius:3px 0 0 3px;"></div>
        <div class="cond-bar-seg" style="width:{cond_b_pct}%;background:#ba7517;"></div>
        <div class="cond-bar-seg" style="width:{cond_c_pct}%;background:#c0312b;border-radius:0 3px 3px 0;"></div>
      </div>
    </div>
  </div>
</div>

<p class="section-label">Damage vector analysis</p>
<div class="chart-row chart-row-2">
  <div class="chart-card">
    <div class="chart-title">Avg score per damage type</div>
    <div class="chart-sub">Scale 0 (none) → 2 (severe)</div>
    <div style="position:relative;width:100%;height:220px;">
      <canvas id="damageRadar" role="img" aria-label="Radar chart of damage dimensions"></canvas>
    </div>
  </div>
  <div class="chart-card">
    <div class="chart-title">Risk priority ranking</div>
    <div class="chart-sub">Sorted by severity — structural issues dominate</div>
    {damage_bars_html}
  </div>
</div>

<p class="section-label">Physical characteristics</p>
<div class="chart-row chart-row-2">
  <div class="chart-card">
    <div class="chart-title">Media type distribution</div>
    <div class="chart-sub">Assessed items with media data</div>
    <div class="legend" id="media-legend"></div>
    <div style="position:relative;width:100%;height:170px;">
      <canvas id="mediaChart" role="img" aria-label="Bar chart of media types"></canvas>
    </div>
  </div>
  <div class="chart-card">
    <div class="chart-title">Fold-outs presence</div>
    <div class="chart-sub">Maps / plans embedded in files</div>
    <div class="legend">
      <span class="legend-item"><span class="legend-swatch" style="background:#3266ad;"></span>With fold-outs ({d["fo_yes"]})</span>
      <span class="legend-item"><span class="legend-swatch" style="background:#d3d1c7;"></span>Without ({d["fo_no"]})</span>
    </div>
    <div style="position:relative;width:100%;height:170px;">
      <canvas id="foldoutChart" role="img" aria-label="Doughnut chart of fold-outs"></canvas>
    </div>
  </div>
</div>

<footer>Generated by Archival Dashboard Generator &mdash; PPA Survey Template &mdash; {d["total"]} records processed</footer>

<script>
const PALETTE = ['#3266ad','#5a9e7c','#d85a30','#ba7517','#7f77dd','#888780','#c0312b','#5a87c5'];
const TEXT_COL = 'rgba(0,0,0,0.45)';
const GRID_COL = 'rgba(0,0,0,0.07)';

function makeLegend(containerId, labels, colors) {{
  const el = document.getElementById(containerId);
  if (!el) return;
  labels.forEach((lbl, i) => {{
    const span = document.createElement('span');
    span.className = 'legend-item';
    span.innerHTML = `<span class="legend-swatch" style="background:${{colors[i % colors.length]}};"></span>${{lbl}}`;
    el.appendChild(span);
  }});
}}

// Decade bar chart
new Chart(document.getElementById('decadeChart'), {{
  type: 'bar',
  data: {{
    labels: {jdl},
    datasets: [{{
      data: {jdv},
      backgroundColor: function(ctx) {{
        const v = ctx.raw;
        if (v >= 100) return '#3266ad';
        if (v >= 50)  return '#5a87c5';
        return '#a0bde0';
      }},
      borderRadius: 3, borderSkipped: false
    }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ color: TEXT_COL, font: {{ size: 10 }}, autoSkip: false, maxRotation: 45 }}, grid: {{ display: false }}, border: {{ display: false }} }},
      y: {{ ticks: {{ color: TEXT_COL, font: {{ size: 10 }} }}, grid: {{ color: GRID_COL }}, border: {{ display: false }} }}
    }}
  }}
}});

// Place pie
const placeLabels = {jpl};
const placeValues = {jpv};
makeLegend('place-legend', placeLabels, PALETTE);
new Chart(document.getElementById('placeChart'), {{
  type: 'pie',
  data: {{
    labels: placeLabels,
    datasets: [{{ data: placeValues, backgroundColor: PALETTE, borderWidth: 2, borderColor: '#fff' }}]
  }},
  options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }} }}
}});

// Material doughnut
const matLabels = {jml};
const matValues = {jmv};
makeLegend('mat-legend', matLabels, PALETTE);
new Chart(document.getElementById('materialChart'), {{
  type: 'doughnut',
  data: {{
    labels: matLabels,
    datasets: [{{ data: matValues, backgroundColor: PALETTE, borderWidth: 2, borderColor: '#fff', cutout: '60%' }}]
  }},
  options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }} }}
}});

// Condition by decade stacked bar
new Chart(document.getElementById('condDecadeChart'), {{
  type: 'bar',
  data: {{
    labels: {jcdl},
    datasets: [
      {{ label: 'A', data: {jcda}, backgroundColor: '#5a9e7c', stack: 's' }},
      {{ label: 'B', data: {jcdb}, backgroundColor: '#ba7517', stack: 's' }},
      {{ label: 'C', data: {jcdc}, backgroundColor: '#c0312b', stack: 's' }}
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ stacked: true, ticks: {{ color: TEXT_COL, font: {{ size: 9 }}, autoSkip: false, maxRotation: 45 }}, grid: {{ display: false }}, border: {{ display: false }} }},
      y: {{ stacked: true, ticks: {{ color: TEXT_COL, font: {{ size: 10 }} }}, grid: {{ color: GRID_COL }}, border: {{ display: false }} }}
    }}
  }}
}});

// Damage radar
new Chart(document.getElementById('damageRadar'), {{
  type: 'radar',
  data: {{
    labels: {dmg_labels},
    datasets: [{{
      data: {dmg_values},
      backgroundColor: 'rgba(192,49,43,0.15)',
      borderColor: '#c0312b', borderWidth: 1.5,
      pointBackgroundColor: '#c0312b', pointRadius: 3
    }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      r: {{
        min: 0, max: 2,
        ticks: {{ stepSize: 0.5, color: TEXT_COL, font: {{ size: 9 }}, backdropColor: 'transparent' }},
        grid: {{ color: GRID_COL }},
        pointLabels: {{ color: TEXT_COL, font: {{ size: 10 }} }},
        angleLines: {{ color: GRID_COL }}
      }}
    }}
  }}
}});

// Media bar
const mediaLabels = {jmedl};
const mediaValues = {jmedv};
makeLegend('media-legend', mediaLabels, PALETTE);
new Chart(document.getElementById('mediaChart'), {{
  type: 'bar',
  data: {{
    labels: mediaLabels,
    datasets: [{{ data: mediaValues, backgroundColor: PALETTE, borderRadius: 3, borderSkipped: false }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ color: TEXT_COL, font: {{ size: 11 }} }}, grid: {{ display: false }}, border: {{ display: false }} }},
      y: {{ ticks: {{ color: TEXT_COL, font: {{ size: 10 }} }}, grid: {{ color: GRID_COL }}, border: {{ display: false }} }}
    }}
  }}
}});

// Fold-outs doughnut
new Chart(document.getElementById('foldoutChart'), {{
  type: 'doughnut',
  data: {{
    labels: ['With fold-outs', 'Without'],
    datasets: [{{ data: [{d["fo_yes"]}, {d["fo_no"]}], backgroundColor: ['#3266ad','#d3d1c7'], borderWidth: 2, borderColor: '#fff', cutout: '65%' }}]
  }},
  options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }} }}
}});
</script>
</body>
</html>"""

    return html


# ── 6. SAVE & DOWNLOAD ────────────────────────────────────────────────────────
def save_and_download(html: str, out_filename: str = "archival_dashboard.html"):
    """Write the HTML to disk and trigger a Colab download."""
    with open(out_filename, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅  Dashboard written to: {out_filename}")

    try:
        from google.colab import files
        files.download(out_filename)
        print("⬇️   Download triggered.")
    except ImportError:
        print(f"   (Not in Colab — open '{out_filename}' directly in your browser)")


# ── 7. MAIN ───────────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  PPA Archival Survey — Dashboard Generator")
    print("=" * 55)

    csv_path = upload_csv()

    print("\n⚙️   Parsing records …")
    records = parse_survey_csv(csv_path)
    print(f"    Found {len(records)} data records.")

    if not records:
        print("❌  No data rows detected. Check your CSV format.")
        return

    print("📊  Computing analytics …")
    data = analyse(records)

    # Use the CSV filename as the dashboard title
    base = Path(csv_path).stem.replace("_", " ").replace("-", " ").title()
    dashboard_title = f"{base} — Archival Survey Dashboard"

    print("🖥️   Building HTML dashboard …")
    html = build_html(data, title=dashboard_title)

    out_name = Path(csv_path).stem + "_dashboard.html"
    save_and_download(html, out_name)
    print("\n✅  Done. Open the HTML file in any browser — no server needed.")


if __name__ == "__main__":
    main()
