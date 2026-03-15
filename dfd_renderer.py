import graphviz


DFD_JSON_SCHEMA = {}


def node_style(t):

    if t == "external":
        return {"shape":"box","style":"rounded,filled","fillcolor":"#FFF2CC","color":"#B7950B"}

    if t == "datastore":
        return {"shape":"cylinder","style":"filled","fillcolor":"#D6EAF8","color":"#1F618D"}

    if t == "decision":
        return {"shape":"diamond","style":"filled","fillcolor":"#F5B7B1","color":"#922B21"}

    return {"shape":"box","style":"rounded,filled","fillcolor":"#FDEDEC","color":"#7B241C"}


def build_graph(nodes, edges, title):

    dot = graphviz.Digraph(
        format="png",
        graph_attr={
            "rankdir":"LR",
            "splines":"ortho",
            "nodesep":"1.0",
            "ranksep":"1.5",
            "fontname":"Segoe UI"
        }
    )

    dot.attr(label=title, labelloc="t", fontsize="20")

    phases = {
        "collection":[],
        "processing":[],
        "storage":[],
        "sharing":[],
        "outcome":[]
    }

    for n in nodes:

        phase = n.get("phase","processing").lower()

        if phase not in phases:
            phase="processing"

        phases[phase].append(n)

    def lane(name, nodeset):

        with dot.subgraph(name=f"cluster_{name}") as c:

            c.attr(
                label=name.capitalize(),
                style="rounded",
                color="#DDDDDD",
                fontname="Segoe UI"
            )

            for n in nodeset:

                s = node_style(n.get("type","process"))

                c.node(n["id"], n["label"], **s)

    lane("collection",phases["collection"])
    lane("processing",phases["processing"])
    lane("storage",phases["storage"])
    lane("sharing",phases["sharing"])
    lane("outcome",phases["outcome"])

    for e in edges:

        dot.edge(
            e["from"],
            e["to"],
            label=e.get("label","")
        )

    return dot


def render_graph(dot):

    png = dot.pipe(format="png")
    pdf = dot.pipe(format="pdf")

    return png,pdf


def render_dfd(dfd):

    # try structured format first
    asis = dfd.get("asis")
    future = dfd.get("future")

    # fallback if AI returned flat nodes/edges
    if not asis:
        asis = {
            "nodes": dfd.get("nodes", []),
            "edges": dfd.get("edges", [])
        }

    if not future:
        future = {
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

    a_png,a_pdf = render_graph(g1)
    f_png,f_pdf = render_graph(g2)

    return a_png,a_pdf,f_png,f_pdf
