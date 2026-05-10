from pathlib import Path
import random

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
OUT_PNG = ROOT / "blaster" / "icon.png"
OUT_ICO = ROOT / "blaster" / "icon.ico"
CANVAS = 1024


def _lerp(a, b, t):
    return int(a + (b - a) * t)


def _lerp_color(c1, c2, t):
    return tuple(_lerp(c1[i], c2[i], t) for i in range(3))


def _rounded_mask(size, radius):
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def _gradient_background():
    bg = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(bg)
    top = (7, 15, 34)
    mid = (16, 42, 82)
    bottom = (2, 5, 14)
    for y in range(CANVAS):
        t = y / (CANVAS - 1)
        if t < 0.58:
            col = _lerp_color(top, mid, t / 0.58)
        else:
            col = _lerp_color(mid, bottom, (t - 0.58) / 0.42)
        draw.line((0, y, CANVAS, y), fill=(*col, 255))

    mask = _rounded_mask(CANVAS, 216)
    clipped = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    clipped.paste(bg, (0, 0), mask)
    return clipped, mask


def _add_glow(base, color, bbox, blur):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(bbox, fill=color)
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def _draw_logo():
    random.seed(42)
    img, mask = _gradient_background()
    draw = ImageDraw.Draw(img)

    _add_glow(img, (56, 178, 255, 84), (104, 130, 924, 760), 64)
    _add_glow(img, (255, 132, 62, 58), (230, 330, 794, 930), 72)
    _add_glow(img, (116, 78, 188, 52), (470, 80, 1110, 570), 70)

    stars = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(stars)
    for _ in range(96):
        x = random.randint(86, CANVAS - 86)
        y = random.randint(86, CANVAS - 86)
        r = random.choice((2, 2, 3, 4))
        alpha = random.randint(68, 190)
        sdraw.ellipse((x - r, y - r, x + r, y + r), fill=(190, 232, 255, alpha))
    img.alpha_composite(stars)

    grid = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grid)
    horizon = 710
    for idx in range(1, 8):
        y = horizon + idx * idx * 7
        gdraw.line((130, y, 894, y), fill=(72, 190, 190, 34), width=3)
    for x in range(170, 880, 92):
        gdraw.line((512, horizon, x, 972), fill=(72, 190, 190, 30), width=3)
    img.alpha_composite(grid)

    blast = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(blast)
    bdraw.ellipse((250, 252, 774, 776), outline=(255, 181, 76, 190), width=30)
    bdraw.ellipse((314, 316, 710, 712), outline=(98, 224, 255, 126), width=18)
    img.alpha_composite(blast.filter(ImageFilter.GaussianBlur(1.0)))

    ship_glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sg = ImageDraw.Draw(ship_glow)
    sg.ellipse((296, 200, 728, 788), fill=(68, 206, 255, 76))
    img.alpha_composite(ship_glow.filter(ImageFilter.GaussianBlur(34)))

    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.polygon([(512, 126), (722, 730), (512, 620), (302, 730)], fill=(0, 0, 0, 118))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(12)))

    wing = (27, 84, 150, 255)
    hull = (43, 148, 237, 255)
    line = (202, 244, 255, 255)
    panel = (10, 30, 64, 255)
    accent = (255, 207, 94, 255)

    left_wing = [(472, 384), (132, 628), (412, 766), (462, 548)]
    right_wing = [(552, 384), (892, 628), (612, 766), (562, 548)]
    tail_left = [(464, 560), (352, 916), (490, 742)]
    tail_right = [(560, 560), (672, 916), (534, 742)]
    hull_shape = [(512, 86), (694, 582), (512, 720), (330, 582)]
    panel_shape = [(512, 188), (608, 560), (512, 624), (416, 560)]

    draw.polygon(left_wing, fill=wing)
    draw.polygon(right_wing, fill=wing)
    draw.polygon(tail_left, fill=(33, 120, 142, 255))
    draw.polygon(tail_right, fill=(33, 120, 142, 255))
    draw.line(left_wing + [left_wing[0]], fill=line, width=16, joint="curve")
    draw.line(right_wing + [right_wing[0]], fill=line, width=16, joint="curve")
    draw.line(tail_left + [tail_left[0]], fill=(106, 244, 214, 230), width=10)
    draw.line(tail_right + [tail_right[0]], fill=(106, 244, 214, 230), width=10)

    draw.polygon(hull_shape, fill=hull)
    draw.line(hull_shape + [hull_shape[0]], fill=line, width=18, joint="curve")
    draw.polygon(panel_shape, fill=panel)
    draw.line(panel_shape + [panel_shape[0]], fill=(126, 224, 255, 255), width=8)

    draw.polygon([(512, 70), (550, 214), (512, 268), (474, 214)], fill=accent)
    draw.line([(512, 70), (550, 214), (512, 268), (474, 214), (512, 70)], fill=(255, 248, 196, 255), width=7)

    draw.ellipse((450, 244, 574, 420), fill=(138, 232, 255, 255), outline=(234, 255, 255, 255), width=9)
    draw.ellipse((480, 280, 544, 380), fill=(235, 254, 255, 230))
    draw.line((512, 250, 512, 416), fill=(15, 54, 96, 220), width=6)

    for x in (420, 604):
        draw.rounded_rectangle((x - 24, 168, x + 24, 388), radius=18, fill=(35, 54, 92, 255), outline=line, width=7)
        draw.ellipse((x - 17, 145, x + 17, 179), fill=accent)

    flame = Image.new("RGBA", img.size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(flame)
    for x in (424, 600):
        fd.rounded_rectangle((x - 38, 706, x + 38, 778), radius=24, fill=(30, 44, 78, 255), outline=(150, 178, 212, 255), width=7)
        fd.polygon([(x - 36, 762), (x + 36, 762), (x, 940)], fill=(255, 122, 72, 218))
        fd.polygon([(x - 18, 762), (x + 18, 762), (x, 888)], fill=(255, 234, 158, 238))
    img.alpha_composite(flame)

    border = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.rounded_rectangle((28, 28, CANVAS - 29, CANVAS - 29), radius=198, outline=(132, 216, 255, 210), width=22)
    bd.rounded_rectangle((60, 60, CANVAS - 61, CANVAS - 61), radius=172, outline=(255, 213, 118, 78), width=8)
    img.alpha_composite(border)

    final = Image.new("RGBA", img.size, (0, 0, 0, 0))
    final.paste(img, (0, 0), mask)
    return final


def main():
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    icon = _draw_logo()
    icon.save(OUT_PNG)
    icon.save(OUT_ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Wrote {OUT_PNG}")
    print(f"Wrote {OUT_ICO}")


if __name__ == "__main__":
    main()
