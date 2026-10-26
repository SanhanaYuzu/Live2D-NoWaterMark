# -*- coding: utf-8 -*-
"""GUI 冒烟（真实打包 exe + WebView2）：把 CDP 打进 pywebview 的 WebView2，
在里面走真实桥（set_dir）→ 真实点击切页 → 真实加载模型 → 读 GPU 真值 / 像素 / 帧率。

为什么必须这么做：浏览器 E2E（_e2e_preview.py）验证的是「同一份 ui.html 在 Edge 里」，
但打包后有三件事只有这里能证：
  ① ui.html / 渲染库真的被 PyInstaller 带进了 exe，且能被内置服务同源提供；
  ② WebView2 里 WebGL 真的可用（这是 Live2D 预览的地基，之前只是「待用户实测」）；
  ③ pywebview 的 JS 桥在打包环境里可用（选目录 → 预览全链路）。

纪律：
  - 只读隔离副本 fixture；跑完必须断言 fixture 的 moc3 与激活码文件 sha256 未变（未触碰用户数据）
  - 浏览器/页面侧只测量，PASS/FAIL 全在 Python 侧判定
  - 必有负向对照（捏造目录被拒 / 捏造进程名不存在）
  - 不固定 sleep 猜时间：轮询调试端口与页面就绪信号
用法: python _gui_verify.py
"""
import io, json, os, subprocess, sys, time, hashlib, urllib.request, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(HERE, "dist", "Live2D去水印_v24.exe")
PORT = 9226
PROFILE_MARK = "_wv2_profile"
OUT_JSON = os.path.join(HERE, "_gui_result.json")
SHOTS = os.path.join(HERE, "shots")
FIXTURE_DIR = os.path.join(HERE, "_fixture_ui")
FIXTURE_MODEL = "悠小喵.pv.model3.json"
EXPECT = {"params": 168, "parts": 64, "textures": 2}
NODE = r"C:\Users\xihaochen\.workbuddy\binaries\node\versions\22.22.2-6\node.exe"
KEEP = os.path.join(HERE, "_trash")

report, fails = [], []
def R(s): report.append(str(s))
def CHK(c, label, extra=""):
    if not c: fails.append(label)
    R("%-4s %s %s" % ("PASS" if c else "FAIL", label, extra)); return bool(c)

def sha(p):
    with io.open(p, "rb") as f: return hashlib.sha256(f.read()).hexdigest()

def port_alive(p):
    import socket
    s = socket.socket()
    s.settimeout(1.0)
    try:
        s.connect(("127.0.0.1", p)); return True
    except Exception:
        return False
    finally:
        s.close()

def targets(p):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/json/list" % p, timeout=2) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return []

# ---- 前置：产物与 fixture ----
R("== GUI 冒烟（打包 exe + WebView2）==")
CHK(os.path.exists(EXE), "exe 产物存在", "%d B" % (os.path.getsize(EXE) if os.path.exists(EXE) else 0))
if not os.path.exists(EXE): sys.exit(1)
CHK(os.path.exists(os.path.join(FIXTURE_DIR, FIXTURE_MODEL)), "fixture 模型存在", FIXTURE_MODEL)

# 未触碰用户数据的基线
moc = [os.path.join(FIXTURE_DIR, f) for f in os.listdir(FIXTURE_DIR) if f.endswith(".moc3")]
CHK(len(moc) == 1, "fixture 有且只有一个 moc3", os.path.basename(moc[0]) if moc else "-")
MOC0 = sha(moc[0]) if moc else ""
CFG = os.path.join(HERE, "nwm_universal.json")
CFG0 = sha(CFG) if os.path.exists(CFG) else ""

# 清掉上一轮结果，避免「读到残留的旧结果」那类假报告
if os.path.exists(OUT_JSON):
    os.makedirs(KEEP, exist_ok=True)
    shutil.move(OUT_JSON, os.path.join(KEEP, "gui_result_prev_%d.json" % int(time.time())))

# ---- 启动 exe：给 WebView2 开远程调试端口（这是打进真实 GUI 内部的唯一通道）----
env = dict(os.environ)
env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
    "--remote-debugging-port=%d --remote-allow-origins=* --user-data-dir=%s"
    % (PORT, os.path.join(HERE, PROFILE_MARK)))
R("启动 %s（WebView2 debug port=%d）" % (os.path.basename(EXE), PORT))
proc = subprocess.Popen([EXE], cwd=HERE, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

def kill_all():
    try:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True, timeout=20)
    except Exception:
        try: proc.kill()
        except Exception: pass

try:
    # 轮询调试端口（不固定 sleep）
    t0 = time.time(); ok_port = False
    while time.time() - t0 < 60:
        if port_alive(PORT):
            ok_port = True; break
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    CHK(ok_port, "WebView2 调试端口开放", "用时 %.1fs" % (time.time() - t0))
    if not ok_port:
        out = b""
        try: out = proc.stdout.read() or b""
        except Exception: pass
        R("exe 输出片段: %s" % out.decode("utf-8", "replace")[-600:])
        raise SystemExit(1)

    # 等页面 target
    t0 = time.time(); tgt = None
    while time.time() - t0 < 60:
        for t in targets(PORT):
            if t.get("type") == "page" and t.get("webSocketDebuggerUrl") and "127.0.0.1" in (t.get("url") or ""):
                tgt = t; break
        if tgt: break
        time.sleep(0.5)
    CHK(tgt is not None, "找到可调试页面 target",
        (tgt or {}).get("url", "").replace("?t=", "?t=<redacted>")[:90])

    # ---- 注入 GUI 驱动（runner 会顺带做视口/贴图/切页复核与截图）----
    if tgt:
        drv = io.open(os.path.join(HERE, "_gui_drive.js"), encoding="utf-8").read()
        drv = drv.replace("%FIXTURE%", FIXTURE_DIR.replace("\\", "\\\\"))
        tmp = os.path.join(HERE, "_gui_drive_filled.js")
        io.open(tmp, "w", encoding="utf-8", newline="\n").write(drv)

        r = subprocess.run([NODE, os.path.join(HERE, "_e2e_preview.js"),
                            str(PORT), OUT_JSON, SHOTS, "127.0.0.1", "_gui_drive_filled.js", "gui"],
                           cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=600)
        R("--- runner 日志（尾 25 行）---")
        for ln in (r.stdout or "").splitlines()[-25:]:
            R("  " + ln)
        if r.stderr:
            R("  [stderr] " + r.stderr.strip()[-400:])
        CHK(r.returncode == 0, "runner 正常结束", "rc=%d" % r.returncode)

        O = {}
        if os.path.exists(OUT_JSON):
            O = json.loads(io.open(OUT_JSON, encoding="utf-8").read())
        bad = O.get("errs") or [] or ([O["fatal"]] if O.get("fatal") else [])
        CHK(not bad, "驱动无早退", "errs=%s" % (bad[:3],))
        if bad: raise SystemExit(1)

        # ---- A. 宿主身份：必须是打包 exe 里的 WebView2，而不是外部浏览器 ----
        e = O.get("env") or {}
        CHK(e.get("hasPywebviewBridge") is True, "页面里有 pywebview JS 桥（只有打包宿主才有）")
        CHK(e.get("isWebView2") is True, "UA 是 WebView2/Edge 内核", (e.get("ua") or "")[-60:])
        CHK(e.get("protocol") == "http:", "页面由内置服务以 http 同源提供", e.get("protocol"))
        CHK(e.get("rafWorks") is True, "GUI 内 rAF 真的会触发（像素证据的前提）")
        CHK(e.get("vis") == "visible", "窗口可见", e.get("vis"))
        R("     桥方法 = %s" % e.get("bridgeKeys"))
        R("     标题 = %r" % (e.get("docTitle") or ""))

        # ---- B. 渲染库确实被引入（v2.4.0 的头号缺陷） ----
        L = O.get("libs") or {}
        for k, lab in [("cubismCore", "Live2DCubismCore"), ("pixi", "PIXI"), ("live2dDisplay", "PIXI.live2d.Live2DModel")]:
            CHK(L.get(k) is True, "打包后 %s 已加载" % lab)
        srcs = L.get("scriptSrcs") or []
        R("     script src = %s" % srcs)
        for need in ["live2dcubismcore.min.js", "pixi.min.js", "pixi-live2d-display.min.js"]:
            CHK(any(s.rstrip("/").endswith(need) for s in srcs), "同源引入 %s" % need)
        CHK(L.get("pvOk") is True and (L.get("tokenLen") or 0) >= 8, "预览上下文已就绪（同源 + token）",
            "tokenLen=%s" % L.get("tokenLen"))

        # ---- C. 桥真的可用（含负向） ----
        CHK((O.get("setDirNeg") or {}).get("ok") is False, "负向: 不存在的目录被拒",
            (O.get("setDirNeg") or {}).get("msg", ""))
        CHK((O.get("setDir") or {}).get("ok") is True, "set_dir 绑定 fixture 成功")
        CHK((O.get("previewUrl") or {}).get("ok") is True, "preview_url 返回地址",
            (O.get("previewUrl") or {}).get("base", ""))
        CHK((O.get("state") or {}).get("root", "").lower() == FIXTURE_DIR.lower(),
            "内置服务已指向 fixture", (O.get("state") or {}).get("root", ""))

        # ---- D. 模型真的加载（真实点击 → 真实渲染） ----
        CHK(O.get("loaded") is True, "模型在 GUI 内加载完成", "tag=%s" % O.get("tagText"))
        m = O.get("meta") or {}
        cnt = m.get("counts") or {}
        R("     counts=%s  moc3=%s B sig=%s" % (cnt, m.get("moc3_bytes"), m.get("moc3_sig")))
        for k in ("params", "parts", "textures"):
            CHK(cnt.get(k) == EXPECT[k], "参数/部件/贴图数 = %d" % EXPECT[k], "= %s" % cnt.get(k))
        CHK(bool(m.get("moc3_sig")), "moc3 指纹被读出（裸 core 真解析过）")

        # ---- E. GPU / WebGL：v2.4.0 最难验的一条 ----
        g = O.get("gpu") or {}
        R("     GL = %s | renderer = %s | vendor = %s | maxTex = %s | webgl2=%s"
          % (g.get("glVersion"), g.get("glRenderer"), g.get("glVendor"), g.get("maxTex"), g.get("isWebGL2")))
        CHK(g.get("isWebGL") is True, "PIXI 用的是 WebGL 渲染器（非 canvas 回退）")
        CHK("WebGL" in (g.get("glVersion") or ""), "WebGL 上下文可读", g.get("glVersion"))
        rnd = (g.get("glRenderer") or "")
        CHK(len(rnd) > 3, "拿到真实 GPU 型号", rnd[:60])
        CHK(g.get("maxTex") and g["maxTex"] >= 4096, "MAX_TEXTURE_SIZE 支持大图集", str(g.get("maxTex")))

        st = O.get("stage") or {}
        R("     舞台 rect=%sx%s canvas=%sx%s 模型=%sx%s scale=%s label=%s"
          % (st.get("rectW"), st.get("rectH"), st.get("canvasW"), st.get("canvasH"),
             st.get("modelW"), st.get("modelH"), st.get("scale"), st.get("zoomLabel")))
        CHK(st.get("fitsW") is True and st.get("fitsH") is True, "模型完整放进舞台（没有被裁）")
        CHK((O.get("pixels0") or 0) > 0, "画面真的有像素（模型上屏了）", "覆盖=%s" % O.get("pixels0"))

        # ---- F. 编辑能力在打包环境里也生效 ----
        CHK((O.get("driveMoved") or 0) >= 1, "参数驱动真的改变画面",
            "moved=%s/%s" % (O.get("driveMoved"), len(O.get("drive") or [])))
        p = O.get("part") or {}
        R("     部件 idx=%s opBefore=%s opHidden=%s opBack=%s pxHid=%s pxBack=%s"
          % (p.get("idx"), p.get("opBefore"), p.get("opHidden"), p.get("opBack"), p.get("pxHid"), p.get("pxBack")))
        if p:
            CHK(p.get("opHidden") is not None and p["opHidden"] < 0.01, "取消勾选后部件不透明度归 0", str(p.get("opHidden")))
            CHK(p.get("savedOp0") is True, "隐藏时记下了原不透明度（能恢复的前提）")
            ob, ok0 = p.get("opBack"), p.get("opBefore")
            CHK(ob is not None and ok0 is not None and abs(ob - ok0) <= 0.08,
                "全部显示后不透明度恢复", "%s → %s" % (ok0, ob))
            CHK(p.get("setSizeAfterShowAll") == 0, "恢复后隐藏集合清空", str(p.get("setSizeAfterShowAll")))

        # ---- G. 页面自带渲染自检（诚实报告 GPU 是真卡还是软件渲染） ----
        d = O.get("diag") or {}
        rows = d.get("rows") or []
        R("     自检面板 %d 行:" % d.get("rowCount", 0))
        for k, v in rows:
            R("       %-14s %s" % (k, v))
        CHK(d.get("rowCount", 0) >= 6, "渲染自检面板产出 ≥6 行", str(d.get("rowCount")))
        dmap = dict(rows)
        CHK(any("覆盖像素" in k for k in dmap), "自检含「覆盖像素」项")
        CHK(dmap.get("覆盖像素", "-") not in ("-", "", "0.00%"), "自检报告覆盖像素 > 0", dmap.get("覆盖像素", "-"))

        f = O.get("fps") or {}
        R("     FPS ticker=%s shared=%s 1.5s内tick=%s" % (f.get("tickerFPS"), f.get("shared"), f.get("ticksDuring1p5s")))
        CHK((f.get("tickerFPS") or 0) >= 20, "GUI 内帧率可交互（≥20）", str(f.get("tickerFPS")))
        ra = O.get("rafAfter") or {}
        CHK(ra.get("fallbacks") == 0, "rAF 兜底 0 次（帧调度正常，像素证据可信）",
            "调用 %s / 兜底 %s" % (ra.get("calls"), ra.get("fallbacks")))

        # 截图（runner 尾段还会打 5 张 gui_*.png）
        shots = sorted([f for f in os.listdir(SHOTS) if f.startswith("gui_")])
        R("     截图 = %s" % shots)
        CHK(len(shots) >= 5, "GUI 侧取证截图 ≥5 张", str(len(shots)))

finally:
    kill_all()
    time.sleep(1.5)

# ---- 未触碰用户数据（跑完必须一致） ----
if MOC0:
    CHK(sha(moc[0]) == MOC0, "fixture moc3 未被改写（GUI 全程只读）", MOC0[:16])
if CFG0:
    CHK(sha(CFG) == CFG0, "激活码文件未被改写（冒烟没动用户授权状态）", CFG0[:16])
CHK(not [t for t in targets(PORT) if t.get("type") == "page"], "负向: 收尾后调试端口不再有页面（exe 已退出）")

R("")
R("== PASS=%d FAIL=%d ==" % (len(report) - len(fails) - 2, len(fails)))
if fails: R("失败项: " + "; ".join(fails))
io.open(os.path.join(HERE, "_gui_report.txt"), "w", encoding="utf-8").write("\n".join(report))
print("\n".join(report))
print("DONE fails=%d" % len(fails))
sys.exit(min(len(fails), 1))
