# dfd_renderer.py
# Robust Graphviz DFD renderer that tolerates variable AI output and improves layout/styling.
# Returns: a_png, a_pdf, f_png, f_pdf (bytes)

import graphviz
import io
import html

# Simple schema placeholder used elsewhere (prompts.py expects it)
DFD_JSON_SCHEMA = {
    "id": "string",
    "process_name": "string",
    "asis": {"nodes": [], "edges": []},
    "future": {"nodes": [], "edges": []}
}

# ---------------------------
# Helpers: normalize / sanitize
# ---------------------------
def _clean_label(v):
    if v is None:
        return ""
    s = str(v)
    # Basic cleanup
    s = s.replace("\n", " ").strip()
    # escape for Graphviz safety if needed
    return html.escape(s)

def _ensure_nodes_edges(dfd_section):
    """
    Accepts a dfd section (maybe missing) and returns (nodes, edges)
    Nodes: list of dict {id, label, type, phase}
    Edges: list of dict {from, to, label}
    This function is tolerant of odd input shapes.
    """
    if not dfd_section:
        return [], []

    nodes_raw = dfd_section.get("nodes") if isinstance(dfd_section, dict) else None
    edges_raw = dfd_section.get("edges") if isinstance(dfd_section, dict) else None

    # If section itself is a list (flat nodes), consider it as nodes
    if nodes_raw is None and isinstance(dfd_section, list):
        nodes_raw = dfd_section

    if nodes_raw is None:
        nodes_raw = []
    if edges_raw is None:
        edges_raw = []

    # Normalize nodes
    nodes = []
    next_id = 1
    for n in nodes_raw:
        if n is None:
            continue
        if isinstance(n, dict):
            nid = n.get("id") or n.get("ID") or None
            label = n.get("label") or n.get("name") or n.get("title") or None
            ntype = n.get("type") or n.get("node_type") or "process"
            phase = n.get("phase") or n.get("lane") or n.get("stage") or "processing"
            if not nid:
                nid = f"n{next_id}"
                next_id += 1
            label = _clean_label(label or nid)
            nodes.append({"id": str(nid), "label": label, "type": str(ntype).lower(), "phase": str(phase).lower()})
        else:
            # node represented as a string: create id
            nid = f"n{next_id}"; next_id += 1
            label = _clean_label(n)
            nodes.append({"id": nid, "label": label, "type": "process", "phase": "processing"})

    # Normalize edges
    edges = []
    for e in edges_raw:
        if e is None:
            continue
        if isinstance(e, dict):
            src = e.get("from") or e.get("src") or e.get("source") or e.get("From") or None
            dst = e.get("to") or e.get("dst") or e.get("target") or e.get("To") or None
            lbl = e.get("label") or e.get("name") or ""
            if src is None or dst is None:
                # skip invalid edge
                continue
            edges.append({"from": str(src), "to": str(dst), "label": _clean_label(lbl)})
        elif isinstance(e, (list, tuple)) and len(e) >= 2:
            edges.append({"from": str(e[0]), "to": str(e[1]), "label": ""})
        else:
            # unknown edge format -> skip
            continue

    return nodes, edges

def _resolve_edge_refs(nodes, edges):
    """
    Convert edges which reference node label instead of id.
    If an edge 'from' or 'to' value matches a node label, replace with that node's id.
    Returns sanitized edges and a warning list (strings).
    """
    id_by_label = {}
    id_set = set()
    for n in nodes:
        id_set.add(n["id"])
        normalized_label = n["label"].lower()
        # if multiple nodes have same label, last wins (rare)
        id_by_label[normalized_label] = n["id"]

    sanitized = []
    warnings = []
    for e in edges:
        f = e["from"]
        t = e["to"]
        # if references equal existing ids, keep as is
        if f not in id_set:
            # try matching label
            mid = id_by_label.get(str(f).lower())
            if mid:
                warnings.append(f"Edge 'from' referenced label '{f}' -> resolved to id '{mid}'")
                f = mid
            else:
                warnings.append(f"Edge 'from' '{f}' not found; edge skipped")
                continue
        if t not in id_set:
            mid = id_by_label.get(str(t).lower())
            if mid:
                warnings.append(f"Edge 'to' referenced label '{t}' -> resolved to id '{mid}'")
                t = mid
            else:
                warnings.append(f"Edge 'to' '{t}' not found; edge skipped")
                continue
        sanitized.append({"from": f, "to": t, "label": e.get("label","")})
    return sanitized, warnings

# ---------------------------
# Graph styling helpers
# ---------------------------
def _node_style(node_type):
    t = (node_type or "process").lower()
    if t == "external":
        return {"shape":"box","style":"rounded,filled","fillcolor":"#FFF2CC","color":"#B7950B"}
    if t in ("datastore","data_store","store"):
        return {"shape":"cylinder","style":"filled","fillcolor":"#D6EAF8","color":"#1F618D"}
    if t in ("decision","diamond"):
        return {"shape":"diamond","style":"filled","fillcolor":"#F5B7B1","color":"#922B21"}
    # default process
    return {"shape":"box","style":"rounded,filled","fillcolor":"#FDEDEC","color":"#7B241C"}

def _build_graph(nodes, edges, title):
    # Graphviz attributes tuned for cleaner consulting-style DFDs
    dot = graphviz.Digraph(
        format="png",
        graph_attr={
            "rankdir":"LR",
            "splines":"ortho",
            "nodesep":"0.9",
            "ranksep":"1.25",
            "fontname":"Segoe UI"
        },
        node_attr={
            "fontname":"Segoe UI",
            "fontsize":"11"
        },
        edge_attr={
            "color":"#555555",
            "penwidth":"1.6",
            "arrowsize":"0.8"
        }
    )

    dot.attr(label=title, labelloc="t", fontsize="18")

    # Create phase buckets
    phases_order = ["collection","processing","storage","sharing","outcome"]
    phase_buckets = {p: [] for p in phases_order}
    # unknown phase goes to processing bucket
    for n in nodes:
        ph = (n.get("phase") or "processing").lower()
        if ph not in phase_buckets:
            ph = "processing"
        phase_buckets[ph].append(n)

    # Add nodes inside clusters (swimlanes)
    for ph in phases_order:
        with dot.subgraph(name=f"cluster_{ph}") as c:
            c.attr(label=ph.capitalize(), style="rounded", color="#DDDDDD", fontname="Segoe UI", fontsize="12")
            for n in phase_buckets[ph]:
                style = _node_style(n.get("type"))
                # label may contain HTML entities already escaped by _clean_label
                c.node(n["id"], n["label"], **style)

    # Add edges
    for e in edges:
        # avoid empty edges
        try:
            if not e.get("from") or not e.get("to"):
                continue
            lbl = e.get("label", "")
            dot.edge(e["from"], e["to"], label=lbl)
        except Exception:
            # defensive: skip malformed edge
            continue

    return dot

# ---------------------------
# main API used by app.py
# ---------------------------
def render_dfd(dfd):
    """
    Accepts the AI-generated dfd object (can be nested or flat).
    Returns: a_png (bytes), a_pdf (bytes), f_png (bytes), f_pdf (bytes)
    Raises Exception if no nodes are found at all.
    """
    # try structured format first
    asis_raw = dfd.get("asis") if isinstance(dfd, dict) else None
    future_raw = dfd.get("future") if isinstance(dfd, dict) else None

    # fallback to flat format if not present
    if not asis_raw:
        asis_raw = {
            "nodes": dfd.get("nodes", []),
            "edges": dfd.get("edges", [])
        }
    if not future_raw:
        future_raw = {
            "nodes": dfd.get("nodes", []),
            "edges": dfd.get("edges", [])
        }

    # normalize each side
    a_nodes, a_edges = _ensure_nodes_edges(asis_raw)
    f_nodes, f_edges = _ensure_nodes_edges(future_raw)

    # if absolutely nothing -> bail
    if not a_nodes and not f_nodes:
        raise Exception("DFD render failed: no nodes found in both 'asis' and 'future' sections.")

    # resolve edges that reference labels
    a_edges, warn_a = _resolve_edge_refs(a_nodes, a_edges)
    f_edges, warn_f = _resolve_edge_refs(f_nodes, f_edges)
    # optional: collect warnings (not thrown) - you can attach to dfd if desired
    warnings = warn_a + warn_f
    if warnings:
        # attach non-fatal warnings into dfd so UI can show them if you want
        try:
            dfd["_render_warnings"] = warnings
        except Exception:
            pass

    # build graphs
    g1 = _build_graph(a_nodes, a_edges, f"{dfd.get('process_name','Process')} — Current State")
    g2 = _build_graph(f_nodes, f_edges, f"{dfd.get('process_name','Process')} — Post Compliance")

    # render to bytes
    a_png = g1.pipe(format="png")
    a_pdf = g1.pipe(format="pdf")
    f_png = g2.pipe(format="png")
    f_pdf = g2.pipe(format="pdf")

    return a_png, a_pdf, f_png, f_pdf
