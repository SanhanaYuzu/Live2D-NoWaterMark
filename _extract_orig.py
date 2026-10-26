import os, struct, sys
sys.path.insert(0, r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm")
from PyInstaller.archive.readers import CArchiveReader

SRC = r"C:\Users\xihaochen\Downloads\Live2D去水印_v24.exe"
OUT = r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm\orig_ui.html"

cr = CArchiveReader(SRC)
print("start_offset =", cr._start_offset, " end_offset =", cr._end_offset, " filesize =", os.path.getsize(SRC))
print("cr.toc keys  =", list(cr.toc.keys()))
print("cr.options   =", cr.options)

with open(SRC, "rb") as fp:
    fp.seek(cr._end_offset - cr._COOKIE_LENGTH)
    ck = fp.read(cr._COOKIE_LENGTH)
magic, archive_length, toc_offset, toc_length, pyvers, pylib = struct.unpack(cr._COOKIE_FORMAT, ck)
print("cookie toc_offset=", toc_offset, " toc_length=", toc_length, " pylib=", pylib.rstrip(b"\0").decode("ascii","replace"))

with open(SRC, "rb") as fp:
    fp.seek(cr._start_offset + toc_offset)
    toc_data = fp.read(toc_length)

cur = 0
print("\n=== ORDERED TOC ===")
order = []
while cur < len(toc_data):
    entry_length, entry_offset, data_length, uncompressed_length, compression_flag, typecode = \
        struct.unpack(cr._TOC_ENTRY_FORMAT, toc_data[cur:cur+cr._TOC_ENTRY_LENGTH])
    cur += cr._TOC_ENTRY_LENGTH
    name_length = entry_length - cr._TOC_ENTRY_LENGTH
    name = toc_data[cur:cur+name_length].rstrip(b"\0").decode("utf-8","replace")
    cur += name_length
    tc = typecode.decode("ascii")
    order.append((name, tc, compression_flag))
    print(f"  {name:42s} tc={tc} comp={compression_flag} dlen={data_length}")

data = cr.extract("ui.html")
print("\nui.html size:", len(data), " (decompressed)")
open(OUT, "wb").write(data)
print("written ->", OUT)
