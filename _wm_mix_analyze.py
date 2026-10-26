# -*- coding: utf-8 -*-
# 混合网格三角形分类分析：
#   判据A: 三角形 UV 质心是否落在同贴图纯文字网格的 UV 盒内（外扩 pad）
#   判据B: 三角形位置质心 y 分布（模型空间，看双峰）
import json, io, sys
sys.stdout.reconfigure(encoding="utf-8")

RAW = json.load(io.open("_wm_uvraw_result.json", encoding="utf-8"))
ALL = json.load(io.open("_wm_alldump_result.json", encoding="utf-8"))["meshes"]
TEX = 4096
PAD = 8.0  # texel 外扩

# 纯文字网格 -> (tex, UV 盒 texel)
PURE = {}
for key in ("d558_ArtMesh1595", "d559_ArtMesh1239", "d560_ArtMesh1644"):
    d = RAW["dump"].get(key) or RAW.get(key)
    if d is None:
        # 兼容不同结构
        for k in RAW:
            if key in str(k): print("结构提示:", k)
print("RAW keys:", list(RAW.keys())[:5])
D = RAW["dump"] if "dump" in RAW else RAW

def get(key):
    m = D.get(key)
    if m is not None and "uvs" not in m and key in ALL:
        m = dict(m); m["uvs"] = ALL[key]["uvs"]
    return m

pure_boxes = {}
for key, tex in (("d558_ArtMesh1595", 3), ("d559_ArtMesh1239", 5), ("d560_ArtMesh1644", 4)):
    m = get(key)
    us = [m["uvs"][i*2] for i in range(m["vertCount"])]
    vs = [m["uvs"][i*2+1] for i in range(m["vertCount"])]
    box = (min(us)*TEX-PAD, min(vs)*TEX-PAD, max(us)*TEX+PAD, max(vs)*TEX+PAD)
    pure_boxes[tex] = (key, box)
    print(f"纯文字 {key} tex{tex} UV盒(texel) = {[round(v,1) for v in box]}")

MIX = (("d323_ArtMesh1307", 3), ("d400_ArtMesh1217", 5), ("d496_ArtMesh1635", 4))
out = {}
for key, tex in MIX:
    m = get(key)
    uvs, pos, idx, vc = m["uvs"], m["positions"], m["indices"], m["vertCount"]
    _, box = pure_boxes[tex]
    n_tri = len(idx)//3
    in_uv = 0; ys = []
    text_tris = []
    for t in range(n_tri):
        vis = [idx[t*3+k] for k in range(3)]
        uc = sum(uvs[v*2] for v in vis)/3*TEX
        vcen = sum(uvs[v*2+1] for v in vis)/3*TEX
        cy = sum(pos[v*2+1] for v in vis)/3
        ys.append(cy)
        if box[0] <= uc <= box[2] and box[1] <= vcen <= box[3]:
            in_uv += 1; text_tris.append(t)
    ys.sort()
    print(f"\n== {key} tex{tex} tri={n_tri} ==")
    print(f"  判据A(UV在纯文字盒内): {in_uv}/{n_tri} = {in_uv/n_tri:.3f}")
    # y 直方 20 桶
    y0, y1 = ys[0], ys[-1]
    hist = [0]*20
    for y in ys:
        b = min(19, int((y-y0)/max(y1-y0, 1e-9)*20))
        hist[b] += 1
    print(f"  y范围 [{y0:.3f},{y1:.3f}] 直方:", hist)
    out[key] = {"tri": n_tri, "in_uv": in_uv, "ys": ys, "text_tris_uv": text_tris,
                "pure_box": pure_boxes[tex][1]}

json.dump({k: {"tri": v["tri"], "in_uv": v["in_uv"], "ys": v["ys"],
               "text_tris_uv": v["text_tris_uv"]} for k, v in out.items()},
          io.open("_wm_mix_analyze.json", "w"), indent=1)
print("\nsaved _wm_mix_analyze.json")
