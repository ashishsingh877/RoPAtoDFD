from PIL import Image, ImageDraw

W = 1800
H = 900


def render_dfd(dfd_json):

    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    x = 80
    y = 100

    for phase in dfd_json["phases"]:

        for step in phase["steps"]:

            draw.rectangle(
                (x, y, x+160, y+60),
                outline="black",
                width=2
            )

            draw.text((x+10, y+20), step["label"], fill="black")

            x += 220

            if x > 1600:
                x = 80
                y += 120

    return img
