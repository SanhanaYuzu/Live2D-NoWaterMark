# -*- coding: utf-8 -*-
# 花嫁小狐去水印 高清对照图：水印区放大 + 脸部特写，原始 vs 处理后
import os, sys, io
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw, ImageFont

HERE = r"C:/Users/xihaochen/WorkBuddy/2026-08-12-17-01-00/live2d_wm"
RAW = os.path.join(HERE, "_scan_out", "hj_frame_raw.png")
PAT = os.path.join(HERE, "_scan_out", "hj_frame_patched.png")
OUT = os.path.join(HERE, "_scan_out", "hj_compare_hd.png")

FONT = r"C:/Windows/Fonts/msyh.ttc"

def font(sz, bold=False):
    p = r"C:/Windows/Fonts/msyhbd.ttc" if bold else FONT
    try:
        return ImageFont.truetype(p, sz)
    except Exception:
        return ImageFont.truetype(FONT, sz)

def crop_frac(im, x0, y0, x1, y1):
    W, H = im.size
    return im.crop((int(W*x0), int(H*y0), int(W*x1), int(H*y1)))

def fit(im, tw, th):
    r = min(tw/im.width, th/im.height)
    return im.resize((max(1,int(im.width*r)), max(1,int(im.height*r))), Image.LANCZOS)

raw = Image.open(RAW).convert("RGB")
pat = Image.open(PAT).convert("RGB")
print("raw", raw.size, "patched", pat.size)

# ---- 区域（按各图自身比例，内容一致）----
# 水印区：x[0.34,0.66] y[0.16,0.84]
WM = (0.34, 0.16, 0.66, 0.84)
# 脸部特写：x[0.40,0.60] y[0.13,0.42]
FACE = (0.40, 0.13, 0.60, 0.42)

TILE_W, TILE_H = 900, 720      # 每个面板内容区
TILE_W2, TILE_H2 = 900, 400    # 第二行

F1 = font(40, True)
F2 = font(26)
F3 = font(30, True)

BG = (255, 255, 255)
PAD = 26
GAP = 26
LABEL_H = 54
HEADER = 96

canvas_w = PAD*2 + TILE_W*2 + GAP
canvas_h = HEADER + LABEL_H + TILE_H + GAP + LABEL_H + TILE_H2 + PAD
sheet = Image.new("RGB", (canvas_w, canvas_h), BG)
dr = ImageDraw.Draw(sheet)

# 标题
dr.text((PAD, 26), "花嫁小狐免费版 · 去水印前后对照（高清放大）", fill=(20,20,20), font=F1)
dr.text((PAD, 74), "左：原始（含 7 行水印）    右：处理后（零水印残留）", fill=(120,120,120), font=F2)

def panel(img, x, y, w, h, label, accent):
    im2 = fit(img, w, h)
    # 标签条
    dr.rectangle([x, y, x+w, y+LABEL_H-6], fill=accent)
    dr.text((x+14, y+11), label, fill=(255,255,255), font=F3)
    # 内容居中
    cx = x + (w - im2.width)//2
    cy = y + LABEL_H + (h - im2.height)//2
    sheet.paste(im2, (cx, cy))
    dr.rectangle([x-1, y-1, x+w, y+LABEL_H+h], outline=(210,210,210), width=2)

y1 = HEADER
xL, xR = PAD, PAD + TILE_W + GAP

panel(crop_frac(raw, *WM), xL, y1, TILE_W, TILE_H, "原始 · 水印区 ×2.5", (200, 60, 60))
panel(crop_frac(pat, *WM), xR, y1, TILE_W, TILE_H, "处理后 · 水印区 ×2.5", (40, 150, 90))

y2 = y1 + LABEL_H + TILE_H + GAP
panel(crop_frac(raw, *FACE), xL, y2, TILE_W, TILE_H2, "原始 · 脸部特写 ×4", (200, 60, 60))
panel(crop_frac(pat, *FACE), xR, y2, TILE_W, TILE_H2, "处理后 · 脸部特写 ×4", (40, 150, 90))

sheet.save(OUT)
print("saved", OUT, sheet.size)
