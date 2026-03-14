"""
dfd_renderer.py  —  Professional DFD renderer v5
- Clean main flowchart (no clutter)
- Post Compliance: same flowchart + professional PIL controls grid below
- 250 DPI, client-ready, directly shareable
"""

import io, re, textwrap, graphviz
from PIL import Image, ImageDraw, ImageFont

_FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def _font(size, bold=False):
    try:    return ImageFont.truetype(_FONT_BOLD if bold else _FONT_REG, size)
    except: return ImageFont.load_default()

def _wrap_gv(text, chars=14):
    lines = textwrap.wrap(str(text).strip(), width=chars)
    return "\\n".join(lines[:3]) if lines else text

def _sid(s):
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(s).strip())[:35]

STYLES = {
    "external":  dict(shape="box",      style="filled,rounded", fillcolor="#FFF5CC", color="#A07800", fontcolor="#5C4400", penwidth="1.8"),
    "team":      dict(shape="box",      style="filled",         fillcolor="#FADADD", color="#B03030", fontcolor="#6B1A1A", penwidth="2.2"),
    "process":   dict(shape="box",      style="filled",         fillcolor="#FFFFFF", color="#555555", fontcolor="#1A1A1A", penwidth="1.4"),
    "decision":  dict(shape="diamond",  style="filled",         fillcolor="#C0392B", color="#8B2222", fontcolor="#FFFFFF", penwidth="2.2"),
    "endpoint":  dict(shape="ellipse",  style="filled",         fillcolor="#B03030", color="#7B1A1A", fontcolor="#FFFFFF", penwidth="2.2"),
    "datastore": dict(shape="cylinder", style="filled",         fillcolor="#D4E8FA", color="#1A5276", fontcolor="#0D3B6E", penwidth="1.8"),
}

def _node_attrs(ntype, label):
    s = STYLES.get(ntype, STYLES["process"]).copy()
    bold = ntype in ("team","endpoint","decision")
    return {
        **s,
        "label":    _wrap_gv(label, 14),
        "fontname": "Helvetica-Bold" if bold else "Helvetica",
        "fontsize": "13",
        "margin":   "0.25,0.18",
        "width":    "1.9",
        "height":   "0.72",
        "fixedsize":"false",
    }

def _build_flow(data: dict) -> bytes:
    """Render clean main flowchart, no privacy control nodes."""
    dot = graphviz.Digraph(engine="dot")
    dot.attr("graph",
        bgcolor="white", rankdir="LR", splines="polyline",
        nodesep="0.75", ranksep="1.6", pad="0.65",
        fontname="Helvetica", size="30,12!", ratio="compress", dpi="200",
    )
    dot.attr("edge", fontname="Helvetica", fontsize="9",
             color="#555555", fontcolor="#333333", arrowsize="0.9",
             penwidth="1.4", minlen="2")

    phases: dict = {}
    for n in data.get("nodes", []):
        phases.setdefault(n.get("phase","main"), []).append(n)

    for ph_nodes in phases.values():
        with dot.subgraph() as sg:
            sg.attr(rank="same")
            for n in ph_nodes:
                sg.node(_sid(n["id"]), **_node_attrs(n.get("type","process"), n.get("label","")))

    for e in data.get("edges", []):
        src, dst = _sid(e.get("from","")), _sid(e.get("to",""))
        if not src or not dst: continue
        raw = e.get("label","").strip()
        lbl = (raw[:13]+"…") if len(raw) > 14 else raw
        sensitive = any(k in raw.lower() for k in
            ["health","medical","biometric","salary","financial","bank","sensitive"])
        attrs = dict(color="#C0392B" if sensitive else "#555555",
                     fontcolor="#C0392B" if sensitive else "#444444",
                     penwidth="2.2" if sensitive else "1.4", minlen="2")
        if lbl:
            attrs["label"]    = f"  {lbl}  "
            attrs["fontsize"] = "9"
        dot.edge(src, dst, **attrs)

    return dot.pipe(format="png")


# ── PIL: professional privacy controls grid ───────────────────────────────────

PILL_H     = 36     # height of each green pill
PILL_PAD_X = 14     # horizontal inner padding
PILL_PAD_Y = 8      # gap between pills vertically
COLS       = 4      # pills per row
CTRL_FONT  = 11     # font size inside pill
ROW_LABEL_W = 220   # width of left "Process Step" label column
ROW_V_PAD   = 20    # extra padding top/bottom per table row
SEC_HEAD_H  = 52    # section header height
COL_HEAD_H  = 36    # column header height
DIVIDER_H   = 10    # gap between section header and col headers

def _measure_pill_width(text: str, draw: ImageDraw.ImageDraw) -> int:
    f = _font(CTRL_FONT)
    try:
        bb = draw.textbbox((0, 0), text, font=f)
        tw = bb[2] - bb[0]
    except Exception:
        tw = len(text) * 7
    return tw + PILL_PAD_X * 2 + 4

def _draw_controls_section(draw: ImageDraw.ImageDraw,
                            img_w: int, y_start: int,
                            privacy_controls: dict, nodes: list) -> int:
    """
    Draw a professional 2-column-style grid:
    Left:  Process Step name
    Right: Row of green pills (up to COLS per row, wrapping)
    Returns new y position after section.
    """
    if not privacy_controls:
        return y_start

    node_labels = {n["id"]: n.get("label", n["id"]) for n in nodes}
    rows = [(nid, node_labels.get(nid, nid), ctrls)
            for nid, ctrls in privacy_controls.items()
            if ctrls and node_labels.get(nid)]
    if not rows:
        return y_start

    PAD  = 48
    W    = img_w - PAD * 2

    # ── Section header ─────────────────────────────────────────────────────
    draw.rectangle([PAD, y_start, img_w-PAD, y_start+SEC_HEAD_H], fill="#1A6B3A")
    draw.text((PAD+18, y_start+14),
              "Privacy Controls by Process Step",
              font=_font(16, bold=True), fill="#FFFFFF")
    y = y_start + SEC_HEAD_H

    # ── Column headers ──────────────────────────────────────────────────────
    draw.rectangle([PAD, y, img_w-PAD, y+COL_HEAD_H], fill="#E8F5E9")
    draw.line([(PAD, y+COL_HEAD_H), (img_w-PAD, y+COL_HEAD_H)], fill="#A5D6A7", width=1)
    draw.text((PAD+12, y+9),  "Process Step / Node",   font=_font(12, bold=True), fill="#1A5C34")
    draw.text((PAD+ROW_LABEL_W+20, y+9), "Privacy Controls Applied", font=_font(12, bold=True), fill="#1A5C34")
    y += COL_HEAD_H

    # ── Data rows ──────────────────────────────────────────────────────────
    for ri, (nid, node_lbl, ctrls) in enumerate(rows):
        # Calculate row height based on number of pills needed
        pills_per_row_actual = max(1, (W - ROW_LABEL_W - 20) // 200)
        n_pill_rows = max(1, (len(ctrls[:8]) + pills_per_row_actual - 1) // pills_per_row_actual)
        row_h = ROW_V_PAD * 2 + n_pill_rows * (PILL_H + PILL_PAD_Y)

        row_bg = "#FFFFFF" if ri % 2 == 0 else "#F5FBF5"
        draw.rectangle([PAD, y, img_w-PAD, y+row_h], fill=row_bg)
        draw.line([(PAD, y+row_h), (img_w-PAD, y+row_h)], fill="#C8E6C9", width=1)

        # Left: node label
        wrapped_lbl = "\n".join(textwrap.wrap(node_lbl, 20)[:2])
        draw.text((PAD+12, y+ROW_V_PAD), wrapped_lbl,
                  font=_font(12, bold=True), fill="#2C3E50")

        # Divider line
        draw.line([(PAD+ROW_LABEL_W, y), (PAD+ROW_LABEL_W, y+row_h)],
                  fill="#C8E6C9", width=1)

        # Right: pills in rows of COLS
        px = PAD + ROW_LABEL_W + 16
        py = y + ROW_V_PAD
        max_x = img_w - PAD - 16
        col_i = 0
        for ctrl in ctrls[:8]:
            # Measure pill
            f = _font(CTRL_FONT)
            try:
                bb = draw.textbbox((0, 0), ctrl[:22], font=f)
                pw = bb[2] - bb[0] + PILL_PAD_X * 2 + 4
            except Exception:
                pw = len(ctrl) * 8 + PILL_PAD_X * 2
            pw = max(pw, 140)
            pw = min(pw, 240)

            if px + pw > max_x or col_i >= COLS:
                px   = PAD + ROW_LABEL_W + 16
                py  += PILL_H + PILL_PAD_Y
                col_i = 0

            # Draw pill
            draw.rounded_rectangle([px, py, px+pw, py+PILL_H],
                                   radius=8, fill="#D5E8D4", outline="#27AE60", width=1)
            draw.text((px+PILL_PAD_X, py+9), ctrl[:22],
                      font=_font(CTRL_FONT), fill="#145A32")
            px   += pw + 10
            col_i += 1

        y += row_h

    # Bottom border
    draw.line([(PAD, y), (img_w-PAD, y)], fill="#A5D6A7", width=2)
    return y + 20


# ── PIL composition ───────────────────────────────────────────────────────────
HEADER_H = 84
BANNER_H = 54
LEG_H    = 46
PAD      = 48

def _compose(graph_png: bytes, title: str, state: str,
             banner_text: str, banner_color: str,
             privacy_controls: dict = None, nodes: list = None) -> Image.Image:

    g = Image.open(io.BytesIO(graph_png)).convert("RGB")

    MIN_W = 3200
    if g.width < MIN_W:
        sc = MIN_W / g.width
        g  = g.resize((int(g.width * sc), int(g.height * sc)), Image.LANCZOS)

    W = g.width + PAD * 2

    # Estimate extra height for privacy controls section
    ctrl_extra = 0
    if state == "future" and privacy_controls and nodes:
        n_rows = sum(1 for nid, ctrls in privacy_controls.items()
                     if ctrls and any(n["id"] == nid for n in nodes))
        if n_rows:
            ctrl_extra = SEC_HEAD_H + COL_HEAD_H + n_rows * (ROW_V_PAD*2 + PILL_H + PILL_PAD_Y + 16) + 40

    H = HEADER_H + BANNER_H + g.height + LEG_H + ctrl_extra + 32

    canvas = Image.new("RGB", (W, H), "#FFFFFF")
    draw   = ImageDraw.Draw(canvas)

    # ── Header ────────────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, HEADER_H], fill="#1A3A5C")
    draw.rectangle([16, 14, 100, HEADER_H-14], fill="#2470A0", outline="#154C80", width=2)
    draw.text((22, 22), "PRIVACY\nTOOL", font=_font(12, bold=True), fill="#FFFFFF")
    draw.text((116, 10), title,     font=_font(30, bold=True), fill="#FFFFFF")
    draw.text((117, 52), "Data Flow Analysis  ·  Privacy & Data Protection Review",
              font=_font(15), fill="#93C6E7")

    # ── Banner ────────────────────────────────────────────────────────────────
    draw.rectangle([0, HEADER_H, W, HEADER_H+BANNER_H], fill=banner_color)
    draw.text((PAD, HEADER_H+15), "◼  " + banner_text,
              font=_font(20, bold=True), fill="#FFFFFF")

    # ── Main diagram ──────────────────────────────────────────────────────────
    canvas.paste(g, (PAD, HEADER_H+BANNER_H))

    # ── Legend ────────────────────────────────────────────────────────────────
    ly = HEADER_H + BANNER_H + g.height + 6
    draw.rectangle([0, ly, W, ly+LEG_H], fill="#F4F6F8")
    draw.line([(0, ly), (W, ly)], fill="#CCCCCC", width=1)
    legend_items = [
        ("#FFF5CC","#A07800","External Entity"),
        ("#FADADD","#B03030","Internal Team"),
        ("#FFFFFF","#555555","Process Step"),
        ("#C0392B","#8B2222","Decision / Endpoint"),
        ("#D4E8FA","#1A5276","Data Store"),
        ("#D5E8D4","#27AE60","Privacy Control"),
    ]
    lx = PAD
    for fill, stroke, lbl in legend_items:
        draw.rounded_rectangle([lx, ly+13, lx+22, ly+33],
                               radius=4, fill=fill, outline=stroke, width=1)
        draw.text((lx+28, ly+14), lbl, font=_font(12), fill="#444444")
        lx += 190

    # ── Privacy controls section (future state only) ──────────────────────────
    if state == "future" and privacy_controls and nodes:
        ctrl_y = ly + LEG_H + 16
        draw.line([(PAD, ctrl_y-8), (W-PAD, ctrl_y-8)], fill="#E0E0E0", width=1)
        end_y = _draw_controls_section(draw, W, ctrl_y, privacy_controls, nodes)
        # Trim canvas to actual content
        canvas = canvas.crop((0, 0, W, end_y + 24))

    return canvas

def _to_png(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(250,250))
    return buf.getvalue()

def _to_pdf(img):
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=250)
    return buf.getvalue()

# ── Public API ────────────────────────────────────────────────────────────────
def render_dfd(dfd_data: dict) -> tuple:
    title  = dfd_data.get("process_name", "Data Flow Diagram")
    asis   = dfd_data.get("asis",   {"nodes":[], "edges":[]})
    future = dfd_data.get("future", {"nodes":[], "edges":[]})
    ctrls  = dfd_data.get("privacy_controls", {})

    a_raw = _build_flow(asis)
    f_raw = _build_flow(future)   # same clean flow, controls go in PIL section

    asis_img   = _compose(a_raw, title, "asis",   "Current State", "#C0392B")
    future_img = _compose(f_raw, title, "future",
                          "Post Compliance  ·  Privacy-Embedded Future State", "#1A6B3A",
                          privacy_controls=ctrls, nodes=future.get("nodes",[]))

    return _to_png(asis_img), _to_pdf(asis_img), _to_png(future_img), _to_pdf(future_img)


DFD_JSON_SCHEMA = '''
Return ONLY a valid JSON array with exactly ONE element. No markdown. No text before or after.

[{
  "id": "P001",
  "process_name": "Name ≤50 chars",
  "asis":   { "nodes": [...], "edges": [...] },
  "future": { "nodes": [...], "edges": [...] },
  "privacy_controls": { "node_id": ["Control A", "Control B", "Control C", "Control D"] },
  "narrative": "3-5 sentences."
}]

NODE: {"id":"snake_id","label":"≤14 chars","type":"external|team|process|decision|endpoint|datastore","phase":"collection|processing|storage|sharing|exit"}
EDGE: {"from":"id","to":"id","label":"≤13 chars"}

PRIVACY CONTROLS: up to 5 per node, ≤22 chars each.
  These appear as a professional green grid table below the diagram.
  Examples: "Privacy Notice", "CMP Consent", "Encryption at Rest", "Role-Based Access",
  "Audit Logging", "DPA in Place", "MFA Enabled", "Data Minimisation",
  "Secure API", "Retention Policy", "Vendor Due Diligence", "Least Privilege"

RULES: Min 12 nodes + 12 edges. future nodes = same IDs as asis. All edge IDs must exist.
'''
