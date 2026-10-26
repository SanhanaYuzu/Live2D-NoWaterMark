# -*- coding: utf-8 -*-
"""后台整帧渲染：起服务 + Edge + 注入整帧探针 → 存 PNG。
用法: python _wm_frame.py <模型目录> <输出png>
不抢前台（hidden 页面同步渲染）。"""
import base64, io, json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)
NODE = r"C:\Users\xihaochen\.workbuddy\binaries\node\versions\22.22.2-6\node.exe"
PORT = 9225
import live2d_preview, live2d_wm_web as W

def edge_exe():
    for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]:
        if os.path.exists(p): return p
    raise SystemExit("找不到 msedge.exe")

root = sys.argv[1]
out_png = sys.argv[2]

prv = live2d_preview.PreviewServer(HERE, W.APP_VER, W.APP_NAME, wm_hit=W.hit_name, moc_parser=W.Moc3)
prv.set_root(root)
prv.start()
edge = edge_exe()
prof = os.path.join(HERE, "_edge_profile_wmf_%d" % (int(time.time()) % 10000))
proc = subprocess.Popen([edge, "--user-data-dir=" + prof, "--no-first-run",
                         "--no-default-browser-check", "--remote-debugging-port=%d" % PORT, prv.url],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    t0 = time.time()
    while time.time() - t0 < 45:
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/json/version" % PORT, timeout=2) as r:
                json.loads(r.read().decode()); break
        except Exception:
            time.sleep(0.5)
    if os.path.exists("_wm_uv_result.json"):
        os.rename("_wm_uv_result.json", os.path.join(HERE, "_trash", "wm_frame_prev_%d.json" % int(time.time())))
    r = subprocess.run([NODE, "_wm_uv_node.js", str(PORT), "_wm_frame_drive.js", "_wm_uv_result.json"],
                       cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=420)
    O = None
    for ln in (r.stdout or "").splitlines():
        if ln.startswith("RESULT_JSON"):
            O = json.loads(ln[len("RESULT_JSON "):])
    if not O:
        print("无结果:", (r.stdout or "")[-400:], (r.stderr or "")[-200:]); sys.exit(1)
    if O.get("errs"):
        print("errs:", O["errs"]); sys.exit(1)
    print("covered(不透明占比) =", O.get("covered"), "| size =", O.get("size"),
          "| modelInfo =", O.get("modelInfo"))
    dataurl = O.get("frame") or ""
    if not dataurl.startswith("data:image/png;base64,"):
        print("frame 缺失"); sys.exit(1)
    png = base64.b64decode(dataurl.split(",", 1)[1])
    with io.open(out_png, "wb") as f:
        f.write(png)
    print("帧图 → %s (%d KB)" % (out_png, len(png) // 1024))
finally:
    try:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=20)
    except Exception:
        pass
    time.sleep(1.0)
    prv.stop()
