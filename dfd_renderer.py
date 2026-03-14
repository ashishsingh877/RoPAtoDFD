"""
dfd_renderer.py — Professional DFD Renderer v8
Clean swimlane clusters, spline edges with xlabels, 250 DPI, client-ready.
"""

import io, re, textwrap, graphviz
from PIL import Image, ImageDraw, ImageFont

_FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def _font(size, bold=False):
    try:    return ImageFont.truetype(_FONT_BOLD if bold else _FONT_REG, size)
    except: return ImageFont.load_default()

def _gv_label(text, n=14):
    lines = textwrap.wrap(str(text).strip(), width=n)
    return "\\n".join(lines[:3]) if lines else str(text)

def _sid(s):
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(s).strip())[:35]

PHASE_ORDER  = ["collection","processing","storage","sharing","exit","main"]
PHASE_LABELS = {
    "collection": "① Collection",
    "processing": "② Processing",
    "storage":    "③ Storage",
    "sharing":    "④ Sharing",
    "exit":       "⑤ Exit / Archive",
    "main":       "Processing",
}

NODE_STYLE = {
    "external":  dict(shape="box",     style="filled,rounded",
                      fillcolor="#FFF5CC", color="#A07800", fontcolor="#5C4400", penwidth="1.8"),
    "team":      dict(shape="box",     style="filled",
                      fillcolor="#FADADD", color="#B03030", fontcolor="#641E16", penwidth="2.2"),
    "process":   dict(shape="box",     style="filled",
                      fillcolor="#FFFFFF", color="#555555", fontcolor="#1A1A1A", penwidth="1.4"),
    "decision":  dict(shape="diamond", style="filled",
                      fillcolor="#C0392B", color="#8B2222", fontcolor="#FFFFFF", penwidth="2.2"),
    "endpoint":  dict(shape="ellipse", style="filled",
                      fillcolor="#B03030", color="#7B1A1A", fontcolor="#FFFFFF", penwidth="2.2"),
    "datastore": dict(shape="cylinder",style="filled",
                      fillcolor="#D4E8FA", color="#1A5276", fontcolor="#0D3B6E", penwidth="1.8"),
}

def _nattrs(ntype, label):
    s = NODE_STYLE.get(ntype, NODE_STYLE["process"]).copy()
    bold = ntype in ("team","endpoint","decision")
    return {**s,
            "label":    _gv_label(label, 13),
            "fontname": "Helvetica-Bold" if bold else "Helvetica",
            "fontsize": "12",
            "margin":   "0.25,0.18",
            "width":    "1.8", "height": "0.70",
            "fixedsize":"false"}

def _build_flow(data: dict) -> bytes:
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    # Group by phase
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
        nodesep  = "0.60",
        ranksep  = "1.3",
        pad      = "0.5",
        fontname = "Helvetica",
        compound = "true",
        size     = "26,12!",
        ratio    = "compress",
        dpi      = "200",
    )
    dot.attr("edge",
        fontname  = "Helvetica",
        fontsize  = "8",
        color     = "#555555",
        fontcolor = "#444444",
        arrowsize = "0.9",
        penwidth  = "1.4",
        minlen    = "2",
    )

    # Build swimlane clusters
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
                fontsize  = "11",
                fontcolor = "#1A3A5C",
                style     = "rounded,filled",
                fillcolor = "#F8F9FA",
                color     = "#CCCCCC",
                penwidth  = "1.0",
                margin    = "14",
            )
            for i, n in enumerate(ph_nodes):
                nid = _sid(n["id"])
                sg.node(nid, **_nattrs(n.get("type","process"), n.get("label","")))
                # Force vertical ordering inside column
                if i > 0:
                    dot.edge(_sid(ph_nodes[i-1]["id"]), nid,
                             style="invis", weight="8")

    # Main flow edges — use xlabel so labels don't overlap nodes
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
            fontcolor= "#C0392B" if sensitive else "#555555",
            penwidth = "2.4"     if sensitive else "1.4",
        )
        if lbl:
            attrs["xlabel"]   = f"  {lbl}  "
            attrs["fontsize"] = "8"
        dot.edge(src, dst, **attrs)

    return dot.pipe(format="png")


# ── Privacy controls grid ─────────────────────────────────────────────────────
PILL_H    = 38
PILL_R    = 9
PILL_MINW = 165
PILL_MAXW = 295
PILL_GAP  = 12
PILL_FONT = 11
LBL_W     = 245
ROW_VPAD  = 20
SEC_H     = 58
COLHDR_H  = 40

def _pw(text, draw):
    f = _font(PILL_FONT)
    try:
        bb = draw.textbbox((0,0), text, font=f)
        return min(PILL_MAXW, max(PILL_MINW, bb[2]-bb[0]+30))
    except:
        return max(PILL_MINW, len(text)*8+30)

def _draw_grid(draw, W, y0, ctrls, nodes):
    if not ctrls: return y0
    nlbl = {n["id"]: n.get("label", n["id"]) for n in nodes}
    rows = [(nid, nlbl.get(nid, nid), c[:6])
            for nid, c in ctrls.items() if c and nlbl.get(nid)]
    if not rows: return y0

    PAD = 48

    # Section header
    draw.rectangle([PAD, y0, W-PAD, y0+SEC_H], fill="#1A6B3A")
    draw.text((PAD+20, y0+17),
              "Privacy Controls Embedded by Process Step",
              font=_font(17, bold=True), fill="#FFFFFF")
    y = y0 + SEC_H

    # Column header
    draw.rectangle([PAD, y, W-PAD, y+COLHDR_H], fill="#E8F5E9")
    draw.line([(PAD, y+COLHDR_H),(W-PAD, y+COLHDR_H)], fill="#A5D6A7", width=1)
    draw.line([(PAD+LBL_W, y),(PAD+LBL_W, y+COLHDR_H)], fill="#A5D6A7", width=1)
    draw.text((PAD+14, y+13), "Process Step / Node",
              font=_font(13, bold=True), fill="#1A5C34")
    draw.text((PAD+LBL_W+16, y+13), "Privacy Controls Applied",
              font=_font(13, bold=True), fill="#1A5C34")
    y += COLHDR_H

    for ri, (nid, lbl, pills) in enumerate(rows):
        # Calc row height (simulate pill wrapping)
        px_s = PAD + LBL_W + 16
        n_pill_rows = 1
        for p in pills:
            pw = _pw(p[:26], draw)
            if px_s + pw > W - PAD - 8:
                n_pill_rows += 1
                px_s = PAD + LBL_W + 16
            px_s += pw + PILL_GAP
        row_h = ROW_VPAD*2 + n_pill_rows*(PILL_H+PILL_GAP) - PILL_GAP + ROW_VPAD

        bg = "#FFFFFF" if ri%2==0 else "#F5FBF5"
        draw.rectangle([PAD, y, W-PAD, y+row_h], fill=bg)
        draw.line([(PAD, y+row_h),(W-PAD, y+row_h)], fill="#C8E6C9", width=1)
        draw.line([(PAD+LBL_W, y),(PAD+LBL_W, y+row_h)], fill="#C8E6C9", width=1)

        # Left: label
        lbl_y = y + ROW_VPAD
        for ll in textwrap.wrap(lbl, 18)[:2]:
            draw.text((PAD+14, lbl_y), ll,
                      font=_font(13, bold=True), fill="#2C3E50")
            lbl_y += 20

        # Right: pills
        px = PAD + LBL_W + 16
        py = y + ROW_VPAD
        for p in pills:
            t  = p[:26]
            pw = _pw(t, draw)
            if px + pw > W - PAD - 8:
                px = PAD + LBL_W + 16
                py += PILL_H + PILL_GAP
            draw.rounded_rectangle([px, py, px+pw, py+PILL_H],
                                   radius=PILL_R, fill="#D5E8D4",
                                   outline="#27AE60", width=1)
            f = _font(PILL_FONT)
            try:
                bb = draw.textbbox((0,0),t,font=f)
                tw,th = bb[2]-bb[0], bb[3]-bb[1]
            except:
                tw,th = len(t)*7, 13
            draw.text((px+(pw-tw)//2, py+(PILL_H-th)//2),
                      t, font=f, fill="#145A32")
            px += pw + PILL_GAP
        y += row_h

    draw.line([(PAD, y),(W-PAD, y)], fill="#A5D6A7", width=2)
    return y + 26


# ── PIL composition ───────────────────────────────────────────────────────────
HEADER_H = 88
BANNER_H = 54
LEG_H    = 52
PAD      = 48

def _compose(graph_png, title, state, banner_txt, banner_color,
             privacy_controls=None, nodes=None):

    g = Image.open(io.BytesIO(graph_png)).convert("RGB")

    MIN_W = 3200
    if g.width < MIN_W:
        sc = MIN_W / g.width
        g  = g.resize((int(g.width*sc), int(g.height*sc)), Image.LANCZOS)

    W = g.width + PAD*2

    ctrl_h = 0
    if state=="future" and privacy_controls and nodes:
        nids = {n["id"] for n in nodes}
        n_r  = sum(1 for nid,c in privacy_controls.items() if c and nid in nids)
        ctrl_h = SEC_H + COLHDR_H + n_r*(ROW_VPAD*2+PILL_H+PILL_GAP+18) + 60

    H = HEADER_H + BANNER_H + g.height + LEG_H + ctrl_h + 40

    cv = Image.new("RGB", (W,H), "#FFFFFF")
    dr = ImageDraw.Draw(cv)

    # Header
    dr.rectangle([0,0,W,HEADER_H], fill="#1A3A5C")
    dr.rectangle([14,12,104,HEADER_H-12], fill="#2470A0", outline="#154C80", width=2)
    dr.text((20,20), "DATA\nFLOW\nANALYSIS", font=_font(10,True), fill="#FFFFFF")
    dr.text((118,10), title, font=_font(30,True), fill="#FFFFFF")
    dr.text((119,52), "Privacy & Data Protection Review  ·  DPDPA 2023 / GDPR",
            font=_font(14), fill="#93C6E7")
    # State badge (top right)
    sl  = "CURRENT STATE" if state=="asis" else "POST COMPLIANCE"
    sc2 = "#C0392B" if state=="asis" else "#1A6B3A"
    dr.rounded_rectangle([W-310,16, W-14, HEADER_H-16], radius=6, fill=sc2)
    dr.text((W-295, 30), sl, font=_font(14,True), fill="#FFFFFF")

    # Banner
    dr.rectangle([0,HEADER_H,W,HEADER_H+BANNER_H], fill=banner_color)
    dr.text((PAD, HEADER_H+15), "◼  "+banner_txt,
            font=_font(20,True), fill="#FFFFFF")

    # Diagram
    cv.paste(g, (PAD, HEADER_H+BANNER_H))

    # Legend
    ly = HEADER_H + BANNER_H + g.height + 6
    dr.rectangle([0,ly,W,ly+LEG_H], fill="#F4F6F8")
    dr.line([(0,ly),(W,ly)], fill="#CCCCCC", width=1)
    items = [
        ("#FFF5CC","#A07800","External Entity / Data Subject"),
        ("#FADADD","#B03030","Internal Team / Department"),
        ("#FFFFFF","#555555","Process Step"),
        ("#C0392B","#8B2222","Decision Gate / Endpoint"),
        ("#D4E8FA","#1A5276","Data Store / System"),
        ("#D5E8D4","#27AE60","Privacy Control"),
    ]
    lx = PAD
    for fc,sc,lb in items:
        dr.rounded_rectangle([lx,ly+14,lx+20,ly+32],radius=4,fill=fc,outline=sc,width=1)
        dr.text((lx+26,ly+15), lb, font=_font(11), fill="#444444")
        lx += 205
    dr.text((PAD, ly+LEG_H-16),
            "⚠  Red arrows indicate sensitive / special category data flows  (health, financial, biometric, etc.)",
            font=_font(9), fill="#C0392B")

    # Privacy grid
    if state=="future" and privacy_controls and nodes:
        cy   = ly + LEG_H + 14
        dr.line([(PAD,cy-6),(W-PAD,cy-6)], fill="#E0E0E0", width=1)
        ey   = _draw_grid(dr, W, cy, privacy_controls, nodes)
        cv   = cv.crop((0,0,W,ey+28))

    return cv

def _to_png(img):
    b=io.BytesIO(); img.save(b,format="PNG",dpi=(250,250)); return b.getvalue()

def _to_pdf(img):
    b=io.BytesIO(); img.save(b,format="PDF",resolution=250); return b.getvalue()

def render_dfd(dfd_data):
    title  = dfd_data.get("process_name","Data Flow Diagram")
    asis   = dfd_data.get("asis",  {"nodes":[],"edges":[]})
    future = dfd_data.get("future",{"nodes":[],"edges":[]})
    ctrls  = dfd_data.get("privacy_controls",{})

    a_raw = _build_flow(asis)
    f_raw = _build_flow(future)

    ai = _compose(a_raw, title, "asis",
                  "Current State  ·  Existing Data Flows (Without Privacy Controls)",
                  "#C0392B")
    fi = _compose(f_raw, title, "future",
                  "Post Compliance  ·  Privacy-Embedded Future State",
                  "#1A6B3A",
                  privacy_controls=ctrls,
                  nodes=future.get("nodes",[]))

    return _to_png(ai), _to_pdf(ai), _to_png(fi), _to_pdf(fi)


DFD_JSON_SCHEMA = '''
Return ONLY a valid JSON array with exactly ONE element. No markdown. No text before or after.

[{"id":"P001","process_name":"Name ≤50 chars",
  "asis":{"nodes":[...],"edges":[...]},
  "future":{"nodes":[...],"edges":[...]},
  "privacy_controls":{"node_id":["Control A","Control B","Control C","Control D"]},
  "narrative":"3-5 sentences."}]

NODE: {"id":"snake_id","label":"≤13 chars","type":"external|team|process|decision|endpoint|datastore","phase":"collection|processing|storage|sharing|exit"}
EDGE: {"from":"id","to":"id","label":"≤13 chars"}

TYPES: external=people/orgs outside company, team=internal depts, process=action steps,
       decision=red diamond yes/no gates, endpoint=final states, datastore=where data lives
PHASES must be in left-to-right order: collection→processing→storage→sharing→exit

CRITICAL: Min 12 nodes+12 edges. future node IDs=same as asis. All edge IDs must exist.
PRIVACY CONTROLS: up to 5 per node, ≤24 chars, be specific (e.g. "MFA for HRMS Login" not "Security")
'''
