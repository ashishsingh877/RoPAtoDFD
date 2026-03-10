"""
dfd_renderer.py
===============
Renders TWO separate professional landscape DFD images per process:
  1. Current State (As-Is)     — red banner
  2. Post Compliance (Future)  — green banner

No description text. No narrative. Clean diagram only.
"""

import io, re, textwrap, graphviz
from PIL import Image, ImageDraw, ImageFont

_FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def _font(size, bold=False):
    try:    return ImageFont.truetype(_FONT_BOLD if bold else _FONT_REG, size)
    except: return ImageFont.load_default()

# ── Node styles ───────────────────────────────────────────────────────────────

def _node_attrs(ntype: str, label: str) -> dict:
    label_w = _wrap(label, 16)
    base = {"fontname": "Helvetica", "fontsize": "10", "margin": "0.22,0.14"}
    styles = {
        "external":  dict(shape="box",      style="filled,rounded", fillcolor="#FFF3CD", color="#856404", fontcolor="#533F03", fontname="Helvetica Bold"),
        "team":      dict(shape="box",      style="filled",         fillcolor="#FADBD8", color="#922B21", fontcolor="#641E16", fontname="Helvetica Bold"),
        "process":   dict(shape="box",      style="filled",         fillcolor="#FFFFFF", color="#444444", fontcolor="#212529"),
        "decision":  dict(shape="diamond",  style="filled",         fillcolor="#C0392B", color="#922B21", fontcolor="#FFFFFF", fontname="Helvetica Bold", fontsize="9"),
        "endpoint":  dict(shape="ellipse",  style="filled",         fillcolor="#C0392B", color="#7B241C", fontcolor="#FFFFFF", fontname="Helvetica Bold"),
        "datastore": dict(shape="cylinder", style="filled",         fillcolor="#D6EAF8", color="#1A5276", fontcolor="#1A5276"),
        "privacy":   dict(shape="box",      style="filled,rounded", fillcolor="#D5E8D4", color="#27AE60", fontcolor="#145A32", fontsize="9", margin="0.14,0.08"),
    }
    s = styles.get(ntype, styles["process"])
    return {**base, **s, "label": label_w}

def _wrap(text: str, w: int = 16) -> str:
    lines = textwrap.wrap(str(text).strip(), width=w)
    return "\\n".join(lines) if lines else text

def _sid(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(s).strip())[:35]

# ── Build one Graphviz graph ──────────────────────────────────────────────────

def _build(data: dict, state: str, privacy_controls: dict = None) -> bytes:
    dot = graphviz.Digraph(engine="dot")
    dot.attr("graph",
        bgcolor="white", rankdir="LR", splines="ortho",
        nodesep="0.6", ranksep="1.2", pad="0.6",
        fontname="Helvetica", fontsize="11",
    )
    dot.attr("edge",
        fontname="Helvetica", fontsize="8",
        color="#555555", fontcolor="#444444", arrowsize="0.75",
    )

    # Group nodes by phase for rank=same columns
    phases: dict = {}
    for n in data.get("nodes", []):
        ph = n.get("phase", "main")
        phases.setdefault(ph, []).append(n)

    for ph_name, ph_nodes in phases.items():
        with dot.subgraph() as sg:
            sg.attr(rank="same")
            for n in ph_nodes:
                dot.node(_sid(n["id"]), **_node_attrs(n.get("type","process"), n.get("label", n["id"])))

    # Privacy controls (future only) — dashed green links
    if state == "future" and privacy_controls:
        for node_id, controls in privacy_controls.items():
            pid = _sid(node_id)
            for i, ctrl in enumerate(controls[:4]):
                cid = f"{pid}_c{i}"
                dot.node(cid, **_node_attrs("privacy", ctrl))
                dot.edge(pid, cid, style="dashed", color="#27AE60",
                         arrowhead="none", arrowsize="0.4", penwidth="0.8")

    # Edges
    for e in data.get("edges", []):
        src, dst = _sid(e.get("from","")), _sid(e.get("to",""))
        if not src or not dst: continue
        lbl = e.get("label","").strip()
        attrs = {"xlabel": f" {lbl} "} if lbl else {}
        sensitive = any(k in lbl.lower() for k in ["health","medical","biometric","salary","financial","bank","special","sensitive"])
        if sensitive:
            attrs.update(color="#E74C3C", fontcolor="#E74C3C", penwidth="2.0")
        dot.edge(src, dst, **attrs)

    return dot.pipe(format="png")

# ── PIL: add banner only ──────────────────────────────────────────────────────

BANNER_H = 44
HEADER_H = 60
LOGO_W   = 72
PAD      = 28

def _compose_single(graph_png: bytes, title: str, state: str) -> Image.Image:
    """Wrap a graph PNG with header + coloured banner. Landscape."""
    g = Image.open(io.BytesIO(graph_png)).convert("RGB")

    # Ensure minimum landscape width
    min_w = 1600
    if g.width < min_w:
        scale = min_w / g.width
        g = g.resize((min_w, int(g.height * scale)), Image.LANCZOS)

    W = g.width + PAD * 2
    H = HEADER_H + BANNER_H + g.height + PAD

    canvas = Image.new("RGB", (W, H), "white")
    draw   = ImageDraw.Draw(canvas)

    # ── Header bar ────────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, HEADER_H], fill="#1A3A5C")
    # Logo box
    draw.rectangle([10, 8, 10+LOGO_W-4, HEADER_H-8], fill="#2E86C1", outline="#1A5276", width=1)
    draw.text((16, 14), "PRIVACY\nTOOL", font=_font(9, bold=True), fill="white")
    # Title
    draw.text((LOGO_W + 20, 12), title, font=_font(20, bold=True), fill="white")
    draw.text((LOGO_W + 20, 38), "Data Flow Analysis — Privacy & Data Protection Review",
              font=_font(10), fill="#AED6F1")

    # ── Coloured banner ───────────────────────────────────────────────────────
    if state == "asis":
        banner_color, label = "#C0392B", "  ◼  Current State"
    else:
        banner_color, label = "#1E8449", "  ◼  Post Compliance  (Privacy-Embedded Future State)"

    draw.rectangle([0, HEADER_H, W, HEADER_H + BANNER_H], fill=banner_color)
    draw.text((PAD, HEADER_H + 11), label, font=_font(14, bold=True), fill="white")

    # ── Diagram ───────────────────────────────────────────────────────────────
    canvas.paste(g, (PAD, HEADER_H + BANNER_H))

    # ── Legend strip ─────────────────────────────────────────────────────────
    # (embedded inside bottom of diagram area — just a thin row)
    legend_y = HEADER_H + BANNER_H + g.height - 28
    draw.rectangle([PAD, legend_y, W - PAD, legend_y + 24], fill="#F8F9FA", outline="#DDDDDD")
    items = [
        ("#FFF3CD","#856404","External Entity"),
        ("#FADBD8","#922B21","Internal Team"),
        ("#FFFFFF","#444444","Process"),
        ("#C0392B","#7B241C","Decision / Endpoint"),
        ("#D6EAF8","#1A5276","Data Store"),
        ("#D5E8D4","#27AE60","Privacy Control"),
    ]
    lx = PAD + 8
    for fill, stroke, lbl in items:
        draw.rectangle([lx, legend_y+6, lx+14, legend_y+18], fill=fill, outline=stroke, width=1)
        draw.text((lx+18, legend_y+6), lbl, font=_font(8), fill="#333333")
        lx += 130

    return canvas

def _to_pdf(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=150)
    return buf.getvalue()

def _to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(150,150))
    return buf.getvalue()

# ── Public API ────────────────────────────────────────────────────────────────

def render_dfd(dfd_data: dict) -> tuple:
    """
    Returns (asis_png, asis_pdf, future_png, future_pdf).
    Each is a separate landscape image — Current State and Post Compliance.
    """
    title            = dfd_data.get("process_name", "Data Flow Diagram")
    asis_data        = dfd_data.get("asis",   {"nodes":[], "edges":[]})
    future_data      = dfd_data.get("future", {"nodes":[], "edges":[]})
    privacy_controls = dfd_data.get("privacy_controls", {})

    asis_graph_png   = _build(asis_data,   "asis")
    future_graph_png = _build(future_data, "future", privacy_controls)

    asis_img   = _compose_single(asis_graph_png,   title, "asis")
    future_img = _compose_single(future_graph_png, title, "future")

    return _to_png(asis_img), _to_pdf(asis_img), _to_png(future_img), _to_pdf(future_img)


# ── AI JSON schema ────────────────────────────────────────────────────────────

DFD_JSON_SCHEMA = '''
Return ONLY a valid JSON array. No markdown. No commentary.

[
  {
    "id": "P001",
    "process_name": "Short process name (max 50 chars)",
    "asis":   { "nodes": [...], "edges": [...] },
    "future": { "nodes": [...], "edges": [...] },
    "privacy_controls": { "node_id": ["Control 1", "Control 2", "Control 3"] },
    "narrative": "3-5 sentence summary."
  }
]

NODE STRUCTURE:
{ "id": "unique_id", "label": "Max 18 chars", "type": "external|team|process|decision|endpoint|datastore", "phase": "collection|processing|storage|sharing|exit" }

EDGE STRUCTURE:
{ "from": "node_id", "to": "node_id", "label": "Max 16 chars" }

NODE TYPES:
- external  → data subjects, vendors, regulators, external orgs        [beige rounded]
- team      → internal HR/IT/Payroll/CSR departments                   [pink box]
- process   → collect, validate, process, report steps                  [white box]
- decision  → Shortlisted? Consent Given? Retained?                    [red diamond]
- endpoint  → Hired, Rejected, Offboarded, Archived                    [red ellipse]
- datastore → HRMS, Email, SharePoint, database, cloud storage         [blue cylinder]

PHASE (left-to-right layout columns):
  collection → processing → storage → sharing → exit

PRIVACY CONTROLS (future state only, 2-4 per key node):
  "node_id": ["Consent Management", "Encryption at Rest", "Role-Based Access", "Audit Logging"]
  Use specific names: "DPA in Place", "MFA Enabled", "Data Minimisation",
  "Secure API Transfer", "Retention Policy", "Privacy Notice", "Vendor Due Diligence"

RULES:
- Minimum 12 nodes and 12 edges per diagram.
- All edge node IDs must exist in nodes array.
- Node IDs: lowercase_underscore, max 30 chars, unique per process.
- future nodes = same as asis nodes (same IDs) — privacy_controls adds the green boxes.
'''
