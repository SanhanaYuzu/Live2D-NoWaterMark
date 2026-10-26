import os, sys
sys.path.insert(0, r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm")
from PyInstaller.archive.readers import CArchiveReader

ORIG = r"C:\Users\xihaochen\Downloads\Live2D去水印_v24.exe"
NEW  = r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm\dist\Live2D去水印_v24.exe"

a = CArchiveReader(ORIG)
b = CArchiveReader(NEW)

# entry metadata dicts
def meta(cr):
    return {k: (v[3], v[4]) for k, v in cr.toc.items()}  # (comp_flag, typecode)

ma, mb = meta(a), meta(b)
na, nb = set(ma), set(mb)
print("entries orig:", len(na), "new:", len(nb))
print("only in orig:", na - nb)
print("only in new :", nb - na)

diff = []
same = 0
for name in sorted(na & nb):
    da = a.extract(name); db = b.extract(name)
    if da == db:
        same += 1
    else:
        diff.append((name, len(da), len(db)))
print("identical entries:", same)
print("DIFFERING entries:")
for name, la, lb in diff:
    print(f"  {name:42s} orig={la} new={lb}")

# PE / file sanity
oa = open(ORIG,'rb').read(2); ob = open(NEW,'rb').read(2)
print("MZ header orig/new:", oa, ob)
print("orig size", os.path.getsize(ORIG), "new size", os.path.getsize(NEW))
