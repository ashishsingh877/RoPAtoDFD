"""
dfd_renderer.py
Professional Consulting-Style DFD Renderer
Improved layout + spacing + orthogonal connectors
"""

import io
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------
# FONT
# ---------------------------------------------------

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def get_font(size, bold=False):
    try:
        return ImageFont.truetype(FONT_BOLD if bold else FONT, size)
    except:
        return ImageFont.load_default()


# ---------------------------------------------------
# COLORS
# ---------------------------------------------------

COLORS = {
    "bg": "#ffffff",
    "external_fill": "#FFF5CC",
    "external_border": "#A07800",

    "process_fill": "#ffffff",
    "process_border": "#555555",

    "team_fill": "#FADADD",
    "team_border": "#B03030",

    "datastore_fill": "#D4E8FA",
    "datastore_border": "#1A5276",

    "decision_fill": "#C0392B",
    "decision_border": "#8B2222",

    "endpoint_fill": "#B03030",
}

# ---------------------------------------------------
# CANVAS
# ---------------------------------------------------

WIDTH = 6000
HEIGHT = 1600

LANE_WIDTH = 1000
TOP_MARGIN = 220

NODE_W = 220
NODE_H = 80

# ---------------------------------------------------
# DRAW TEXT
# ---------------------------------------------------

def draw_center_text(draw, box, text, font):
    x1,y1,x2,y2 = box
    w = x2-x1
    h = y2-y1

    lines = text.split("\n")

    total_h = len(lines) * (font.size + 4)
    y = y1 + (h-total_h)/2

    for line in lines:
        bbox = draw.textbbox((0,0),line,font=font)
        tw = bbox[2]-bbox[0]
        draw.text((x1 + (w-tw)/2 , y), line, font=font, fill="black")
        y += font.size+4


# ---------------------------------------------------
# NODE DRAWING
# ---------------------------------------------------

def draw_process(draw,x,y,label):

    box = (x,y,x+NODE_W,y+NODE_H)

    draw.rectangle(
        box,
        fill=COLORS["process_fill"],
        outline=COLORS["process_border"],
        width=2
    )

    draw_center_text(draw,box,label,get_font(14))


def draw_external(draw,x,y,label):

    box = (x,y,x+NODE_W,y+NODE_H)

    draw.rounded_rectangle(
        box,
        radius=14,
        fill=COLORS["external_fill"],
        outline=COLORS["external_border"],
        width=2
    )

    draw_center_text(draw,box,label,get_font(14))


def draw_datastore(draw,x,y,label):

    box = (x,y,x+NODE_W,y+NODE_H)

    draw.rectangle(
        box,
        fill=COLORS["datastore_fill"],
        outline=COLORS["datastore_border"],
        width=2
    )

    draw_center_text(draw,box,label,get_font(14))


def draw_decision(draw,x,y,label):

    cx = x + NODE_W/2
    cy = y + NODE_H/2

    pts = [
        (cx,y),
        (x+NODE_W,cy),
        (cx,y+NODE_H),
        (x,cy)
    ]

    draw.polygon(
        pts,
        fill=COLORS["decision_fill"],
        outline=COLORS["decision_border"]
    )

    draw_center_text(draw,(x,y,x+NODE_W,y+NODE_H),label,get_font(14,True))


# ---------------------------------------------------
# ORTHOGONAL CONNECTOR
# ---------------------------------------------------

def connect(draw,x1,y1,x2,y2):

    mid = (x1 + x2) / 2

    draw.line([(x1,y1),(mid,y1)], fill="#666", width=3)
    draw.line([(mid,y1),(mid,y2)], fill="#666", width=3)
    draw.line([(mid,y2),(x2,y2)], fill="#666", width=3)

    # arrow

    arrow = [
        (x2,y2),
        (x2-12,y2-6),
        (x2-12,y2+6)
    ]

    draw.polygon(arrow, fill="#666")


# ---------------------------------------------------
# MAIN RENDER
# ---------------------------------------------------

def render_dfd(nodes,edges,title="DFD"):

    img = Image.new("RGB",(WIDTH,HEIGHT),COLORS["bg"])
    draw = ImageDraw.Draw(img)

    title_font = get_font(34,True)

    draw.text((60,60),title,font=title_font,fill="#1a1a1a")

    # ------------------------------------------------
    # PHASE LANES
    # ------------------------------------------------

    phases = [
        "Collection",
        "Processing",
        "Storage",
        "Sharing",
        "Outcome"
    ]

    lane_font = get_font(18,True)

    for i,p in enumerate(phases):

        x = i * LANE_WIDTH + 60

        draw.text(
            (x,140),
            p,
            font=lane_font,
            fill="#555"
        )

        draw.line(
            [(x-20,180),(x-20,HEIGHT-60)],
            fill="#dddddd",
            width=2
        )

    # ------------------------------------------------
    # NODE POSITIONS
    # ------------------------------------------------

    positions = {}

    for i,node in enumerate(nodes):

        lane = node.get("phase","processing")

        lane_index = phases.index(lane.capitalize()) if lane.capitalize() in phases else 1

        x = lane_index * LANE_WIDTH + 80
        y = TOP_MARGIN + (i%5)*220

        positions[node["id"]] = (x,y)

        typ = node.get("type","process")

        if typ=="external":
            draw_external(draw,x,y,node["label"])

        elif typ=="datastore":
            draw_datastore(draw,x,y,node["label"])

        elif typ=="decision":
            draw_decision(draw,x,y,node["label"])

        else:
            draw_process(draw,x,y,node["label"])


    # ------------------------------------------------
    # EDGES
    # ------------------------------------------------

    for e in edges:

        a = positions[e["from"]]
        b = positions[e["to"]]

        x1 = a[0]+NODE_W
        y1 = a[1]+NODE_H/2

        x2 = b[0]
        y2 = b[1]+NODE_H/2

        connect(draw,x1,y1,x2,y2)


    buf = io.BytesIO()
    img.save(buf,"PNG",dpi=(300,300))
    buf.seek(0)

    return buf
