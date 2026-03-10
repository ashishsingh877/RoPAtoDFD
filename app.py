"""
app.py  -  ROPA Intelligence Platform
Generates professional As-Is + Post-Compliance DFDs matching the RateGain/Protiviti style.
Powered by Groq (free) + Graphviz + PIL (server-side rendering).
"""

import io
import json
import base64
import zipfile
from datetime import datetime

import streamlit as st
from ropa_parser  import parse_ropa_excel, processes_to_text
from ai_client    import chat, stream_chat, parse_json_from_response
from prompts      import EXTRACT_SYSTEM, DFD_SYSTEM, RISK_SYSTEM
from dfd_renderer import render_dfd

# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title = "ROPA — DFD & Risk Analyzer",
    page_icon  = "🔐",
    layout     = "wide",
    initial_sidebar_state = "expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
html,body,[class*="css"]  { font-family:'Inter',sans-serif; }
.stApp { background:#0d1117; color:#c9d1d9; }
section[data-testid="stSidebar"] { background:#161b22; border-right:1px solid #21262d; }

.hero { background:linear-gradient(160deg,#0d1117 0%,#0d2136 50%,#0d1117 100%);
        border:1px solid #1f3a5c; border-radius:14px; padding:2rem; margin-bottom:1.5rem; text-align:center; }
.hero-title { font-family:'JetBrains Mono',monospace; font-size:1.75rem; font-weight:600; color:#58a6ff; margin:0; }
.hero-sub   { color:#6e7681; font-size:.9rem; margin-top:.4rem; }

.metric-row { display:flex; gap:.75rem; margin:1rem 0; flex-wrap:wrap; }
.metric-box { flex:1; min-width:100px; text-align:center; background:#161b22;
              border:1px solid #21262d; border-radius:10px; padding:.85rem; }
.metric-num  { font-family:'JetBrains Mono',monospace; font-size:1.85rem; color:#58a6ff; font-weight:700; }
.metric-lbl  { font-size:.65rem; color:#484f58; text-transform:uppercase; letter-spacing:1.5px; margin-top:.15rem; }

.stage-row { display:flex; gap:.5rem; margin:1rem 0; flex-wrap:wrap; }
.stage { flex:1; min-width:120px; text-align:center; border:1px solid #21262d; border-radius:7px;
         padding:.45rem .6rem; font-family:'JetBrains Mono',monospace; font-size:.72rem; color:#484f58; background:#161b22; }
.stage.active { border-color:#388bfd; color:#388bfd; background:#0d1f35; }
.stage.done   { border-color:#3fb950; color:#3fb950; background:#0d1e14; }

.dfd-wrap { background:#f8f9fa; border:1px solid #dee2e6; border-radius:10px;
            padding:.5rem; overflow:auto; margin:.5rem 0; }
.dfd-meta { background:#161b22; border:1px solid #21262d; border-radius:8px; padding:1rem; margin-top:.6rem; }
.narrative { border-left:3px solid #388bfd; padding:.6rem 1rem; color:#8b949e; font-size:.85rem; line-height:1.6; }

.info-box { background:#0d1f35; border:1px solid #1f3a5c; border-radius:8px;
            padding:.65rem 1rem; color:#7a8db0; font-size:.82rem; }
.badge { display:inline-block; padding:.15rem .6rem; border-radius:999px;
         font-size:.7rem; font-weight:600; font-family:'JetBrains Mono',monospace; }
.b-blue  { background:#0d2136; color:#58a6ff; border:1px solid #1f3a5c; }
.b-green { background:#0d1e14; color:#3fb950; border:1px solid #1a4228; }

.stButton>button { background:linear-gradient(135deg,#1f3a5c,#388bfd30); color:#58a6ff;
                   border:1px solid #388bfd; border-radius:8px; font-family:'JetBrains Mono',monospace;
                   font-weight:600; padding:.55rem 1.4rem; transition:all .2s; }
.stButton>button:hover { background:#388bfd; color:#fff; transform:translateY(-1px); }
.stTabs [data-baseweb="tab-list"] { background:#161b22; border-radius:8px; gap:3px; }
.stTabs [data-baseweb="tab"]      { color:#484f58; border-radius:6px; font-size:.85rem; }
.stTabs [aria-selected="true"]    { background:#21262d !important; color:#58a6ff !important; }
div[data-testid="stExpander"]     { background:#161b22; border:1px solid #21262d; border-radius:8px; }
hr { border-color:#21262d; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p style="font-family:JetBrains Mono,monospace;color:#58a6ff;font-size:1rem;">🔐 ROPA Analyzer</p>', unsafe_allow_html=True)
    st.markdown("---")
    groq_key = st.text_input("Groq API Key", type="password", placeholder="gsk_…", help="Free at console.groq.com")
    model    = st.selectbox("Model", ["llama-3.3-70b-versatile","llama3-70b-8192","mixtral-8x7b-32768","gemma2-9b-it"])
    st.markdown("---")
    st.markdown("""
**Workflow**
1. Upload filled ROPA Excel
2. AI extracts all processes
3. Generates professional two-state DFDs  
   *(Current State + Post-Compliance)*
4. Produces Risk & Gap Analysis
5. Download DFDs as PNG / PDF
""")
    st.markdown("---")
    st.markdown('<span class="badge b-green">Groq Free</span> <span class="badge b-blue">DPDPA 2023 / GDPR</span>', unsafe_allow_html=True)

# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-title">🔐 ROPA Intelligence Platform</div>
  <div class="hero-sub">Upload ROPA · AI generates professional As-Is + Post-Compliance DFDs · Risk Report · Export PNG / PDF</div>
</div>
""", unsafe_allow_html=True)

# ── Upload ─────────────────────────────────────────────────────────────────────
st.markdown("### 📂 Upload ROPA File")
c1, c2 = st.columns([2, 3])
with c1:
    uploaded = st.file_uploader("ROPA Excel", type=["xlsx","xls"], label_visibility="collapsed")
with c2:
    st.markdown('<div class="info-box">Supports both ROPA layouts:<br>• <b>Vertical</b> — one sheet per process (Data Fiduciary format)<br>• <b>Horizontal</b> — RoPA_Template with 7-section, 53-column layout</div>', unsafe_allow_html=True)

if uploaded:
    st.markdown(f'<span class="badge b-green">✓ {uploaded.name}</span> <span class="badge b-blue">{uploaded.size:,} bytes</span>', unsafe_allow_html=True)

st.markdown("---")

# ── Helpers ────────────────────────────────────────────────────────────────────
def stream_box(api_key, system, user, max_tokens=6000):
    full, ph = "", st.empty()
    try:
        for chunk in stream_chat(api_key, system, user, max_tokens, model):
            full += chunk
            preview = full[-900:].replace("<","&lt;").replace(">","&gt;")
            ph.markdown(
                f'<div style="background:#010409;border:1px solid #21262d;border-radius:6px;'
                f'padding:.6rem;font-family:JetBrains Mono,monospace;font-size:.75rem;'
                f'color:#58a6ff;max-height:160px;overflow:auto;">{preview}</div>',
                unsafe_allow_html=True)
    except Exception:
        try: full = chat(api_key, system, user, max_tokens, model)
        except Exception as e: st.error(f"API error: {e}"); return ""
    ph.empty()
    return full


def set_stages(s1, s2, s3):
    stage_ph.markdown(
        f'<div class="stage-row">'
        f'<div class="stage {s1}">① Extract Processes</div>'
        f'<div class="stage {s2}">② Build DFDs</div>'
        f'<div class="stage {s3}">③ Risk Analysis</div>'
        f'</div>', unsafe_allow_html=True)


def img_b64(b): return base64.b64encode(b).decode()


def show_dfd(dfd, idx):
    pname = dfd.get("process_name", f"Process {idx+1}")
    pid   = dfd.get("id", f"P{idx+1:03d}")

    png = dfd.get("_png")
    pdf = dfd.get("_pdf")

    if png:
        st.markdown(
            f'<div class="dfd-wrap">'
            f'<img src="data:image/png;base64,{img_b64(png)}" '
            f'style="width:100%;min-width:900px;border-radius:4px;" /></div>',
            unsafe_allow_html=True)

        cc1, cc2, cc3 = st.columns([1,1,4])
        safe = pname.replace(" ","_").replace("/","-")[:35]
        with cc1:
            st.download_button("⬇️ PNG", data=png,
                file_name=f"DFD_{pid}_{safe}.png", mime="image/png",
                use_container_width=True, key=f"png_{idx}")
        with cc2:
            st.download_button("⬇️ PDF", data=pdf,
                file_name=f"DFD_{pid}_{safe}.pdf", mime="application/pdf",
                use_container_width=True, key=f"pdf_{idx}")

        narrative = dfd.get("narrative","")
        if narrative:
            st.markdown(f'<div class="dfd-meta"><div class="narrative">📋 <b>Flow Summary:</b> {narrative}</div></div>', unsafe_allow_html=True)
    else:
        err = dfd.get("_render_error","Unknown error")
        st.error(f"Render failed for {pname}: {err}")


# ── Analysis trigger ───────────────────────────────────────────────────────────
if uploaded and groq_key:
    c_run, c_info = st.columns([1,3])
    with c_run:
        run = st.button("🚀  Analyse ROPA", use_container_width=True)
    with c_info:
        st.markdown('<div class="info-box">3 AI stages: Extract → DFDs (As-Is + Post-Compliance) → Risk Report. Diagrams are server-side rendered — professional PNG + PDF output.</div>', unsafe_allow_html=True)

    if run:
        raw_bytes = uploaded.read()
        with st.spinner("Parsing ROPA file…"):
            raw_procs = parse_ropa_excel(raw_bytes, uploaded.name)

        if not raw_procs or (len(raw_procs)==1 and raw_procs[0].get("_format")=="B_EMPTY"):
            st.error("No processing activities found. Please upload a filled ROPA file.")
            st.stop()

        stage_ph = st.empty()

        # ── Stage 1: Extract ────────────────────────────────────────────────
        set_stages("active","","")
        st.markdown("#### ① Extracting processing activities…")

        raw_ext = stream_box(groq_key, EXTRACT_SYSTEM,
                             f"ROPA DATA:\n\n{processes_to_text(raw_procs)[:18000]}", 4096)
        try:    enriched = parse_json_from_response(raw_ext)
        except: enriched = raw_procs

        st.session_state["enriched"] = enriched
        n = len(enriched)
        depts     = len({p.get("function_name","") for p in enriched if p.get("function_name")})
        sensitive = sum(1 for p in enriched if str(p.get("sensitive_data","")).strip().lower() not in ("","none","no","n/a","not applicable"))
        transfers = sum(1 for p in enriched if str(p.get("transfer_jurisdictions","")).strip().lower() not in ("","none","no","n/a","not applicable"))

        st.success(f"✓ {n} processing activities extracted")
        st.markdown(
            f'<div class="metric-row">'
            f'<div class="metric-box"><div class="metric-num">{n}</div><div class="metric-lbl">Processes</div></div>'
            f'<div class="metric-box"><div class="metric-num">{depts}</div><div class="metric-lbl">Departments</div></div>'
            f'<div class="metric-box"><div class="metric-num">{sensitive}</div><div class="metric-lbl">Sensitive</div></div>'
            f'<div class="metric-box"><div class="metric-num">{transfers}</div><div class="metric-lbl">Transfers</div></div>'
            f'</div>', unsafe_allow_html=True)

        # ── Stage 2: DFDs ───────────────────────────────────────────────────
        set_stages("done","active","")
        st.markdown("#### ② Generating professional two-state DFDs…")

        raw_dfds = stream_box(groq_key, DFD_SYSTEM,
                              f"PROCESSING ACTIVITIES:\n\n{json.dumps(enriched,indent=2)[:16000]}", 7000)
        try:    dfd_list = parse_json_from_response(raw_dfds)
        except: dfd_list = []; st.session_state["dfds_raw"] = raw_dfds; st.warning("DFD JSON parse failed.")

        prog = st.progress(0, text="Rendering diagrams…")
        rendered = []
        for i, dfd in enumerate(dfd_list):
            try:
                png, pdf = render_dfd(dfd)
                dfd["_png"], dfd["_pdf"] = png, pdf
            except Exception as e:
                dfd["_png"] = dfd["_pdf"] = None
                dfd["_render_error"] = str(e)
            rendered.append(dfd)
            prog.progress((i+1)/max(len(dfd_list),1), text=f"Rendered {i+1}/{len(dfd_list)}")
        prog.empty()

        st.session_state["dfds"] = rendered
        st.success(f"✓ {len(rendered)} DFDs rendered (As-Is + Post-Compliance)")

        # ── Stage 3: Risk ───────────────────────────────────────────────────
        set_stages("done","done","active")
        st.markdown("#### ③ Running Risk & Gap Analysis…")

        risk_md = stream_box(groq_key, RISK_SYSTEM,
                             f"PROCESSING ACTIVITIES:\n\n{json.dumps(enriched,indent=2)[:16000]}", 5000)
        st.session_state["risk_md"] = risk_md
        set_stages("done","done","done")
        st.success("✓ Analysis complete")
        st.balloons()

elif not uploaded:
    st.markdown('<div style="background:#161b22;border:1px solid #21262d;border-radius:10px;text-align:center;color:#21262d;padding:3rem;">⬆️  Upload a ROPA Excel file above to begin</div>', unsafe_allow_html=True)
elif not groq_key:
    st.markdown('<div style="background:#161b22;border:1px solid #21262d;border-radius:10px;text-align:center;color:#21262d;padding:2rem;">🔑  Enter your Groq API key in the sidebar</div>', unsafe_allow_html=True)

# ── Results ────────────────────────────────────────────────────────────────────
if "dfds" in st.session_state or "risk_md" in st.session_state:
    dfds     = st.session_state.get("dfds", [])
    risk_md  = st.session_state.get("risk_md", "")
    enriched = st.session_state.get("enriched", [])

    st.markdown("---")
    tab_dfd, tab_risk, tab_export = st.tabs(["🔷 Data Flow Diagrams", "⚠️ Risk Analysis", "⬇️ Export"])

    # ── DFD Tab ────────────────────────────────────────────────────────────────
    with tab_dfd:
        if not dfds:
            if "dfds_raw" in st.session_state:
                st.warning("JSON parse failed — raw output:")
                st.code(st.session_state["dfds_raw"])
            else:
                st.info("Run the analysis to generate DFDs.")
        else:
            st.markdown(
                f'<div class="info-box">&#9670; {len(dfds)} process diagram(s) — each shows <b>Current State (As-Is)</b> and <b>Post-Compliance (Future State)</b> stacked. '
                f'Red flow arrows = sensitive data. Green boxes = privacy controls. Download PNG or PDF per diagram.</div>',
                unsafe_allow_html=True)
            st.markdown("")

            for i, dfd in enumerate(dfds):
                pname = dfd.get("process_name", f"Process {i+1}")
                pid   = dfd.get("id", f"P{i+1:03d}")
                with st.expander(f"**[{pid}]** {pname}", expanded=(i == 0)):
                    show_dfd(dfd, i)

    # ── Risk Tab ───────────────────────────────────────────────────────────────
    with tab_risk:
        if risk_md:
            st.markdown(risk_md)
        else:
            st.info("Run analysis to generate the Risk Report.")

    # ── Export Tab ─────────────────────────────────────────────────────────────
    with tab_export:
        st.markdown("### ⬇️ Export All Outputs")
        ts = datetime.now().strftime("%Y%m%d_%H%M")

        if dfds:
            st.markdown("**Individual DFDs**")
            cols = st.columns(min(len(dfds) * 2, 6))
            ci   = 0
            for i, dfd in enumerate(dfds):
                pname = dfd.get("process_name", f"P{i+1:03d}")
                safe  = pname.replace(" ","_").replace("/","-")[:30]
                pid   = dfd.get("id", f"P{i+1:03d}")
                if dfd.get("_png"):
                    with cols[ci % 6]:
                        st.download_button(f"🖼 {pid} PNG", data=dfd["_png"],
                            file_name=f"DFD_{pid}_{safe}.png", mime="image/png",
                            use_container_width=True, key=f"ex_png_{i}")
                    ci += 1
                if dfd.get("_pdf"):
                    with cols[ci % 6]:
                        st.download_button(f"📄 {pid} PDF", data=dfd["_pdf"],
                            file_name=f"DFD_{pid}_{safe}.pdf", mime="application/pdf",
                            use_container_width=True, key=f"ex_pdf_{i}")
                    ci += 1

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("⚠️ Risk Analysis (.md)", data=risk_md or "Not generated.",
                file_name=f"risk_analysis_{ts}.md", mime="text/markdown", use_container_width=True)
        with col2:
            st.download_button("📊 Processes JSON", data=json.dumps(enriched,indent=2,ensure_ascii=False),
                file_name=f"ropa_processes_{ts}.json", mime="application/json", use_container_width=True)

        st.markdown("---")
        zio = io.BytesIO()
        with zipfile.ZipFile(zio, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, dfd in enumerate(dfds):
                pn   = dfd.get("process_name", f"P{i+1:03d}")
                safe = pn.replace(" ","_").replace("/","-")[:30]
                pid  = dfd.get("id", f"P{i+1:03d}")
                if dfd.get("_png"): zf.writestr(f"dfds/DFD_{pid}_{safe}.png", dfd["_png"])
                if dfd.get("_pdf"): zf.writestr(f"dfds/DFD_{pid}_{safe}.pdf", dfd["_pdf"])
            if risk_md: zf.writestr(f"risk_analysis_{ts}.md", risk_md)
            zf.writestr(f"ropa_processes_{ts}.json", json.dumps(enriched,indent=2,ensure_ascii=False))
        zio.seek(0)

        st.download_button("📦 Download Full Bundle (ZIP)", data=zio.getvalue(),
            file_name=f"ropa_analysis_{ts}.zip", mime="application/zip")

        st.markdown('<div class="info-box" style="margin-top:.75rem;">💡 ZIP contains <code>dfds/</code> folder with PNG + PDF per process, Risk Analysis Markdown, and Processes JSON.</div>', unsafe_allow_html=True)
