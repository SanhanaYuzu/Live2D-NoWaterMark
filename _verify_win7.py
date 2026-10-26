# -*- coding: utf-8 -*-
import sys, os
ROOT = r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm"
EXE  = os.path.join(ROOT, "dist_win7", "Live2D去水印_v24_win7.exe")
sys.path.insert(0, ROOT)
from PyInstaller.archive.readers import CArchiveReader

raw = open(EXE, "rb").read()
print("=== 运行时 DLL ===")
print("python38.dll 存在:", b"python38.dll" in raw)
print("python314.dll 存在:", b"python314.dll" in raw)

cr = CArchiveReader(EXE)
toc = set(cr.toc.keys())
print("\n=== CArchive 关键条目 ===")
for k in ["PYZ.pyz", "nwm_auth", "live2d_preview", "webview",
          "webview.platforms.mshtml", "webview.platforms.edgechromium",
          "clr_loader", "pythonnet"]:
    print(f"  {k:32s}: {'OK' if k in toc else '缺失'}")

ui = cr.extract("ui.html")
print("\n=== ui.html 法律警告页标记 ===")
checks = {
    'id="warn"': b'id="warn"' in ui,
    'splashXhc': b'splashXhc' in ui,
    'showWarn()': b'showWarn' in ui,
    'agreeWarn()': b'agreeWarn' in ui,
    'quitWarn()': b'quitWarn' in ui,
    'tryHideSplash hook (开屏后弹警告)': b'if(s) s.remove(); showWarn();' in ui,
    '法律声明文本': b'\xe6\xb3\x95\xe5\xbe\x8b\xe5\xa3\xb0\xe6\x98\x8e' in ui,
}
for name, ok in checks.items():
    print(f"  {name:36s}: {'OK' if ok else '缺失!!'}")

pylib = cr.toc.get('PYZ.pyz')
print("\nPYZ.pyz 大小:", len(cr.extract('PYZ.pyz')), "bytes")
print("ui.html 大小:", len(ui), "bytes")
print("\nALL_OK" if all(checks.values()) and b"python38.dll" in raw and b"python314.dll" not in raw else "HAS_ISSUE")
