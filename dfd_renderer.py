"""
dfd_renderer.py
===============
Professional DFD renderer matching the RateGain / Protiviti HR Data Flow style.

Produces TWO stacked diagrams per process:
  - Current State (As-Is)  — red banner, no privacy controls
  - Post Compliance (Future State) — green banner, green privacy control annotations

Output: PNG + PDF via PIL composition.
"""

import io
import re
import textwrap
import graphviz
from PIL import Image, ImageDraw, ImageFont

# ── Font paths ────────────────────────────────────────────────────────────────
_FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def _font(size, bold=False):
    try:
        return ImageFont.truetype(_FONT_BOLD if bold else _FONT_REG, size)
    except Exception:
        return ImageFont.load_default()

# ── Color palette ─────────────────────────────────────────────────────────────
C = {
    "bg":           "#FFFFFF",
    "border":       "#CCCCCC",
    # Node types
    "ext_fill":     "#FFF3CD",   # beige  — external entities / data subjects
    "ext_stroke":   "#856404",
    "ext_font":     "#533F03",
    "team_fill":    "#FADBD8",   # pink   — internal teams / departments
    "team_stroke":  "#922B21",
    "team_font":    "#641E16",
    "proc_fill":    "#FFFFFF",   # white  — process steps
    "proc_stroke":  "#444444",
    "proc_font":    "#212529",
    "dec_fill":     "#C0392B",   # red    — decisions / gates
    "dec_stroke":   "#922B21",
    "dec_font":     "#FFFFFF",
    "end_fill":     "#C0392B",   # red    — endpoints (hired / offboarded)
    "end_stroke":   "#7B241C",
    "end_font":     "#FFFFFF",
    "store_fill":   "#D6EAF8",   # blue   — data stores / systems
    "store_stroke": "#1A5276",
    "store_font":   "#1A5276",
    "ctrl_fill":    "#D5E8D4",   # green  — privacy controls (future state)
    "ctrl_stroke":  "#27AE60",
    "ctrl_font":    "#145A32",
    # Banners
    "banner_asis":    "#C0392B",   # red
    "banner_future":  "#1E8449",   # green
    "banner_font":    "#FFFFFF",
    # Title header
    "header_bg":      "#1A3A5C",
    "header_font":    "#FFFFFF",
    # Legend bg
    "legend_bg":      "#F8F9FA",
    # Edge
    "edge":           "#555555",
    "edge_lbl":       "#444444",
    "ctrl_edge":      "#27AE60",
    "annotation":     "#0D6EFD",   # blue annotation text
}

# ── Graphviz node styles ──────────────────────────────────────────────────────

def _node_attrs(ntype: str, label: str) -> dict:
    """Return Graphviz node attributes for a given node type."""
    label_wrapped = _wrap_label(label, 18)
    base = {"fontname": "Helvetica", "fontsize": "9", "margin": "0.18,0.10"}

    if ntype == "external":
        return {**base, "label": label_wrapped, "shape": "box",
                "style": "filled,rounded", "fillcolor": C["ext_fill"],
                "color": C["ext_stroke"], "fontcolor": C["ext_font"],
                "fontname": "Helvetica Bold"}
    if ntype == "team":
        return {**base, "label": label_wrapped, "shape": "box",
                "style": "filled", "fillcolor": C["team_fill"],
                "color": C["team_stroke"], "fontcolor": C["team_font"],
                "fontname": "Helvetica Bold"}
    if ntype == "decision":
        return {**base, "label": label_wrapped, "shape": "diamond",
                "style": "filled", "fillcolor": C["dec_fill"],
                "color": C["dec_stroke"], "fontcolor": C["dec_font"],
                "fontname": "Helvetica Bold", "fontsize": "8"}
    if ntype == "endpoint":
        return {**base, "label": label_wrapped, "shape": "ellipse",
                "style": "filled", "fillcolor": C["end_fill"],
                "color": C["end_stroke"], "fontcolor": C["end_font"],
                "fontname": "Helvetica Bold"}
    if ntype == "datastore":
        return {**base, "label": label_wrapped, "shape": "cylinder",
                "style": "filled", "fillcolor": C["store_fill"],
                "color": C["store_stroke"], "fontcolor": C["store_font"]}
    if ntype == "privacy":
        return {**base, "label": label_wrapped, "shape": "box",
                "style": "filled,rounded", "fillcolor": C["ctrl_fill"],
                "color": C["ctrl_stroke"], "fontcolor": C["ctrl_font"],
                "fontsize": "8", "margin": "0.12,0.07"}
    # default: process
    return {**base, "label": label_wrapped, "shape": "box",
            "style": "filled", "fillcolor": C["proc_fill"],
            "color": C["proc_stroke"], "fontcolor": C["proc_font"]}


def _wrap_label(text: str, width: int = 18) -> str:
    lines = textwrap.wrap(str(text).strip(), width=width)
    return "\\n".join(lines) if lines else text


def _sid(s: str) -> str:
    """Sanitize node ID."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(s))[:40]


# ── Build one Graphviz diagram ────────────────────────────────────────────────

def _build_graph(state_data: dict, state_type: str, process_name: str,
                 privacy_controls: dict = None) -> bytes:
    """
    Build and render one Graphviz diagram (As-Is or Future State).
    Returns PNG bytes.
    """
    dot = graphviz.Digraph(engine="dot")
    dot.attr("graph",
        bgcolor     = C["bg"],
        rankdir     = "LR",
        splines     = "ortho",
        nodesep     = "0.55",
        ranksep     = "1.1",
        pad         = "0.5",
        fontname    = "Helvetica",
        fontsize    = "10",
    )
    dot.attr("edge",
        fontname  = "Helvetica",
        fontsize  = "8",
        color     = C["edge"],
        fontcolor = C["edge_lbl"],
        arrowsize = "0.7",
    )

    nodes = state_data.get("nodes", [])
    edges = state_data.get("edges", [])

    # ── Group nodes by phase for rank=same columns ────────────────────────────
    phase_groups: dict = {}
    for n in nodes:
        ph = n.get("phase", "main")
        phase_groups.setdefault(ph, []).append(n)

    # Add nodes (inside rank-same subgraphs for column layout)
    for ph_idx, (ph_name, ph_nodes) in enumerate(phase_groups.items()):
        with dot.subgraph() as sg:
            sg.attr(rank="same")
            for node in ph_nodes:
                nid   = _sid(node["id"])
                ntype = node.get("type", "process")
                label = node.get("label", nid)
                sg.node(nid, **_node_attrs(ntype, label))

    # ── Privacy controls (future state only) ─────────────────────────────────
    if state_type == "future" and privacy_controls:
        for node_id, controls in privacy_controls.items():
            if not controls:
                continue
            parent_id = _sid(node_id)
            # Group all controls in a subgraph
            with dot.subgraph() as sg:
                sg.attr(rank="same")
                for i, ctrl in enumerate(controls[:4]):   # max 4 per node
                    ctrl_id = f"{parent_id}_c{i}"
                    sg.node(ctrl_id, **_node_attrs("privacy", ctrl))
                    dot.edge(parent_id, ctrl_id,
                             style     = "dashed",
                             color     = C["ctrl_edge"],
                             arrowhead = "none",
                             arrowsize = "0.4",
                             penwidth  = "0.8")

    # ── Edges ─────────────────────────────────────────────────────────────────
    for edge in edges:
        src = _sid(edge.get("from", ""))
        dst = _sid(edge.get("to", ""))
        lbl = edge.get("label", "").strip()
        if not src or not dst:
            continue
        attrs = {}
        if lbl:
            attrs["xlabel"] = f" {lbl} "
        # Colour-code sensitive flows
        if any(kw in lbl.lower() for kw in ["health", "biometric", "sensitive", "special", "medical", "salary", "financial", "bank"]):
            attrs["color"]     = "#E74C3C"
            attrs["fontcolor"] = "#E74C3C"
            attrs["penwidth"]  = "1.8"
        dot.edge(src, dst, **attrs)

    return dot.pipe(format="png")


# ── PIL composition ───────────────────────────────────────────────────────────

BANNER_H    = 38
HEADER_H    = 64
LEGEND_H    = 44
DESC_H      = 64    # description text area under each banner
SIDE_PAD    = 30

def _draw_rounded_rect(draw, xy, radius=8, fill=None, outline=None, width=1):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius,
                            fill=fill, outline=outline, width=width)


def _compose(asis_png: bytes, future_png: bytes, process_name: str,
             asis_description: str, future_description: str) -> Image.Image:
    """Compose As-Is + Future State into one professional A3-landscape image."""

    img_a = Image.open(io.BytesIO(asis_png)).convert("RGB")
    img_f = Image.open(io.BytesIO(future_png)).convert("RGB")

    # Scale images to same width
    target_w = max(img_a.width, img_f.width, 1800)

    def _scale(img, w):
        if img.width == w:
            return img
        ratio = w / img.width
        return img.resize((w, int(img.height * ratio)), Image.LANCZOS)

    img_a = _scale(img_a, target_w)
    img_f = _scale(img_f, target_w)

    canvas_w = target_w + SIDE_PAD * 2
    canvas_h = (HEADER_H + BANNER_H + DESC_H + img_a.height +
                BANNER_H + DESC_H + img_f.height + LEGEND_H + 30)

    canvas = Image.new("RGB", (canvas_w, canvas_h), C["bg"])
    draw   = ImageDraw.Draw(canvas)

    # ── Header ────────────────────────────────────────────────────────────────
    draw.rectangle([0, 0, canvas_w, HEADER_H], fill=C["header_bg"])
    # Small logo box
    draw.rectangle([12, 10, 70, HEADER_H - 10], fill="#2E86C1", outline="#1A5276")
    draw.text((18, 18), "PRIVACY\nTOOL", font=_font(9, bold=True), fill="white")
    # Title
    draw.text((82, 14), process_name, font=_font(20, bold=True), fill=C["header_font"])
    draw.text((82, 42), "Data Flow Analysis: Current State vs Privacy-Embedded Future State",
              font=_font(11), fill="#AED6F1")

    y = HEADER_H

    def _section(y_start, label, bg_color, description):
        """Draw a section banner + description text. Returns new y."""
        # Banner
        draw.rectangle([0, y_start, canvas_w, y_start + BANNER_H], fill=bg_color)
        draw.text((SIDE_PAD, y_start + 10), label,
                  font=_font(13, bold=True), fill=C["banner_font"])
        y = y_start + BANNER_H
        # Description background
        draw.rectangle([0, y, canvas_w, y + DESC_H], fill="#FDFEFE")
        draw.line([(0, y + DESC_H), (canvas_w, y + DESC_H)], fill=C["border"], width=1)
        # Wrap and draw description
        lines = textwrap.wrap(description, width=180)
        ty = y + 8
        for line in lines[:3]:
            draw.text((SIDE_PAD, ty), line, font=_font(10), fill="#555555")
            ty += 16
        return y + DESC_H

    # ── As-Is section ─────────────────────────────────────────────────────────
    y = _section(y, "  ◼  Current State", C["banner_asis"], asis_description)
    canvas.paste(img_a, (SIDE_PAD, y))
    y += img_a.height + 4

    # ── Future section ────────────────────────────────────────────────────────
    y = _section(y, "  ◼  Post Compliance (Privacy-Embedded Future State)",
                 C["banner_future"], future_description)
    canvas.paste(img_f, (SIDE_PAD, y))
    y += img_f.height + 4

    # ── Legend ────────────────────────────────────────────────────────────────
    draw.rectangle([0, y, canvas_w, y + LEGEND_H], fill=C["legend_bg"])
    draw.line([(0, y), (canvas_w, y)], fill=C["border"], width=1)

    lx, ly = SIDE_PAD, y + 12
    legend_items = [
        (C["ext_fill"],   C["ext_stroke"],   "External Entity"),
        (C["team_fill"],  C["team_stroke"],  "Internal Team"),
        (C["proc_fill"],  C["proc_stroke"],  "Process"),
        (C["dec_fill"],   C["dec_stroke"],   "Decision Gate"),
        (C["end_fill"],   C["end_stroke"],   "Endpoint"),
        (C["store_fill"], C["store_stroke"], "Data Store"),
        (C["ctrl_fill"],  C["ctrl_stroke"],  "Privacy Control"),
    ]
    for fill, stroke, label in legend_items:
        draw.rectangle([lx, ly, lx + 18, ly + 14], fill=fill, outline=stroke)
        draw.text((lx + 22, ly), label, font=_font(9), fill="#333333")
        lx += 145

    return canvas


def _image_to_pdf(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=150)
    return buf.getvalue()


# ── Public API ────────────────────────────────────────────────────────────────

def render_dfd(dfd_data: dict) -> tuple:
    """
    Render a professional two-state DFD.
    Returns (png_bytes, pdf_bytes).

    dfd_data keys:
      process_name, asis, future, privacy_controls, narrative,
      asis_description, future_description
    """
    process_name      = dfd_data.get("process_name", "Data Flow Diagram")
    asis_data         = dfd_data.get("asis", {"nodes": [], "edges": []})
    future_data       = dfd_data.get("future", {"nodes": [], "edges": []})
    privacy_controls  = dfd_data.get("privacy_controls", {})
    asis_desc         = dfd_data.get("asis_description",
        "Current operational state — personal data may be processed without formal privacy governance or structured safeguards.")
    future_desc       = dfd_data.get("future_description",
        "Privacy-embedded future state incorporating consent management, encryption, access controls, and data minimisation.")

    asis_png   = _build_graph(asis_data,   "asis",   process_name)
    future_png = _build_graph(future_data, "future", process_name, privacy_controls)

    composed   = _compose(asis_png, future_png, process_name, asis_desc, future_desc)

    # PNG
    png_buf = io.BytesIO()
    composed.save(png_buf, format="PNG", dpi=(150, 150))
    png_bytes = png_buf.getvalue()

    # PDF
    pdf_bytes = _image_to_pdf(composed)

    return png_bytes, pdf_bytes


# ── AI JSON schema (used in prompts.py) ──────────────────────────────────────

DFD_JSON_SCHEMA = '''
Return ONLY a valid JSON array. No markdown fences. No commentary.
Each element represents one ROPA processing activity:

{
  "id": "P001",
  "process_name": "Concise name (max 50 chars)",
  "asis_description": "2-sentence description of the current uncontrolled state.",
  "future_description": "2-sentence description of the privacy-embedded future state.",

  "asis": {
    "nodes": [
      {
        "id":    "unique_id",
        "label": "Short label (max 22 chars)",
        "type":  "external|team|process|decision|endpoint|datastore",
        "phase": "phase_name"
      }
    ],
    "edges": [
      { "from": "node_id", "to": "node_id", "label": "data element (max 18 chars)" }
    ]
  },

  "future": {
    "nodes": [
      (same structure as asis — can add new nodes for enhanced controls)
    ],
    "edges": [
      (same structure as asis edges)
    ]
  },

  "privacy_controls": {
    "node_id": ["Control Label 1", "Control Label 2", "Control Label 3"]
  },

  "narrative": "3-5 sentence explanation of the data flow and privacy risks."
}

NODE TYPE GUIDE:
- external   → data subjects, job applicants, customers, regulators, external orgs
- team       → internal departments, HR team, IT team, payroll, managers
- process    → collection, review, validation, approval, reporting, settlement steps
- decision   → Shortlisted?, Retained?, Asset Required?, Consent Given?
- endpoint   → final states: Hired, Offboarded, Rejected, Record Archived
- datastore  → HRMS, email system, SharePoint, database, local files, cloud storage

PHASE GUIDE (use these exact phase names for left-to-right column layout):
  "collection" → "processing" → "storage" → "sharing" → "exit"

RULES:
- Every edge must reference node IDs that exist in the nodes array.
- Node IDs: lowercase_underscore only, max 30 chars, unique within a process.
- Use at least 12 nodes and 12 edges per diagram for a meaningful Level-1 DFD.
- Privacy controls: provide 2-4 controls per relevant process/team node.
  Use short, specific control names: "Consent Management", "Encryption at Rest",
  "Role-Based Access", "Data Minimisation", "Audit Logging", "DPA in Place",
  "Secure API Transfer", "Retention Policy", "MFA Enabled", "Privacy Notice".
'''
