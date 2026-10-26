# -*- coding: utf-8 -*-
"""
在「原版 v2.4.0 exe」（Downloads 里的真源）上【仅注入法律警告页】，
其余所有字节（Python 字节码 / splash 图 / 资源）保持原样，重新写回 CArchive。
策略：重建 CArchive 时，未改动条目直接复用原始存储字节 + 原始压缩标记；
只有 ui.html 用注入后的版本替换。
"""
import os, re, struct, zlib, base64, sys

SRC_EXE  = r"C:\Users\xihaochen\Downloads\Live2D去水印_v24.exe"
ORIG_UI  = r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm\orig_ui.html"
LOGO     = r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm\warning_logo.png"
OUT_EXE  = r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm\dist\Live2D去水印_v24.exe"
PATCHED  = r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm\ui_patched.html"

sys.path.insert(0, r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm")
from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.archive.writers import CArchiveWriter

# ───────────────────────── 1) 注入警告页到 ui.html ─────────────────────────
html = open(ORIG_UI, "r", encoding="utf-8").read()
assert 'id="warn"' not in html, "ui.html 已有警告页？"
assert 'id="splash"' in html and 'splashXhc' in html, "不是原版 ui.html"

b64 = base64.b64encode(open(LOGO, "rb").read()).decode("ascii")
LOGO_URI = "data:image/png;base64," + b64

# 1a) CSS（自包含，不依赖原版 CSS 变量）插到 </head> 前
WARN_CSS = """  /* ── 法律警告页（开屏后、主界面前）── */
  #warn{position:fixed;inset:0;z-index:60;display:none;flex-direction:column;align-items:center;background:#fff;padding:32px;overflow:auto}
  #warn.show{display:flex;animation:warnIn .3s ease}
  #warn.gone{opacity:0;pointer-events:none;transition:opacity .3s ease}
  @keyframes warnIn{from{opacity:0}to{opacity:1}}
  #warnLogo{align-self:flex-start;max-height:56px;max-width:220px;width:auto;margin-bottom:56px}
  #warnCard{max-width:600px;width:100%;margin:auto 0;display:flex;flex-direction:column;align-items:center;text-align:center}
  #warnVer{font-size:12px;color:#9aa3b2;letter-spacing:.5px;margin-bottom:18px}
  #warnBody{padding:0 8px}
  #warnTitle{font-size:18px;font-weight:700;color:#1f2733;margin:0 0 8px;display:flex;align-items:center;justify-content:center;gap:8px}
  #warnTitle .dot{width:8px;height:8px;border-radius:50%;background:#F2A65A;box-shadow:0 0 0 4px rgba(242,166,90,.16);flex:0 0 8px}
  #warnText{font-size:14px;line-height:1.8;color:#3a4456;margin:0}
  #warnText b{color:#1f2733}
  #warnText .hl{color:#e5484d;font-weight:700}
  #warnList{margin:14px auto 0;padding-left:18px;text-align:left;font-size:13px;line-height:1.75;color:#3a4456;display:inline-block}
  #warnList li{margin-bottom:4px}
  #warnFoot{margin-top:24px;display:flex;gap:14px;justify-content:center}
  #warnFoot button{font:inherit;font-size:14px;font-weight:600;padding:11px 26px;border-radius:10px;cursor:pointer;border:1px solid transparent;transition:.15s}
  #warnAgree{background:#F2A65A;color:#fff}
  #warnAgree:hover{background:#e0913f}
  #warnQuit{background:#fff;color:#6b7686;border-color:#e6e9f0}
  #warnQuit:hover{color:#e5484d;border-color:#e5484d}
"""
assert "</head>" in html
html = html.replace("</head>", "<style>\n" + WARN_CSS + "</style>\n</head>", 1)

# 1b) HTML + JS 插到 </body> 前
WARN_HTML = """<!-- 法律警告：开屏 logo 之后、主界面之前 -->
<div id="warn">
  <img id="warnLogo" src="%s" alt="XHC Software">
  <div id="warnCard">
    <div id="warnVer">XHC Software™ · Live2D 去水印工具 v2.4.0</div>
    <div id="warnBody">
      <h3 id="warnTitle"><span class="dot"></span>使用须知与法律声明</h3>
      <p id="warnText">本软件（含全部源代码、算法、模型与资源）的知识产权归 <b>XHC Software™ / 三花工坊（Sanhana Studio）</b> 所有，受《中华人民共和国著作权法》及国际条约保护。启动即代表你已阅读并同意以下条款：</p>
      <ul id="warnList">
        <li><span class="hl">严禁二次贩卖 / 转售 / 出租 / 分发</span>本软件或其任何副本，包括但不限于打包售卖、加价倒卖、捆绑销售。</li>
        <li><span class="hl">严禁反编译 / 逆向工程 / 破解</span>本程序，或试图提取、还原其源代码、密钥与授权逻辑。</li>
        <li><span class="hl">严禁窃取 / 抄袭 / 搬运源码</span>用于二次开发、竞品或商业获利。</li>
        <li>违反上述任一条款，开发者将依法追究民事责任直至刑事责任，并保留向你索赔全部损失的权利。</li>
      </ul>
    </div>
    <div id="warnFoot">
      <button id="warnQuit" onclick="quitWarn()">退出</button>
      <button id="warnAgree" onclick="agreeWarn()">我已阅读并同意</button>
    </div>
  </div>
</div>
<script>
(function(){
  var warnShown = false;
  window.showWarn = function(){
    if (warnShown) return; warnShown = true;
    var w = document.getElementById('warn');
    if (w) w.classList.add('show');
  };
  window.agreeWarn = function(){
    var w = document.getElementById('warn');
    if (!w) return;
    w.classList.add('gone');
    setTimeout(function(){ w.remove(); }, 320);
  };
  window.quitWarn = function(){
    try { var a = window.pywebview && window.pywebview.api; if (a && a.quit) a.quit(); } catch(e){}
  };
  // 兜底：万一开屏逻辑异常没触发 showWarn，9s 后强制弹出
  setTimeout(function(){ if (!warnShown) window.showWarn(); }, 9000);
})();
</script>
""" % LOGO_URI

assert "</body>" in html
html = html.replace("</body>", WARN_HTML + "</body>", 1)

# 1c) 给 tryHideSplash 增加「开屏结束后弹警告」
OLD = '  s.classList.add("gone"); setTimeout(()=>s.remove(), 600);'
NEW = '  s.classList.add("gone"); setTimeout(()=>{ if(s) s.remove(); showWarn(); }, 650);'
assert OLD in html, "tryHideSplash 结构不匹配，注入中止"
html = html.replace(OLD, NEW, 1)

open(PATCHED, "w", encoding="utf-8").write(html)
print("patched ui.html ->", PATCHED, "size", len(html.encode("utf-8")))
patched_bytes = html.encode("utf-8")

# ───────────────────────── 2) 重建 CArchive ─────────────────────────
cr = CArchiveReader(SRC_EXE)
with open(SRC_EXE, "rb") as fp:
    fp.seek(cr._end_offset - cr._COOKIE_LENGTH)
    ck = fp.read(cr._COOKIE_LENGTH)
magic, archive_length, toc_offset, toc_length, pyvers, pylib = struct.unpack(cr._COOKIE_FORMAT, ck)
pylib_name = pylib.rstrip(b"\0").decode("ascii")

start = cr._start_offset
with open(SRC_EXE, "rb") as fp:
    def read_raw(entry_offset, data_length):
        fp.seek(start + entry_offset); return fp.read(data_length)
    entries = []   # (name, typecode, comp_flag, raw_or_None_for_ui, uncompressed_length)
    for name, (entry_offset, data_length, uncompressed_length, compression_flag, typecode) in cr.toc.items():
        if name == "ui.html":
            entries.append((name, typecode, 1, None, len(patched_bytes)))  # 占位，稍后压
        else:
            raw = read_raw(entry_offset, data_length)
            entries.append((name, typecode, int(compression_flag), raw, uncompressed_length))
    for opt in cr.options:
        entries.append((opt, 'o', 0, b'', 0))

COMP_LEVEL = CArchiveWriter._COMPRESSION_LEVEL
def write_raw(fp, raw, dest_name, typecode, comp_flag, uncompressed_length):
    data_offset = fp.tell()
    data_length = len(raw)
    fp.write(raw)
    return (data_offset, data_length, uncompressed_length, int(comp_flag), typecode, dest_name)

tmp_ca = PATCHED + ".ca"
toc = []
with open(tmp_ca, "wb") as fp:
    for name, typecode, comp_flag, payload, uncompressed_length in entries:
        if payload is None:  # ui.html
            blob = zlib.compress(patched_bytes, COMP_LEVEL)
            toc.append(write_raw(fp, blob, name, 'b', 1, uncompressed_length))
        else:
            toc.append(write_raw(fp, payload, name, typecode, comp_flag, uncompressed_length))
    toc_offset2 = fp.tell()
    toc_data = CArchiveWriter._serialize_toc(toc)
    toc_length2 = len(toc_data)
    fp.write(toc_data)
    archive_length2 = toc_offset2 + toc_length2 + CArchiveWriter._COOKIE_LENGTH
    cookie = struct.pack(CArchiveWriter._COOKIE_FORMAT, CArchiveWriter._COOKIE_MAGIC_PATTERN,
                         archive_length2, toc_offset2, toc_length2, pyvers, pylib_name.encode('ascii'))
    fp.write(cookie)
print("new CArchive ->", tmp_ca, "size", os.path.getsize(tmp_ca), "pylib", pylib_name, "pyvers", pyvers)

# ───────────────────────── 3) 拼回 exe ─────────────────────────
orig = open(SRC_EXE, "rb").read()
new_ca = open(tmp_ca, "rb").read()
assert cr._end_offset == len(orig), "原 archive 不在文件末尾，拼接假设失效"
out = orig[:start] + new_ca
os.makedirs(os.path.dirname(OUT_EXE), exist_ok=True)
open(OUT_EXE, "wb").write(out)
print("written exe ->", OUT_EXE, "size", len(out))

# ───────────────────────── 4) 校验 ─────────────────────────
cr2 = CArchiveReader(OUT_EXE)
u = cr2.extract("ui.html")
print("verify ui.html has warn:", b'id="warn"' in u, "| has splashXhc:", b'splashXhc' in u,
      "| has showWarn:", b'showWarn' in u, "| has tryHideSplash hook:", b'if(s) s.remove(); showWarn();' in u)
print("verify PYZ present:", 'PYZ.pyz' in cr2.toc, "| splash_xhc present:", 'splash_xhc.png' in cr2.toc)
print("DONE")
