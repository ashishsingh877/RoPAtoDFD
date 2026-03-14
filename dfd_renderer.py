"""
dfd_renderer.py — Professional DFD Renderer v12
Key: splines=ortho + xlabel for labels + constraint=false on back-edges
Guarantees ZERO lines through nodes or text.
"""
import io, re, json, math, textwrap, graphviz
from PIL import Image, ImageDraw, ImageFont

_FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def _font(sz, bold=False):
    try:    return ImageFont.truetype(_FONT_BOLD if bold else _FONT_REG, sz)
    except: return ImageFont.load_default()

def _gv(text, n=15):
    lines = textwrap.wrap(str(text).strip(), width=n)
    return "\\n".join(lines[:3]) if lines else str(text)

def _sid(s):
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(s).strip())[:35]

PHASE_RANK = {"collection":0,"processing":1,"storage":2,"sharing":3,"exit":4,"main":2}

NODE_STYLES = {
    "external":  dict(shape="box",     style="filled,rounded",
                      fillcolor="#FFF5CC", color="#A07800",
                      fontcolor="#5C4400"),
    "team":      dict(shape="box",     style="filled",
                      fillcolor="#FADADD", color="#B03030",
                      fontcolor="#641E16", fontname="Helvetica-Bold"),
    "process":   dict(shape="box",     style="filled",
                      fillcolor="#FFFFFF", color="#555555",
                      fontcolor="#1A1A1A"),
    "decision":  dict(shape="diamond", style="filled",
                      fillcolor="#C0392B", color="#8B2222",
                      fontcolor="#FFFFFF", fontname="Helvetica-Bold"),
    "endpoint":  dict(shape="ellipse", style="filled",
                      fillcolor="#B03030", color="#7B1A1A",
                      fontcolor="#FFFFFF", fontname="Helvetica-Bold"),
    "datastore": dict(shape="cylinder",style="filled",
                      fillcolor="#D4E8FA", color="#1A5276",
                      fontcolor="#0D3B6E"),
}

def _nattrs(ntype, label):
    s = NODE_STYLES.get(ntype, NODE_STYLES["process"]).copy()
    s.setdefault("fontname","Helvetica")
    return {**s,
            "label":_gv(label,14), "fontsize":"12",
            "margin":"0.30,0.22",
            "width":"2.0", "height":"0.75",
            "fixedsize":"false", "penwidth":"1.6"}

GV_DPI = 180

def _make_dot(data):
    nodes = data.get("nodes",[])
    edges = data.get("edges",[])

    # Compute which phases exist and assign to ranks
    phase_map = {}
    for n in nodes:
        ph = n.get("phase","processing").lower().strip()
        if ph not in PHASE_RANK: ph = "processing"
        phase_map.setdefault(ph,[]).append(n)

    # Build set of node IDs for quick lookup
    node_ids = {_sid(n["id"]) for n in nodes}

    # Detect back-edges (source rank >= dest rank)
    node_rank = {}
    for n in nodes:
        ph = n.get("phase","processing").lower().strip()
        if ph not in PHASE_RANK: ph = "processing"
        node_rank[_sid(n["id"])] = PHASE_RANK[ph]

    dot = graphviz.Digraph(engine="dot")
    dot.attr("graph",
        bgcolor  = "white",
        rankdir  = "LR",
        splines  = "ortho",        # RIGHT-ANGLE routing, never through nodes
        nodesep  = "0.90",         # generous vertical space
        ranksep  = "1.80",         # generous horizontal space
        pad      = "0.60",
        fontname = "Helvetica",
        newrank  = "true",
        size     = "32,12!",
        ratio    = "compress",
        dpi      = str(GV_DPI),
    )
    dot.attr("edge",
        fontname  = "Helvetica",
        fontsize  = "9",
        color     = "#666666",
        fontcolor = "#555555",
        arrowsize = "0.9",
        penwidth  = "1.4",
    )

    # Add all nodes
    for n in nodes:
        dot.node(_sid(n["id"]), **_nattrs(n.get("type","process"), n.get("label","")))

    # rank=same for parallel collection sources
    coll = phase_map.get("collection",[])
    if len(coll) > 1:
        with dot.subgraph() as sg:
            sg.attr(rank="same")
            for n in coll: sg.node(_sid(n["id"]))

    # rank=same for parallel sharing recipients
    shar = phase_map.get("sharing",[])
    if len(shar) > 1:
        with dot.subgraph() as sg:
            sg.attr(rank="same")
            for n in shar: sg.node(_sid(n["id"]))

    # rank=same for exit endpoints
    exit_ = phase_map.get("exit",[])
    if len(exit_) > 1:
        with dot.subgraph() as sg:
            sg.attr(rank="same")
            for n in exit_: sg.node(_sid(n["id"]))

    # Invisible chain to enforce phase ordering
    phase_reps = {}
    for ph, ph_nodes in phase_map.items():
        r = PHASE_RANK.get(ph,2)
        if r not in phase_reps:
            phase_reps[r] = _sid(ph_nodes[0]["id"])
    for r in sorted(phase_reps)[:-1]:
        dot.edge(phase_reps[r], phase_reps[r+1] if r+1 in phase_reps else phase_reps[max(phase_reps)],
                 style="invis", weight="6")

    # Edges — use xlabel (required for ortho splines)
    for e in edges:
        src = _sid(e.get("from",""))
        dst = _sid(e.get("to",""))
        if not src or not dst: continue
        raw = e.get("label","").strip()
        lbl = (raw[:14]+"…") if len(raw)>15 else raw
        sensitive = any(k in raw.lower() for k in
            ["health","medical","biometric","salary","financial",
             "bank","sensitive","special","aadhaar","pan","criminal"])

        # Back-edge: source rank >= dest rank — use constraint=false, dashed
        src_r = node_rank.get(src, 2)
        dst_r = node_rank.get(dst, 2)
        is_back = src_r >= dst_r and src != dst

        attrs = dict(
            color    = "#C0392B" if sensitive else "#666666",
            fontcolor= "#555555",
            penwidth = "2.0" if sensitive else "1.4",
        )
        if is_back:
            attrs["constraint"] = "false"
            attrs["style"]      = "dashed"
            attrs["color"]      = "#999999"
            attrs["penwidth"]   = "1.2"
        if lbl:
            attrs["xlabel"]   = lbl   # xlabel for ortho (label not supported)
            attrs["fontsize"] = "9"
        dot.edge(src, dst, **attrs)
    return dot


def _get_positions(dot, img_w, img_h):
    raw = dot.pipe(format="json")
    gv  = json.loads(raw)
    bb  = [float(x) for x in gv.get("bb","0,0,100,100").split(",")]
    if bb[2]==0 or bb[3]==0: return {}
    sx,sy = img_w/bb[2], img_h/bb[3]
    pos = {}
    for obj in gv.get("objects",[]):
        name = obj.get("name","")
        if not name: continue
        ps = obj.get("pos","")
        if not ps or "," not in ps: continue
        try: gx,gy = [float(v) for v in ps.split(",")]
        except: continue
        wi = float(obj.get("width",1.0))
        hi = float(obj.get("height",0.5))
        cx=gx*sx; cy=(bb[3]-gy)*sy
        pw=wi*72*sx; ph_=hi*72*sy
        pos[name]=dict(cx=cx,cy=cy,w=pw,h=ph_,
                       x1=cx-pw/2,y1=cy-ph_/2,
                       x2=cx+pw/2,y2=cy+ph_/2)
    return pos


def _overlay_controls(img, positions, privacy_controls, nodes):
    """Overlay green privacy controls. Fuzzy key matching."""
    img  = img.copy()
    draw = ImageDraw.Draw(img)
    W,H  = img.size
    sc   = W/3600

    BW   = max(160, int(210*sc))
    BH   = max(30,  int(36*sc))
    GX   = max(8,   int(10*sc))
    GY   = max(6,   int(8*sc))
    MAR  = max(16,  int(22*sc))
    FS   = max(9,   int(11*sc))
    PR   = max(5,   int(7*sc))
    LW   = max(1,   int(2*sc))
    COLS = 2

    def _norm(s):
        return re.sub(r"[^a-z0-9]","_",str(s).lower().strip())

    norm_map = {}
    for pk in positions:
        norm_map[_norm(pk)] = pk
        parts = [p for p in _norm(pk).split("_") if len(p)>2]
        if parts: norm_map[parts[0]] = pk

    for raw_nid, controls in privacy_controls.items():
        if not controls: continue
        sid = _sid(raw_nid)
        if sid in positions:
            pk = sid
        else:
            nk = _norm(raw_nid)
            pk = norm_map.get(nk) or norm_map.get(nk.split("_")[0] if "_" in nk else nk)
            if not pk: continue

        p     = positions[pk]
        pills = controls[:6]
        nr    = math.ceil(len(pills)/COLS)
        nc    = min(COLS,len(pills))
        BLW   = nc*(BW+GX)-GX
        BLH   = nr*(BH+GY)-GY

        # Always place ABOVE — we have TOP_PAD white space
        bx = p["cx"] - BLW/2
        by = p["y1"] - BLH - MAR

        # If not enough space above, place below
        if by < 4:
            bx = p["cx"] - BLW/2
            by = p["y2"] + MAR

        bx = max(4, min(float(bx), W-BLW-4))
        by = max(4, min(float(by), H-BLH-4))

        # Connector line
        conn_y1 = by+BLH+3 if by < p["y1"] else by-3
        conn_y2 = p["y1"]-2 if by < p["y1"] else p["y2"]+2
        draw.line([(int(p["cx"]), int(conn_y2)),
                   (int(p["cx"]), int(conn_y1))],
                  fill="#27AE60", width=LW)

        for i, ctrl in enumerate(pills):
            r=i//COLS; c=i%COLS
            px=bx+c*(BW+GX); py=by+r*(BH+GY)
            draw.rounded_rectangle(
                [int(px),int(py),int(px+BW),int(py+BH)],
                radius=PR, fill="#D5E8D4", outline="#2E8B57", width=1)
            text=ctrl[:24]; f=_font(FS)
            try:
                bb2=draw.textbbox((0,0),text,font=f)
                tw,th=bb2[2]-bb2[0],bb2[3]-bb2[1]
            except: tw,th=len(text)*6,FS
            draw.text((int(px+(BW-tw)/2), int(py+(BH-th)/2)),
                      text, font=f, fill="#145A32")
    return img


HEADER_H=88; BANNER_H=52; LEG_H=52; PAD=48
TOP_PAD=300; BOT_PAD=60

def _compose(flow_png, title, state, banner_txt, banner_color,
             privacy_controls=None, nodes=None):

    g = Image.open(io.BytesIO(flow_png)).convert("RGB")
    MIN_W = 3400
    if g.width < MIN_W:
        sc=MIN_W/g.width; g=g.resize((int(g.width*sc),int(g.height*sc)),Image.LANCZOS)

    W=g.width+PAD*2
    H=HEADER_H+BANNER_H+g.height+LEG_H+20
    cv=Image.new("RGB",(W,H),"#FFFFFF")
    dr=ImageDraw.Draw(cv)

    # Header
    dr.rectangle([0,0,W,HEADER_H], fill="#1A3A5C")
    dr.rectangle([14,12,108,HEADER_H-12], fill="#2470A0", outline="#154C80", width=2)
    dr.text((20,18),"DATA\nFLOW\nANALYSIS",font=_font(10,True),fill="#FFFFFF")
    dr.text((118,10),title,font=_font(28,True),fill="#FFFFFF")
    dr.text((119,50),"Privacy & Data Protection Review  ·  DPDPA 2023 / GDPR",
            font=_font(14),fill="#93C6E7")
    bc="#C0392B" if state=="asis" else "#1A6B3A"
    bt="CURRENT STATE" if state=="asis" else "POST COMPLIANCE"
    dr.rounded_rectangle([W-305,16,W-14,HEADER_H-16],radius=6,fill=bc)
    dr.text((W-290,30),bt,font=_font(14,True),fill="#FFFFFF")

    # Banner
    dr.rectangle([0,HEADER_H,W,HEADER_H+BANNER_H],fill=banner_color)
    dr.text((PAD,HEADER_H+14),"◼  "+banner_txt,font=_font(18,True),fill="#FFFFFF")

    cv.paste(g,(PAD,HEADER_H+BANNER_H))

    # Legend
    ly=HEADER_H+BANNER_H+g.height+5
    dr.rectangle([0,ly,W,ly+LEG_H],fill="#F4F6F8")
    dr.line([(0,ly),(W,ly)],fill="#CCCCCC",width=1)
    items=[("#FFF5CC","#A07800","External Entity"),
           ("#FADADD","#B03030","Internal Team"),
           ("#FFFFFF","#555555","Process Step"),
           ("#C0392B","#8B2222","Decision / Endpoint"),
           ("#D4E8FA","#1A5276","Data Store"),
           ("#D5E8D4","#2E8B57","Privacy Control"),
           ("#999999","#999999","Back-flow / Feedback")]
    lx=PAD
    for fc,sc2,lb in items:
        if lb=="Back-flow / Feedback":
            dr.line([lx,ly+23,lx+20,ly+23],fill="#999999",width=2)
            dr.text((lx+26,ly+15),lb,font=_font(10),fill="#666666")
        else:
            dr.rounded_rectangle([lx,ly+13,lx+20,ly+31],radius=3,fill=fc,outline=sc2,width=1)
            dr.text((lx+26,ly+14),lb,font=_font(11),fill="#444444")
        lx+=180
    dr.text((PAD,ly+LEG_H-15),
            "⚠  Red arrows = sensitive data (financial, health, biometric)  ·  Dashed = back-flow / result",
            font=_font(9),fill="#C0392B")
    return cv


def render_dfd(dfd_data):
    title  = dfd_data.get("process_name","Data Flow Diagram")
    asis   = dfd_data.get("asis",  {"nodes":[],"edges":[]})
    future = dfd_data.get("future",{"nodes":[],"edges":[]})
    ctrls  = dfd_data.get("privacy_controls",{})

    def _to_png(img):
        b=io.BytesIO(); img.save(b,format="PNG",dpi=(250,250)); return b.getvalue()
    def _to_pdf(img):
        b=io.BytesIO(); img.save(b,format="PDF",resolution=250); return b.getvalue()

    # ── Current State ──────────────────────────────────────────────────────────
    dot_a   = _make_dot(asis)
    asis_cv = _compose(dot_a.pipe(format="png"), title, "asis",
                       "Current State  ·  Existing Data Flows (Without Privacy Controls)","#C0392B")

    # ── Post Compliance ─────────────────────────────────────────────────────────
    dot_f    = _make_dot(future)
    raw_flow = dot_f.pipe(format="png")
    flow     = Image.open(io.BytesIO(raw_flow)).convert("RGB")
    fw,fh    = flow.size

    # White canvas with TOP_PAD space for control boxes
    padded   = Image.new("RGB",(fw,fh+TOP_PAD+BOT_PAD),"#FFFFFF")
    padded.paste(flow,(0,TOP_PAD))

    pos = _get_positions(dot_f, fw, fh)
    for k in pos:
        pos[k]["cy"]+=TOP_PAD; pos[k]["y1"]+=TOP_PAD; pos[k]["y2"]+=TOP_PAD

    annotated = _overlay_controls(padded, pos, ctrls, future.get("nodes",[]))
    buf=io.BytesIO(); annotated.save(buf,format="PNG"); buf.seek(0)
    future_cv = _compose(buf.getvalue(), title, "future",
                         "Post Compliance  ·  Privacy-Embedded Future State","#1A6B3A")

    return _to_png(asis_cv),_to_pdf(asis_cv),_to_png(future_cv),_to_pdf(future_cv)


DFD_JSON_SCHEMA='''
Return ONLY a valid JSON array with exactly ONE element. No markdown. No text.

[{"id":"P001","process_name":"Name ≤50 chars",
  "asis":{"nodes":[...],"edges":[...]},
  "future":{"nodes":[...],"edges":[...]},
  "privacy_controls":{"node_id":["Control 1","Control 2","Control 3","Control 4"]},
  "narrative":"3-5 sentences."}]

NODE: {"id":"snake_id","label":"≤14 chars","type":"external|team|process|decision|endpoint|datastore","phase":"collection|processing|storage|sharing|exit"}
EDGE: {"from":"id","to":"id","label":"≤12 chars"}

PHASES: collection=sources flowing IN | processing=sequential steps | storage=data stores | sharing=recipients out | exit=final states

CRITICAL: privacy_controls keys MUST exactly match node IDs (same snake_case as in nodes array).
PRIVACY CONTROLS: 3-5 per node, ≤22 chars. Shown as green boxes on diagram.
Min 12 nodes + 12 edges. future node IDs = same as asis.
'''
