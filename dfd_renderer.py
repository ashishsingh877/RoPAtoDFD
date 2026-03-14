"""
dfd_renderer.py — Professional DFD Renderer v11
Layout: True horizontal flow. Sequential steps flow L→R.
Only parallel sources/sinks share a rank column.
Matches RateGain reference: wide landscape, controls overlaid on diagram.
"""
import io, re, json, math, textwrap, graphviz
from PIL import Image, ImageDraw, ImageFont

_FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def _font(sz, bold=False):
    try:    return ImageFont.truetype(_FONT_BOLD if bold else _FONT_REG, sz)
    except: return ImageFont.load_default()

def _gv(text, n=14):
    lines = textwrap.wrap(str(text).strip(), width=n)
    return "\\n".join(lines[:3]) if lines else str(text)

def _sid(s):
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(s).strip())[:35]

# Phase ordering for left-to-right enforcement
PHASE_RANK = {"collection":0,"processing":1,"storage":2,"sharing":3,"exit":4,"main":2}

NODE_STYLES = {
    "external":  dict(shape="box",style="filled,rounded",
                      fillcolor="#FFF5CC",color="#A07800",fontcolor="#5C4400"),
    "team":      dict(shape="box",style="filled",
                      fillcolor="#FADADD",color="#B03030",fontcolor="#641E16",
                      fontname="Helvetica-Bold"),
    "process":   dict(shape="box",style="filled",
                      fillcolor="#FFFFFF",color="#555555",fontcolor="#1A1A1A"),
    "decision":  dict(shape="diamond",style="filled",
                      fillcolor="#C0392B",color="#8B2222",fontcolor="#FFFFFF",
                      fontname="Helvetica-Bold"),
    "endpoint":  dict(shape="ellipse",style="filled",
                      fillcolor="#B03030",color="#7B1A1A",fontcolor="#FFFFFF",
                      fontname="Helvetica-Bold"),
    "datastore": dict(shape="cylinder",style="filled",
                      fillcolor="#D4E8FA",color="#1A5276",fontcolor="#0D3B6E"),
}

def _nattrs(ntype, label):
    s = NODE_STYLES.get(ntype, NODE_STYLES["process"]).copy()
    s.setdefault("fontname","Helvetica")
    return {**s,
            "label":_gv(label,13),"fontsize":"12",
            "margin":"0.22,0.16",
            "width":"1.8","height":"0.68","fixedsize":"false",
            "penwidth":"1.5"}

GV_DPI = 180

def _make_dot(data):
    nodes = data.get("nodes",[])
    edges = data.get("edges",[])

    # Group by phase
    phase_map = {}
    for n in nodes:
        ph = n.get("phase","processing").lower().strip()
        if ph not in PHASE_RANK: ph = "processing"
        phase_map.setdefault(ph, []).append(n)

    dot = graphviz.Digraph(engine="dot")
    dot.attr("graph",
        bgcolor="white", rankdir="LR",
        splines="polyline",
        nodesep="0.50", ranksep="1.20",
        pad="0.45", fontname="Helvetica",
        newrank="true",
        size="32,10!", ratio="fill",
        dpi=str(GV_DPI),
    )
    dot.attr("edge",
        fontname="Helvetica", fontsize="9",
        color="#666666", fontcolor="#555555",
        arrowsize="0.85", penwidth="1.3", minlen="2",
    )

    # Add all nodes
    for n in nodes:
        dot.node(_sid(n["id"]), **_nattrs(n.get("type","process"), n.get("label","")))

    # Phase columns: use rank=same ONLY for parallel sources (external collection nodes)
    # and parallel sinks (sharing/exit nodes)
    parallel_phases = {"collection","sharing","exit"}
    for ph, ph_nodes in phase_map.items():
        if ph in parallel_phases and len(ph_nodes) > 1:
            with dot.subgraph() as sg:
                sg.attr(rank="same")
                for n in ph_nodes:
                    sg.node(_sid(n["id"]))

    # Phase ordering: create invisible chain to enforce L→R phase ordering
    # Pick one representative node per phase and chain them
    phase_reps = {}
    for ph, ph_nodes in phase_map.items():
        phase_reps[PHASE_RANK.get(ph,2)] = _sid(ph_nodes[0]["id"])
    sorted_ranks = sorted(phase_reps.keys())
    for i in range(len(sorted_ranks)-1):
        src = phase_reps[sorted_ranks[i]]
        dst = phase_reps[sorted_ranks[i+1]]
        dot.edge(src, dst, style="invis", weight="8")

    # Main flow edges
    for e in edges:
        src = _sid(e.get("from",""));  dst = _sid(e.get("to",""))
        if not src or not dst: continue
        raw = e.get("label","").strip()
        lbl = (raw[:13]+"…") if len(raw)>14 else raw
        sensitive = any(k in raw.lower() for k in
            ["health","medical","biometric","salary","financial",
             "bank","sensitive","special","aadhaar","pan","criminal"])
        attrs = dict(
            color    = "#C0392B" if sensitive else "#666666",
            fontcolor= "#C0392B" if sensitive else "#666666",
            penwidth = "2.0"     if sensitive else "1.3",
        )
        if lbl:
            attrs["label"]    = lbl
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
        pw=wi*72*sx; ph=hi*72*sy
        pos[name]=dict(cx=cx,cy=cy,w=pw,h=ph,
                       x1=cx-pw/2,y1=cy-ph/2,
                       x2=cx+pw/2,y2=cy+ph/2)
    return pos


def _overlay_controls(img, positions, privacy_controls, nodes):
    img  = img.copy()
    draw = ImageDraw.Draw(img)
    W, H = img.size
    scale = W / 3400

    BW  = max(155, int(200*scale))
    BH  = max(27,  int(34*scale))
    GX  = max(6,   int(9*scale))
    GY  = max(5,   int(7*scale))
    MAR = max(14,  int(20*scale))
    FS  = max(8,   int(10*scale))
    PR  = max(4,   int(6*scale))
    LW  = max(1,   int(2*scale))
    COLS= 2

    for raw_nid, controls in privacy_controls.items():
        sid = _sid(raw_nid)
        if sid not in positions or not controls: continue
        p     = positions[sid]
        pills = controls[:6]
        nr    = math.ceil(len(pills)/COLS)
        nc    = min(COLS, len(pills))
        BLW   = nc*(BW+GX)-GX
        BLH   = nr*(BH+GY)-GY

        # Place ABOVE if space, else BELOW
        if p["y1"] > BLH + MAR + 8:
            bx = p["cx"] - BLW/2
            by = p["y1"] - BLH - MAR
            draw.line([(int(p["cx"]),int(p["y1"])),
                       (int(p["cx"]),int(by+BLH+2))],
                      fill="#27AE60", width=LW)
        else:
            bx = p["cx"] - BLW/2
            by = p["y2"] + MAR
            draw.line([(int(p["cx"]),int(p["y2"])),
                       (int(p["cx"]),int(by-2))],
                      fill="#27AE60", width=LW)

        bx = max(4, min(bx, W-BLW-4))
        by = max(4, min(by, H-BLH-4))

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
            draw.text((int(px+(BW-tw)/2),int(py+(BH-th)/2)),
                      text,font=f,fill="#145A32")
    return img


HEADER_H=88; BANNER_H=52; LEG_H=52; PAD=44
TOP_PAD=270; BOT_PAD=55

def _compose(flow_png, title, state, banner_txt, banner_color,
             privacy_controls=None, nodes=None):

    g = Image.open(io.BytesIO(flow_png)).convert("RGB")
    MIN_W = 3400
    if g.width < MIN_W:
        sc=MIN_W/g.width; g=g.resize((int(g.width*sc),int(g.height*sc)),Image.LANCZOS)

    W=g.width+PAD*2; H=HEADER_H+BANNER_H+g.height+LEG_H+20
    cv=Image.new("RGB",(W,H),"#FFFFFF")
    dr=ImageDraw.Draw(cv)

    # Header
    dr.rectangle([0,0,W,HEADER_H],fill="#1A3A5C")
    dr.rectangle([14,12,106,HEADER_H-12],fill="#2470A0",outline="#154C80",width=2)
    dr.text((20,18),"DATA\nFLOW\nANALYSIS",font=_font(10,True),fill="#FFFFFF")
    dr.text((118,10),title,font=_font(30,True),fill="#FFFFFF")
    dr.text((119,52),"Privacy & Data Protection Review  ·  DPDPA 2023 / GDPR",
            font=_font(14),fill="#93C6E7")
    bc="#C0392B" if state=="asis" else "#1A6B3A"
    bt="CURRENT STATE" if state=="asis" else "POST COMPLIANCE"
    dr.rounded_rectangle([W-305,16,W-14,HEADER_H-16],radius=6,fill=bc)
    dr.text((W-290,30),bt,font=_font(14,True),fill="#FFFFFF")

    # Banner
    dr.rectangle([0,HEADER_H,W,HEADER_H+BANNER_H],fill=banner_color)
    dr.text((PAD,HEADER_H+14),"◼  "+banner_txt,font=_font(18,True),fill="#FFFFFF")

    # Diagram
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
           ("#D5E8D4","#2E8B57","Privacy Control")]
    lx=PAD
    for fc,sc,lb in items:
        dr.rounded_rectangle([lx,ly+14,lx+20,ly+32],radius=4,fill=fc,outline=sc,width=1)
        dr.text((lx+26,ly+15),lb,font=_font(11),fill="#444444")
        lx+=185
    dr.text((PAD,ly+LEG_H-16),
            "⚠  Red arrows = sensitive / special category data (financial, health, biometric, etc.)",
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

    # ── As-Is ─────────────────────────────────────────────────────────────────
    dot_a   = _make_dot(asis)
    asis_cv = _compose(dot_a.pipe(format="png"), title, "asis",
                       "Current State  ·  Existing Data Flows (Without Privacy Controls)","#C0392B")

    # ── Post Compliance ────────────────────────────────────────────────────────
    dot_f    = _make_dot(future)
    raw_flow = dot_f.pipe(format="png")
    flow     = Image.open(io.BytesIO(raw_flow)).convert("RGB")
    fw,fh    = flow.size

    # Padded canvas: extra space above for control boxes
    padded = Image.new("RGB",(fw,fh+TOP_PAD+BOT_PAD),"#FFFFFF")
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
Return ONLY a valid JSON array with exactly ONE element. No markdown. No text before or after.

[{"id":"P001","process_name":"Name ≤50 chars",
  "asis":{"nodes":[...],"edges":[...]},
  "future":{"nodes":[...],"edges":[...]},
  "privacy_controls":{"node_id":["Control 1","Control 2","Control 3","Control 4"]},
  "narrative":"3-5 sentences."}]

NODE: {"id":"snake_id","label":"≤13 chars","type":"external|team|process|decision|endpoint|datastore","phase":"collection|processing|storage|sharing|exit"}
EDGE: {"from":"id","to":"id","label":"≤12 chars"}

CRITICAL LAYOUT RULES:
- "collection" phase = data SOURCES (people/systems sending data in). Use rank=same for these.
- "processing" phase = sequential processing STEPS flowing left-to-right. Do NOT put many nodes here.
- "storage" phase = data stores / systems. Max 3 nodes.
- "sharing" phase = external recipients. Use rank=same for these.
- "exit" phase = final states (hired, offboarded, archived).
- The main SEQUENTIAL FLOW should go: collection→processing→storage→sharing→exit
- Keep processing phase to at most 4-5 SEQUENTIAL nodes connected by edges.

PRIVACY CONTROLS: 3-5 per node, ≤22 chars. Specific. Green boxes overlaid on diagram.
RULES: Min 10 nodes+10 edges. future node IDs=same as asis. All edge IDs must exist.
'''
