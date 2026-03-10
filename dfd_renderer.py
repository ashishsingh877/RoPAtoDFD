"""
dfd_renderer.py  —  Professional DFD renderer
- Main flowchart: clean, no overlaps, proper spacing
- Privacy controls: neat PIL-drawn table below the diagram (future state only)
- Two separate landscape images: Current State + Post Compliance
"""

import io, re, textwrap, graphviz
from PIL import Image, ImageDraw, ImageFont

_FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def _font(size, bold=False):
    try:    return ImageFont.truetype(_FONT_BOLD if bold else _FONT_REG, size)
    except: return ImageFont.load_default()

def _wrap_gv(text, chars=14):
    """Wrap for Graphviz labels."""
    lines = textwrap.wrap(str(text).strip(), width=chars)
    return "\\n".join(lines[:3]) if lines else text

def _sid(s):
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(s).strip())[:35]

# ── Node visual styles ────────────────────────────────────────────────────────
STYLE = {
    "external":  dict(shape="box",      style="filled,rounded", fillcolor="#FFF5CC", color="#A07800", fontcolor="#5C4400", penwidth="1.5"),
    "team":      dict(shape="box",      style="filled",         fillcolor="#FADADD", color="#B03030", fontcolor="#6B1A1A", penwidth="2.0"),
    "process":   dict(shape="box",      style="filled",         fillcolor="#FAFAFA", color="#555555", fontcolor="#1A1A1A", penwidth="1.2"),
    "decision":  dict(shape="diamond",  style="filled",         fillcolor="#C0392B", color="#8B2222", fontcolor="#FFFFFF", penwidth="2.0"),
    "endpoint":  dict(shape="ellipse",  style="filled",         fillcolor="#B03030", color="#7B1A1A", fontcolor="#FFFFFF", penwidth="2.0"),
    "datastore": dict(shape="cylinder", style="filled",         fillcolor="#D4E8FA", color="#1A5276", fontcolor="#0D3B6E", penwidth="1.5"),
}

def _node_attrs(ntype, label):
    s = STYLE.get(ntype, STYLE["process"]).copy()
    bold = ntype in ("team", "endpoint", "decision")
    return {
        **s,
        "label":    _wrap_gv(label, 13),
        "fontname": "Helvetica-Bold" if bold else "Helvetica",
        "fontsize": "12",
        "margin":   "0.24,0.18",
        "width":    "1.7",
        "height":   "0.65",
        "fixedsize":"false",
    }

# ── Build clean main flowchart (NO privacy control nodes) ────────────────────
def _build_graph(data: dict) -> bytes:
    dot = graphviz.Digraph(engine="dot")
    dot.attr("graph",
        bgcolor     = "white",
        rankdir     = "LR",
        splines     = "polyline",
        nodesep     = "0.80",
        ranksep     = "1.5",
        pad         = "0.65",
        fontname    = "Helvetica",
        size        = "26,9!",
        ratio       = "compress",
        dpi         = "150",
    )
    dot.attr("edge",
        fontname = "Helvetica",
        fontsize = "9",
        color    = "#666666",
        fontcolor= "#444444",
        arrowsize= "0.9",
        penwidth = "1.3",
        minlen   = "2",
    )

    phases: dict = {}
    for n in data.get("nodes", []):
        phases.setdefault(n.get("phase","main"), []).append(n)

    for ph_nodes in phases.values():
        with dot.subgraph() as sg:
            sg.attr(rank="same")
            for n in ph_nodes:
                dot.node(_sid(n["id"]), **_node_attrs(n.get("type","process"), n.get("label","")))

    for e in data.get("edges", []):
        src, dst = _sid(e.get("from","")), _sid(e.get("to",""))
        if not src or not dst: continue
        raw = e.get("label","").strip()
        lbl = (raw[:12] + "…") if len(raw) > 13 else raw
        sensitive = any(k in raw.lower() for k in
            ["health","medical","biometric","salary","financial","bank","sensitive","special"])
        attrs = dict(
            color    = "#C0392B" if sensitive else "#666666",
            fontcolor= "#C0392B" if sensitive else "#555555",
            penwidth = "2.2"     if sensitive else "1.3",
        )
        if lbl:
            attrs["label"]    = f"  {lbl}  "
            attrs["fontsize"] = "9"
        dot.edge(src, dst, **attrs)

    return dot.pipe(format="png")


# ── PIL: draw privacy controls as a clean table ───────────────────────────────
CTRL_TAG_W  = 170    # width of one green tag
CTRL_TAG_H  = 28     # height of one green tag
CTRL_PAD    = 8      # gap between tags
CTRL_ROW_H  = 52     # height of one table row
CTRL_LBL_W  = 200    # width of the "Process Step" label column

def _draw_controls_table(draw: ImageDraw.ImageDraw, privacy_controls: dict,
                          nodes: list, y_start: int, width: int) -> int:
    """Draw a clean privacy controls reference table. Returns new y."""
    if not privacy_controls:
        return y_start

    # Build lookup: node_id → label
    node_labels = {n["id"]: n.get("label", n["id"]) for n in nodes}

    # Filter to only nodes that have controls AND exist
    rows = [(nid, node_labels.get(nid, nid), ctrls)
            for nid, ctrls in privacy_controls.items()
            if ctrls and node_labels.get(nid)]
    if not rows:
        return y_start

    PAD = 36
    table_w = width - PAD * 2

    # Section header
    draw.rectangle([PAD, y_start, width - PAD, y_start + 38], fill="#1A6B3A")
    draw.text((PAD + 14, y_start + 9),
              "Privacy Controls by Process Step", font=_font(13, bold=True), fill="#FFFFFF")
    y = y_start + 38

    # Column headers
    draw.rectangle([PAD, y, width - PAD, y + 32], fill="#E8F5E9")
    draw.line([(PAD, y + 32), (width - PAD, y + 32)], fill="#A5D6A7", width=1)
    draw.text((PAD + 10, y + 8),  "Process Step / Node", font=_font(10, bold=True), fill="#1A5C34")
    draw.text((PAD + CTRL_LBL_W + 16, y + 8), "Privacy Controls Applied", font=_font(10, bold=True), fill="#1A5C34")
    y += 32

    # Rows
    for row_idx, (nid, node_lbl, ctrls) in enumerate(rows):
        row_bg = "#FFFFFF" if row_idx % 2 == 0 else "#F9FBF9"
        row_h  = max(CTRL_ROW_H, 14 + len(ctrls[:5]) * (CTRL_TAG_H + CTRL_PAD // 2))
        draw.rectangle([PAD, y, width - PAD, y + row_h], fill=row_bg)
        draw.line([(PAD, y + row_h), (width - PAD, y + row_h)], fill="#C8E6C9", width=1)

        # Node label (left column)
        draw.text((PAD + 10, y + 14),
                  "\n".join(textwrap.wrap(node_lbl, 22)[:2]),
                  font=_font(10, bold=True), fill="#333333")

        # Vertical divider
        div_x = PAD + CTRL_LBL_W
        draw.line([(div_x, y), (div_x, y + row_h)], fill="#C8E6C9", width=1)

        # Control tags (right side)
        tx = div_x + 12
        ty = y + 10
        max_x = width - PAD - 12
        for ctrl in ctrls[:6]:
            short_ctrl = ctrl[:20]
            tw = CTRL_TAG_W
            if tx + tw > max_x:   # wrap to next line
                tx = div_x + 12
                ty += CTRL_TAG_H + 6
            draw.rounded_rectangle([tx, ty, tx + tw, ty + CTRL_TAG_H],
                                   radius=5, fill="#D6EFD6", outline="#2E8B57", width=1)
            draw.text((tx + 8, ty + 6), short_ctrl, font=_font(9), fill="#1A5C34")
            tx += tw + CTRL_PAD

        y += row_h

    # Bottom border
    draw.line([(PAD, y), (width - PAD, y)], fill="#A5D6A7", width=1)
    return y + 16


# ── PIL composition ───────────────────────────────────────────────────────────
HEADER_H = 72
BANNER_H = 48
LEG_H    = 38
PAD_X    = 40
PAD_BOT  = 24

def _compose(graph_png: bytes, title: str, state: str,
             banner_text: str, banner_color: str,
             privacy_controls: dict = None, nodes: list = None) -> Image.Image:

    g = Image.open(io.BytesIO(graph_png)).convert("RGB")

    # Normalise to target width
    TARGET_W = 2200
    if g.width != TARGET_W:
        sc = TARGET_W / g.width
        g  = g.resize((TARGET_W, max(360, int(g.height * sc))), Image.LANCZOS)

    W = g.width + PAD_X * 2

    # Pre-calculate controls table height
    ctrl_h = 0
    if state == "future" and privacy_controls and nodes:
        rows = [ctrls for nid, ctrls in privacy_controls.items() if ctrls]
        n_rows = len(rows)
        if n_rows:
            ctrl_h = 38 + 32 + n_rows * CTRL_ROW_H + 30   # approx

    H = HEADER_H + BANNER_H + g.height + LEG_H + ctrl_h + PAD_BOT

    canvas = Image.new("RGB", (W, H), "#FFFFFF")
    draw   = ImageDraw.Draw(canvas)

    # ── Header ────────────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, HEADER_H], fill="#1A3A5C")
    draw.rectangle([14, 12, 88, HEADER_H - 12], fill="#2470A0", outline="#154C80", width=1)
    draw.text((21, 18), "PRIVACY\nTOOL", font=_font(10, bold=True), fill="#FFFFFF")
    draw.text((104, 11), title,           font=_font(24, bold=True), fill="#FFFFFF")
    draw.text((105, 44), "Data Flow Analysis  ·  Privacy & Data Protection Review",
              font=_font(12), fill="#93C6E7")

    # ── Banner ────────────────────────────────────────────────────────────────
    draw.rectangle([0, HEADER_H, W, HEADER_H + BANNER_H], fill=banner_color)
    draw.text((PAD_X, HEADER_H + 13), "◼  " + banner_text,
              font=_font(16, bold=True), fill="#FFFFFF")

    # ── Main diagram ──────────────────────────────────────────────────────────
    canvas.paste(g, (PAD_X, HEADER_H + BANNER_H))

    # ── Legend ────────────────────────────────────────────────────────────────
    ly = HEADER_H + BANNER_H + g.height + 4
    draw.rectangle([0, ly, W, ly + LEG_H], fill="#F4F6F8")
    draw.line([(0, ly), (W, ly)], fill="#CCCCCC", width=1)

    legend_items = [
        ("#FFF5CC","#A07800","External Entity"),
        ("#FADADD","#B03030","Internal Team"),
        ("#FAFAFA","#555555","Process Step"),
        ("#C0392B","#8B2222","Decision / Endpoint"),
        ("#D4E8FA","#1A5276","Data Store"),
        ("#D6EFD6","#2E8B57","Privacy Control"),
    ]
    lx = PAD_X
    for fill, stroke, lbl in legend_items:
        draw.rounded_rectangle([lx, ly + 10, lx + 18, ly + 27],
                               radius=3, fill=fill, outline=stroke, width=1)
        draw.text((lx + 22, ly + 11), lbl, font=_font(10), fill="#444444")
        lx += 158

    # ── Privacy controls table (future state only) ────────────────────────────
    if state == "future" and privacy_controls and nodes:
        # Add spacing line
        ctrl_y = ly + LEG_H + 8
        draw.line([(PAD_X, ctrl_y), (W - PAD_X, ctrl_y)], fill="#E0E0E0", width=1)
        ctrl_y += 10
        # Expand canvas if needed (re-render)
        actual_end = _draw_controls_table(draw, privacy_controls, nodes, ctrl_y, W)
        # If we underestimated height, crop to actual_end + PAD_BOT
        if actual_end + PAD_BOT < H:
            canvas = canvas.crop((0, 0, W, actual_end + PAD_BOT))

    return canvas


def _to_png(img):
    buf = io.BytesIO(); img.save(buf, format="PNG", dpi=(150,150)); return buf.getvalue()

def _to_pdf(img):
    buf = io.BytesIO(); img.save(buf, format="PDF", resolution=150); return buf.getvalue()


# ── Public API ────────────────────────────────────────────────────────────────
def render_dfd(dfd_data: dict) -> tuple:
    """Returns (asis_png, asis_pdf, future_png, future_pdf)."""
    title  = dfd_data.get("process_name", "Data Flow Diagram")
    asis   = dfd_data.get("asis",   {"nodes":[], "edges":[]})
    future = dfd_data.get("future", {"nodes":[], "edges":[]})
    ctrls  = dfd_data.get("privacy_controls", {})

    a_raw = _build_graph(asis)
    f_raw = _build_graph(future)

    asis_img   = _compose(a_raw, title, "asis",
                          "Current State",
                          "#C0392B")
    future_img = _compose(f_raw, title, "future",
                          "Post Compliance  ·  Privacy-Embedded Future State",
                          "#1A6B3A",
                          privacy_controls = ctrls,
                          nodes            = future.get("nodes", []))

    return _to_png(asis_img), _to_pdf(asis_img), _to_png(future_img), _to_pdf(future_img)


# ── AI JSON schema ────────────────────────────────────────────────────────────
DFD_JSON_SCHEMA = '''
Return ONLY a valid JSON array. No markdown fences.

[{
  "id": "P001",
  "process_name": "Name ≤50 chars",
  "asis":   { "nodes": [...], "edges": [...] },
  "future": { "nodes": [...], "edges": [...] },
  "privacy_controls": { "node_id": ["Control A", "Control B", "Control C"] },
  "narrative": "3-5 sentences."
}]

NODE: {"id":"snake_id","label":"≤16 chars","type":"external|team|process|decision|endpoint|datastore","phase":"collection|processing|storage|sharing|exit"}
EDGE: {"from":"id","to":"id","label":"≤12 chars"}

Privacy controls: up to 5 per node, ≤20 chars each. These appear as a clean table below the diagram.
Min 12 nodes + 12 edges per diagram.
'''
