import graphviz
import io


DFD_JSON_SCHEMA = {
    "id": "string",
    "process_name": "string",
    "asis": {
        "nodes": [],
        "edges": []
    },
    "future": {
        "nodes": [],
        "edges": []
    }
}


# --------------------------------------------------
# node styling
# --------------------------------------------------

def node_style(node_type):

    if node_type == "external":
        return dict(shape="box", style="rounded,filled",
                    fillcolor="#FFF2CC", color="#B7950B")

    if node_type == "datastore":
        return dict(shape="cylinder", style="filled",
                    fillcolor="#D6EAF8", color="#1F618D")

    if node_type == "decision":
        return dict(shape="diamond", style="filled",
                    fillcolor="#F5B7B1", color="#922B21")

    return dict(shape="box", style="rounded,filled",
                fillcolor="#FDEDEC", color="#7B241C")


# --------------------------------------------------
# graph builder
# --------------------------------------------------

def build_graph(nodes, edges, title):

    dot = graphviz.Digraph(
        format="png",
        graph_attr={
            "rankdir": "LR",
            "splines": "ortho",
            "nodesep": "0.9",
            "ranksep": "1.2",
            "fontname": "Segoe UI"
        },
        node_attr={
            "fontname": "Segoe UI",
            "fontsize": "11"
        },
        edge_attr={
            "color": "#555555",
            "penwidth": "1.6"
        }
    )

    dot.attr(label=title, labelloc="t", fontsize="20")

    for n in nodes:

        style = node_style(n.get("type", "process"))

        dot.node(
            n["id"],
            n["label"],
            **style
        )

    for e in edges:

        dot.edge(
            e["from"],
            e["to"],
            label=e.get("label", "")
        )

    return dot


# --------------------------------------------------
# render helper
# --------------------------------------------------

def render_graph(dot):

    png = dot.pipe(format="png")
    pdf = dot.pipe(format="pdf")

    return png, pdf


# --------------------------------------------------
# main renderer used by app.py
# --------------------------------------------------

def render_dfd(dfd):

    # fallback if AI returns flat structure
    asis = dfd.get("asis") or {
        "nodes": dfd.get("nodes", []),
        "edges": dfd.get("edges", [])
    }

    future = dfd.get("future") or {
        "nodes": dfd.get("nodes", []),
        "edges": dfd.get("edges", [])
    }

    pname = dfd.get("process_name", "Process")

    g1 = build_graph(
        asis.get("nodes", []),
        asis.get("edges", []),
        f"{pname} — Current State"
    )

    g2 = build_graph(
        future.get("nodes", []),
        future.get("edges", []),
        f"{pname} — Post Compliance"
    )

    a_png, a_pdf = render_graph(g1)
    f_png, f_pdf = render_graph(g2)

    return a_png, a_pdf, f_png, f_pdf
