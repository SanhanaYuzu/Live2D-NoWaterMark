# -*- coding: utf-8 -*-
"""裁贴图区域看细节：_crop_tex.py <tex.png> <x0> <y0> <x1> <y1> <out.png> [scale]"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image

a = sys.argv[1:]
tex, x0, y0, x1, y1, out = a[0], int(a[1]), int(a[2]), int(a[3]), int(a[4]), a[5]
scale = int(a[6]) if len(a) > 6 else 4
im = Image.open(tex).convert("RGBA")
W, H = im.size
x0 = max(0, min(W, x0)); x1 = max(0, min(W, x1))
y0 = max(0, min(H, y0)); y1 = max(0, min(H, y1))
c = im.crop((x0, y0, x1, y1))
print("tex=%s size=%dx%d crop=(%d,%d)-(%d,%d) -> %dx%d scale=%d"
      % (os.path.basename(tex), W, H, x0, y0, x1, y1, c.width, c.height, scale))
c = c.resize((max(1, c.width * scale), max(1, c.height * scale)), Image.NEAREST)
# 贴到不透明浅灰底，便于看透明区
bg = Image.new("RGBA", c.size, (235, 235, 235, 255))
bg.alpha_composite(c)
bg.convert("RGB").save(out)
print("saved", out, bg.size)
