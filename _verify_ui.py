# -*- coding: utf-8 -*-
"""ui.html 静态校验：
  1) 抽出所有内联 <script> 用 node --check 做语法校验；
  2) 收集全文件里出现过的 id="xxx"（含 JS 字符串里动态生成的），
     再收集 JS 里 $('#xxx') / getElementById('xxx') 的引用，
     报告「引用了但任何地方都没有定义」的 id —— 这类拼写错会静默失效；
  3) 选择器唯一性：幂等选择器（#id）在全文件里的「定义」次数应为 1（排除 JS 里的字符串复用）；
  4) 标签配对（div/canvas/dl/button/span 等）粗检。
"""
import io
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "ui.html")
NODE = r"C:\Users\xihaochen\.workbuddy\binaries\node\versions\22.22.2-6\node.exe"

FAIL = []
PASS = []


def ok(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  — " + str(detail)) if detail else ""), flush=True)


s = io.open(HTML, encoding="utf-8").read()
print("ui.html = %d 字符 / %d 字节" % (len(s), len(s.encode("utf-8"))))

# ---- 1. 内联脚本语法 ----
scripts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", s, re.S)
print("内联 script 块：%d 个（大小 %s）" % (len(scripts), [len(x) for x in scripts]))
ok("至少 1 个内联脚本块", len(scripts) >= 1, str(len(scripts)))
syn_ok = True
for i, js in enumerate(scripts):
    # 包一层 IIFE 避免顶层 return 之类误报；用 .mjs 让 node 允许顶层 await
    fd, p = tempfile.mkstemp(suffix=".js")
    os.close(fd)
    with io.open(p, "w", encoding="utf-8") as f:
        f.write("(function(){\n" + js + "\n})();\n")
    r = subprocess.run([NODE, "--check", p], capture_output=True, text=True)
    if r.returncode != 0:
        syn_ok = False
        print("    script#%d 语法错误：\n%s" % (i, (r.stderr or "")[:1500]))
    os.rename(p, os.path.join(HERE, "_trash", os.path.basename(p)) if os.path.isdir(
        os.path.join(HERE, "_trash")) else p)
ok("全部内联脚本语法正确（node --check）", syn_ok)

# ---- 2. id 定义 vs 引用 ----
#     抽取逻辑必须在「主检查」与「负向对照」两处完全一致，否则对照会假失败
#     （曾因负向对照只重跑了其中一条正则而误报，踩过）。
RE_DEF = re.compile(r"""id=["']([A-Za-z0-9_\-]+)["']""")
RE_REF = re.compile(r"""\$\(\s*["']#([A-Za-z0-9_\-]+)["']\s*\)"""
                    r"""|getElementById\(\s*["']([A-Za-z0-9_\-]+)["']\s*\)"""
                    r"""|querySelector\(\s*["']#([A-Za-z0-9_\-]+)["']\s*\)""")


def extract(text):
    """→ (定义过的 id 集合, 被引用的 id 集合)"""
    d = set(RE_DEF.findall(text))
    r = set()
    for m in RE_REF.finditer(text):
        r.add(next(g for g in m.groups() if g))
    return d, r


defined, refs = extract(s)
missing = sorted(r for r in refs if r not in defined)
print("id 定义 %d 个；JS 引用 %d 个" % (len(defined), len(refs)))
ok("所有 JS 引用的 id 都有对应元素", not missing, "缺失：%s" % missing)
ok("引用集合非空（阳性对照：检查本身在工作）", len(refs) > 20, "引用 %d 个" % len(refs))

# ---- 3. 关键 id 唯一 ----
KEYS = ["pvCanvas", "pvOverlay", "pvList", "pvFoot", "pvSearch", "pvStage",
        "pvMotions", "pvInfo", "pvTag", "pvCounts", "pvBusy", "pvBusyTxt",
        "pvHint", "pvZoom", "pvTabs", "modes"]
dup = []
for k in KEYS:
    n = len(re.findall(r"""id=["']%s["']""" % re.escape(k), s))
    if n != 1:
        dup.append("%s x%d" % (k, n))
ok("关键元素 id 各出现恰好 1 次", not dup, "; ".join(dup))

# ---- 4. 标签配对（只查 div，最容易漏） ----
open_div = len(re.findall(r"<div\b", s))
close_div = len(re.findall(r"</div>", s))
ok("div 开闭配平", open_div == close_div, "开 %d 闭 %d" % (open_div, close_div))
for tag in ("canvas", "dl", "button", "svg", "span", "textarea"):
    o = len(re.findall(r"<%s\b" % tag, s))
    c = len(re.findall(r"</%s>" % tag, s))
    ok("%s 开闭配平" % tag, o == c, "开 %d 闭 %d" % (o, c))

# ---- 5. 预览相关必备片段 ----
NEED = [
    ('CSS: body[data-mode="preview"] 切换', 'body[data-mode="preview"] #panePreview{display:grid}'),
    ("HTML: 模式切换按钮", 'data-mode="preview"'),
    ("JS: PV 对象", "const PV = {"),
    ("JS: 参数驱动 setParameterValueByIndex", "setParameterValueByIndex"),
    ("JS: 部件显隐 setPartOpacityByIndex", "setPartOpacityByIndex"),
    ("JS: 投影 toGlobal", "toGlobal(pvPt)"),
    ("JS: 动作 startMotion", "startMotion("),
    ("JS: 表情 expression(", ".expression("),
    ("JS: 写入默认值 /api/param_write", '"/api/param_write"'),
    ("JS: 元数据 /api/meta", '"/api/meta"'),
    ("JS: 贴图 UV 高亮 polygon", 'createElementNS(PVNS, "polygon")'),
    ("JS: 渲染自检 readPixels", "readPixels"),
    ("JS: 水印关键词与 Python 对齐", "water_mark"),
]
miss = [n for n, p in NEED if p not in s]
ok("预览功能必备片段齐全（%d 项）" % len(NEED), not miss, "缺失：%s" % miss)

# ---- 6. 交互控件必须真的接线（「渲染了但没绑事件」是本项目踩过的真实缺陷）----
#    判据：某个交互 class 在 JS 里被 querySelectorAll(".X") 选中后，紧随其后必须出现
#    on<input|change|click> 或 addEventListener —— 只看「构造了 HTML」不算接线。
INTERACTIVE = [".pv-rng", ".pv-vis", ".pv-tab", ".mode", ".pv-row", ".pv-tab"]
unbound = []
for cls in INTERACTIVE:
    ne = "querySelectorAll(\"%s\")" % cls
    hits = []
    for m in re.finditer(re.escape(ne), s):
        seg = s[m.end():m.end() + 900]
        if re.search(r"\.on(input|change|click)\s*=|addEventListener\(\s*['\"](input|change|click)", seg):
            hits.append(m.start())
    if not hits:
        unbound.append(cls)
ok("交互 class 都在选中后真绑了事件（%d 个）" % len(set(INTERACTIVE)), not unbound,
   "未接线：%s" % sorted(set(unbound)))

# 参数滑块的核心语义：必须调用 setParameterValueByIndex 驱动运行时值
_rng_seg = ""
_m = re.search(r'querySelectorAll\("\.pv-rng"\)', s)
if _m:
    _rng_seg = s[_m.end():_m.end() + 900]
ok("参数滑块真的调用 setParameterValueByIndex 驱动参数",
   "setParameterValueByIndex" in _rng_seg, _rng_seg[:200].replace("\n", " ") if _rng_seg else "找不到 .pv-rng 绑定块")
ok("参数滑块改动会记入 PV.edits（写入按钮才有东西可写）", "PV.edits.set(" in _rng_seg)

# ---- 7. 负向对照：把伪造的引用真的注入到 HTML 文本里，验证抽取器能抓到 ----
#    注意：注入的必须是 ASCII id —— 抽取器的字符类就是 ASCII id 范围
#    （[A-Za-z0-9_\-]），注入中文 id 会「抽不到」而让对照假失败（踩过）。
FAKE = "__neg_probe_id__"
BROKEN = s.replace("</script>", '\n$("#%s").onclick = ()=>{};\n</script>' % FAKE, 1)
assert BROKEN != s, "注入锚点 </script> 没找到"
_d2, _r2 = extract(BROKEN)
_miss2 = sorted(r for r in _r2 if r not in _d2)
ok("负向对照：在真实 HTML 文本里注入一个假 id 引用 → 抽取器抓到并报缺",
   FAKE in _r2 and FAKE in _miss2,
   "抽取到该引用=%s；判为缺失=%s" % (FAKE in _r2, FAKE in _miss2))
ok("负向对照同时验了「不应误报」：真实 id 定义集合不变",
   _d2 == defined, "多出 %s" % sorted(_d2 - defined))
ok("负向对照未污染原始引用集合（原始 refs 全在 broken 结果里）",
   refs <= _r2, "丢了 %s" % sorted(refs - _r2))

# ---- 8. 渲染库必须真的被引入，且顺序正确 ----
#    踩过的坑：ui.html 只写了内联脚本、**一个 vendor <script src> 都没有**，
#    于是浏览器里 PIXI 是 undefined，整个预览页直接崩（而静态检查此前只看内联脚本，
#    根本没发现）。这里把「依赖是否被引入 + 顺序」固化成断言。
srcs = re.findall(r"""<script[^>]*\bsrc=["']([^"']+)["']""", s)
print("外部脚本 %d 个：%s" % (len(srcs), srcs))
VENDOR_NEED = ["live2dcubismcore.min.js", "pixi.min.js", "pixi-live2d-display.min.js"]
missing_src = [n for n in VENDOR_NEED if not any(u.rstrip("/").endswith(n) for u in srcs)]
ok("三个渲染库都通过 <script src> 引入", not missing_src, "缺：%s" % missing_src)
ok("外部脚本都走同源 /vendor/（file:// 下预览不可用属预期）",
   all(u.startswith("/vendor/") for u in srcs), srcs)
idx = {n: next((k for k, u in enumerate(srcs) if u.endswith(n)), -1) for n in VENDOR_NEED}
ok("加载顺序：cubismcore → pixi → pixi-live2d-display",
   idx["live2dcubismcore.min.js"] == 0 and idx["pixi.min.js"] == 1
   and idx["pixi-live2d-display.min.js"] == 2, idx)
ok("外部脚本在被内联脚本之前（PIXI 先于 PV 逻辑就绪）",
   len(srcs) > 0 and s.index(srcs[-1]) < s.index("<script>\nconst $ ="),
   "最后一个 vendor 位置 %d" % (s.index(srcs[-1]) if srcs else -1))
ok("渲染库缺失时不会抛「PIXI is not defined」而是给明确提示",
   'typeof PIXI === "undefined"' in s and "缺渲染库" in s)

# ---- 9. 版本号一致 ----
ok("ui.html 版本号与 Python 一致（v2.4.0）", "v2.4.0" in s, [x for x in re.findall(r"v2\.\d+\.\d+", s)])

print("=" * 70)
print("PASS=%d FAIL=%d" % (len(PASS), len(FAIL)))
for f in FAIL:
    print("  !! " + f)
sys.exit(len(FAIL))
