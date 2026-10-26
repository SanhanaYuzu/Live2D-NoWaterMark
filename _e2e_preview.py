# -*- coding: utf-8 -*-
"""ui.html 端到端校验（真实浏览器 + 真实 PreviewServer）
=========================================================
为什么必须这样测（而不是只看静态校验）：
  静态校验只能证明「控件被构造出来了」；本轮就在这上面栽过一次 ——
  参数滑块 .pv-rng 渲染正常、文案正常，但**根本没绑任何事件**，
  整块「参数编辑」是死的。只有真的 dispatch 一个 input 事件、
  再读回 cubism core 的参数值和画面像素，才能证伪。
  同理，「点部件行隔离」「点网格画红色线框」「写入 moc3 默认值」都必须真点。

纪律：
  · 只在 **隔离副本** 上跑：E:\\__nwm_fx__ 复制到 _e2e_ui\\，写入只落在副本上；
    结束时断言源目录的 moc3 sha256 未变（G1/K1）。
  · 正对照 + 负向对照都必有：写前取消不得落盘、关掉线框开关线框必须消失、
    无 token 的 API 必须 403、无改动时「写入」按钮必须禁用。
  · 浏览器侧只做「测量」（_e2e_drive.js），PASS/FAIL 全在 Python 侧判定。
  · 不依赖 pywebview：直接把 Edge 指向 PreviewServer 的 URL（同源，等价于窗口里那套）。
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SRC_FIXTURE_CANDS = [
    os.path.join(HERE, "_fixture_ui"),          # 项目内固定 fixture（首选，自包含）
    r"E:\__nwm_fx__",                           # 早期放在外置盘上的原件（可能已不可用）
]
MODEL_REL = "悠小喵.pv.model3.json"
WORK = os.path.join(HERE, "_e2e_ui")
SHOTS = os.path.join(HERE, "shots")
OUT_JSON = os.path.join(HERE, "_e2e_result.json")
NODE = r"C:\Users\xihaochen\.workbuddy\binaries\node\versions\22.22.2-6\node.exe"
DEBUG_PORT = 9225

PASS, FAIL = [], []


def find_fixture():
    for p in SRC_FIXTURE_CANDS:
        if os.path.isdir(p):
            m = [f for f in os.listdir(p) if f.lower().endswith(".moc3")]
            if m:
                return p, os.path.join(p, m[0])
    raise SystemExit("找不到可用的模型 fixture，试过：%s" % SRC_FIXTURE_CANDS)


def ok(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    if isinstance(detail, (bytes, bytearray)):
        detail = detail[:200].decode("utf-8", "replace")
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  — " + str(detail)) if detail != "" else ""), flush=True)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def note(s):
    print("  %s" % s, flush=True)


# ────────────────────── 0. 准备隔离副本 ──────────────────────
def prepare(SRC_FIXTURE):
    trash = os.path.join(HERE, "_trash")
    os.makedirs(trash, exist_ok=True)
    if os.path.isdir(WORK):
        # safe-delete 纪律：只 rename 挪走，绝不 rmtree
        dst = os.path.join(trash, "_e2e_ui_%s" % time.strftime("%H%M%S"))
        os.rename(WORK, dst)
        note("旧副本挪走 → %s" % dst)
    shutil.copytree(SRC_FIXTURE, WORK)
    note("隔离副本：%s（复制自 %s）" % (WORK, SRC_FIXTURE))
    moc = None
    for fn in os.listdir(WORK):
        if fn.lower().endswith(".moc3"):
            moc = os.path.join(WORK, fn)
    assert moc, "副本里找不到 .moc3"
    return moc


def main():
    import live2d_wm_web as LW
    import live2d_preview as LP

    SRC_FIXTURE, SRC_MOC = find_fixture()
    print("=" * 74)
    SRC_SHA = sha(SRC_MOC)
    print("源 fixture：%s" % SRC_FIXTURE)
    print("源 moc3 sha256 = %s" % SRC_SHA)
    TEST_MOC = prepare(SRC_FIXTURE)
    SHA_BEFORE = sha(TEST_MOC)
    print("副本 moc3 sha256（写前）= %s" % SHA_BEFORE)

    srv = LP.PreviewServer(HERE, "2.4.0", "Live2D 去水印工具",
                           wm_hit=LW.hit_name, moc_parser=LW.Moc3,
                           log=lambda s: note("[srv] " + s))
    srv.start()
    print("预览服务：http://127.0.0.1:%d/  (token %d 字符)" % (srv.port, len(srv.token)))
    r = srv.set_root(WORK)
    assert r.get("ok"), r
    r2 = srv.set_model(MODEL_REL)
    assert r2.get("ok"), r2
    note("models = %s" % json.dumps((r2.get("state") or {}).get("models"), ensure_ascii=False))
    bk_before = [b["name"] for b in srv.list_backups()]
    note("写前备份 = %s" % bk_before)

    # ────────────────────── 1. 起 Edge ──────────────────────
    exe = None
    for pat in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe")):
        if os.path.isfile(pat):
            exe = pat
            break
    if not exe:
        print("找不到 msedge.exe，无法做端到端")
        return 2
    prof = os.path.join(HERE, "_edge_profile_e2e")
    os.makedirs(prof, exist_ok=True)
    args = [exe, "--user-data-dir=" + prof, "--no-first-run", "--no-default-browser-check",
            "--disable-extensions", "--disable-sync",
            "--remote-debugging-port=%d" % DEBUG_PORT,
            # 最大化启动：窗口被最小化/遮挡时 rAF 不触发，整套像素测量失效
            # （实测踩过两次：一次挂死 5 分钟，一次就绪门超时）
            "--start-maximized",
            "--window-size=1320,1040", "--window-position=20,20",
            srv.url]
    note("启动 Edge（真实窗口，约 1~2 分钟）：%s" % exe)
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    note("Edge pid = %d" % proc.pid)

    rc = None
    # ⚠ 先把上一轮的结果挪走。否则 node 在就绪门失败（不写结果文件）时，
    #    下面会读到**上一轮的残留结果**，打出一份「混合两次运行」的假报告 ——
    #    实测踩过：J9/J11/J12 自相矛盾，差点当成产品缺陷去查。
    if os.path.isfile(OUT_JSON):
        _bk = os.path.join(HERE, "_trash", "result_%s.json" % time.strftime("%H%M%S"))
        os.makedirs(os.path.dirname(_bk), exist_ok=True)
        os.rename(OUT_JSON, _bk)
        note("上一轮结果挪走 → %s" % os.path.basename(_bk))
    try:
        t0 = time.time()
        p = subprocess.run([NODE, "_e2e_preview.js", str(DEBUG_PORT), OUT_JSON, SHOTS,
                            "127.0.0.1"],
                           cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=420)
        rc = p.returncode
        print("-" * 74)
        print("node stdout:")
        for ln in (p.stdout or "").splitlines():
            if ln.startswith("RESULT_JSON "):
                continue
            print("  " + ln)
        if p.stderr:
            print("node stderr:")
            for ln in (p.stderr or "").splitlines():
                print("  " + ln)
        print("node 用时 %.1fs，退出码 %s" % (time.time() - t0, rc))
    except subprocess.TimeoutExpired:
        ok("node 运行器在 420s 内结束", False, "超时")
    finally:
        # 记忆铁律：GUI 进程收尾用 taskkill /T /F，否则子进程留着占端口
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        srv.stop()
        time.sleep(0.5)

    # ────────────────────── 2. 读回原始测量值 ──────────────────────
    print("-" * 74)
    if rc != 0:
        ok("node 运行器正常结束（退出码 0）", False, "退出码 %s —— 页面未达到可测量状态，本轮结论作废" % rc)
        print("PASS=%d FAIL=%d" % (len(PASS), len(FAIL)))
        return 3
    if not os.path.isfile(OUT_JSON):
        ok("本轮产出了结果文件", False, "没有 %s" % OUT_JSON)
        print("PASS=%d FAIL=%d" % (len(PASS), len(FAIL)))
        return 3
    O = json.load(io.open(OUT_JSON, encoding="utf-8"))

    def g(*path, default=None):
        cur = O
        for k in path:
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return cur

    if g("fatal") or (g("errs") or []):
        # 驱动早退（例如页面还没就绪、PV 未定义）→ 直接报出来。
        # 不加这条的话会产出几十条「字段为 None」的 FAIL，把真正的原因埋掉（踩过）。
        print("=" * 74)
        ok("页面驱动完整跑完（未早退）", False,
           "errs=%s fatal=%s" % (g("errs"), (g("fatal") or g("fatalStack") or "")[:300]))
        print("页面侧 console 尾部：")
        for ln in (g("__pageLogs") or [])[-12:]:
            print("  " + str(ln)[:220])
        print("PASS=%d FAIL=%d" % (len(PASS), len(FAIL)))
        return 4

    print("=" * 74)
    print("A. 页面与预览初始化")
    ok("A0 测量前提成立：页面可见且 requestAnimationFrame 真的在跑",
       (g("visibility") or {}).get("rafWorks") is True
       and (g("visibility") or {}).get("state") == "visible",
       json.dumps(g("visibility") or {}, ensure_ascii=False))
    ok("A1 PV.ok = True（识别为本地服务托管）", g("pvOk") is True, g("pvOk"))
    ok("A2 协议是 http:", g("proto") == "http:", g("proto"))
    ok("A3 token 由 URL 交到页面", (g("tokenLen") or 0) >= 20, "长度 %s" % g("tokenLen"))
    ok("A4 「去水印」模式下预览面板不占位（display:none）",
       g("paneDisplayClean") == "none", g("paneDisplayClean"))
    ok("A5 点「预览与编辑」→ data-mode 切换且面板 display:grid",
       g("modeAfterSwitch") == "preview" and g("paneDisplayPreview") == "grid" and g("modeBtnOn") is True,
       "mode=%s display=%s on=%s" % (g("modeAfterSwitch"), g("paneDisplayPreview"), g("modeBtnOn")))
    ok("A6 模型加载完成且状态标签为「已加载」",
       g("loaded") is True and g("tagText") == "已加载", "tag=%s" % g("tagText"))
    ok("A7 页面无 JS 异常/错误日志（负向对照：不许有静默报错）",
       not g("__pageErrors"), (g("__pageErrors") or [])[:2])
    ok("A8 版本号 v2.4.0 已显示", g("verTag") == "v2.4.0", g("verTag"))
    ok("A9 水印关键词表在页面侧存在（与 Python 对齐的前提）", g("wmKeysAligned") is True)

    print("B. 元数据 / 裸 core 数据面")
    ok("B1 参数数：cdi3+moc3 元数据 == 运行时 core.parameters.count",
       g("meta", "counts", "params") == g("core", "paCount"),
       "%s vs %s" % (g("meta", "counts", "params"), g("core", "paCount")))
    ok("B2 部件数：cdi3 元数据 == 运行时 core.parts.count",
       g("meta", "counts", "parts") == g("core", "ptCount"),
       "%s vs %s" % (g("meta", "counts", "parts"), g("core", "ptCount")))
    ok("B3 网格数 > 0", (g("core", "drCount") or 0) > 0, g("core", "drCount"))
    ok("B4 贴图 URL 数 == 元数据贴图数",
       g("meta", "url_count") == g("meta", "counts", "textures"),
       "%s vs %s" % (g("meta", "url_count"), g("meta", "counts", "textures")))
    ok("B5 moc3 只回传相对路径（绝对路径不外泄前端）",
       g("meta", "moc3_is_abs") is False and g("meta", "moc3") == "悠小喵.moc3",
       g("meta", "moc3"))
    ok("B6 参数区定位走 cdi3 锚点", g("meta", "anchored") is True and "cdi3" in (g("meta", "locate") or ""),
       g("meta", "locate"))
    ok("B7 裸 core 上没有 getParameterCount（纠正后的 API 面事实）",
       g("core", "rawHasNoGetParam") is True)
    ok("B8 包装层 coreModel 上有 getParameterValueByIndex", g("core", "hasIdxMethods") is True)
    cnv = g("core", "canvas") or {}
    ok("B9 canvasinfo 原始值合理（宽高/PPU > 0，原点有限）",
       (cnv.get("w") or 0) > 0 and (cnv.get("h") or 0) > 0 and (cnv.get("ppu") or 0) > 0
       and cnv.get("ox") is not None and cnv.get("oy") is not None,
       "w=%s h=%s ppu=%s ox=%s oy=%s" % (cnv.get("w"), cnv.get("h"), cnv.get("ppu"), cnv.get("ox"), cnv.get("oy")))
    ok("B10 承载纹理的数值走裸 core 的 textureIndices（非空）",
       len(g("core", "drTex") or []) > 0, (g("core", "drTex") or [])[:8])

    print("C. 视口与渲染")
    st = g("stage") or {}
    ok("C1 舞台有真实尺寸", (st.get("rectW") or 0) > 100 and (st.get("rectH") or 0) > 100,
       "%sx%s" % (st.get("rectW"), st.get("rectH")))
    ok("C2 渲染器是 WebGL（type==1）", st.get("rendererType") == 1, st.get("rendererType"))
    ok("C3 overlay 画布 = 舞台尺寸 × 分辨率",
       st.get("ovW") == (st.get("canvasW") or 0) * (st.get("res") or 1)
       and st.get("ovH") == (st.get("canvasH") or 0) * (st.get("res") or 1),
       "ov=%sx%s vs %sx%s@%s" % (st.get("ovW"), st.get("ovH"), st.get("canvasW"), st.get("canvasH"), st.get("res")))
    ok("C4 模型已缩放且尺寸有效",
       (st.get("modelW") or 0) > 0 and (st.get("modelH") or 0) > 0 and (st.get("scale") or 0) > 0,
       "model=%sx%s scale=%s" % (st.get("modelW"), st.get("modelH"), st.get("scale")))
    ok("C5 ticker 在跑（动作走真实时钟的前提）", st.get("tickerStarted") is True)
    ok("C6 画面真的画出了像素（阳性对照）", (g("pixels0") or 0) > 0, "覆盖 %s" % g("pixels0"))
    ct = g("countsText") or ""
    ok("C7 顶部计数条把 参数/部件/网格/贴图 都写出来了",
       all(k in ct for k in ("参数", "部件", "网格", "贴图")), ct)
    ok("C8 模型加载耗时已记录", (g("loadMs") or 0) > 0, "%s ms" % g("loadMs"))

    print("D. 参数编辑（滑块必须真的驱动 core 与画面）")
    pt = g("paramTab") or {}
    ok("D1 参数页每个参数行都有滑块", pt.get("sliders") == pt.get("rows") and (pt.get("rows") or 0) > 100,
       "%s 滑块 / %s 行" % (pt.get("sliders"), pt.get("rows")))
    ok("D2 无改动时「写入 moc3 默认值」按钮禁用（负向对照）",
       pt.get("writeDisabled") is True and pt.get("resetDisabled") is True)
    ok("D3 抽样 6 个参数置 max → ≥4 个改变了画面",
       (g("driveMoved") or 0) >= 4, "%s / 6" % g("driveMoved"))
    sb, sa = g("sliderBefore") or {}, g("sliderAfter") or {}
    ok("D4 用 UI 滑块拖到 max：core 参数值精确等于 max（已修漏绑事件）",
       sa.get("core") == sa.get("editVal") and sb.get("core") != sa.get("core"),
       "before=%s after=%s max=%s" % (sb.get("core"), sa.get("core"),
                                      (g("sliderAfter", "editVal"))))
    ok("D5 滑块动作真的改变了画面像素（漏绑时这条不可能通过）",
       sa.get("px") is not None and sb.get("px") is not None and sa.get("px") != sb.get("px"),
       "px %s → %s" % (sb.get("px"), sa.get("px")))
    ok("D6 改动被记入 PV.edits（写入按钮才有东西可写）",
       sa.get("edits") == 1 and sa.get("hasEdit") is True, "edits=%s" % sa.get("edits"))
    ok("D7 计数与按钮状态同步刷新",
       "1" in (sa.get("footHtml") or "") and sa.get("writeDisabled") is False,
       "%s / writeDisabled=%s" % (sa.get("footHtml"), sa.get("writeDisabled")))
    ps = g("paramSel") or {}
    ok("D8 点参数行会高亮该行（sel 生效）",
       ps.get("kind") == "param" and ps.get("rowSel") is True, json.dumps(ps, ensure_ascii=False))

    print("E. 部件树（显隐 / 隔离 / 恢复）")
    ptab = g("partTab") or {}
    ok("E1 部件行数 == core.parts.count", ptab.get("rows") == g("core", "ptCount"),
       "%s vs %s" % (ptab.get("rows"), g("core", "ptCount")))
    ok("E2 取消勾选 → 该部件进入隐藏集合", (g("partHide") or {}).get("inSet") is True)
    # ⚠ 不要写 `x or 1`：0 是合法测量值却被当成缺失（第一轮就因此误报了一条 FAIL）
    _op_max = g("partHide", "opAfter")
    ok("E3 隐藏真的生效：core.parts.opacities[i] → 0",
       isinstance(_op_max, (int, float)) and _op_max < 0.01,
       "before=%s after=%s" % (g("partHide", "opBefore"), _op_max))
    ok("E4 行内标签与脚注计数同步", g("partHide", "rowLabel") == "隐藏" and g("partHide", "count") == "1",
       "%s / %s" % (g("partHide", "rowLabel"), g("partHide", "count")))
    ok("E5 点行 → 隔离：除该部件外全部隐藏",
       (g("partIso") or {}).get("othersHidden") is True,
       "setSize=%s / ptCount=%s" % (g("partIso", "setSize"), g("partIso", "ptCount")))
    _op_back = g("partShowAll", "opBack")
    ok("E6 「全部显示」→ 隐藏集合清空且不透明度**主动写回**原值",
       (g("partShowAll") or {}).get("setSize") == 0
       and isinstance(_op_back, (int, float)) and _op_back > 0.9,
       "setSize=%s opBack=%s（core 不会自己重算，必须显式写回）"
       % (g("partShowAll", "setSize"), _op_back))
    px0, pxh = g("partPixels0"), g("partHide", "pxHid")
    pxi, pxb = g("partIso", "pxIso"), g("partShowAll", "pxBack")
    # 像素覆盖率不是恒定值：模型带 physics3.json，画面每帧都在小幅抖动，
    # 所以「恢复后」只能要求落在原值的容许带内（实测抖动 ~1%），不能要求精确相等。
    ok("E7 像素三态自洽：隐藏后画面变小；隔离后进一步变小；恢复后回到原值附近",
       all(isinstance(x, (int, float)) for x in (px0, pxh, pxi, pxb))
       and pxh < px0 * 0.95 and pxi < pxh and abs(pxb - px0) <= px0 * 0.08,
       "原 %s → 隐藏 %s → 隔离 %s → 恢复 %s（容许 ±8%%，实测 physics 抖动约 1%%）"
       % (px0, pxh, pxi, pxb))
    ok("E8 隐藏时保存了原不透明度（恢复的依据）",
       isinstance(g("partHide", "savedOp0"), (int, float)) and g("partHide", "savedOp0") > 0.9,
       g("partHide", "savedOp0"))

    print("F. 网格定位（红色线框真的画上屏幕）")
    ms = g("mesh") or {}
    ok("F1 网格有顶点与三角面", (ms.get("verts") or 0) > 0 and (ms.get("tris") or 0) > 0,
       "verts=%s tris=%s" % (ms.get("verts"), ms.get("tris")))
    ok("F2 投影无 NaN（toGlobal 公式可用）", ms.get("nanPts") == 0, "nan=%s" % ms.get("nanPts"))
    ok("F3 投影点落在视口内（坐标没跑飞）", (ms.get("insidePts") or 0) > 0,
       "inside=%s / %s" % (ms.get("insidePts"), ms.get("verts")))
    ok("F4 overlay 上真的画出了红色线框", (ms.get("ovRed") or 0) > 0 and (ms.get("ovAny") or 0) > 0,
       "redPx=%s anyPx=%s" % (ms.get("ovRed"), ms.get("ovAny")))
    ok("F5 负向对照：关掉线框开关 → overlay 变全透明",
       ms.get("ovAnyAfterToggleOff") == 0, "any=%s" % ms.get("ovAnyAfterToggleOff"))
    ok("F6 选中态与列表一致", ms.get("sel") == ms.get("d"), "sel=%s d=%s" % (ms.get("sel"), ms.get("d")))
    ok("F7 选中后出现「隔离该部件」按钮", ms.get("footHasIso") is True)
    ok("F8 「隔离该部件」→ 切到部件页并只留该部件",
       (g("meshIso") or {}).get("tab") == "part"
       and (g("meshIso", "setSize") or 0) == (g("core", "ptCount") or 0) - 1,
       json.dumps(g("meshIso") or {}, ensure_ascii=False))

    print("G. 贴图与 UV 高亮")
    tx = g("tex") or {}
    ok("G1 贴图项数与图片数都等于元数据贴图数",
       tx.get("items") == tx.get("metaTex") and tx.get("imgs") == tx.get("metaTex"),
       "items=%s imgs=%s meta=%s" % (tx.get("items"), tx.get("imgs"), tx.get("metaTex")))
    good = [n for n in (tx.get("natural") or []) if n and not n.startswith("0x")]
    ok("G2 至少一张贴图真实解码成功（naturalWidth>0）", len(good) >= 1, (tx.get("natural") or [])[:4])
    ok("G3 选中网格在其所属贴图上生成了 UV 多边形高亮",
       (tx.get("polyTot") or 0) >= 1 and (tx.get("polySvgs") or 0) == 1,
       "polygons=%s 覆盖贴图数=%s" % (tx.get("polyTot"), tx.get("polySvgs")))
    _umin, _umax = tx.get("uvMin"), tx.get("uvMax")
    ok("G3b UV 落在 0..1（否则 polygon 会被 viewBox 裁掉成为「有元素但看不见」）",
       isinstance(_umin, (int, float)) and isinstance(_umax, (int, float))
       and _umin >= -0.001 and _umax <= 1.001,
       "uv ∈ [%s, %s]" % (_umin, _umax))
    ok("G3c 高亮多边形在屏幕上真有面积（不是 0×0 的空壳）",
       isinstance(tx.get("polyBox"), list) and tx["polyBox"][0] > 5 and tx["polyBox"][1] > 5,
       "polygon 屏幕尺寸 = %s" % (tx.get("polyBox"),))
    ok("G3d 切页签不再清掉选中态（高亮的锚点）",
       g("meshPickBeforeTex", "sel") is not None and tx.get("selKeptAcrossTab") is not None,
       "切页前 sel=%s，切页后 sel=%s" % (g("meshPickBeforeTex", "sel"), tx.get("selKeptAcrossTab")))
    ok("G4 贴图页禁用「只看水印」（语义上不适用）", tx.get("wmOnlyDisabled") is True)

    print("H. 动作 / 表情（真实时钟）")
    mb = g("motionBtns") or {}
    ok("H1 动作/表情按钮来自 model3.json 声明（fixture 有 1 动作 + 3 表情）",
       (mb.get("total") or 0) >= 4, "共 %s 个：%s" % (mb.get("total"), (mb.get("labels") or [])[:5]))
    ok("H2 播动作真的改变了参数值（固定 dt 循环做不到）",
       (g("motion", "changed") or 0) > 0,
       "changed=%s 例=%s" % (g("motion", "changed"), (g("motion", "changedIdx") or [])[:3]))
    ok("H3 切表情也真的改变了参数值", (g("expression", "changed") or 0) > 0,
       "changed=%s (%s)" % (g("expression", "changed"), g("expression", "label")))

    print("I. 交互与自检面板")
    pa = g("pause") or {}
    ok("I1 暂停/继续按钮真的控制 ticker",
       pa.get("started") is False and pa.get("text") == "继续" and pa.get("startedBack") is True,
       json.dumps(pa, ensure_ascii=False))
    zm = g("zoom") or {}
    # 注意比对的是**双击之后**的 fitS（fitS 会被 pvFit 改写，读成双击前的值会误判）
    ok("I2 双击舞台 → 重新适应：scale == 双击后的 fitS，且模型真的装得进画布",
       zm.get("scaleAfterDbl") == zm.get("fitSAfter") and zm.get("fitsInBox") is True
       and zm.get("userZoomAfter") is False,
       "scale=%s fitSAfter=%s 初始fitS=%s 装得下=%s"
       % (zm.get("scaleAfterDbl"), zm.get("fitSAfter"), zm.get("fitSBefore"), zm.get("fitsInBox")))
    ok("I2b 滚轮缩放后标记为用户接管（之后 resize 不再自动改写比例）",
       (g("zoom", "afterWheel") or {}).get("userZoom") is True,
       json.dumps(g("zoom", "afterWheel") or {}, ensure_ascii=False))
    ok("I2c 点「适应」按钮 → 比例回到 fitS 并交回自动接管",
       (g("zoom", "afterFitBtn") or {}).get("scale") == (g("zoom", "afterFitBtn") or {}).get("fitS")
       and (g("zoom", "afterFitBtn") or {}).get("userZoom") is False,
       json.dumps(g("zoom", "afterFitBtn") or {}, ensure_ascii=False))
    vs = g("viewportShrink") or {}
    ok("I2d 真实视口变矮后模型重新适应、不再被裁（这是 E2E 抓到的真实缺陷）",
       vs.get("fitsH") is True and vs.get("fitsW") is True
       and vs.get("scale") == vs.get("fitS"),
       json.dumps(vs, ensure_ascii=False))
    dg = g("diag") or {}
    labels = [r[0] for r in (dg.get("rows") or [])]
    ok("I3 渲染自检面板有完整条目（含 GPU/覆盖像素/驱动自检/gl.getError）",
       (dg.get("dtCount") or 0) >= 11
       and all(k in labels for k in ("GPU", "WebGL", "覆盖像素", "驱动自检", "gl.getError")),
       "%s 行：%s" % (dg.get("dtCount"), labels))
    drv = [r[1] for r in (dg.get("rows") or []) if r[0] == "驱动自检"]
    ok("I4 自检报告的「驱动自检」命中数 > 0（设完参数必须让出一帧再读像素）",
       bool(drv) and not drv[0].startswith("0 /"), drv)
    gerr = [r[1] for r in (dg.get("rows") or []) if r[0] == "gl.getError"]
    ok("I5 WebGL 无报错（gl.getError == 0）", bool(gerr) and "无错误" in gerr[0], gerr)
    se = g("search") or {}
    ok("I6 搜索过滤生效且清空后恢复全量",
       (se.get("filtered") is not None) and 0 < se.get("filtered") < se.get("all")
       and se.get("back") == se.get("all"),
       json.dumps(se, ensure_ascii=False))
    # 「只看水印」的语义 vs 结构性对照（原先我假设本模型 0 命中，是错的假设）：
    #   正确对照 = 只看水印的行数 == 元数据报告的命中数；且 > 0 说明过滤真的在起作用。
    wo = g("wmOnly") or {}
    ok("I7 「只看水印」过滤结果 == 元数据命中数（结构性正对照）",
       wo.get("rows") == wo.get("wmParamCount") and (wo.get("wmParamCount") or 0) > 0,
       "rows=%s wmParamCount=%s label=%s" % (wo.get("rows"), wo.get("wmParamCount"), wo.get("label")))
    ok("I7b 负向对照：关掉「只看水印」行数恢复全量",
       wo.get("rowsBack") == se.get("all"), "rowsBack=%s all=%s" % (wo.get("rowsBack"), se.get("all")))
    # 真正的不存在匹配项负向对照
    ok("I7c 负向对照：搜一个绝不存在的串 → 0 行且给空态提示",
       g("searchNone", "rows") == 0 and bool(g("searchNone", "hasEmpty")),
       json.dumps(g("searchNone") or {}, ensure_ascii=False))
    ok("I8 页面侧无 token 访问 /api/meta → 403（负向对照）",
       (g("apiNoToken") or {}).get("status") == 403, json.dumps(g("apiNoToken") or {}, ensure_ascii=False))

    print("J. 写入 moc3 默认值（UI 全路径 + 备份闭环）")
    wm_ = g("writeModal") or {}
    ok("J1 点「写入」弹出确认层", wm_.get("exists") is True)
    ok("J2 确认按钮文案与 moc3 相对路径写入提示", wm_.get("okText") == "确认写入" and wm_.get("bodyHasMoc3") is True,
       "%s / body含moc3=%s" % (wm_.get("okText"), wm_.get("bodyHasMoc3")))
    wc = g("writeCancel") or {}
    ok("J3 负向对照：点「取消」→ 弹层关闭且不落盘（moc3_sig 未变、改动保留）",
       wc.get("modalGone") is True and wc.get("editsKept") is True and wc.get("sigSame") is True,
       json.dumps(wc, ensure_ascii=False))
    ok("J4 写入请求内容 = 滑块改动的那 1 项",
       (g("writeRequest") or {}).get("n") == 1, json.dumps(g("writeRequest") or {}, ensure_ascii=False))
    ok("J5 点「确认写入」后流程走完（弹层关闭 + 改动清零）",
       g("writeDone") is True and (g("writeAfter") or {}).get("edits") == 0,
       "done=%s edits=%s %sms" % (g("writeDone"), g("writeAfter", "edits"), g("writeWaitMs")))
    wa = g("writeAfter") or {}
    ok("J6 moc3 的 mtime:size 签名真的变了（文件被写）", wa.get("sigChanged") is True,
       "%s → %s" % (wa.get("sigBefore"), wa.get("sigAfter")))
    ok("J7 日志区明确回显「已写入」",
       any("已写入" in (x or "") for x in (wa.get("logTail") or [])),
       (wa.get("logTail") or [])[-3:])
    bka = g("backupsAfter") or {}
    ok("J8 写入后备份数 +1", (bka.get("n") or 0) == ((g("backupsBefore") or {}).get("n") or 0) + 1,
       "%s → %s" % (g("backupsBefore", "n"), bka.get("n")))

    # ---- Python 侧独立核对（不信任页面自述）----
    bk_after = srv.list_backups()
    new_bk = [b for b in bk_after if b["name"] not in bk_before]
    ok("J9 服务端独立确认：新增恰好 1 个备份目录（且是预览服务格式）",
       len(new_bk) == 1 and new_bk[0].get("source") == "preview",
       [b["name"] for b in new_bk])
    bk_moc = None
    if new_bk:
        for r_, _d_, f_ in os.walk(new_bk[0]["dir"]):
            for fn in f_:
                if fn.lower().endswith(".moc3"):
                    bk_moc = os.path.join(r_, fn)
    ok("J10 备份副本的 sha256 == 写入前的 moc3 sha256（可完整还原）",
       bool(bk_moc) and sha(bk_moc) == SHA_BEFORE,
       ("%s → %s" % (os.path.basename(bk_moc), sha(bk_moc)) if bk_moc else "备份里没有 .moc3"))
    ok("J11 磁盘 moc3 与写入前不同（确实落盘了）", sha(TEST_MOC) != SHA_BEFORE)
    # 用主程序自己的解析器读回默认值，验证「写进去的是我们要的值」
    want_pid = ((g("writeRequest") or {}).get("first") or {}).get("pid")
    want_val = ((g("writeRequest") or {}).get("first") or {}).get("value")
    readback = None
    try:
        moc2 = LW.Moc3(TEST_MOC)
        for it in moc2.param_defaults(None):
            if it["pid"] == want_pid:
                readback = round(float(it["def"]), 5)
                break
    except Exception as e:
        readback = "解析失败 %r" % e
    ok("J12 主程序解析器读回的默认值 == 写入值（%s → %s）" % (want_pid, want_val),
       readback == round(float(want_val), 5) if isinstance(readback, float) else False,
       "读回 %s" % readback)
    ok("J13 撤销/还原后无副作用（写入完成后改动集合为 0）",
       (g("resetAfterWrite") or {}).get("edits") == 0, g("resetAfterWrite"))

    print("K. 与「去水印」互不破坏 / 未触碰源数据")
    mbk = g("modeBack") or {}
    ok("K1 切回「去水印」→ 预览面板让位，模型与元数据仍在内存（不互相破坏）",
       mbk.get("mode") == "clean" and mbk.get("display") == "none"
       and mbk.get("modelAlive") is True and mbk.get("listAlive") is True,
       json.dumps(mbk, ensure_ascii=False))
    ok("K2 源 fixture 的 moc3 sha256 未被触碰（写入只落在工作副本上）",
       sha(SRC_MOC) == SRC_SHA, "%s" % SRC_FIXTURE)
    shot_files = sorted(f for f in os.listdir(SHOTS) if f.startswith("e2e_"))
    ok("K3 已产出 %d 张截图取证" % len(shot_files), len(shot_files) >= 5, shot_files)
    # 原先这里断言「rAF 降级次数 < 调用次数」，实测被判失败：本机渲染 8192² 贴图时
    # 单帧耗时可超过 150ms，于是「慢帧」被误判成「rAF 被挂起」。
    # 真正的前提是 rAF **会**触发（A0 已断言），这里改为给出真实帧率 —— 它还有信息量：
    # 预览是否流畅直接决定这个功能的可用性。
    fps = g("fps") or {}
    ok("K4 rAF 可用且预览帧率达到可交互水平",
       (g("visibility") or {}).get("rafWorks") is True
       and isinstance(fps.get("ticker"), (int, float)) and fps["ticker"] >= 10,
       "ticker FPS=%s / shared FPS=%s（maxFPS=%s，画面 %s，贴图 %s 张）"
       % (fps.get("ticker"), fps.get("shared"), fps.get("maxFPS"), fps.get("screen"), fps.get("textures")))
    ok("K5 rAF 兜底次数远低于调用次数（说明帧调度正常，像素证据可信）",
       isinstance(g("rafCalls"), int) and isinstance(g("rafFallbacks"), int)
       and g("rafCalls") > 0 and g("rafFallbacks") < g("rafCalls"),
       "rAF 调用 %s 次，兜底 %s 次" % (g("rafCalls"), g("rafFallbacks")))

    print("=" * 74)
    print("PASS=%d FAIL=%d" % (len(PASS), len(FAIL)))
    for f in FAIL:
        print("  !! " + f)
    return len(FAIL)


if __name__ == "__main__":
    sys.exit(main())
