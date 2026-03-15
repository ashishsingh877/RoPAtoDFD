import graphviz

# --------------------------------------------------
# REQUIRED BY prompts.py
# --------------------------------------------------

DFD_JSON_SCHEMA = {
    "nodes": [
        {
            "id": "string",
            "label": "string",
            "type": "external | process | datastore | decision",
            "phase": "collection | processing | storage | sharing | outcome"
        }
    ],
    "edges": [
        {
            "from": "node_id",
            "to": "node_id",
            "label": "optional"
        }
    ]
}


# --------------------------------------------------
# NODE STYLE MAP
# --------------------------------------------------

def get_node_style(node_type):

    if node_type == "external":
        return {
            "shape": "box",
            "style": "rounded,filled",
            "fillcolor": "#FFF2CC",
            "color": "#B7950B"
        }

    elif node_type == "datastore":
        return {
            "shape": "cylinder",
            "style": "filled",
            "fillcolor": "#D6EAF8",
            "color": "#1F618D"
        }

    elif node_type == "decision":
        return {
            "shape": "diamond",
            "style": "filled",
            "fillcolor": "#F5B7B1",
            "color": "#922B21"
        }

    else:
        return {
            "shape": "box",
            "style": "rounded,filled",
            "fillcolor": "#FDEDEC",
            "color": "#7B241C"
        }


# --------------------------------------------------
# MAIN GRAPH RENDERER
# --------------------------------------------------

def render_dfd(nodes, edges, title="Data Flow Diagram"):

    dot = graphviz.Digraph(
        "DFD",
        format="png",
        graph_attr={
            "rankdir": "LR",
            "splines": "ortho",
            "nodesep": "0.9",
            "ranksep": "1.3",
            "pad": "0.5",
            "fontname": "Segoe UI"
        },
        node_attr={
            "fontname": "Segoe UI",
            "fontsize": "11"
        },
        edge_attr={
            "color": "#555555",
            "penwidth": "1.8",
            "arrowsize": "0.8"
        }
    )

    dot.attr(label=title, labelloc="t", fontsize="20")

    # --------------------------------------------------
    # PHASE GROUPING
    # --------------------------------------------------

    phases = {
        "collection": [],
        "processing": [],
        "storage": [],
        "sharing": [],
        "outcome": []
    }

    for n in nodes:

        phase = n.get("phase", "processing").lower()

        if phase not in phases:
            phase = "processing"

        phases[phase].append(n)

    # --------------------------------------------------
    # CREATE SWIMLANE CLUSTERS
    # --------------------------------------------------

    def create_cluster(name, nodes):

        with dot.subgraph(name=f"cluster_{name}") as c:

            c.attr(
                label=name.capitalize(),
                style="rounded",
                color="#DDDDDD",
                fontname="Segoe UI",
                fontsize="14"
            )

            for node in nodes:

                style = get_node_style(node.get("type", "process"))

                c.node(
                    node["id"],
                    node["label"],
                    **style
                )

    create_cluster("collection", phases["collection"])
    create_cluster("processing", phases["processing"])
    create_cluster("storage", phases["storage"])
    create_cluster("sharing", phases["sharing"])
    create_cluster("outcome", phases["outcome"])

    # --------------------------------------------------
    # EDGES
    # --------------------------------------------------

    for e in edges:

        dot.edge(
            e["from"],
            e["to"],
            label=e.get("label", "")
        )

    return dot
