# -*- coding: utf-8 -*-
"""隐藏指定部件并 dump 其 drawable 明细。
用法: python _wm_part_dump.py <模型目录> <部件运行时索引>
注入 _wm_part10_dump.js（占位符 __PARTIDX__），解码 hiddenFrame，打印明细表。"""
import base64, io, json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")
NODE = r"C:\Users\xihaochen\.workbuddy\binaries\node\versions\22.22.2-6\node.exe"
PORT = 9226
OUT_JSON = os.path.join(HERE, "_wm_part10_result.json")

def edge_exe():
    for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]:
        if os.path.exists(p): return p
    raise SystemExit("找不到 msedge.exe")

def main():
    root = sys.argv[1]
    part_idx = int(sys.argv[2])
    drv = io.open(os.path.join(HERE, "_wm_part10_dump.js"), encoding="utf-8").read()
    drv = drv.replace("__PARTIDX__", str(part_idx))
    tmp = os.path.join(HERE, "_wm_part10_dump_filled.js")
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(drv)

    import live2d_preview, live2d_wm_web as W
    prv = live2d_preview.PreviewServer(HERE, W.APP_VER, W.APP_NAME,
                                       wm_hit=W.hit_name, moc_parser=W.Moc3)
    prv.set_root(root)
    prv.start()
    try:
        url = prv.url
        print("预览:", url.split("?")[0], "(token 已隐藏)")
        prof = os.path.join(HERE, "_edge_profile_wmpd_%d" % (int(time.time()) % 1000))
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
                os.rename(OUT_JSON, os.path.join(HERE, "_trash", "wm_p10_prev_%d.json" % int(time.time())))
            r = subprocess.run([NODE, os.path.join(HERE, "_wm_uv_node.js"), str(PORT),
                                "_wm_part10_dump_filled.js", OUT_JSON],
                               cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=600)
            print("--- runner 尾部 ---")
            for ln in (r.stdout or "").splitlines()[-4:]:
                print(" ", ln[:200])
            if not os.path.exists(OUT_JSON):
                print("!! 无结果 JSON"); return
            O = json.loads(io.open(OUT_JSON, encoding="utf-8").read())
            hf = O.pop("hiddenFrame", None)
            if isinstance(hf, str) and hf.startswith("data:image/png"):
                fn = os.path.join(HERE, "_scan_out", "p10_hidden_frame.png")
                io.open(fn, "wb").write(base64.b64decode(hf.split(",", 1)[1]))
                O["hiddenFrame"] = os.path.basename(fn)
            io.open(OUT_JSON, "w", encoding="utf-8").write(json.dumps(O, ensure_ascii=False, indent=1))
            print("== 结果 ==")
            print("errs:", O.get("errs"), " target:", O.get("targetName"),
                  " size:", O.get("size"), " dropped:", len(O.get("dropped") or []))
            print("%-5s %-24s tex uvBoxPx                    masks     maskedBy  verts opBefore->after" % ("d", "id"))
            for h in O.get("detail") or []:
                print("%-5s %-24s %3d %-26s %-9s %-9s %5d %.2f->%.2f" % (
                    h["d"], h["id"], h["tex"], str(h["uvBoxPx"]),
                    str(h["masks"])[:9], str(h["maskedBy"])[:9], h["vertCount"],
                    h["opBefore"], h["opAfter"]))
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
