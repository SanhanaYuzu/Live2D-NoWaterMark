# -*- coding: utf-8 -*-
"""
安全替换 exe 图标：Windows UpdateResource 会丢弃 PyInstaller 追加的 CArchive 覆盖层，
因此先提取覆盖层 → 改图标 → 再把原覆盖层拼回去（cookie 中的 pkg_length 不变）。
"""
import os, struct, shutil, sys
from PIL import Image
from win32ctypes.pywin32.win32api import (
    LoadLibraryEx, FreeLibrary, EnumResourceTypes, EnumResourceNames,
    BeginUpdateResource, UpdateResource, EndUpdateResource
)

RT_ICON = 3
RT_GROUP_ICON = 14
LOAD_LIBRARY_AS_DATAFILE = 2
COOKIE_MAGIC = b'MEI\x0c\x0b\x0a\x0b\x0e'
COOKIE_FORMAT = '!8sIIII64s'
COOKIE_LEN = struct.calcsize(COOKIE_FORMAT)

SRC_PNG = r"C:\Users\xihaochen\.workbuddy\clipboard-images\clipboard-2026-10-07T12-32-20-814Z-4716a6cc.png"
ICO     = r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm\atech_icon.ico"
EXE     = r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm\dist\Live2D去水印_v24.exe"
TMP     = r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm\_icon_tmp.exe"
BACKUP  = r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm\_trash\Live2D去水印_v24_换图标前_安全版.exe"

LANCZOS = getattr(Image, 'Resampling', Image).LANCZOS

# ───────────── 1) 生成 7 尺寸 ICO（白底转透明） ─────────────
im = Image.open(SRC_PNG).convert("RGBA")
px = list(im.getdata())
out = []
for r, g, b, a in px:
    lum = (r + g + b) // 3
    new_a = max(0, min(255, 255 - lum))
    out.append((r, g, b, new_a))
im.putdata(out)

w, h = im.size
s = min(w, h)
im = im.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
im256 = im.resize((256, 256), LANCZOS)

sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
im256.save(ICO, format='ICO', sizes=sizes)
print("ICO created:", ICO, os.path.getsize(ICO), "bytes")

with open(ICO, "rb") as f:
    ico = f.read()
reserved, itype, count = struct.unpack('<HHH', ico[:6])
ico_entries = []
off = 6
for i in range(count):
    w, h, colors, reserved, planes, bitcount, size, img_off = struct.unpack('<BBBBHHII', ico[off:off + 16])
    ico_entries.append({
        'width': w or 256, 'height': h or 256,
        'planes': planes, 'bitcount': bitcount,
        'size': size, 'data': ico[img_off:img_off + size]
    })
    off += 16
print("ICO entries:", [(e['width'], e['height'], e['size']) for e in ico_entries])
assert len(ico_entries) == 7

# ───────────── 2) 备份并提取 CArchive 覆盖层 ─────────────
shutil.copy2(EXE, BACKUP)
print("backup ->", BACKUP)

with open(EXE, "rb") as f:
    f.seek(-COOKIE_LEN, 2)
    ck = f.read(COOKIE_LEN)
magic, pkg_length, toc_offset, toc_length, pyvers, pylib = struct.unpack(COOKIE_FORMAT, ck)
assert magic == COOKIE_MAGIC
file_size = os.path.getsize(EXE)
overlay_start = file_size - pkg_length
with open(EXE, "rb") as f:
    f.seek(overlay_start)
    overlay = f.read()
assert len(overlay) == pkg_length
print("overlay extracted:", len(overlay), "bytes from offset", overlay_start)

# ───────────── 3) 在临时副本上替换图标 ─────────────
shutil.copy2(EXE, TMP)
hupd = BeginUpdateResource(TMP, False)
try:
    for idx, e in enumerate(ico_entries, start=1):
        UpdateResource(hupd, RT_ICON, idx, e['data'])
    group_header = struct.pack('<HHH', 0, 1, len(ico_entries))
    group_entries = b''
    for idx, e in enumerate(ico_entries, start=1):
        group_entries += struct.pack('<BBBBHHIH',
            e['width'] if e['width'] < 256 else 0,
            e['height'] if e['height'] < 256 else 0,
            0, 0,
            e['planes'], e['bitcount'], e['size'],
            idx)
    UpdateResource(hupd, RT_GROUP_ICON, 1, group_header + group_entries)
finally:
    EndUpdateResource(hupd, False)
print("icon updated in temp exe")

# ───────────── 4) 把覆盖层拼回去 ─────────────
with open(TMP, "ab") as f:
    f.write(overlay)
print("overlay re-appended, temp size:", os.path.getsize(TMP))

# ───────────── 5) 校验 CArchive ─────────────
sys.path.insert(0, r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm")
from PyInstaller.archive.readers import CArchiveReader
cr = CArchiveReader(TMP)
u = cr.extract("ui.html")
print("CArchive verify: ui.html", len(u), "has warn:", b'id="warn"' in u,
      "PYZ present:", 'PYZ.pyz' in cr.toc)

# ───────────── 6) 转正 ─────────────
os.replace(TMP, EXE)
print("delivered:", EXE, os.path.getsize(EXE), "bytes")
