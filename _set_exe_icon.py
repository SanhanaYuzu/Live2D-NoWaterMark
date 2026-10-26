# -*- coding: utf-8 -*-
"""
把用户提供的 ATECH A 字 logo 设成 dist/Live2D去水印_v24.exe 的图标。
流程：生成 7 尺寸 ICO（先放大到 256）→ 直接覆盖 RT_ICON 1..7 与 RT_GROUP_ICON 1 →
修复 PyInstaller CArchive cookie 的 pkg_length。
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
BACKUP  = r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm\_trash\Live2D去水印_v24_换图标前.exe"

LANCZOS = getattr(Image, 'Resampling', Image).LANCZOS

# ───────────── 1) 生成 ICO：白底转透明，7 个标准尺寸 ─────────────
im = Image.open(SRC_PNG).convert("RGBA")
# 白底 → alpha：白色变透明，黑色保留，灰阶边缘半透明
px = list(im.getdata())
out = []
for r, g, b, a in px:
    lum = (r + g + b) // 3
    new_a = max(0, min(255, 255 - lum))
    out.append((r, g, b, new_a))
im.putdata(out)

# 裁成正方形并放大到 256（ICO 最大标准尺寸，Pillow 只对 <= 源尺寸的大小生成条目）
w, h = im.size
s = min(w, h)
im = im.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
im256 = im.resize((256, 256), LANCZOS)

sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
im256.save(ICO, format='ICO', sizes=sizes)
print("ICO created:", ICO, os.path.getsize(ICO), "bytes")

# 解析 ICO
with open(ICO, "rb") as f:
    ico = f.read()
reserved, itype, count = struct.unpack('<HHH', ico[:6])
assert reserved == 0 and itype == 1
ico_entries = []
off = 6
for i in range(count):
    w, h, colors, reserved, planes, bitcount, size, img_off = struct.unpack('<BBBBHHII', ico[off:off + 16])
    ico_entries.append({
        'width': w or 256, 'height': h or 256,
        'planes': planes, 'bitcount': bitcount,
        'size': size,
        'data': ico[img_off:img_off + size]
    })
    off += 16
print("ICO entries:", [(e['width'], e['height'], e['size']) for e in ico_entries])
assert len(ico_entries) == 7, f"期望 7 个图标条目，实际 {len(ico_entries)}"

# ───────────── 2) 备份当前 exe ─────────────
shutil.copy2(EXE, BACKUP)
print("backup ->", BACKUP)

# ───────────── 3) 读原 CArchive cookie，记录覆盖层长度 ─────────────
old_size = os.path.getsize(EXE)
with open(EXE, "rb") as f:
    f.seek(-COOKIE_LEN, 2)
    ck = f.read(COOKIE_LEN)
magic, old_pkg_length, toc_offset, toc_length, pyvers, pylib = struct.unpack(COOKIE_FORMAT, ck)
assert magic == COOKIE_MAGIC, "cookie magic 不匹配"
overlay_start = old_size - old_pkg_length
print("old file size:", old_size, "old pkg_length:", old_pkg_length, "overlay_start:", overlay_start)

# ───────────── 4) 直接覆盖图标资源（不删除，避免 WinError 87） ─────────────
hupd = BeginUpdateResource(EXE, False)
try:
    # 覆盖 RT_ICON 1..7
    for idx, e in enumerate(ico_entries, start=1):
        UpdateResource(hupd, RT_ICON, idx, e['data'])
    # 覆盖 RT_GROUP_ICON 1
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
print("icon resources overwritten")

# ───────────── 5) 修正 CArchive cookie 的 pkg_length ─────────────
new_size = os.path.getsize(EXE)
with open(EXE, "r+b") as f:
    f.seek(-COOKIE_LEN, 2)
    cookie_pos = f.tell()
    ck = f.read(COOKIE_LEN)
    magic, _, toc_offset, toc_length, pyvers, pylib = struct.unpack(COOKIE_FORMAT, ck)
    assert magic == COOKIE_MAGIC
    new_overlay_start = cookie_pos + COOKIE_LEN - old_pkg_length
    new_pkg_length = new_size - new_overlay_start
    new_ck = struct.pack(COOKIE_FORMAT, COOKIE_MAGIC, new_pkg_length, toc_offset, toc_length, pyvers, pylib)
    f.seek(cookie_pos)
    f.write(new_ck)
print("patched pkg_length:", old_pkg_length, "->", new_pkg_length, "new size:", new_size)

# ───────────── 6) 校验 ─────────────
sys.path.insert(0, r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm")
from PyInstaller.archive.readers import CArchiveReader
cr = CArchiveReader(EXE)
u = cr.extract("ui.html")
print("CArchive verify: ui.html", len(u), "has warn:", b'id="warn"' in u,
      "PYZ present:", 'PYZ.pyz' in cr.toc)
