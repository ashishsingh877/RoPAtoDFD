"""
dfd_renderer.py — Professional DFD Renderer v9
Matches RateGain/Protiviti reference style:
  - Clean Graphviz flow diagram
  - Privacy controls overlaid as green boxes DIRECTLY on diagram via PIL
  - Node positions computed from Graphviz JSON output
  - 250 DPI, client-ready, print-quality
"""

import io, re, json, math, textwrap, graphviz
from PIL import Image, ImageDraw, ImageFont

_FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def _font(size, bold=False):
    try:    return ImageFont.truetype(_FONT_BOLD if bold else _FONT_REG, size)
    except: return ImageFont.load_default()

def _gv_wrap(text, n=14):
    lines = textwrap.wrap(str(text).strip(), width=n)
    return "\\n".join(lines[:3]) if lines else str(text)

def _sid(s):
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(s).strip())[:35]

PHASE_ORDER  = ["collection","processing","storage","sharing","exit","main"]
PHASE_LABELS = {
    "collection": "① Data Collection",
    "processing": "② Processing & Review",
    "storage":    "③ Storage",
    "sharing":    "④ Sharing & Disclosure",
    "exit":       "⑤ Exit / Archive",
    "main":       "Processing",
}

NODE_STYLES = {
    "external":  dict(shape="box",     style="filled,rounded",
                      fillcolor="#FFF5CC", color="#A07800",
                      fontcolor="#5C4400", penwidth="1.6"),
    "team":      dict(shape="box",     style="filled",
                      fillcolor="#FADADD", color="#B03030",
                      fontcolor="#641E16", penwidth="2.0",
                      fontname="Helvetica-Bold"),
    "process":   dict(shape="box",     style="filled",
                      fillcolor="#FFFFFF", color="#555555",
                      fontcolor="#1A1A1A", penwidth="1.3"),
    "decision":  dict(shape="diamond", style="filled",
                      fillcolor="#C0392B", color="#8B2222",
                      fontcolor="#FFFFFF", penwidth="2.0",
                      fontname="Helvetica-Bold"),
    "endpoint":  dict(shape="ellipse", style="filled",
                      fillcolor="#B03030", color="#7B1A1A",
                      fontcolor="#FFFFFF", penwidth="2.0",
                      fontname="Helvetica-Bold"),
    "datastore": dict(shape="cylinder",style="filled",
                      fillcolor="#D4E8FA", color="#1A5276",
                      fontcolor="#0D3B6E", penwidth="1.6"),
}

def _nattrs(ntype, label):
    s = NODE_STYLES.get(ntype, NODE_STYLES["process"]).copy()
    s.setdefault("fontname","Helvetica")
    return {
        **s,
        "label":    _gv_wrap(label, 13),
        "fontsize": "12",
        "margin":   "0.25,0.18",
        "width":    "1.8",
        "height":   "0.70",
        "fixedsize":"false",
    }

GV_DPI = 180

def _make_dot(data: dict) -> graphviz.Digraph:
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    phase_map: dict = {}
    for n in nodes:
        ph = n.get("phase","main").lower().strip()
        if ph not in PHASE_ORDER: ph = "main"
        phase_map.setdefault(ph, []).append(n)

    dot = graphviz.Digraph(engine="dot")
    dot.attr("graph",
        bgcolor  = "white",
        rankdir  = "LR",
        splines  = "spline",
        nodesep  = "0.55",
        ranksep  = "1.2",
        pad      = "0.40",
        fontname = "Helvetica",
        compound = "true",
        size     = "28,10!",
        ratio    = "compress",
        dpi      = str(GV_DPI),
    )
    dot.attr("edge",
        fontname  = "Helvetica",
        fontsize  = "8",
        color     = "#555555",
        fontcolor = "#555555",
        arrowsize = "0.85",
        penwidth  = "1.3",
        minlen    = "2",
    )

    for ph in PHASE_ORDER:
        ph_nodes = phase_map.get(ph, [])
        if not ph_nodes: continue
        with dot.subgraph(name=f"cluster_{ph}") as sg:
            sg.attr(
                rank      = "same",
                label     = PHASE_LABELS.get(ph, ph.title()),
                labeljust = "c",
                labelloc  = "t",
                fontname  = "Helvetica-Bold",
                fontsize  = "10",
                fontcolor = "#1A3A5C",
                style     = "rounded,filled",
                fillcolor = "#F8F9FA",
                color     = "#CCCCCC",
                penwidth  = "0.8",
                margin    = "12",
            )
            for i, n in enumerate(ph_nodes):
                nid = _sid(n["id"])
                sg.node(nid, **_nattrs(n.get("type","process"), n.get("label","")))
                if i > 0:
                    dot.edge(_sid(ph_nodes[i-1]["id"]), nid,
                             style="invis", weight="10")

    for e in edges:
        src = _sid(e.get("from",""))
        dst = _sid(e.get("to",""))
        if not src or not dst: continue
        raw = e.get("label","").strip()
        lbl = (raw[:13]+"…") if len(raw)>14 else raw
        sensitive = any(k in raw.lower() for k in
            ["health","medical","biometric","salary","financial","bank",
             "sensitive","special","criminal","aadhaar","pan"])
        attrs = dict(
            color    = "#C0392B" if sensitive else "#555555",
            fontcolor= "#C0392B" if sensitive else "#666666",
            penwidth = "2.2"     if sensitive else "1.3",
        )
        if lbl:
            attrs["xlabel"]   = f"  {lbl}  "
            attrs["fontsize"] = "8"
        dot.edge(src, dst, **attrs)

    return dot


def _get_positions(dot: graphviz.Digraph, img_w: int, img_h: int) -> dict:
    """Get node center positions and sizes in PNG pixel coords."""
    raw = dot.pipe(format="json")
    gv  = json.loads(raw)

    bb_str = gv.get("bb", "0,0,100,100")
    bb     = [float(x) for x in bb_str.split(",")]
    bb_w, bb_h = bb[2], bb[3]
    if bb_w == 0 or bb_h == 0:
        return {}

    sx = img_w / bb_w   # pixels per point (x)
    sy = img_h / bb_h   # pixels per point (y)

    positions = {}
    for obj in gv.get("objects", []):
        name = obj.get("name", "")
        if not name or name.startswith("cluster"):
            continue
        pos_str = obj.get("pos", "")
        if not pos_str or "," not in pos_str:
            continue
        try:
            gx, gy = [float(v) for v in pos_str.split(",")]
        except:
            continue

        # Node size: graphviz width/height are in INCHES
        w_in = float(obj.get("width",  1.0))
        h_in = float(obj.get("height", 0.5))

        px_cx = gx * sx
        px_cy = (bb_h - gy) * sy          # flip Y
        px_w  = w_in * 72.0 * sx          # inches → pts → px
        px_h  = h_in * 72.0 * sy

        positions[name] = {
            "cx": px_cx, "cy": px_cy,
            "w":  px_w,  "h":  px_h,
            "x1": px_cx - px_w/2, "y1": px_cy - px_h/2,
            "x2": px_cx + px_w/2, "y2": px_cy + px_h/2,
        }

    return positions


def _overlay_controls(img: Image.Image, positions: dict,
                       privacy_controls: dict, nodes: list) -> Image.Image:
    """
    Overlay green privacy control boxes directly on the diagram,
    adjacent to each relevant node — matching the RateGain reference style.
    """
    img   = img.copy()
    draw  = ImageDraw.Draw(img)
    img_w, img_h = img.size

    # Scale control box sizes proportionally to image
    scale     = img_w / 3200          # reference scale
    BOX_W     = max(140, int(175 * scale))
    BOX_H     = max(24,  int(30  * scale))
    GAP_X     = max(5,   int(8   * scale))
    GAP_Y     = max(4,   int(6   * scale))
    COLS      = 2
    V_MARGIN  = max(14,  int(18  * scale))
    FONT_SZ   = max(8,   int(10  * scale))
    LINE_W    = max(1,   int(1.5 * scale))

    node_lbl = {n["id"]: n.get("label", n["id"]) for n in nodes}

    for raw_nid, controls in privacy_controls.items():
        sid = _sid(raw_nid)
        if sid not in positions or not controls:
            continue

        pos = positions[sid]
        cx   = pos["cx"];  cy = pos["cy"]
        nw   = pos["w"];   nh = pos["h"]
        y1   = pos["y1"];  y2 = pos["y2"]
        x1   = pos["x1"];  x2 = pos["x2"]

        pills = controls[:8]
        n_c   = min(COLS, len(pills))
        n_r   = math.ceil(len(pills) / n_c)

        block_w = n_c * (BOX_W + GAP_X) - GAP_X
        block_h = n_r * (BOX_H + GAP_Y) - GAP_Y

        # Choose placement: above if enough room, else below
        if y1 > block_h + V_MARGIN * 2:
            bx = cx - block_w / 2
            by = y1 - block_h - V_MARGIN
            # Connector line: from node top to block bottom
            draw.line([(int(cx), int(y1)),
                       (int(cx), int(by + block_h + 4))],
                      fill="#27AE60", width=LINE_W)
        else:
            bx = cx - block_w / 2
            by = y2 + V_MARGIN
            # Connector line: from node bottom to block top
            draw.line([(int(cx), int(y2)),
                       (int(cx), int(by - 4))],
                      fill="#27AE60", width=LINE_W)

        # Clamp block to image bounds
        if bx < 4:               bx = 4
        if bx + block_w > img_w - 4: bx = img_w - block_w - 4

        # Draw each pill
        for i, ctrl in enumerate(pills):
            r = i // n_c
            c = i  % n_c
            px = bx + c * (BOX_W + GAP_X)
            py = by + r * (BOX_H + GAP_Y)

            draw.rounded_rectangle(
                [int(px), int(py), int(px+BOX_W), int(py+BOX_H)],
                radius=max(4, int(6*scale)),
                fill="#D5E8D4", outline="#2E8B57", width=1
            )

            text = ctrl[:24]
            f    = _font(FONT_SZ)
            try:
                bb = draw.textbbox((0,0), text, font=f)
                tw, th = bb[2]-bb[0], bb[3]-bb[1]
            except:
                tw, th = len(text)*6, FONT_SZ

            draw.text(
                (int(px + (BOX_W-tw)/2),
                 int(py + (BOX_H-th)/2)),
                text, font=f, fill="#145A32"
            )

    return img


# ── PIL composition ────────────────────────────────────────────────────────────
HEADER_H = 88
BANNER_H = 52
LEG_H    = 52
PAD      = 48

def _compose(flow_png: bytes, title: str, state: str,
             banner_txt: str, banner_color: str,
             privacy_controls: dict = None,
             nodes: list = None) -> Image.Image:

    # ── Load and scale flow diagram ───────────────────────────────────────────
    g = Image.open(io.BytesIO(flow_png)).convert("RGB")
    MIN_W = 3200
    if g.width < MIN_W:
        sc = MIN_W / g.width
        g  = g.resize((int(g.width * sc), int(g.height * sc)), Image.LANCZOS)

    W = g.width + PAD * 2
    H = HEADER_H + BANNER_H + g.height + LEG_H + 24

    canvas = Image.new("RGB", (W, H), "#FFFFFF")
    draw   = ImageDraw.Draw(canvas)

    # ── Header ────────────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, HEADER_H], fill="#1A3A5C")
    # Logo tile
    draw.rectangle([14, 12, 106, HEADER_H-12],
                   fill="#2470A0", outline="#154C80", width=2)
    draw.text((20, 18), "DATA\nFLOW\nANALYSIS",
              font=_font(10, bold=True), fill="#FFFFFF")
    # Title
    draw.text((120, 10), title,
              font=_font(30, bold=True), fill="#FFFFFF")
    draw.text((121, 52),
              "Privacy & Data Protection Review  ·  DPDPA 2023 / GDPR",
              font=_font(14), fill="#93C6E7")
    # State badge top-right
    badge_txt = "CURRENT STATE" if state == "asis" else "POST COMPLIANCE"
    badge_col = "#C0392B"       if state == "asis" else "#1A6B3A"
    draw.rounded_rectangle([W-310, 16, W-14, HEADER_H-16],
                           radius=6, fill=badge_col)
    draw.text((W-297, 30), badge_txt,
              font=_font(14, bold=True), fill="#FFFFFF")

    # ── Banner ────────────────────────────────────────────────────────────────
    draw.rectangle([0, HEADER_H, W, HEADER_H+BANNER_H], fill=banner_color)
    draw.text((PAD, HEADER_H+14), "◼  " + banner_txt,
              font=_font(18, bold=True), fill="#FFFFFF")

    # ── Paste flow diagram ────────────────────────────────────────────────────
    canvas.paste(g, (PAD, HEADER_H + BANNER_H))

    # ── Legend ────────────────────────────────────────────────────────────────
    ly = HEADER_H + BANNER_H + g.height + 5
    draw.rectangle([0, ly, W, ly + LEG_H], fill="#F4F6F8")
    draw.line([(0, ly), (W, ly)], fill="#CCCCCC", width=1)
    items = [
        ("#FFF5CC","#A07800","External Entity"),
        ("#FADADD","#B03030","Internal Team"),
        ("#FFFFFF","#555555","Process Step"),
        ("#C0392B","#8B2222","Decision / Endpoint"),
        ("#D4E8FA","#1A5276","Data Store"),
        ("#D5E8D4","#2E8B57","Privacy Control"),
    ]
    lx = PAD
    for fc, sc, lb in items:
        draw.rounded_rectangle([lx, ly+14, lx+20, ly+32],
                               radius=4, fill=fc, outline=sc, width=1)
        draw.text((lx+26, ly+15), lb, font=_font(11), fill="#444444")
        lx += 188
    draw.text((PAD, ly+LEG_H-16),
              "⚠  Red arrows = sensitive / special category data flows",
              font=_font(9), fill="#C0392B")

    return canvas


def render_dfd(dfd_data: dict) -> tuple:
    """
    Returns (asis_png, asis_pdf, future_png, future_pdf).
    Post-compliance: green privacy controls overlaid DIRECTLY on diagram near each node.
    """
    title  = dfd_data.get("process_name", "Data Flow Diagram")
    asis   = dfd_data.get("asis",   {"nodes":[], "edges":[]})
    future = dfd_data.get("future", {"nodes":[], "edges":[]})
    ctrls  = dfd_data.get("privacy_controls", {})

    def _to_png(img):
        b = io.BytesIO(); img.save(b, format="PNG", dpi=(250,250)); return b.getvalue()
    def _to_pdf(img):
        b = io.BytesIO(); img.save(b, format="PDF", resolution=250); return b.getvalue()

    # ── Current State (clean flow) ─────────────────────────────────────────────
    dot_a    = _make_dot(asis)
    png_a    = dot_a.pipe(format="png")
    asis_img = _compose(png_a, title, "asis",
                        "Current State  ·  Existing Data Flows (Without Privacy Controls)",
                        "#C0392B")

    # ── Post Compliance (flow + overlaid green control boxes) ─────────────────
    TOP_PAD = 260  # pixels of white space above diagram for control boxes
    BOT_PAD = 80

    dot_f    = _make_dot(future)
    raw_png  = dot_f.pipe(format="png")
    flow_raw = Image.open(io.BytesIO(raw_png)).convert("RGB")
    orig_w, orig_h = flow_raw.size

    # Create padded canvas with white space above/below
    padded = Image.new("RGB", (orig_w, orig_h + TOP_PAD + BOT_PAD), "#FFFFFF")
    padded.paste(flow_raw, (0, TOP_PAD))

    # Get positions from original image dimensions, then offset Y by TOP_PAD
    positions = _get_positions(dot_f, orig_w, orig_h)
    for k in positions:
        positions[k]["cy"] += TOP_PAD
        positions[k]["y1"] += TOP_PAD
        positions[k]["y2"] += TOP_PAD

    # Overlay controls
    annotated = _overlay_controls(padded, positions, ctrls, future.get("nodes", []))

    # Save to bytes for compose
    buf = io.BytesIO(); annotated.save(buf, format="PNG"); buf.seek(0)
    png_f_annotated = buf.getvalue()

    future_img = _compose(png_f_annotated, title, "future",
                          "Post Compliance  ·  Privacy-Embedded Future State",
                          "#1A6B3A")

    return _to_png(asis_img), _to_pdf(asis_img), _to_png(future_img), _to_pdf(future_img)


# ── AI schema ─────────────────────────────────────────────────────────────────
DFD_JSON_SCHEMA = '''
Return ONLY a valid JSON array with exactly ONE element. No markdown. No text before or after.

[{"id":"P001","process_name":"Name ≤50 chars",
  "asis":{"nodes":[...],"edges":[...]},
  "future":{"nodes":[...],"edges":[...]},
  "privacy_controls":{"node_id":["Control 1","Control 2","Control 3","Control 4"]},
  "narrative":"3-5 sentences."}]

NODE: {"id":"snake_id","label":"≤13 chars","type":"external|team|process|decision|endpoint|datastore","phase":"collection|processing|storage|sharing|exit"}
EDGE: {"from":"id","to":"id","label":"≤13 chars"}

TYPES: external=people/orgs outside; team=internal depts; process=action steps;
       decision=yes/no gates (red diamond); endpoint=final states (red oval); datastore=storage systems
PHASES (strict L→R): collection → processing → storage → sharing → exit

PRIVACY CONTROLS (future state): 3-5 per node, ≤22 chars each.
  These appear as green boxes DIRECTLY ON the diagram near each node.
  Be specific: "MFA for HRMS Login" not "Security"; "DPA with BGV Vendor" not "Agreement"
RULES: Min 12 nodes+12 edges. future node IDs=same as asis. All edge IDs must exist.
'''
