# -*- coding: utf-8 -*-
"""逐部件差分定位水印部件。
用法: python _wm_part_scan.py <模型目录>
起预览服务 + Edge（独立 profile），注入 _wm_part_scan_drive.js，解码 diff PNG，打印表格。"""
import base64, io, json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")
NODE = r"C:\Users\xihaochen\.workbuddy\binaries\node\versions\22.22.2-6\node.exe"
PORT = 9225
OUT_JSON = os.path.join(HERE, "_wm_part_result.json")
DRIVER = "_wm_part_scan_drive.js"

def edge_exe():
    for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]:
        if os.path.exists(p): return p
    raise SystemExit("找不到 msedge.exe")

def main():
    root = sys.argv[1]
    import live2d_preview, live2d_wm_web as W
    prv = live2d_preview.PreviewServer(HERE, W.APP_VER, W.APP_NAME,
                                       wm_hit=W.hit_name, moc_parser=W.Moc3)
    prv.set_root(root)
    prv.start()
    try:
        url = prv.url
        print("预览:", url.split("?")[0], "(token 已隐藏)")
        prof = os.path.join(HERE, "_edge_profile_wmps_%d" % (int(time.time()) % 1000))
        args = [edge_exe(), "--user-data-dir=" + prof, "--no-first-run",
                "--no-default-browser-check", "--start-maximized",
                "--remote-debugging-port=%d" % PORT,
                "--disable-features=Translate", url]
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            t0 = time.time()
            while time.time() - t0 < 45:
                try:
                    with urllib.request.urlopen("http://127.0.0.1:%d/json/version" % PORT, timeout=2) as r:
                        json.loads(r.read().decode()); break
                except Exception:
                    time.sleep(0.5)
            if os.path.exists(OUT_JSON):
                os.rename(OUT_JSON, os.path.join(HERE, "_trash", "wm_part_prev_%d.json" % int(time.time())))
            r = subprocess.run([NODE, os.path.join(HERE, "_wm_uv_node.js"), str(PORT),
                                DRIVER, OUT_JSON],
                               cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=900)
            print("--- runner 尾部 ---")
            for ln in (r.stdout or "").splitlines()[-6:]:
                print(" ", ln[:220])
            if not os.path.exists(OUT_JSON):
                print("!! 无结果 JSON"); return
            O = json.loads(io.open(OUT_JSON, encoding="utf-8").read())
            # 解码 PNG（先顶层，再逐 part；两者顺序无关）
            for k, v in list(O.items()):
                if isinstance(v, str) and v.startswith("data:image/png"):
                    fn = os.path.join(HERE, "_scan_out", "pdiff_%s.png" % k.replace("_png", ""))
                    io.open(fn, "wb").write(base64.b64decode(v.split(",", 1)[1]))
                    O[k] = "→ " + os.path.basename(fn)
            if isinstance(O.get("parts"), list):
                for rec in O["parts"]:
                    dp = rec.pop("diff_png", None)
                    if isinstance(dp, str) and dp.startswith("data:image/png"):
                        fn = os.path.join(HERE, "_scan_out", "pdiff_part%03d_%s.png"
                                          % (rec["i"], rec.get("name") or "?"))
                        io.open(fn, "wb").write(base64.b64decode(dp.split(",", 1)[1]))
                        rec["diff_png"] = "→ " + os.path.basename(fn)
            io.open(OUT_JSON, "w", encoding="utf-8").write(json.dumps(O, ensure_ascii=False, indent=1))
            print("== 结果 ==")
            print("errs:", O.get("errs"), " size:", O.get("size"), " box:", O.get("box"))
            print("%-4s %-28s %8s %9s  %s" % ("part", "name", "boxDiff", "fullDiff", "dropped(前12)"))
            for rec in O.get("parts", [])[:20]:
                print("%-4s %-28s %8d %9d  %s%s" % (
                    rec["i"], rec.get("name") or "?", rec["box"], rec["full"],
                    rec["dropped"][:12], "..." if len(rec["dropped"]) > 12 else ""))
            return O
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
