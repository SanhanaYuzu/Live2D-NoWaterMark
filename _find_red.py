# -*- coding: utf-8 -*-
"""在贴图里找红色像素簇（水印红字指纹）: _find_red.py <model_dir_4096> <out_prefix>
纯 PIL 实现（无 numpy）。
"""
import sys, os, glob
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image
from collections import Counter

texdir = sys.argv[1]
outpfx = sys.argv[2]
for tex in sorted(glob.glob(os.path.join(texdir, "texture_*.png"))):
    im = Image.open(tex).convert("RGBA")
    W, H = im.size
    px = im.load()
    pts = []
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            if r > 120 and r - g > 50 and r - b > 50 and a > 40:
                pts.append((x, y))
    print(os.path.basename(tex), "red px =", len(pts))
    if len(pts) < 30:
        continue
    cells = Counter((x // 32, y // 32) for x, y in pts)
    hot = [(c, k) for c, k in cells.items() if k >= 5]
    hot.sort(key=lambda t: -t[1])
    print("  hot 32px cells:", len(hot))
    for (cx, cy), k in hot[:12]:
        print("    cell(x=%d,y=%d) px=%d -> px box x[%d,%d] y[%d,%d]"
              % (cx, cy, k, cx * 32, cx * 32 + 32, cy * 32, cy * 32 + 32))
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    print("  total bbox: x[%d,%d] y[%d,%d]" % (min(xs), max(xs), min(ys), max(ys)))
    vis = im.copy()
    vp = vis.load()
    for x, y in pts:
        vp[x, y] = (255, 0, 255, 255)
    vis.save("%s_%s" % (outpfx, os.path.basename(tex)))
