# -*- coding: utf-8 -*-
"""贴图侦查：① 生成每张贴图的缩略总览图（人工看整体）② 统计"疑似文字"区域。
只读，产物写进 _scan_out/。"""
import os, sys, io
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_scan_out")
os.makedirs(OUT, exist_ok=True)

MODELS = [
    ("花嫁小狐免费版", os.path.join(HERE, "_work", "花嫁小狐免费版", "花嫁小狐免费版")),
    ("薄巧_体验版",   os.path.join(HERE, "_work", "薄巧_体验版", "薄巧_体验版")),
]

def texs(root):
    out = []
    for dp, dn, fn in os.walk(root):
        for f in sorted(fn):
            if f.lower().endswith(".png") and "texture" in f.lower():
                out.append(os.path.join(dp, f))
    return sorted(out)

for name, root in MODELS:
    files = texs(root)
    print("=" * 70); print(name, "贴图", len(files), "张")
    thumbs = []
    for p in files:
        im = Image.open(p)
        a = im.convert("RGBA")
        # 透明像素占比（图集里常有大量空白）
        alpha = a.getchannel("A")
        hist = alpha.histogram()
        nonzero = sum(hist[1:])
        total = a.size[0] * a.size[1]
        print("  %-14s %sx%s  非透明 %.1f%%" % (os.path.basename(p), a.size[0], a.size[1],
                                              100.0 * nonzero / total))
        t = a.resize((768, 768), Image.LANCZOS)
        thumbs.append((os.path.basename(p), t))
    cols = 3
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * 768, rows * 768), (24, 24, 28, 255))
    for i, (nm, t) in enumerate(thumbs):
        sheet.paste(t, ((i % cols) * 768, (i // cols) * 768), t)
    f = os.path.join(OUT, "tex_sheet_%s.png" % name)
    sheet.convert("RGB").save(f)
    print("  总览图 →", f)
