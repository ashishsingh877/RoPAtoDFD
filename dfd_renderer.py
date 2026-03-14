"""
dfd_renderer.py — Professional DFD Renderer v14
Matches RateGain reference exactly:
  - Clean horizontal flow (main nodes in a line)
  - Privacy controls appear in same COLUMN as their parent node (below)
  - rank=same per node + its controls ensures proper column placement
  - ortho splines, no lines through nodes
  - 250 DPI, print-quality
"""
import io, re, textwrap, graphviz
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
    return re.sub(r"[^a-zA-Z0-9_]","_",str(s).strip())[:35]

PHASE_RANK = {"collection":0,"processing":1,"storage":2,"sharing":3,"exit":4,"main":2}

NODE_CFG = {
    "external":  ("box",     "filled,rounded","#FFF5CC","#A07800","#5C4400","Helvetica",     "1.5","0.55","0.55"),
    "team":      ("box",     "filled",        "#FADADD","#B03030","#641E16","Helvetica-Bold","1.8","0.55","0.55"),
    "process":   ("box",     "filled",        "#FFFFFF","#555555","#1A1A1A","Helvetica",     "1.3","0.55","0.55"),
    "decision":  ("diamond", "filled",        "#C0392B","#8B2222","#FFFFFF","Helvetica-Bold","1.8","0.65","0.65"),
    "endpoint":  ("ellipse", "filled",        "#B03030","#7B1A1A","#FFFFFF","Helvetica-Bold","1.8","0.55","0.55"),
    "datastore": ("cylinder","filled",        "#D4E8FA","#1A5276","#0D3B6E","Helvetica",     "1.5","0.65","0.65"),
}

def _nattr(ntype, label):
    shape,style,fc,col,fnc,fn,pw,w,h = NODE_CFG.get(ntype, NODE_CFG["process"])
    return dict(label=_gv(label,13),shape=shape,style=style,
                fillcolor=fc,color=col,fontcolor=fnc,fontname=fn,
                fontsize="12",margin="0.25,0.16",
                width=w,height=h,fixedsize="false",penwidth=pw)

def _ctrl_attr(label):
    return dict(label=_gv(label,18),shape="box",style="filled,rounded",
                fillcolor="#D5E8D4",color="#2E8B57",fontcolor="#145A32",
                fontname="Helvetica",fontsize="9",
                margin="0.09,0.05",width="1.4",height="0.34",
                fixedsize="false",penwidth="0.9")

GV_DPI = 200

def _resolve_ctrls(privacy_controls, node_ids):
    """Fuzzy-match privacy_controls keys to actual node IDs."""
    def _norm(s):
        return re.sub(r"[^a-z0-9]","_",str(s).lower().strip())
    norm_map = {}
    for nid in node_ids:
        norm_map[_norm(nid)] = nid
        parts=[p for p in _norm(nid).split("_") if len(p)>2]
        if parts: norm_map[parts[0]] = nid
    resolved = {}
    for key,clist in privacy_controls.items():
        sid = _sid(key)
        if sid in node_ids:
            resolved[sid] = clist[:3]
        else:
            nk = _norm(key)
            match = norm_map.get(nk) or norm_map.get(nk.split("_")[0] if "_" in nk else nk)
            if match: resolved[match] = clist[:3]
    return resolved

def _dot_base(extra_size=False):
    dot = graphviz.Digraph(engine="dot")
    dot.attr("graph",
        bgcolor="white", rankdir="LR",
        splines="ortho", newrank="true",
        nodesep="0.85", ranksep="1.70",
        pad="0.60", fontname="Helvetica",
        size="34,14!" if extra_size else "32,10!",
        ratio="compress",
        dpi=str(GV_DPI),
    )
    dot.attr("edge",
        fontname="Helvetica", fontsize="8",
        color="#888888", fontcolor="#666666",
        arrowsize="0.90", penwidth="1.3",
    )
    return dot

def _add_nodes_and_groups(dot, nodes):
    """Add all main nodes; group parallel phases with rank=same."""
    phase_map = {}
    for n in nodes:
        ph = n.get("phase","processing").lower()
        if ph not in PHASE_RANK: ph = "processing"
        phase_map.setdefault(ph,[]).append(n)

    for n in nodes:
        dot.node(_sid(n["id"]), **_nattr(n.get("type","process"), n.get("label","")))

    for ph in ["collection","sharing","exit"]:
        pn = phase_map.get(ph,[])
        if len(pn)>1:
            with dot.subgraph() as sg:
                sg.attr(rank="same")
                for n in pn: sg.node(_sid(n["id"]))

    return phase_map

def _add_phase_order(dot, phase_map):
    """Invisible chain to enforce left→right phase ordering."""
    phase_reps = {}
    for ph,pn in phase_map.items():
        r = PHASE_RANK.get(ph,2)
        if r not in phase_reps:
            phase_reps[r] = _sid(pn[0]["id"])
    sorted_r = sorted(phase_reps)
    for i in range(len(sorted_r)-1):
        nxt = phase_reps.get(sorted_r[i+1])
        if nxt:
            dot.edge(phase_reps[sorted_r[i]], nxt, style="invis", weight="6")

def _add_edges(dot, edges, node_rank):
    for e in edges:
        s=_sid(e.get("from","")); d=_sid(e.get("to",""))
        if not s or not d: continue
        raw=e.get("label","").strip()
        lbl=(raw[:13]+"…") if len(raw)>14 else raw
        sensitive=any(k in raw.lower() for k in
            ["health","medical","biometric","salary","financial","bank","sensitive","aadhaar","pan"])
        is_back = node_rank.get(s,2) >= node_rank.get(d,2) and s!=d
        attrs=dict(
            color   ="#C0392B" if sensitive else "#888888",
            fontcolor="#666666",
            penwidth="2.0" if sensitive else "1.3",
        )
        if is_back:
            attrs.update(constraint="false",style="dashed",color="#AAAAAA",penwidth="1.0")
        if lbl:
            attrs["xlabel"]="  "+lbl+"  "; attrs["fontsize"]="8"
        dot.edge(s,d,**attrs)

def build_asis(data):
    nodes=data.get("nodes",[]); edges=data.get("edges",[])
    dot=_dot_base()
    phase_map=_add_nodes_and_groups(dot,nodes)
    _add_phase_order(dot,phase_map)
    node_rank={_sid(n["id"]):PHASE_RANK.get(n.get("phase","processing").lower(),2) for n in nodes}
    _add_edges(dot,edges,node_rank)
    return dot.pipe(format="png")

def build_future(data, privacy_controls):
    nodes=data.get("nodes",[]); edges=data.get("edges",[])
    node_ids={_sid(n["id"]) for n in nodes}
    node_rank={_sid(n["id"]):PHASE_RANK.get(n.get("phase","processing").lower(),2) for n in nodes}
    resolved=_resolve_ctrls(privacy_controls,node_ids)

    dot=_dot_base(extra_size=True)
    phase_map=_add_nodes_and_groups(dot,nodes)
    _add_phase_order(dot,phase_map)

    # Add controls: each node + its controls share rank=same (same column)
    # This puts controls BELOW the main node in the same vertical column
    for nid, ctrls in resolved.items():
        with dot.subgraph() as sg:
            sg.attr(rank="same")
            sg.node(nid)          # main node in this column
            for ci,ctrl in enumerate(ctrls):
                cid=f"__c_{nid}_{ci}"
                sg.node(cid,**_ctrl_attr(ctrl))
                # Connect with dashed line — constraint=false keeps main flow clean
                dot.edge(nid,cid,
                         style="dashed",color="#2E8B57",
                         arrowhead="none",penwidth="0.8",
                         constraint="false",weight="0")

    _add_edges(dot,edges,node_rank)
    return dot.pipe(format="png")


HEADER_H=84; BANNER_H=52; LEG_H=50; PAD=46

def _compose(graph_png, title, state, banner_txt, banner_color):
    g = Image.open(io.BytesIO(graph_png)).convert("RGB")
    MIN_W=3400
    if g.width<MIN_W:
        sc=MIN_W/g.width; g=g.resize((int(g.width*sc),int(g.height*sc)),Image.LANCZOS)

    W=g.width+PAD*2; H=HEADER_H+BANNER_H+g.height+LEG_H+18
    cv=Image.new("RGB",(W,H),"#FFFFFF")
    dr=ImageDraw.Draw(cv)

    # Header
    dr.rectangle([0,0,W,HEADER_H],fill="#1A3A5C")
    dr.rectangle([14,12,106,HEADER_H-12],fill="#2470A0",outline="#154C80",width=2)
    dr.text((20,18),"DATA\nFLOW\nANALYSIS",font=_font(10,True),fill="#FFFFFF")
    dr.text((118,10),title,font=_font(28,True),fill="#FFFFFF")
    dr.text((119,50),"Privacy & Data Protection Review  ·  DPDPA 2023 / GDPR",
            font=_font(13),fill="#93C6E7")
    bc="#C0392B" if state=="asis" else "#1A6B3A"
    bt="CURRENT STATE" if state=="asis" else "POST COMPLIANCE"
    dr.rounded_rectangle([W-300,16,W-14,HEADER_H-16],radius=6,fill=bc)
    dr.text((W-286,30),bt,font=_font(14,True),fill="#FFFFFF")

    dr.rectangle([0,HEADER_H,W,HEADER_H+BANNER_H],fill=banner_color)
    dr.text((PAD,HEADER_H+14),"◼  "+banner_txt,font=_font(17,True),fill="#FFFFFF")
    cv.paste(g,(PAD,HEADER_H+BANNER_H))

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
    for fc,sc2,lb in items:
        dr.rounded_rectangle([lx,ly+13,lx+20,ly+31],radius=3,fill=fc,outline=sc2,width=1)
        dr.text((lx+26,ly+14),lb,font=_font(11),fill="#444444")
        lx+=192
    dr.text((PAD,ly+LEG_H-14),
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

    ai = _compose(build_asis(asis), title, "asis",
                  "Current State  ·  Existing Data Flows (Without Privacy Controls)","#C0392B")
    fi = _compose(build_future(future,ctrls), title, "future",
                  "Post Compliance  ·  Privacy-Embedded Future State","#1A6B3A")
    return _to_png(ai),_to_pdf(ai),_to_png(fi),_to_pdf(fi)


DFD_JSON_SCHEMA='''
Return ONLY a valid JSON array with exactly ONE element. No markdown. No text before or after.

[{"id":"P001","process_name":"Name ≤50 chars",
  "asis":{"nodes":[...],"edges":[...]},
  "future":{"nodes":[...],"edges":[...]},
  "privacy_controls":{"node_id":["Control 1","Control 2","Control 3","Control 4"]},
  "narrative":"3-5 sentences."}]

NODE: {"id":"snake_id","label":"≤13 chars","type":"external|team|process|decision|endpoint|datastore","phase":"collection|processing|storage|sharing|exit"}
EDGE: {"from":"id","to":"id","label":"≤12 chars"}

PHASE GUIDE:
  collection = data SOURCES entering the system (external entities, portals, channels)
  processing = sequential STEPS from left to right (team review, interview, verification, decision)
  storage    = data STORES / systems (HRMS, Email System, database)
  sharing    = external RECIPIENTS (vendors, banks, insurance, regulatory bodies)
  exit       = final STATES (Hired, Rejected, Archived, Offboarded)

CRITICAL: privacy_controls keys MUST exactly match node IDs (snake_case).
Controls appear as green boxes below each node. Provide 3-5 per node, ≤20 chars each.
Min 12 nodes + 12 edges. future node IDs = same as asis.
'''
