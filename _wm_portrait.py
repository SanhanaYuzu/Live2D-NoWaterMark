# -*- coding: utf-8 -*-
"""高清全身立绘导出。用法: python _wm_portrait.py <模型目录> <输出png> [目标高度=2100]"""
import base64, io, json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")
NODE = r"C:\Users\xihaochen\.workbuddy\binaries\node\versions\22.22.2-6\node.exe"
PORT = 9229
OUT_JSON = os.path.join(HERE, "_wm_portrait_result.json")

def edge_exe():
    for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]:
        if os.path.exists(p): return p
    raise SystemExit("找不到 msedge.exe")

def main():
    root = sys.argv[1]
    out_png = sys.argv[2]
    target_h = sys.argv[3] if len(sys.argv) > 3 else "2100"
    drv = io.open(os.path.join(HERE, "_wm_portrait_drive.js"), encoding="utf-8").read()
    drv = drv.replace("__H__", target_h)
    tmp = os.path.join(HERE, "_wm_portrait_drive_filled.js")
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(drv)

    import live2d_preview, live2d_wm_web as W
    prv = live2d_preview.PreviewServer(HERE, W.APP_VER, W.APP_NAME,
                                       wm_hit=W.hit_name, moc_parser=W.Moc3)
    prv.set_root(root)
    prv.start()
    try:
        url = prv.url
        print("预览:", url.split("?")[0], "(token 已隐藏)")
        prof = os.path.join(HERE, "_edge_profile_wmpor_%d" % (int(time.time()) % 1000))
        args = [edge_exe(), "--user-data-dir=" + prof, "--no-first-run",
                "--no-default-browser-check", "--remote-debugging-port=%d" % PORT,
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
            r = subprocess.run([NODE, os.path.join(HERE, "_wm_uv_node.js"), str(PORT),
                                "_wm_portrait_drive_filled.js", OUT_JSON],
                               cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=900)
            print("--- runner 尾部 ---")
            for ln in (r.stdout or "").splitlines()[-3:]:
                print(" ", ln[:200])
            if not os.path.exists(OUT_JSON):
                print("!! 无结果 JSON"); return
            O = json.loads(io.open(OUT_JSON, encoding="utf-8").read())
            print("errs:", O.get("errs"), " size:", O.get("size"),
                  " glSize:", O.get("glSize"), " modelBox:", O.get("modelBox"))
            png = O.get("png")
            if isinstance(png, str) and png.startswith("data:image/png"):
                io.open(out_png, "wb").write(base64.b64decode(png.split(",", 1)[1]))
                from PIL import Image
                im = Image.open(out_png)
                print("立绘 →", out_png, im.size, os.path.getsize(out_png) // 1024, "KB")
            else:
                print("!! 无 PNG 数据")
            return O
        finally:
            try: proc.terminate()
            except Exception: pass
            time.sleep(1.5)
            try:
                subprocess.run(["powershell", "-NoProfile", "-Command",
                                "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
                                "Where-Object { $_.CommandLine -like '*%s*' } | ForEach-Object { "
                                "Stop-Process -Id $_.ProcessId -Force }" % os.path.basename(prof)],
                               capture_output=True, timeout=30)
            except Exception:
                pass
    finally:
        prv.stop()

if __name__ == "__main__":
    main()
