#!/usr/bin/env python3
"""
Generates the Phase 1 flow diagram: raw indicators -> aggregation ->
module synthesis -> classification (regime/risk) -> 12-action matrix.

Produces a self-contained HTML (inline CSS + SVG, no external
dependencies) at diagram_phase1.html.
"""

import json

# ---------------------------------------------------------------------------
# Data (mirrors config.py and matrix.py from the pipeline 1:1)
# ---------------------------------------------------------------------------

GROUP_COLOR = {
    "production": "#2a78d6",
    "employment": "#1baf7a",
    "consumption": "#eda100",
    "module_b": "#4a3aa7",
}
GROUP_LABEL = {
    "production": "Production",
    "employment": "Employment",
    "consumption": "Consumption",
    "module_b": "Module B — Risk-on / Risk-off",
}

INDICATORS = [
    dict(id="indpro", label="Industrial Production", sub="FRED: INDPRO", group="production",
         note="The most direct proxy for real activity — the 'backbone' series of the CFNAI."),
    dict(id="payrolls", label="Payrolls (Nonfarm)", sub="FRED: PAYEMS", group="employment",
         note="Month-to-month job creation — a strong coincident signal of the cycle."),
    dict(id="unemployment_rate", label="Unemployment Rate", sub="FRED: UNRATE", group="employment",
         note="Inverted level: rising unemployment weighs against the activity score."),
    dict(id="unemployment_claims", label="Unemployment Claims", sub="FRED: ICSA", group="employment",
         note="Weekly — the fastest available employment data, 4-week moving average."),
    dict(id="retail_sales", label="Retail Sales", sub="FRED: RSAFS", group="consumption",
         note="Consumption thermometer, ~70% of US GDP."),
    dict(id="philly_fed", label="Philly Fed", sub="FRED: GACDFSA066MSFRBPHI", group="consumption",
         note="Industrial sentiment diffusion index — leading, not coincident."),
    dict(id="vix", label="VIX", sub="FRED: VIXCLS", group="module_b",
         note="Implied volatility — the stock market's 'fear gauge'. Inverted signal."),
    dict(id="credit_spread", label="Credit Spread", sub="FRED: BAA10Y", group="module_b",
         note="Baa vs. 10y Treasury credit risk premium. Inverted signal."),
    dict(id="jpy_usd", label="Yen / Dollar", sub="FRED: DEXJPUS", group="module_b",
         note="The yen is a safe-haven currency — strengthens in risk-off. Inverted signal."),
    dict(id="treasury_10y", label="10Y Treasury", sub="FRED: DGS10", group="module_b",
         note="Yield rises with risk appetite, falls with flight to quality. Inverted signal."),
    dict(id="aud_jpy", label="AUD / JPY", sub="Yahoo: AUDJPY=X", group="module_b",
         note="Classic FX risk-on/off thermometer (commodity currency vs. safe-haven currency)."),
    dict(id="gold", label="Gold", sub="Yahoo: GC=F", group="module_b",
         note="Store of value in crises — reduced weight (0.5) since it also reacts to inflation."),
]

COL2 = [
    dict(id="cat_production", label="Production", sub="z-score (10-year window)", group="production"),
    dict(id="cat_employment", label="Employment", sub="average z-score of 3 indicators", group="employment"),
    dict(id="cat_consumption", label="Consumption", sub="average z-score of 2 indicators", group="consumption"),
    dict(id="composite_risk_score", label="Risk Score", sub="weighted composite (6 indicators)", group="module_b"),
]

COL3 = [
    dict(id="level_momentum_score", label="Level + Momentum Score", sub="average of 3 categories · 3M MA · Δ3m",
         color="#5b5b5b", srcs=["production", "employment", "consumption"]),
    dict(id="filtered_risk_score", label="Filtered Risk Score", sub="discretization (-2 to +2) + persistence filter",
         color="#4a3aa7", srcs=["module_b"]),
]

REGIMES = [
    dict(id="expansion", label="Expansion", color="#70AD47"),
    dict(id="recovery", label="Recovery", color="#4472C4"),
    dict(id="slowdown", label="Slowdown", color="#ED7D31"),
    dict(id="contraction", label="Contraction", color="#C00000"),
]
RISKS = [
    dict(id="riskon", label="Risk-on", color="#70AD47"),
    dict(id="neutral", label="Neutral", color="#9c9c9c"),
    dict(id="riskoff", label="Risk-off", color="#C00000"),
]

# Mirrors matrix.py::ACTION_MATRIX
ACTION_MATRIX = {
    ("expansion", "riskon"): "Increase exposure to cyclicals / high beta",
    ("expansion", "neutral"): "Maintain target exposure",
    ("expansion", "riskoff"): "Temporary risk-off → hold position, treat as noise",
    ("recovery", "riskon"): "Increase exposure gradually, start rotating into cyclicals",
    ("recovery", "neutral"): "Neutral stance, wait for confirmation",
    ("recovery", "riskoff"): "Caution — may be a false recovery; reduce position size",
    ("slowdown", "riskon"): "Reduce gradually, rotate into quality/defensives",
    ("slowdown", "neutral"): "Reduce target exposure",
    ("slowdown", "riskoff"): "Cut risk decisively",
    ("contraction", "riskon"): 'Alert — possible "bear market rally"; don\'t trust the tactical signal alone',
    ("contraction", "neutral"): "Cut risk decisively",
    ("contraction", "riskoff"): "Cut risk decisively (the framework's most defensive stance)",
}

# Action groups with identical text -> same "badge" (letter) in the corner
# of the cell, to make it visually obvious when two different combinations
# lead to the same recommendation.
ACTION_BADGE = {}
_badge_by_text = {}
_next_letter = ord("A")
for key, text in ACTION_MATRIX.items():
    if text not in _badge_by_text:
        _badge_by_text[text] = chr(_next_letter)
        _next_letter += 1
    ACTION_BADGE[key] = _badge_by_text[text]
# only show the badge when the text repeats in more than 1 cell
_text_count = {}
for text in ACTION_MATRIX.values():
    _text_count[text] = _text_count.get(text, 0) + 1
for key, text in ACTION_MATRIX.items():
    if _text_count[text] < 2:
        ACTION_BADGE[key] = None

print(json.dumps({"indicators": len(INDICATORS), "col2": len(COL2)}, indent=2))

# ---------------------------------------------------------------------------
# Layout — all coordinates in pixels, computed from the constants below
# (tweaking a constant automatically flows through the entire layout, no
# need to recompute anything by hand).
# ---------------------------------------------------------------------------

MARGIN_TOP = 46
NODE_H1 = 40          # height of each indicator (column 1)
GAP1 = 9              # spacing between indicators of the same group
GROUP_HEADER_H = 24
GROUP_GAP = 20         # extra spacing between groups

COL1_X, COL1_W = 26, 216
COL2_X, COL2_W = 306, 200
COL3_X, COL3_W = 566, 232
COL4_X, COL4_W = 862, 160
MATRIX_X = 1096
MATRIX_ROW_LABEL_W = 118
MATRIX_COL_W = 172
MATRIX_HEADER_H = 64
MATRIX_ROW_H = 92
MATRIX_ROW_GAP = 10

NODE_H2 = 56
NODE_H3 = 78
NODE_H4 = 46
GAP4 = 16

# --- Column 1: grouped indicators -------------------------------------------
groups_order = ["production", "employment", "consumption", "module_b"]
col1_nodes = {}   # id -> dict with x,y,w,h
col1_group_bounds = {}  # group -> (top, bottom) of the NODES (without the header)
y = MARGIN_TOP
for g in groups_order:
    header_top = y
    y += GROUP_HEADER_H
    members = [i for i in INDICATORS if i["group"] == g]
    group_top = y
    for idx, ind in enumerate(members):
        col1_nodes[ind["id"]] = dict(x=COL1_X, y=y, w=COL1_W, h=NODE_H1, data=ind)
        y += NODE_H1
        if idx < len(members) - 1:
            y += GAP1
    group_bottom = y
    col1_group_bounds[g] = (group_top, group_bottom, header_top)
    y += GROUP_GAP
COL1_BOTTOM = y - GROUP_GAP

# --- Column 2: aggregation by category (centered on the source cluster) ----
col2_nodes = {}
for node in COL2:
    top, bottom, _ = col1_group_bounds[node["group"]]
    center = (top + bottom) / 2
    ny = center - NODE_H2 / 2
    col2_nodes[node["id"]] = dict(x=COL2_X, y=ny, w=COL2_W, h=NODE_H2, data=node,
                                   color=GROUP_COLOR[node["group"]])

# --- Column 3: module synthesis ---------------------------------------------
col3_nodes = {}
for node in COL3:
    centers = []
    for src in node["srcs"]:
        matches = [c for c in col2_nodes.values() if c["data"]["group"] == src]
        for m in matches:
            centers.append(m["y"] + m["h"] / 2)
    center = sum(centers) / len(centers)
    ny = center - NODE_H3 / 2
    col3_nodes[node["id"]] = dict(x=COL3_X, y=ny, w=COL3_W, h=NODE_H3, data=node, color=node["color"])

# --- Column 4: classification (regime + risk) -------------------------------
def stack_centered(items, x, w, h, gap, center):
    total = len(items) * h + (len(items) - 1) * gap
    top = center - total / 2
    out = {}
    yy = top
    for it in items:
        out[it["id"]] = dict(x=x, y=yy, w=w, h=h, data=it, color=it["color"])
        yy += h + gap
    return out

regime_center = col3_nodes["level_momentum_score"]["y"] + col3_nodes["level_momentum_score"]["h"] / 2
risk_center = col3_nodes["filtered_risk_score"]["y"] + col3_nodes["filtered_risk_score"]["h"] / 2

regime_nodes = stack_centered(REGIMES, COL4_X, COL4_W, NODE_H4, GAP4, regime_center)
risk_nodes = stack_centered(RISKS, COL4_X, COL4_W, NODE_H4, GAP4, risk_center)
col4_nodes = {**regime_nodes, **risk_nodes}

# --- Column 5: 4x3 matrix ----------------------------------------------------
# The top of the matrix needs to leave room, above it, for the column
# header (MATRIX_HEADER_H) + the column's own "Recommended action" title
# + a margin — otherwise the two visually overlap (that's exactly what
# happened in the first version: the matrix's colored header covered the
# column title, because regime_center ended up too close to the top).
MATRIX_TOP_MIN = MARGIN_TOP + 28 + MATRIX_HEADER_H
matrix_top = max(
    regime_center - (4 * MATRIX_ROW_H + 3 * MATRIX_ROW_GAP) / 2,
    MATRIX_TOP_MIN,
)
matrix_rows_y = {}
yy = matrix_top
for r in REGIMES:
    matrix_rows_y[r["id"]] = yy
    yy += MATRIX_ROW_H + MATRIX_ROW_GAP
matrix_grid_x = MATRIX_X + MATRIX_ROW_LABEL_W
matrix_cols_x = {}
xx = matrix_grid_x
for rc in RISKS:
    matrix_cols_x[rc["id"]] = xx
    xx += MATRIX_COL_W

MATRIX_RIGHT = matrix_grid_x + 3 * MATRIX_COL_W
MATRIX_BOTTOM = matrix_top + 4 * MATRIX_ROW_H + 3 * MATRIX_ROW_GAP

CANVAS_W = MATRIX_RIGHT + 40
CANVAS_H = max(COL1_BOTTOM, MATRIX_BOTTOM, risk_nodes[RISKS[-1]["id"]]["y"] + NODE_H4) + 50

print("layout ok", CANVAS_W, CANVAS_H)

# ---------------------------------------------------------------------------
# Curves (SVG bezier) between nodes
# ---------------------------------------------------------------------------

def bezier_hh(x1, y1, x2, y2):
    """Horizontal->horizontal curve: leaves straight from the origin's
    right side, arrives straight at the destination's left side. This is
    the classic flow-diagram (Sankey) stroke — works well even with a
    large vertical difference between origin and destination."""
    dx = max(abs(x2 - x1) * 0.5, 30)
    return f"M {x1:.1f} {y1:.1f} C {x1+dx:.1f} {y1:.1f}, {x2-dx:.1f} {y2:.1f}, {x2:.1f} {y2:.1f}"


def bezier_hv(x1, y1, x2, y2):
    """Horizontal->vertical curve: leaves straight from the origin's right
    side, but arrives at the destination going from BOTTOM to TOP (used
    for the risk nodes, which need to 'climb' to the top of the matrix
    columns)."""
    dx = max(abs(x2 - x1) * 0.55, 40)
    dy = max(abs(y2 - y1) * 0.5, 30)
    return f"M {x1:.1f} {y1:.1f} C {x1+dx:.1f} {y1:.1f}, {x2:.1f} {y2-dy:.1f}, {x2:.1f} {y2:.1f}"


def right_mid(n):
    return (n["x"] + n["w"], n["y"] + n["h"] / 2)


def left_mid(n):
    return (n["x"], n["y"] + n["h"] / 2)


edges_svg = []

def add_edge(p1, p2, color, mode="hh", width=1.6, opacity=0.55):
    x1, y1 = p1
    x2, y2 = p2
    path = bezier_hh(x1, y1, x2, y2) if mode == "hh" else bezier_hv(x1, y1, x2, y2)
    edges_svg.append(f'<path d="{path}" stroke="{color}" stroke-width="{width}" '
                      f'fill="none" opacity="{opacity}"/>')

# indicator -> category/composite (column 1 -> column 2)
for ind in INDICATORS:
    src = col1_nodes[ind["id"]]
    dst = [c for c in col2_nodes.values() if c["data"]["group"] == ind["group"]][0]
    add_edge(right_mid(src), left_mid(dst), GROUP_COLOR[ind["group"]], width=1.2, opacity=0.38)

# category/composite -> module synthesis (column 2 -> column 3)
for c2 in col2_nodes.values():
    dst = [c for c in col3_nodes.values() if c2["data"]["group"] in c["data"]["srcs"]][0]
    add_edge(right_mid(c2), left_mid(dst), c2["color"], width=2, opacity=0.55)

# synthesis -> regime / risk (column 3 -> column 4)
for rid in [r["id"] for r in REGIMES]:
    add_edge(right_mid(col3_nodes["level_momentum_score"]), left_mid(col4_nodes[rid]),
              col4_nodes[rid]["color"], width=2, opacity=0.5)
for rid in [r["id"] for r in RISKS]:
    add_edge(right_mid(col3_nodes["filtered_risk_score"]), left_mid(col4_nodes[rid]),
              col4_nodes[rid]["color"], width=2, opacity=0.5)

# regime -> matrix row (column 4 -> matrix, enters from the left)
for r in REGIMES:
    node = col4_nodes[r["id"]]
    target = (MATRIX_X, matrix_rows_y[r["id"]] + MATRIX_ROW_H / 2)
    add_edge(right_mid(node), target, r["color"], mode="hh", width=2.4, opacity=0.6)

# risk -> matrix column (column 4 -> matrix, enters from the top)
for rc in RISKS:
    node = col4_nodes[rc["id"]]
    target = (matrix_cols_x[rc["id"]] + MATRIX_COL_W / 2, matrix_top)
    add_edge(right_mid(node), target, rc["color"], mode="hv", width=2.4, opacity=0.6)

print("edges:", len(edges_svg))

# ---------------------------------------------------------------------------
# HTML — nodes (positioned divs) + column labels + legend
# ---------------------------------------------------------------------------

def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


html_parts = []

# --- column 1: indicators + group headers ---
for g in groups_order:
    top, bottom, header_top = col1_group_bounds[g]
    html_parts.append(
        f'<div class="group-header" style="left:{COL1_X}px; top:{header_top}px; width:{COL1_W}px;">'
        f'<span class="swatch" style="background:{GROUP_COLOR[g]}"></span>{esc(GROUP_LABEL[g])}</div>'
    )
for ind in INDICATORS:
    n = col1_nodes[ind["id"]]
    color = GROUP_COLOR[ind["group"]]
    html_parts.append(
        f'<div class="node node-ind" style="left:{n["x"]}px; top:{n["y"]}px; width:{n["w"]}px; '
        f'height:{n["h"]}px; border-left-color:{color};">'
        f'<div class="node-label">{esc(ind["label"])}</div>'
        f'<div class="node-sub">{esc(ind["sub"])}</div>'
        f'<div class="tooltip">{esc(ind["note"])}</div>'
        f'</div>'
    )

# --- column 2 ---
for c2 in col2_nodes.values():
    n = c2
    html_parts.append(
        f'<div class="node node-agg" style="left:{n["x"]}px; top:{n["y"]}px; width:{n["w"]}px; '
        f'height:{n["h"]}px; border-left-color:{n["color"]};">'
        f'<div class="node-label">{esc(n["data"]["label"])}</div>'
        f'<div class="node-sub">{esc(n["data"]["sub"])}</div>'
        f'</div>'
    )

# --- column 3 ---
for n in col3_nodes.values():
    html_parts.append(
        f'<div class="node node-synth" style="left:{n["x"]}px; top:{n["y"]}px; width:{n["w"]}px; '
        f'height:{n["h"]}px; border-left-color:{n["color"]};">'
        f'<div class="node-label">{esc(n["data"]["label"])}</div>'
        f'<div class="node-sub">{esc(n["data"]["sub"])}</div>'
        f'</div>'
    )

# --- column 4 (regime + risk) ---
for n in col4_nodes.values():
    html_parts.append(
        f'<div class="node node-class" style="left:{n["x"]}px; top:{n["y"]}px; width:{n["w"]}px; '
        f'height:{n["h"]}px; background:{n["color"]};">'
        f'<div class="node-label node-label-white">{esc(n["data"]["label"])}</div>'
        f'</div>'
    )

# --- column labels (general headers at the top of the canvas) ---
col_titles = [
    (COL1_X, COL1_W, "Raw indicators"),
    (COL2_X, COL2_W, "Category aggregation"),
    (COL3_X, COL3_W, "Module synthesis"),
    (COL4_X, COL4_W, "Classification"),
    (MATRIX_X, MATRIX_RIGHT - MATRIX_X, "Recommended action (4×3 matrix)"),
]
for x, w, title in col_titles:
    html_parts.append(f'<div class="col-title" style="left:{x}px; top:8px; width:{w}px;">{esc(title)}</div>')

# --- matrix: column headers (risk) ---
for rc in RISKS:
    x = matrix_cols_x[rc["id"]]
    html_parts.append(
        f'<div class="matrix-col-header" style="left:{x}px; top:{matrix_top - MATRIX_HEADER_H}px; '
        f'width:{MATRIX_COL_W - 8}px; height:{MATRIX_HEADER_H - 8}px; background:{rc["color"]};">'
        f'{esc(rc["label"])}</div>'
    )

# --- matrix: row labels (regime) ---
for r in REGIMES:
    y = matrix_rows_y[r["id"]]
    html_parts.append(
        f'<div class="matrix-row-header" style="left:{MATRIX_X}px; top:{y}px; '
        f'width:{MATRIX_ROW_LABEL_W - 10}px; height:{MATRIX_ROW_H - 8}px; border-left-color:{r["color"]};">'
        f'{esc(r["label"])}</div>'
    )

# --- matrix: 12 cells ---
for r in REGIMES:
    for rc in RISKS:
        key = (r["id"], rc["id"])
        text = ACTION_MATRIX[key]
        badge = ACTION_BADGE[key]
        x = matrix_cols_x[rc["id"]]
        y = matrix_rows_y[r["id"]]
        badge_html = f'<span class="badge">{badge}</span>' if badge else ""
        html_parts.append(
            f'<div class="matrix-cell" style="left:{x}px; top:{y}px; width:{MATRIX_COL_W - 8}px; '
            f'height:{MATRIX_ROW_H - 8}px; border-top-color:{rc["color"]}; border-left-color:{r["color"]};">'
            f'{badge_html}<div class="cell-text">{esc(text)}</div></div>'
        )

nodes_html = "\n".join(html_parts)
edges_html = "\n".join(edges_svg)

# ---------------------------------------------------------------------------
# Footnote (repeated badges)
# ---------------------------------------------------------------------------
badge_notes = {}
for key, badge in ACTION_BADGE.items():
    if badge:
        badge_notes.setdefault(badge, ACTION_MATRIX[key])
badge_legend = " &nbsp;·&nbsp; ".join(
    f'<span class="badge">{b}</span> {esc(t)}' for b, t in sorted(badge_notes.items())
)

print("html assembled, nodes:", len(html_parts))

# ---------------------------------------------------------------------------
# Final document
# ---------------------------------------------------------------------------

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Phase 1 — From indicator to action: pipeline map</title>
<style>
  :root {{
    --surface-1: #fcfcfb;
    --page: #f4f3f0;
    --text-primary: #0b0b0b;
    --text-secondary: #52514e;
    --muted: #898781;
    --border: rgba(11,11,11,0.12);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 28px;
    background: var(--page);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    color: var(--text-primary);
  }}
  h1 {{
    font-size: 21px;
    margin: 0 0 4px 0;
  }}
  .subtitle {{
    color: var(--text-secondary);
    font-size: 13.5px;
    margin: 0 0 20px 0;
    max-width: 900px;
    line-height: 1.5;
  }}
  .canvas-wrap {{
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: auto;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }}
  .canvas {{
    position: relative;
    width: {CANVAS_W}px;
    height: {CANVAS_H}px;
  }}
  svg.edges {{
    position: absolute; left: 0; top: 0;
    width: {CANVAS_W}px; height: {CANVAS_H}px;
    pointer-events: none;
  }}
  .col-title {{
    position: absolute;
    font-size: 11.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--muted);
  }}
  .group-header {{
    position: absolute;
    font-size: 12px;
    font-weight: 700;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    height: 20px;
  }}
  .swatch {{
    display: inline-block;
    width: 9px; height: 9px;
    border-radius: 2px;
    margin-right: 6px;
  }}
  .node {{
    position: absolute;
    background: #ffffff;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 5px 9px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    display: flex;
    flex-direction: column;
    justify-content: center;
    overflow: hidden;
  }}
  .node-ind {{ border-left-width: 4px; cursor: default; overflow: visible; }}
  .node-agg {{ border-left-width: 5px; }}
  .node-synth {{ border-left-width: 5px; background: #fbfbfa; }}
  .node-class {{ border: none; border-radius: 6px; justify-content: center; align-items: center; }}
  .node-label {{
    font-size: 12px;
    font-weight: 600;
    line-height: 1.25;
  }}
  .node-label-white {{ color: #fff; font-size: 13px; text-align: center; }}
  .node-sub {{
    font-size: 10.5px;
    color: var(--text-secondary);
    margin-top: 2px;
    line-height: 1.2;
  }}
  .node-ind .tooltip {{
    display: none;
    position: absolute;
    left: 0;
    top: 100%;
    margin-top: 6px;
    width: 240px;
    background: #202020;
    color: #fff;
    font-size: 11.5px;
    line-height: 1.4;
    padding: 8px 10px;
    border-radius: 6px;
    z-index: 20;
    box-shadow: 0 4px 14px rgba(0,0,0,0.25);
    pointer-events: none;
  }}
  .node-ind:hover {{
    border-color: #b8b6ad;
    box-shadow: 0 2px 6px rgba(0,0,0,0.12);
    z-index: 10;
  }}
  .node-ind:hover .tooltip {{ display: block; }}
  .matrix-col-header {{
    position: absolute;
    border-radius: 6px;
    color: #fff;
    font-size: 12px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
  }}
  .matrix-row-header {{
    position: absolute;
    display: flex;
    align-items: center;
    font-size: 12.5px;
    font-weight: 700;
    border-left: 5px solid;
    padding-left: 8px;
    color: var(--text-primary);
  }}
  .matrix-cell {{
    position: absolute;
    background: #ffffff;
    border: 1px solid var(--border);
    border-top-width: 4px;
    border-left-width: 4px;
    border-radius: 6px;
    padding: 8px 9px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  }}
  .cell-text {{
    font-size: 11.5px;
    line-height: 1.35;
    color: var(--text-primary);
  }}
  .badge {{
    display: inline-block;
    float: right;
    width: 16px; height: 16px;
    border-radius: 50%;
    background: var(--muted);
    color: #fff;
    font-size: 10px;
    font-weight: 700;
    text-align: center;
    line-height: 16px;
    margin-left: 6px;
  }}
  .footnote {{
    margin-top: 14px;
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.6;
  }}
  .footnote .badge {{ float: none; margin-right: 4px; }}
</style>
</head>
<body>
  <h1>Phase 1 — From indicator to action: full pipeline map</h1>
  <p class="subtitle">
    The 12 raw indicators (left) feed Module A (economic cycle nowcasting)
    and Module B (market risk). Each module synthesizes its indicators into
    a single score, which is classified into a category — regime (Module A)
    or risk level (Module B). Crossing the two classifications defines the
    recommended action, in the 4×3 matrix on the right. Hover over an
    indicator to see why it was chosen.
  </p>
  <div class="canvas-wrap">
    <div class="canvas">
      <svg class="edges" viewBox="0 0 {CANVAS_W} {CANVAS_H}">
        {edges_html}
      </svg>
      {nodes_html}
    </div>
  </div>
  <div class="footnote">
    <strong>Note:</strong> two different (regime, risk) combinations can lead
    to the same recommended action — marked with the same numbered circle:
    &nbsp;{badge_legend}.
  </div>
</body>
</html>
"""

with open("diagram_phase1.html", "w", encoding="utf-8") as f:
    f.write(HTML)

print("File generated: diagram_phase1.html")
