#!/usr/bin/env python3
"""
Gera o diagrama de fluxo da Fase 1: indicadores brutos -> agregacao ->
sintese por modulo -> classificacao (regime/risco) -> matriz de 12 acoes.

Produz um HTML autocontido (CSS + SVG inline, sem dependencias externas)
em diagrama_fase1.html.
"""

import json

# ---------------------------------------------------------------------------
# Dados (espelham 1:1 config.py e matriz.py do pipeline)
# ---------------------------------------------------------------------------

GROUP_COLOR = {
    "producao": "#2a78d6",
    "emprego": "#1baf7a",
    "consumo": "#eda100",
    "modulob": "#4a3aa7",
}
GROUP_LABEL = {
    "producao": "Produção",
    "emprego": "Emprego",
    "consumo": "Consumo",
    "modulob": "Módulo B — Risk-on / Risk-off",
}

INDICATORS = [
    dict(id="indpro", label="Produção Industrial", sub="FRED: INDPRO", group="producao",
         nota="Proxy mais direto de atividade real — a série 'espinha dorsal' do CFNAI."),
    dict(id="payrolls", label="Payrolls (folha não-agrícola)", sub="FRED: PAYEMS", group="emprego",
         nota="Geração de empregos mês a mês — sinal coincidente forte do ciclo."),
    dict(id="desemprego", label="Taxa de Desemprego", sub="FRED: UNRATE", group="emprego",
         nota="Nível invertido: desemprego subindo pesa contra o score de atividade."),
    dict(id="seguro_desemprego", label="Seguro-Desemprego", sub="FRED: ICSA", group="emprego",
         nota="Semanal — o dado de emprego mais rápido disponível, média móvel de 4 semanas."),
    dict(id="varejo", label="Vendas no Varejo", sub="FRED: RSAFS", group="consumo",
         nota="Termômetro do consumo, ~70% do PIB americano."),
    dict(id="philly", label="Philly Fed", sub="FRED: GACDFSA066MSFRBPHI", group="consumo",
         nota="Índice de difusão de sentimento industrial — antecedente, não coincidente."),
    dict(id="vix", label="VIX", sub="FRED: VIXCLS", group="modulob",
         nota="Volatilidade implícita — o 'medo' do mercado de ações. Sinal invertido."),
    dict(id="credit", label="Spread de Crédito", sub="FRED: BAA10Y", group="modulob",
         nota="Prêmio de risco de crédito Baa vs. Treasury 10y. Sinal invertido."),
    dict(id="jpy", label="Iene / Dólar", sub="FRED: DEXJPUS", group="modulob",
         nota="Iene é moeda de refúgio — fortalece em risk-off. Sinal invertido."),
    dict(id="treasury", label="Treasury 10Y", sub="FRED: DGS10", group="modulob",
         nota="Yield sobe com apetite a risco, cai com fuga para qualidade. Sinal invertido."),
    dict(id="audjpy", label="AUD / JPY", sub="Yahoo: AUDJPY=X", group="modulob",
         nota="Clássico termômetro cambial de risk-on/off (moeda-commodity vs. moeda-refúgio)."),
    dict(id="ouro", label="Ouro", sub="Yahoo: GC=F", group="modulob",
         nota="Reserva de valor em crises — peso reduzido (0,5) por também reagir à inflação."),
]

COL2 = [
    dict(id="cat_producao", label="Produção", sub="z-score (janela de 10 anos)", group="producao"),
    dict(id="cat_emprego", label="Emprego", sub="z-score médio de 3 indicadores", group="emprego"),
    dict(id="cat_consumo", label="Consumo", sub="z-score médio de 2 indicadores", group="consumo"),
    dict(id="score_risco_composto", label="Score de Risco", sub="composto ponderado (6 indicadores)", group="modulob"),
]

COL3 = [
    dict(id="score_nivel_momentum", label="Score de Nível + Momentum", sub="média das 3 categorias · MM3 · Δ3m",
         color="#5b5b5b", srcs=["producao", "emprego", "consumo"]),
    dict(id="score_risco_filtrado", label="Score de Risco Filtrado", sub="discretização (-2 a +2) + filtro de persistência",
         color="#4a3aa7", srcs=["modulob"]),
]

REGIMES = [
    dict(id="expansao", label="Expansão", color="#70AD47"),
    dict(id="recuperacao", label="Recuperação", color="#4472C4"),
    dict(id="desaceleracao", label="Desaceleração", color="#ED7D31"),
    dict(id="contracao", label="Contração", color="#C00000"),
]
RISCOS = [
    dict(id="riskon", label="Risk-on", color="#70AD47"),
    dict(id="neutro", label="Neutro", color="#9c9c9c"),
    dict(id="riskoff", label="Risk-off", color="#C00000"),
]

# Espelha matriz.py::MATRIZ_ACAO
MATRIZ_ACAO = {
    ("expansao", "riskon"): "Aumentar exposição a cíclicos / beta alto",
    ("expansao", "neutro"): "Manter exposição-alvo",
    ("expansao", "riskoff"): "Risk-off temporário → manter posição, tratar como ruído",
    ("recuperacao", "riskon"): "Aumentar exposição gradualmente, rotacionar para cíclicos",
    ("recuperacao", "neutro"): "Postura neutra, aguardar confirmação",
    ("recuperacao", "riskoff"): "Cautela — pode ser recuperação falsa; reduzir tamanho",
    ("desaceleracao", "riskon"): "Reduzir gradualmente, rotacionar para qualidade/defensivos",
    ("desaceleracao", "neutro"): "Reduzir exposição-alvo",
    ("desaceleracao", "riskoff"): "Reduzir risco de forma decisiva",
    ("contracao", "riskon"): 'Alerta — possível "bear market rally"; não confiar sozinho',
    ("contracao", "neutro"): "Reduzir risco de forma decisiva",
    ("contracao", "riskoff"): "Reduzir risco de forma decisiva (mais defensiva do framework)",
}

# Grupos de ação com texto idêntico -> mesmo "badge" (letra) no canto da célula,
# pra deixar visualmente óbvio quando duas combinações diferentes levam à
# mesma recomendação.
ACAO_BADGE = {}
_badge_por_texto = {}
_proxima_letra = ord("A")
for chave, texto in MATRIZ_ACAO.items():
    if texto not in _badge_por_texto:
        _badge_por_texto[texto] = chr(_proxima_letra)
        _proxima_letra += 1
    ACAO_BADGE[chave] = _badge_por_texto[texto]
# só mostramos o badge quando o texto se repete em mais de 1 célula
_contagem_texto = {}
for texto in MATRIZ_ACAO.values():
    _contagem_texto[texto] = _contagem_texto.get(texto, 0) + 1
for chave, texto in MATRIZ_ACAO.items():
    if _contagem_texto[texto] < 2:
        ACAO_BADGE[chave] = None

print(json.dumps({"indicators": len(INDICATORS), "col2": len(COL2)}, indent=2))

# ---------------------------------------------------------------------------
# Layout — todas as coordenadas em pixels, calculadas a partir das
# constantes abaixo (mexer nas constantes reflui automaticamente pro
# layout inteiro, não precisa re-calcular nada à mão).
# ---------------------------------------------------------------------------

MARGIN_TOP = 46
NODE_H1 = 40          # altura de cada indicador (coluna 1)
GAP1 = 9              # espaço entre indicadores do mesmo grupo
GROUP_HEADER_H = 24
GROUP_GAP = 20         # espaço extra entre grupos

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

# --- Coluna 1: indicadores agrupados ---------------------------------------
groups_order = ["producao", "emprego", "consumo", "modulob"]
col1_nodes = {}   # id -> dict com x,y,w,h
col1_group_bounds = {}  # group -> (top, bottom) dos NÓS (sem o header)
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

# --- Coluna 2: agregação por categoria (centralizada no cluster de origem) --
col2_nodes = {}
for node in COL2:
    top, bottom, _ = col1_group_bounds[node["group"]]
    center = (top + bottom) / 2
    ny = center - NODE_H2 / 2
    col2_nodes[node["id"]] = dict(x=COL2_X, y=ny, w=COL2_W, h=NODE_H2, data=node,
                                   color=GROUP_COLOR[node["group"]])

# --- Coluna 3: síntese por módulo ------------------------------------------
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

# --- Coluna 4: classificação (regime + risco) -------------------------------
def stack_centered(items, x, w, h, gap, center):
    total = len(items) * h + (len(items) - 1) * gap
    top = center - total / 2
    out = {}
    yy = top
    for it in items:
        out[it["id"]] = dict(x=x, y=yy, w=w, h=h, data=it, color=it["color"])
        yy += h + gap
    return out

regime_center = col3_nodes["score_nivel_momentum"]["y"] + col3_nodes["score_nivel_momentum"]["h"] / 2
risco_center = col3_nodes["score_risco_filtrado"]["y"] + col3_nodes["score_risco_filtrado"]["h"] / 2

regime_nodes = stack_centered(REGIMES, COL4_X, COL4_W, NODE_H4, GAP4, regime_center)
risco_nodes = stack_centered(RISCOS, COL4_X, COL4_W, NODE_H4, GAP4, risco_center)
col4_nodes = {**regime_nodes, **risco_nodes}

# --- Coluna 5: matriz 4x3 ----------------------------------------------------
# O topo da matriz precisa deixar espaço, acima dele, para o cabeçalho de
# coluna (MATRIX_HEADER_H) + o título "Ação recomendada" da própria coluna
# + uma margem — senão os dois se sobrepõem visualmente (foi exatamente o
# que aconteceu na primeira versão: o cabeçalho colorido da matriz cobria
# o título da coluna, porque regime_center ficava perto demais do topo).
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
for rc in RISCOS:
    matrix_cols_x[rc["id"]] = xx
    xx += MATRIX_COL_W

MATRIX_RIGHT = matrix_grid_x + 3 * MATRIX_COL_W
MATRIX_BOTTOM = matrix_top + 4 * MATRIX_ROW_H + 3 * MATRIX_ROW_GAP

CANVAS_W = MATRIX_RIGHT + 40
CANVAS_H = max(COL1_BOTTOM, MATRIX_BOTTOM, risco_nodes[RISCOS[-1]["id"]]["y"] + NODE_H4) + 50

print("layout ok", CANVAS_W, CANVAS_H)

# ---------------------------------------------------------------------------
# Curvas (SVG bezier) entre nós
# ---------------------------------------------------------------------------

def bezier_hh(x1, y1, x2, y2):
    """Curva horizontal->horizontal: sai reto da direita da origem, chega
    reto na esquerda do destino. É o traçado clássico de diagrama de fluxo
    (Sankey) — funciona bem mesmo com grande diferença vertical entre
    origem e destino."""
    dx = max(abs(x2 - x1) * 0.5, 30)
    return f"M {x1:.1f} {y1:.1f} C {x1+dx:.1f} {y1:.1f}, {x2-dx:.1f} {y2:.1f}, {x2:.1f} {y2:.1f}"


def bezier_hv(x1, y1, x2, y2):
    """Curva horizontal->vertical: sai reto da direita da origem, mas
    chega de BAIXO para CIMA no destino (usada para os nós de risco, que
    precisam 'subir' até o topo das colunas da matriz)."""
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

# indicador -> categoria/composto (coluna 1 -> coluna 2)
for ind in INDICATORS:
    src = col1_nodes[ind["id"]]
    dst = [c for c in col2_nodes.values() if c["data"]["group"] == ind["group"]][0]
    add_edge(right_mid(src), left_mid(dst), GROUP_COLOR[ind["group"]], width=1.2, opacity=0.38)

# categoria/composto -> síntese do módulo (coluna 2 -> coluna 3)
for c2 in col2_nodes.values():
    dst = [c for c in col3_nodes.values() if c2["data"]["group"] in c["data"]["srcs"]][0]
    add_edge(right_mid(c2), left_mid(dst), c2["color"], width=2, opacity=0.55)

# síntese -> regime / risco (coluna 3 -> coluna 4)
for rid in [r["id"] for r in REGIMES]:
    add_edge(right_mid(col3_nodes["score_nivel_momentum"]), left_mid(col4_nodes[rid]),
              col4_nodes[rid]["color"], width=2, opacity=0.5)
for rid in [r["id"] for r in RISCOS]:
    add_edge(right_mid(col3_nodes["score_risco_filtrado"]), left_mid(col4_nodes[rid]),
              col4_nodes[rid]["color"], width=2, opacity=0.5)

# regime -> linha da matriz (coluna 4 -> matriz, entra pela esquerda)
for r in REGIMES:
    node = col4_nodes[r["id"]]
    target = (MATRIX_X, matrix_rows_y[r["id"]] + MATRIX_ROW_H / 2)
    add_edge(right_mid(node), target, r["color"], mode="hh", width=2.4, opacity=0.6)

# risco -> coluna da matriz (coluna 4 -> matriz, entra por cima)
for rc in RISCOS:
    node = col4_nodes[rc["id"]]
    target = (matrix_cols_x[rc["id"]] + MATRIX_COL_W / 2, matrix_top)
    add_edge(right_mid(node), target, rc["color"], mode="hv", width=2.4, opacity=0.6)

print("edges:", len(edges_svg))

# ---------------------------------------------------------------------------
# HTML — nós (divs posicionados) + rótulos de coluna + legenda
# ---------------------------------------------------------------------------

def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


html_parts = []

# --- coluna 1: indicadores + cabeçalhos de grupo ---
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
        f'<div class="tooltip">{esc(ind["nota"])}</div>'
        f'</div>'
    )

# --- coluna 2 ---
for c2 in col2_nodes.values():
    n = c2
    html_parts.append(
        f'<div class="node node-agg" style="left:{n["x"]}px; top:{n["y"]}px; width:{n["w"]}px; '
        f'height:{n["h"]}px; border-left-color:{n["color"]};">'
        f'<div class="node-label">{esc(n["data"]["label"])}</div>'
        f'<div class="node-sub">{esc(n["data"]["sub"])}</div>'
        f'</div>'
    )

# --- coluna 3 ---
for n in col3_nodes.values():
    html_parts.append(
        f'<div class="node node-sintese" style="left:{n["x"]}px; top:{n["y"]}px; width:{n["w"]}px; '
        f'height:{n["h"]}px; border-left-color:{n["color"]};">'
        f'<div class="node-label">{esc(n["data"]["label"])}</div>'
        f'<div class="node-sub">{esc(n["data"]["sub"])}</div>'
        f'</div>'
    )

# --- coluna 4 (regime + risco) ---
for n in col4_nodes.values():
    html_parts.append(
        f'<div class="node node-classe" style="left:{n["x"]}px; top:{n["y"]}px; width:{n["w"]}px; '
        f'height:{n["h"]}px; background:{n["color"]};">'
        f'<div class="node-label node-label-white">{esc(n["data"]["label"])}</div>'
        f'</div>'
    )

# --- rótulos de coluna (cabeçalhos gerais no topo do canvas) ---
col_titles = [
    (COL1_X, COL1_W, "Indicadores brutos"),
    (COL2_X, COL2_W, "Agregação por categoria"),
    (COL3_X, COL3_W, "Síntese do módulo"),
    (COL4_X, COL4_W, "Classificação"),
    (MATRIX_X, MATRIX_RIGHT - MATRIX_X, "Ação recomendada (matriz 4×3)"),
]
for x, w, title in col_titles:
    html_parts.append(f'<div class="col-title" style="left:{x}px; top:8px; width:{w}px;">{esc(title)}</div>')

# --- matriz: cabeçalhos de coluna (risco) ---
for rc in RISCOS:
    x = matrix_cols_x[rc["id"]]
    html_parts.append(
        f'<div class="matrix-col-header" style="left:{x}px; top:{matrix_top - MATRIX_HEADER_H}px; '
        f'width:{MATRIX_COL_W - 8}px; height:{MATRIX_HEADER_H - 8}px; background:{rc["color"]};">'
        f'{esc(rc["label"])}</div>'
    )

# --- matriz: rótulos de linha (regime) ---
for r in REGIMES:
    y = matrix_rows_y[r["id"]]
    html_parts.append(
        f'<div class="matrix-row-header" style="left:{MATRIX_X}px; top:{y}px; '
        f'width:{MATRIX_ROW_LABEL_W - 10}px; height:{MATRIX_ROW_H - 8}px; border-left-color:{r["color"]};">'
        f'{esc(r["label"])}</div>'
    )

# --- matriz: 12 células ---
for r in REGIMES:
    for rc in RISCOS:
        chave = (r["id"], rc["id"])
        texto = MATRIZ_ACAO[chave]
        badge = ACAO_BADGE[chave]
        x = matrix_cols_x[rc["id"]]
        y = matrix_rows_y[r["id"]]
        badge_html = f'<span class="badge">{badge}</span>' if badge else ""
        html_parts.append(
            f'<div class="matrix-cell" style="left:{x}px; top:{y}px; width:{MATRIX_COL_W - 8}px; '
            f'height:{MATRIX_ROW_H - 8}px; border-top-color:{rc["color"]}; border-left-color:{r["color"]};">'
            f'{badge_html}<div class="cell-text">{esc(texto)}</div></div>'
        )

nodes_html = "\n".join(html_parts)
edges_html = "\n".join(edges_svg)

# ---------------------------------------------------------------------------
# Nota de rodapé (badges repetidos)
# ---------------------------------------------------------------------------
badge_notes = {}
for chave, badge in ACAO_BADGE.items():
    if badge:
        badge_notes.setdefault(badge, MATRIZ_ACAO[chave])
badge_legend = " &nbsp;·&nbsp; ".join(
    f'<span class="badge">{b}</span> {esc(t)}' for b, t in sorted(badge_notes.items())
)

print("html assembled, nodes:", len(html_parts))

# ---------------------------------------------------------------------------
# Documento final
# ---------------------------------------------------------------------------

HTML = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Fase 1 — Do indicador à ação: mapa do pipeline</title>
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
  .node-sintese {{ border-left-width: 5px; background: #fbfbfa; }}
  .node-classe {{ border: none; border-radius: 6px; justify-content: center; align-items: center; }}
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
  <h1>Fase 1 — Do indicador à ação: mapa do pipeline completo</h1>
  <p class="subtitle">
    Os 12 indicadores brutos (esquerda) alimentam o Módulo A (nowcasting do ciclo
    econômico) e o Módulo B (risco de mercado). Cada módulo sintetiza seus
    indicadores num score único, que é classificado numa categoria — regime
    (Módulo A) ou nível de risco (Módulo B). O cruzamento das duas classificações
    define a ação recomendada, na matriz 4×3 à direita. Passe o mouse sobre um
    indicador para ver por que ele foi escolhido.
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
    <strong>Nota:</strong> duas combinações diferentes de (regime, risco) podem levar
    à mesma ação recomendada — marcadas com o mesmo círculo numerado:
    &nbsp;{badge_legend}.
  </div>
</body>
</html>
"""

with open("diagrama_fase1.html", "w", encoding="utf-8") as f:
    f.write(HTML)

print("Arquivo gerado: diagrama_fase1.html")
