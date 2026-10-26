# -*- coding: utf-8 -*-
"""逐部件 solo 渲染。用法: python _wm_psolo.py <模型目录>"""
import base64, io, json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")
NODE = r"C:\Users\xihaochen\.workbuddy\binaries\node\versions\22.22.2-6\node.exe"
PORT = 9235
OUT_JSON = os.path.join(HERE, "_wm_psolo_result.json")

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
        print("预览:", prv.url.split("?")[0])
        prof = os.path.join(HERE, "_edge_profile_wmps_%d" % (int(time.time()) % 1000))
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
                os.rename(OUT_JSON, os.path.join(HERE, "_trash", "wm_psolo_prev_%d.json" % int(time.time())))
            r = subprocess.run([NODE, os.path.join(HERE, "_wm_uv_node.js"), str(PORT),
                                "_wm_psolo_drive.js", OUT_JSON],
                               cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=900)
            if not os.path.exists(OUT_JSON):
                print("!! 无结果"); return
            O = json.loads(io.open(OUT_JSON, encoding="utf-8").read())
            print("errs:", O.get("errs"), " size:", O.get("size"), " box:", O.get("box"))
            solos = O.get("solos") or {}
            from PIL import Image, ImageDraw
            tiles = []
            for k in sorted(solos.keys()):
                v = solos[k]
                if isinstance(v, str) and v.startswith("data:image/png"):
                    raw = base64.b64decode(v.split(",", 1)[1])
                    im = Image.open(io.BytesIO(raw)).convert("RGB")
                    # 非黑统计
                    g = im.convert("L")
                    p2 = g.load()
                    W2, H2 = g.size
                    nz = sum(1 for y in range(0, H2, 2) for x in range(0, W2, 2) if p2[x, y] > 14)
                    im2 = im.point(lambda x: min(255, x * 10))
                    tile = Image.new("RGB", (im2.width + 6, im2.height + 22), (25, 25, 25))
                    tile.paste(im2, (3, 18))
                    d2 = ImageDraw.Draw(tile)
                    d2.text((3, 3), "%s nz=%d" % (k.replace("_png", ""), nz),
                            fill=(255, 255, 0) if nz else (120, 120, 120))
                    tiles.append((k, tile, nz))
            cols = 3
            cw = max(t[1].width for t in tiles) + 4
            rh = max(t[1].height for t in tiles) + 4
            rows = (len(tiles) + cols - 1) // cols
            sheet = Image.new("RGB", (cols * cw, rows * rh), (10, 10, 10))
            for i, (k, tile, nz) in enumerate(tiles):
                sheet.paste(tile, ((i % cols) * cw + 2, (i // cols) * rh + 2))
            out = os.path.join(HERE, "_scan_out", "psolo_sheet.png")
            sheet.save(out)
            print("拼图:", out, sheet.size, "tiles:", len(tiles))
            for k, tile, nz in tiles:
                if nz > 30:
                    print("  有内容:", k, "nz =", nz)
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
