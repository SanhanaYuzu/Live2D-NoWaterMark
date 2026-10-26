# -*- coding: utf-8 -*-
"""探测 internalModel 结构（headless Edge）。用法: python _probe.py <模型目录>"""
import io, json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")
NODE = r"C:\Users\xihaochen\.workbuddy\binaries\node\versions\22.22.2-6\node.exe"
PORT = 9228

def edge_exe():
    for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]:
        if os.path.exists(p): return p
    raise SystemExit("no edge")

def main():
    root = sys.argv[1]
    import live2d_preview, live2d_wm_web as W
    prv = live2d_preview.PreviewServer(HERE, W.APP_VER, W.APP_NAME,
                                       wm_hit=W.hit_name, moc_parser=W.Moc3)
    prv.set_root(root); prv.start()
    try:
        prof = os.path.join(HERE, "_edge_profile_wmpr_%d" % (int(time.time()) % 1000))
        proc = subprocess.Popen([edge_exe(), "--user-data-dir=" + prof, "--no-first-run",
                                 "--no-default-browser-check", "--headless=new",
                                 "--remote-debugging-port=%d" % PORT, prv.url],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            t0 = time.time()
            while time.time() - t0 < 45:
                try:
                    with urllib.request.urlopen("http://127.0.0.1:%d/json/version" % PORT, timeout=2) as r:
                        json.loads(r.read().decode()); break
                except Exception: time.sleep(0.5)
            out = os.path.join(HERE, "_probe.json")
            if os.path.exists(out):
                os.rename(out, os.path.join(HERE, "_trash", "probe_prev_%d.json" % int(time.time())))
            r = subprocess.run([NODE, os.path.join(HERE, "_wm_uv_node.js"), str(PORT),
                                "_probe_drive.js", "_probe.json"],
                               cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=180)
            O = json.load(io.open(out, encoding="utf-8"))
            print(json.dumps(O, ensure_ascii=False, indent=1)[:3000])
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
