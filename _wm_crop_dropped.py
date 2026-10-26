# -*- coding: utf-8 -*-
"""把 dropped drawable 的 UV 框从贴图裁出，拼标注对照图。
用法: python _wm_crop_dropped.py"""
import json, io, os, sys
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "_work", "薄巧_体验版", "薄巧_体验版")
TEXDIR = os.path.join(MODEL, "薄巧_体验版.4096")

O = json.load(io.open(os.path.join(HERE, "_wm_part10_result.json"), encoding="utf-8"))
texs = {}
tiles = []
for h in O["detail"]:
    tex = h["tex"]
    if tex not in texs:
        texs[tex] = Image.open(os.path.join(TEXDIR, "texture_%02d.png" % tex)).convert("RGBA")
    im = texs[tex]
    x0, y0, x1, y1 = h["uvBoxPx"]
    pad = 16
    c = im.crop((max(0, x0 - pad), max(0, y0 - pad), min(4096, x1 + pad), min(4096, y1 + pad)))
    # 放大到 260 宽
    if c.width < 260:
        s = 260 / c.width
        c = c.resize((260, max(1, int(c.height * s))), Image.NEAREST)
    tile = Image.new("RGB", (270, c.height + 26), (30, 30, 30))
    bg = Image.new("RGBA", c.size, (235, 235, 235, 255))
    bg.alpha_composite(c)
    tile.paste(bg.convert("RGB"), (5, 22))
    d = ImageDraw.Draw(tile)
    d.text((5, 4), "d=%s %s tex%d v%s" % (h["d"], h["id"], tex, h["vertCount"]), fill=(255, 220, 120))
    tiles.append(tile)

# 拼列
cols = 5
colw = 275
rows = (len(tiles) + cols - 1) // cols
colh = [max(t.height for t in tiles[r * cols:(r + 1) * cols]) for r in range(rows)]
W = cols * colw
H = sum(colh)
sheet = Image.new("RGB", (W, H), (15, 15, 15))
y = 0
for r in range(rows):
    for c2 in range(cols):
        i = r * cols + c2
        if i < len(tiles):
            sheet.paste(tiles[i], (c2 * colw, y))
    y += colh[r]
out = os.path.join(HERE, "_scan_out", "p10_dropped_sheet.png")
sheet.save(out)
print("saved", out, sheet.size, "tiles", len(tiles))
