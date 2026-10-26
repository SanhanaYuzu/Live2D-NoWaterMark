# -*- coding: utf-8 -*-
"""运行时索引复验。用法: python _wm_idx_probe.py <模型目录> <d,d,...>"""
import base64, io, json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")
NODE = r"C:\Users\xihaochen\.workbuddy\binaries\node\versions\22.22.2-6\node.exe"
PORT = 9230
OUT_JSON = os.path.join(HERE, "_wm_idx_result.json")

def edge_exe():
    for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]:
        if os.path.exists(p): return p
    raise SystemExit("找不到 msedge.exe")

def main():
    root = sys.argv[1]
    dlist = [int(v) for v in sys.argv[2].split(",") if v.strip()]
    drv = io.open(os.path.join(HERE, "_wm_idx_probe_drive.js"), encoding="utf-8").read()
    drv = drv.replace("__DLIST__", json.dumps(dlist))
    tmp = os.path.join(HERE, "_wm_idx_probe_filled.js")
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(drv)

    import live2d_preview, live2d_wm_web as W
    prv = live2d_preview.PreviewServer(HERE, W.APP_VER, W.APP_NAME,
                                       wm_hit=W.hit_name, moc_parser=W.Moc3)
    prv.set_root(root)
    prv.start()
    try:
        print("预览:", prv.url.split("?")[0])
        prof = os.path.join(HERE, "_edge_profile_wmix_%d" % (int(time.time()) % 1000))
        proc = subprocess.Popen([edge_exe(), "--user-data-dir=" + prof, "--no-first-run",
                                 "--no-default-browser-check",
                                 "--remote-debugging-port=%d" % PORT, prv.url],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            t0 = time.time()
            while time.time() - t0 < 45:
                try:
                    with urllib.request.urlopen("http://127.0.0.1:%d/json/version" % PORT, timeout=2) as r:
                        json.loads(r.read().decode()); break
                except Exception:
                    time.sleep(0.5)
            if os.path.exists(OUT_JSON):
                os.rename(OUT_JSON, os.path.join(HERE, "_trash", "wm_idx_prev_%d.json" % int(time.time())))
            r = subprocess.run([NODE, os.path.join(HERE, "_wm_uv_node.js"), str(PORT),
                                "_wm_idx_probe_filled.js", OUT_JSON],
                               cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=600)
            if not os.path.exists(OUT_JSON):
                print("!! 无结果"); print((r.stdout or "")[-500:]); return
            O = json.loads(io.open(OUT_JSON, encoding="utf-8").read())
            print("errs:", O.get("errs"))
            bad = 0
            for k, v in (O.get("idx") or {}).items():
                st = "CLEARED" if v.get("nonzero") == 0 else "!!!NOT-CLEARED"
                if v.get("nonzero"): bad += 1
                print("  %-28s len=%-6s nonzero=%-6s %s" % (k, v.get("len"), v.get("nonzero"), st))
            print("===", "ALL_ZERO_IN_RUNTIME" if bad == 0 else ("BAD=%d" % bad))
        finally:
            try: proc.terminate()
            except Exception: pass
            time.sleep(1.5)
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
                            "Where-Object { $_.CommandLine -like '*%s*' } | ForEach-Object { "
                            "Stop-Process -Id $_.ProcessId -Force }" % os.path.basename(prof)],
                           capture_output=True, timeout=30)
    finally:
        prv.stop()

if __name__ == "__main__":
    main()
