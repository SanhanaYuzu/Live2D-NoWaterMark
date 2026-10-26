# -*- coding: utf-8 -*-
# 立绘：统一裁剪框对齐 + 单张高清输出 + 深灰底对比大图
import os, sys
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageChops, ImageDraw, ImageFont

HERE = r"C:/Users/xihaochen/WorkBuddy/2026-08-12-17-01-00/live2d_wm"
SO = os.path.join(HERE, "_scan_out")

def alpha_bbox(path):
    im = Image.open(path).convert("RGBA")
    return im, im.split()[3].getbbox()

raw, rb = alpha_bbox(os.path.join(SO, "portrait_raw.png"))
pat, pb = alpha_bbox(os.path.join(SO, "portrait_patched.png"))
print("raw bbox", rb, " patched bbox", pb)

# 公共框（并集）+ 少量留白
x0 = min(rb[0], pb[0]) - 12; y0 = min(rb[1], pb[1]) - 12
x1 = max(rb[2], pb[2]) + 12; y1 = max(rb[3], pb[3]) + 12
box = (max(0,x0), max(0,y0), min(raw.width,x1), min(raw.height,y1))
print("统一裁剪框", box, "→", (box[2]-box[0], box[3]-box[1]))

raw_c = raw.crop(box)
pat_c = pat.crop(box)
raw_c.save(os.path.join(SO, "portrait_raw_HD.png"))
pat_c.save(os.path.join(SO, "portrait_patched_HD.png"))
print("单张立绘 → portrait_raw_HD.png / portrait_patched_HD.png", raw_c.size)

# ---- 对比大图 ----
BG = (32, 32, 36, 255)
FONT = r"C:/Windows/Fonts/msyh.ttc"
def font(sz):
    try: return ImageFont.truetype(r"C:/Windows/Fonts/msyhbd.ttc", sz)
    except Exception: return ImageFont.truetype(FONT, sz)

PAD, GAP, LABEL = 36, 36, 96
W = PAD*2 + raw_c.width*2 + GAP
H = PAD*2 + LABEL + raw_c.height
sheet = Image.new("RGBA", (W, H), BG)
dr = ImageDraw.Draw(sheet)

def panel(im, x, y, label, accent):
    dr.rectangle([x, y, x+im.width, y+LABEL-16], fill=accent)
    f = font(52)
    tw = dr.textlength(label, font=f)
    dr.text((x + (im.width-tw)//2, y+16), label, fill=(255,255,255), font=f)
    sheet.paste(im, (x, y+LABEL), im)

panel(raw_c, PAD, PAD, "原始（含水印）", (198, 62, 62, 255))
panel(pat_c, PAD+raw_c.width+GAP, PAD, "去水印后（零残留）", (36, 148, 92, 255))
out = os.path.join(SO, "portrait_compare.png")
sheet.convert("RGB").save(out)
print("对比图 →", out, sheet.size, os.path.getsize(out)//1024, "KB")
