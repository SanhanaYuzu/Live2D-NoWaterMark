# -*- coding: utf-8 -*-
"""在贴图里定位"孤立文字簇"（水印候选）：
① 4px 块级化 ② BFS 连通域 ③ 按特征筛"文字块"（面积小/密度低/远离主体部件）
④ 输出标记总览图 + bbox 列表（图像坐标，供 UV 覆盖检查用）。只读。"""
import os, sys, json
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_scan_out")
os.makedirs(OUT, exist_ok=True)
BLK = 4

def clusters(a, min_area=12, max_fill=700):
    """块级连通域。a: RGBA Image。返回 [(bbox(l,t,r,b) 图像坐标, 块数, 密度)]"""
    w, h = a.size
    alpha = a.getchannel("A")
    bw, bh = w // BLK, h // BLK
    small = alpha.resize((bw, bh), Image.BOX)      # 每块平均 alpha
    px = small.load()
    grid = [[1 if px[x, y] > 8 else 0 for x in range(bw)] for y in range(bh)]
    seen = [[False] * bw for _ in range(bh)]
    out = []
    for y0 in range(bh):
        for x0 in range(bw):
            if grid[y0][x0] and not seen[y0][x0]:
                stack = [(x0, y0)]; seen[y0][x0] = True
                minx = maxx = x0; miny = maxy = y0; cnt = 0
                while stack:
                    x, y = stack.pop(); cnt += 1
                    minx = min(minx, x); maxx = max(maxx, x)
                    miny = min(miny, y); maxy = max(maxy, y)
                    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < bw and 0 <= ny < bh and grid[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True; stack.append((nx, ny))
                area = cnt * BLK * BLK
                box_w, box_h = (maxx - minx + 1) * BLK, (maxy - miny + 1) * BLK
                dens = cnt / float((maxx - minx + 1) * (maxy - miny + 1))
                if area >= min_area:
                    out.append({"bbox": [minx*BLK, miny*BLK, (maxx+1)*BLK, (maxy+1)*BLK],
                                "area": area, "w": box_w, "h": box_h, "dens": round(dens, 3)})
    return out

def looks_like_text(c):
    """文字簇：细长、密度不高、不算太大（主体部件通常又大又密）"""
    return (c["area"] < 60000 and c["w"] >= 40 and c["h"] >= 12
            and c["dens"] < 0.55 and max(c["w"], c["h"]) < 2400)

for tex in sys.argv[1:]:
    name = os.path.splitext(os.path.basename(tex))[0]
    model = os.path.basename(os.path.dirname(os.path.dirname(tex)))
    im = Image.open(tex).convert("RGBA")
    cs = clusters(im)
    texts = [c for c in cs if looks_like_text(c)]
    # 画标记图
    vis = im.resize((1024, 1024), Image.LANCZOS).convert("RGB")
    dr = ImageDraw.Draw(vis)
    sx = 1024.0 / im.size[0]
    for c in texts:
        l, t, r, b = c["bbox"]
        dr.rectangle([l*sx, t*sx, r*sx, b*sx], outline=(255, 40, 40), width=2)
    f = os.path.join(OUT, "clusters_%s_%s.png" % (model, name))
    vis.save(f)
    print("=" * 70)
    print("%s / %s：连通域 %d 个，疑似文字簇 %d 个 → %s" % (model, name, len(cs), len(texts), f))
    for c in sorted(texts, key=lambda c: -c["area"])[:15]:
        print("   bbox=%s area=%d %dx%d dens=%s" % (c["bbox"], c["area"], c["w"], c["h"], c["dens"]))
