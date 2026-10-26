# -*- coding: utf-8 -*-
"""solo 渲染指定 drawable（全幅帧）。用法: python _wm_solo6.py <模型目录> <d,d,...>"""
import base64, io, json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")
NODE = r"C:\Users\xihaochen\.workbuddy\binaries\node\versions\22.22.2-6\node.exe"
PORT = 9229
OUT_JSON = os.path.join(HERE, "_wm_solo6_result.json")

def edge_exe():
    for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]:
        if os.path.exists(p): return p
    raise SystemExit("找不到 msedge.exe")

def main():
    root = sys.argv[1]
    dlist = [int(v) for v in sys.argv[2].split(",") if v.strip()]
    wm_part = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    drv = io.open(os.path.join(HERE, "_wm_solo6_drive.js"), encoding="utf-8").read()
    drv = drv.replace("__DLIST__", json.dumps(dlist)).replace("__WMPART__", str(wm_part))
    tmp = os.path.join(HERE, "_wm_solo6_drive_filled.js")
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(drv)

    import live2d_preview, live2d_wm_web as W
    prv = live2d_preview.PreviewServer(HERE, W.APP_VER, W.APP_NAME,
                                       wm_hit=W.hit_name, moc_parser=W.Moc3)
    prv.set_root(root)
    prv.start()
    try:
        url = prv.url
        print("预览:", url.split("?")[0], "(token 已隐藏)")
        prof = os.path.join(HERE, "_edge_profile_wms6_%d" % (int(time.time()) % 1000))
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
                os.rename(OUT_JSON, os.path.join(HERE, "_trash", "wm_solo6_prev_%d.json" % int(time.time())))
            r = subprocess.run([NODE, os.path.join(HERE, "_wm_uv_node.js"), str(PORT),
                                "_wm_solo6_drive_filled.js", OUT_JSON],
                               cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=900)
            print("--- runner 尾部 ---")
            for ln in (r.stdout or "").splitlines()[-4:]:
                print(" ", ln[:200])
            if not os.path.exists(OUT_JSON):
                print("!! 无结果 JSON"); return
            O = json.loads(io.open(OUT_JSON, encoding="utf-8").read())
            print("errs:", O.get("errs"), " size:", O.get("size"))
            from PIL import Image
            solos = O.get("solos") or {}
            paths = []
            for k in sorted(solos.keys()):
                v = solos[k]
                if isinstance(v, str) and v.startswith("data:image/png"):
                    fn = os.path.join(HERE, "_scan_out", "solo6_%s.png" % k.replace("_png", ""))
                    io.open(fn, "wb").write(base64.b64decode(v.split(",", 1)[1]))
                    paths.append(fn)
                    print("  saved", os.path.basename(fn))
            # 拼图（缩到 40%）
            if paths:
                ims = []
                for p in paths:
                    im = Image.open(p).convert("RGB")
                    im = im.resize((im.width * 2 // 5, im.height * 2 // 5))
                    ims.append((os.path.basename(p), im))
                cols = 2
                cw = max(im.width for _, im in ims) + 4
                rh = max(im.height for _, im in ims) + 4
                rows = (len(ims) + cols - 1) // cols
                sheet = Image.new("RGB", (cols * cw, rows * rh), (10, 10, 10))
                for i, (name, im) in enumerate(ims):
                    sheet.paste(im, ((i % cols) * cw + 2, (i // cols) * rh + 2))
                out = os.path.join(HERE, "_scan_out", "solo6_sheet.png")
                sheet.save(out)
                print("拼图:", out, sheet.size)
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
