# -*- coding: utf-8 -*-
"""分块定位文字三角形。用法: python _wm_chunk.py <模型目录> <wmpart> <d,d,...>"""
import base64, io, json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")
NODE = r"C:\Users\xihaochen\.workbuddy\binaries\node\versions\22.22.2-6\node.exe"
PORT = 9232
OUT_JSON = os.path.join(HERE, "_wm_chunk_result.json")

def edge_exe():
    for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]:
        if os.path.exists(p): return p
    raise SystemExit("找不到 msedge.exe")

def main():
    root = sys.argv[1]
    wm_part = int(sys.argv[2])
    dlist = [int(v) for v in sys.argv[3].split(",") if v.strip()]
    drv = io.open(os.path.join(HERE, "_wm_chunk_drive.js"), encoding="utf-8").read()
    drv = drv.replace("__WMPART__", str(wm_part)).replace("__DLIST__", json.dumps(dlist))
    tmp = os.path.join(HERE, "_wm_chunk_filled.js")
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(drv)

    import live2d_preview, live2d_wm_web as W
    prv = live2d_preview.PreviewServer(HERE, W.APP_VER, W.APP_NAME,
                                       wm_hit=W.hit_name, moc_parser=W.Moc3)
    prv.set_root(root)
    prv.start()
    try:
        print("预览:", prv.url.split("?")[0])
        prof = os.path.join(HERE, "_edge_profile_wmck_%d" % (int(time.time()) % 1000))
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
                os.rename(OUT_JSON, os.path.join(HERE, "_trash", "wm_chunk_prev_%d.json" % int(time.time())))
            r = subprocess.run([NODE, os.path.join(HERE, "_wm_uv_node.js"), str(PORT),
                                "_wm_chunk_filled.js", OUT_JSON],
                               cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=1200)
            print("--- runner 尾部 ---")
            for ln in (r.stdout or "").splitlines()[-3:]:
                print(" ", ln[:200])
            if not os.path.exists(OUT_JSON):
                print("!! 无结果"); return
            O = json.loads(io.open(OUT_JSON, encoding="utf-8").read())
            print("errs:", O.get("errs"), " size:", O.get("size"), " group:", O.get("group"))
            shots = O.get("shots") or {}
            from PIL import Image, ImageDraw
            tiles = []
            for k in sorted(shots.keys()):
                v = shots[k]
                if isinstance(v, str) and v.startswith("data:image/png"):
                    fn = os.path.join(HERE, "_scan_out", "ck_%s.png" % k.replace("_png", ""))
                    io.open(fn, "wb").write(base64.b64decode(v.split(",", 1)[1]))
                    im = Image.open(fn).convert("RGB")
                    # 裁中下部（文字区），缩小
                    W, H = im.size
                    im = im.crop((int(W*0.30), int(H*0.05), int(W*0.75), int(H*0.60)))
                    im = im.point(lambda x: min(255, x*10))
                    im.thumbnail((420, 220))
                    tiles.append((k.replace("_png", ""), im))
            cols = 3
            cw = max(t[1].width for t in tiles) + 4
            rh = max(t[1].height for t in tiles) + 16
            rows = (len(tiles) + cols - 1) // cols
            sheet = Image.new("RGB", (cols * cw, rows * rh), (0, 0, 0))
            dr = ImageDraw.Draw(sheet)
            for i, (name, im) in enumerate(tiles):
                x = (i % cols) * cw; y = (i // cols) * rh
                sheet.paste(im, (x + 2, y + 14))
                dr.text((x + 4, y + 2), name, fill=(255, 255, 0))
            out = os.path.join(HERE, "_scan_out", "chunk_sheet.png")
            sheet.save(out)
            print("拼图:", out, sheet.size, "tiles:", len(tiles))
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
