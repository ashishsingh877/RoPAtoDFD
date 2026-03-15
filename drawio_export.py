import uuid
import xml.etree.ElementTree as ET

NODE_W = 160
NODE_H = 60
PHASE_VERTICAL_GAP = 120
HORIZONTAL_GAP = 220

COLORS = {

    "external": dict(
        fillColor="#FFE6CC",
        strokeColor="#D79B00",
        rounded="1"
    ),

    "process": dict(
        fillColor="#FFFFFF",
        strokeColor="#000000",
        rounded="0"
    ),

    "decision": dict(
        fillColor="#FF0000",
        strokeColor="#000000",
        fontColor="#FFFFFF",
        shape="rhombus"
    ),

    "endpoint": dict(
        fillColor="#FF0000",
        strokeColor="#000000",
        fontColor="#FFFFFF",
        shape="ellipse"
    ),

    "datastore": dict(
        fillColor="#DAE8FC",
        strokeColor="#000000",
        shape="mxgraph.flowchart.stored_data"
    ),

    "privacy": dict(
        fillColor="#D5E8D4",
        strokeColor="#82B366",
        rounded="1"
    ),
}


def build_style(style_dict):
    style = []
    for k, v in style_dict.items():
        style.append(f"{k}={v}")
    return ";".join(style)


def create_vertex(parent, value, x, y, style):

    cell_id = str(uuid.uuid4())

    cell = ET.SubElement(parent, "mxCell", {
        "id": cell_id,
        "value": value,
        "style": style,
        "vertex": "1",
        "parent": "1"
    })

    geo = ET.SubElement(cell, "mxGeometry", {
        "x": str(x),
        "y": str(y),
        "width": str(NODE_W),
        "height": str(NODE_H),
        "as": "geometry"
    })

    return cell_id


def create_edge(parent, source, target):

    edge_id = str(uuid.uuid4())

    ET.SubElement(parent, "mxCell", {
        "id": edge_id,
        "edge": "1",
        "parent": "1",
        "source": source,
        "target": target,
        "style": "edgeStyle=orthogonalEdgeStyle;rounded=0;strokeColor=#000000;endArrow=block;endFill=1;"
    })


def generate_drawio_xml(dfd_json, state="future"):

    root = ET.Element("mxfile")
    diagram = ET.SubElement(root, "diagram", {"name": "DFD"})
    graph = ET.SubElement(diagram, "mxGraphModel")

    root_cell = ET.SubElement(graph, "root")

    ET.SubElement(root_cell, "mxCell", {"id": "0"})
    ET.SubElement(root_cell, "mxCell", {"id": "1", "parent": "0"})

    nodes = []
    edges = []

    for phase in dfd_json["phases"]:
        for step in phase["steps"]:
            nodes.append(step)

    for phase in dfd_json["phases"]:
        for flow in phase.get("flows", []):
            edges.append(flow)

    parent = root_cell

    node_ids = {}

    x = 80
    y = 80

    for node in nodes:

        style = build_style(COLORS.get(node["type"], COLORS["process"]))

        node_id = create_vertex(parent, node["label"], x, y, style)

        node_ids[node["id"]] = node_id

        x += HORIZONTAL_GAP

        if x > 1600:
            x = 80
            y += PHASE_VERTICAL_GAP

    for e in edges:

        src = node_ids.get(e["from"])
        dst = node_ids.get(e["to"])

        if src and dst:
            create_edge(parent, src, dst)

    xml_str = ET.tostring(root).decode()

    return xml_str
