"""
dfd_renderer.py — Professional DFD renderer v6
- 250 DPI landscape, client-ready
- Clean main flowchart (no clutter)  
- Post Compliance: same diagram + properly spaced controls grid
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
        "width":    "1.9", "height":"0.72",
        "fixedsize":"false",
    }

def _build_flow(data: dict) -> bytes:
    dot = graphviz.Digraph(engine="dot")
    dot.attr("graph",
        bgcolor="white", rankdir="LR", splines="polyline",
        nodesep="0.75", ranksep="1.6", pad="0.65",
        fontname="Helvetica", size="30,12!", ratio="compress", dpi="200",
    )
    dot.attr("edge", fontname="Helvetica", fontsize="9",
             color="#555555", fontcolor="#333333",
             arrowsize="0.9", penwidth="1.4", minlen="2")

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
        attrs = dict(
            color    = "#C0392B" if sensitive else "#555555",
            fontcolor= "#C0392B" if sensitive else "#444444",
            penwidth = "2.2"     if sensitive else "1.4",
            minlen   = "2",
        )
        if lbl:
            attrs["label"]    = f"  {lbl}  "
            attrs["fontsize"] = "9"
        dot.edge(src, dst, **attrs)
    return dot.pipe(format="png")


# ── Professional Privacy Controls Grid ───────────────────────────────────────

PILL_H    = 38      # pill height
PILL_R    = 10      # pill corner radius
PILL_MINW = 160     # minimum pill width
PILL_MAXW = 280     # maximum pill width
PILL_GAP  = 12      # gap between pills
PILL_FONT = 12      # font inside pill

LBL_COL_W = 240     # left "Process Step" column width
ROW_PAD_V = 18      # top+bottom padding inside each row
ROW_DIVIDER_COLOR = "#C8E6C9"
SEC_HDR_H = 58
COL_HDR_H = 40

def _pill_width(text, draw):
    f = _font(PILL_FONT)
    try:
        bb = draw.textbbox((0,0), text, font=f)
        return min(PILL_MAXW, max(PILL_MINW, bb[2]-bb[0] + 28))
    except Exception:
        return max(PILL_MINW, len(text)*8 + 28)

def _draw_controls_grid(draw, canvas_w, y, privacy_controls, nodes):
    """
    Draw professional 2-column privacy controls grid.
    Left column: process step name
    Right column: green pills in rows
    Returns new y.
    """
    if not privacy_controls: return y

    node_labels = {n["id"]: n.get("label", n["id"]) for n in nodes}
    rows = [(nid, node_labels.get(nid, nid), ctrls)
            for nid, ctrls in privacy_controls.items()
            if ctrls and node_labels.get(nid)]
    if not rows: return y

    PAD   = 48
    TW    = canvas_w - PAD * 2          # total table width
    PILLS_W = TW - LBL_COL_W - 1       # right column width

    # Section header
    draw.rectangle([PAD, y, canvas_w-PAD, y+SEC_HDR_H], fill="#1A6B3A")
    draw.text((PAD+20, y+17),
              "Privacy Controls by Process Step",
              font=_font(17, bold=True), fill="#FFFFFF")
    y += SEC_HDR_H

    # Column header row
    draw.rectangle([PAD, y, canvas_w-PAD, y+COL_HDR_H], fill="#E8F5E9")
    draw.line([(PAD, y+COL_HDR_H), (canvas_w-PAD, y+COL_HDR_H)],
              fill="#A5D6A7", width=1)
    draw.text((PAD+14, y+11), "Process Step / Node",
              font=_font(13, bold=True), fill="#1A5C34")
    draw.text((PAD+LBL_COL_W+16, y+11), "Privacy Controls Applied",
              font=_font(13, bold=True), fill="#1A5C34")
    y += COL_HDR_H

    for ri, (nid, node_lbl, ctrls) in enumerate(rows):
        # Calculate how many pill-rows needed
        pills = ctrls[:8]
        # First pass: measure row height
        px = PAD + LBL_COL_W + 16
        col_count = 0
        pill_rows = 1
        for ctrl in pills:
            pw = _pill_width(ctrl[:24], draw)
            if px + pw > canvas_w - PAD - 8:
                pill_rows += 1
                px = PAD + LBL_COL_W + 16
                col_count = 0
            px += pw + PILL_GAP
            col_count += 1

        row_h = ROW_PAD_V * 2 + pill_rows * (PILL_H + PILL_GAP) - PILL_GAP

        # Row background (alternating)
        row_bg = "#FFFFFF" if ri % 2 == 0 else "#F5FBF5"
        draw.rectangle([PAD, y, canvas_w-PAD, y+row_h], fill=row_bg)

        # Bottom border
        draw.line([(PAD, y+row_h), (canvas_w-PAD, y+row_h)],
                  fill=ROW_DIVIDER_COLOR, width=1)

        # Left column: node label  (vertically centred)
        lbl_lines = textwrap.wrap(node_lbl, 18)[:2]
        lbl_text  = "\n".join(lbl_lines)
        text_h    = len(lbl_lines) * 20
        lbl_y     = y + (row_h - text_h) // 2
        draw.text((PAD+14, lbl_y), lbl_text,
                  font=_font(13, bold=True), fill="#2C3E50")

        # Vertical divider
        draw.line([(PAD+LBL_COL_W, y), (PAD+LBL_COL_W, y+row_h)],
                  fill=ROW_DIVIDER_COLOR, width=1)

        # Right column: pills
        px   = PAD + LBL_COL_W + 16
        py   = y + ROW_PAD_V
        for ctrl in pills:
            text = ctrl[:24]
            pw   = _pill_width(text, draw)
            if px + pw > canvas_w - PAD - 8:
                px  = PAD + LBL_COL_W + 16
                py += PILL_H + PILL_GAP

            # Pill background
            draw.rounded_rectangle(
                [px, py, px+pw, py+PILL_H],
                radius=PILL_R,
                fill="#D5E8D4", outline="#2E8B57", width=1
            )
            # Centre text vertically in pill
            f  = _font(PILL_FONT)
            try:
                bb  = draw.textbbox((0,0), text, font=f)
                tw  = bb[2]-bb[0]
                th  = bb[3]-bb[1]
            except Exception:
                tw, th = len(text)*7, 14
            tx = px + (pw - tw) // 2
            ty = py + (PILL_H - th) // 2
            draw.text((tx, ty), text, font=f, fill="#145A32")
            px += pw + PILL_GAP

        y += row_h

    draw.line([(PAD, y), (canvas_w-PAD, y)], fill="#A5D6A7", width=2)
    return y + 24


# ── PIL composition ───────────────────────────────────────────────────────────
HEADER_H = 84
BANNER_H = 54
LEG_H    = 48
PAD      = 48

def _compose(graph_png: bytes, title: str, state: str,
             banner_text: str, banner_color: str,
             privacy_controls=None, nodes=None) -> Image.Image:

    g = Image.open(io.BytesIO(graph_png)).convert("RGB")
    MIN_W = 3200
    if g.width < MIN_W:
        sc = MIN_W / g.width
        g  = g.resize((int(g.width*sc), int(g.height*sc)), Image.LANCZOS)

    W = g.width + PAD * 2

    # Estimate canvas height
    ctrl_h = 0
    if state == "future" and privacy_controls and nodes:
        node_ids = {n["id"] for n in nodes}
        n_rows = sum(1 for nid, ctrls in privacy_controls.items()
                     if ctrls and nid in node_ids)
        ctrl_h = SEC_HDR_H + COL_HDR_H + n_rows * (ROW_PAD_V*2 + PILL_H + PILL_GAP + 20) + 60

    H = HEADER_H + BANNER_H + g.height + LEG_H + ctrl_h + 40

    canvas = Image.new("RGB", (W, H), "#FFFFFF")
    draw   = ImageDraw.Draw(canvas)

    # Header
    draw.rectangle([0, 0, W, HEADER_H], fill="#1A3A5C")
    draw.rectangle([16, 14, 100, HEADER_H-14], fill="#2470A0", outline="#154C80", width=2)
    draw.text((22, 20), "PRIVACY\nTOOL", font=_font(12, bold=True), fill="#FFFFFF")
    draw.text((116, 10), title, font=_font(30, bold=True), fill="#FFFFFF")
    draw.text((117, 52), "Data Flow Analysis  ·  Privacy & Data Protection Review",
              font=_font(15), fill="#93C6E7")

    # Banner
    draw.rectangle([0, HEADER_H, W, HEADER_H+BANNER_H], fill=banner_color)
    draw.text((PAD, HEADER_H+15), "◼  "+banner_text,
              font=_font(20, bold=True), fill="#FFFFFF")

    # Diagram
    canvas.paste(g, (PAD, HEADER_H+BANNER_H))

    # Legend
    ly = HEADER_H + BANNER_H + g.height + 6
    draw.rectangle([0, ly, W, ly+LEG_H], fill="#F4F6F8")
    draw.line([(0, ly), (W, ly)], fill="#CCCCCC", width=1)
    items = [
        ("#FFF5CC","#A07800","External Entity"),
        ("#FADADD","#B03030","Internal Team"),
        ("#FFFFFF","#555555","Process Step"),
        ("#C0392B","#8B2222","Decision / Endpoint"),
        ("#D4E8FA","#1A5276","Data Store"),
        ("#D5E8D4","#27AE60","Privacy Control"),
    ]
    lx = PAD
    for fill, stroke, lbl in items:
        draw.rounded_rectangle([lx, ly+13, lx+22, ly+33],
                               radius=4, fill=fill, outline=stroke, width=1)
        draw.text((lx+28, ly+14), lbl, font=_font(12), fill="#444444")
        lx += 192

    # Privacy controls grid
    if state == "future" and privacy_controls and nodes:
        ctrl_y = ly + LEG_H + 16
        end_y  = _draw_controls_grid(draw, W, ctrl_y, privacy_controls, nodes)
        canvas = canvas.crop((0, 0, W, end_y + 28))

    return canvas


def _to_png(img):
    buf = io.BytesIO(); img.save(buf, format="PNG", dpi=(250,250)); return buf.getvalue()

def _to_pdf(img):
    buf = io.BytesIO(); img.save(buf, format="PDF", resolution=250); return buf.getvalue()


# ── Public API ────────────────────────────────────────────────────────────────
def render_dfd(dfd_data: dict) -> tuple:
    title  = dfd_data.get("process_name", "Data Flow Diagram")
    asis   = dfd_data.get("asis",   {"nodes":[], "edges":[]})
    future = dfd_data.get("future", {"nodes":[], "edges":[]})
    ctrls  = dfd_data.get("privacy_controls", {})

    a_raw  = _build_flow(asis)
    f_raw  = _build_flow(future)

    asis_img   = _compose(a_raw, title, "asis",   "Current State", "#C0392B")
    future_img = _compose(f_raw, title, "future",
                          "Post Compliance  ·  Privacy-Embedded Future State", "#1A6B3A",
                          privacy_controls=ctrls, nodes=future.get("nodes",[]))

    return _to_png(asis_img), _to_pdf(asis_img), _to_png(future_img), _to_pdf(future_img)


DFD_JSON_SCHEMA = '''
Return ONLY a valid JSON array with exactly ONE element. No markdown. No text before or after.

[{"id":"P001","process_name":"Name ≤50 chars",
  "asis":{"nodes":[...],"edges":[...]},
  "future":{"nodes":[...],"edges":[...]},
  "privacy_controls":{"node_id":["Control A","Control B","Control C","Control D"]},
  "narrative":"3-5 sentences."}]

NODE: {"id":"snake_id","label":"≤14 chars","type":"external|team|process|decision|endpoint|datastore","phase":"collection|processing|storage|sharing|exit"}
EDGE: {"from":"id","to":"id","label":"≤13 chars"}
PRIVACY CONTROLS: up to 5 per node, ≤22 chars each.
RULES: Min 12 nodes+edges. future node IDs = same as asis. All edge IDs must exist.
'''
