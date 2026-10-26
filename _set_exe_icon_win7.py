# -*- coding: utf-8 -*-
"""
给 Win7 版 exe 套 ATECH 图标（安全版：保留 PyInstaller CArchive 覆盖层）。
直接读取已生成的 atech_icon.ico，不再依赖剪贴板 PNG。
"""
import os, struct, shutil, sys

RT_ICON = 3
RT_GROUP_ICON = 14
COOKIE_MAGIC = b'MEI\x0c\x0b\x0a\x0b\x0e'
COOKIE_FORMAT = '!8sIIII64s'
COOKIE_LEN = struct.calcsize(COOKIE_FORMAT)

ROOT    = r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm"
ICO     = os.path.join(ROOT, "atech_icon.ico")
EXE     = os.path.join(ROOT, "dist_win7", "Live2D去水印_v24_win7.exe")
TMP     = os.path.join(ROOT, "_icon_tmp_win7.exe")
BACKUP  = os.path.join(ROOT, "_trash", "Live2D去水印_v24_win7_换图标前_安全版.exe")

from win32ctypes.pywin32.win32api import (
    BeginUpdateResource, UpdateResource, EndUpdateResource
)

assert os.path.exists(EXE), "Win7 exe 不存在，先完成打包"
assert os.path.exists(ICO), "atech_icon.ico 不存在"

with open(ICO, "rb") as f:
    ico = f.read()
reserved, itype, count = struct.unpack('<HHH', ico[:6])
assert itype == 1, "不是 .ico 文件"
ico_entries = []
off = 6
for i in range(count):
    w, h, colors, reserved_c, planes, bitcount, size, img_off = struct.unpack('<BBBBHHII', ico[off:off + 16])
    ico_entries.append({
        'width': w or 256, 'height': h or 256,
        'planes': planes, 'bitcount': bitcount,
        'size': size, 'data': ico[img_off:img_off + size]
    })
    off += 16
print("ICO entries:", [(e['width'], e['height'], e['size']) for e in ico_entries])

os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
shutil.copy2(EXE, BACKUP)
print("backup ->", BACKUP)

with open(EXE, "rb") as f:
    f.seek(-COOKIE_LEN, 2)
    ck = f.read(COOKIE_LEN)
magic, pkg_length, toc_offset, toc_length, pyvers, pylib = struct.unpack(COOKIE_FORMAT, ck)
assert magic == COOKIE_MAGIC, "CArchive cookie 不匹配，可能不是 PyInstaller exe"
file_size = os.path.getsize(EXE)
overlay_start = file_size - pkg_length
with open(EXE, "rb") as f:
    f.seek(overlay_start)
    overlay = f.read()
assert len(overlay) == pkg_length
print("overlay extracted:", len(overlay), "bytes from offset", overlay_start)

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

with open(TMP, "ab") as f:
    f.write(overlay)
print("overlay re-appended, temp size:", os.path.getsize(TMP))

sys.path.insert(0, ROOT)
from PyInstaller.archive.readers import CArchiveReader
cr = CArchiveReader(TMP)
u = cr.extract("ui.html")
print("CArchive verify: ui.html", len(u), "has warn:", b'id="warn"' in u,
      "PYZ present:", 'PYZ.pyz' in cr.toc, "pylib:", pylib.rstrip(b'\0').decode('ascii', 'ignore'))

os.replace(TMP, EXE)
print("delivered:", EXE, os.path.getsize(EXE), "bytes")
