# -*- coding: utf-8 -*-
"""运行时复验（数据级）：core 是否真加载了清零后的索引。"""
import io, json, os, subprocess, sys, time, urllib.request

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

root = os.path.join(HERE, "_work", "花嫁小狐免费版", "花嫁小狐免费版")
prv = live2d_preview.PreviewServer(HERE, W.APP_VER, W.APP_NAME, wm_hit=W.hit_name, moc_parser=W.Moc3)
prv.set_root(root)
prv.start()
edge = edge_exe()
prof = os.path.join(HERE, "_edge_profile_wmv_%d" % (int(time.time()) % 10000))
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
        os.rename("_wm_uv_result.json", os.path.join(HERE, "_trash", "wm_verify_prev_%d.json" % int(time.time())))
    r = subprocess.run([NODE, "_wm_uv_node.js", str(PORT), "_wm_verify_drive.js", "_wm_uv_result.json"],
                       cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=420)
    for ln in (r.stdout or "").splitlines():
        if ln.startswith("RESULT_JSON"):
            O = json.loads(ln[len("RESULT_JSON "):])
            print("errs:", O.get("errs"))
            print("allTargetsZero:", O.get("allTargetsZero"), "| controlsHaveIdx:", O.get("controlsHaveIdx"))
            for t in O.get("targets") or []:
                print("  目标 d=%-4s %-12s len=%-5s nonzero=%-5s allZero=%s uvLen=%-5s vert=%s"
                      % (t["d"], t["id"], t["len"], t["nonzero"], t["allZero"], t["uvLen"], t["vertCount"]))
            for c in O.get("controls") or []:
                print("  对照 d=%-4s %-12s nonzero=%s/%s" % (c["d"], c["id"], c["nonzero"], c["len"]))
        elif "fatal" in ln or "target =" in ln or "就绪" in ln:
            print(ln[:160])
finally:
    try:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=20)
    except Exception:
        pass
    time.sleep(1.0)
    prv.stop()
