# -*- coding: utf-8 -*-
"""只做「法律警告页注入」，产出 ui_win7.html（供 Win7 spec 当作 datas）。
逻辑与 _inject_warn_repack.py 的注入段完全一致，但不重建 CArchive。"""
import base64, os

ROOT = r"C:\Users\xihaochen\WorkBuddy\2026-08-12-17-01-00\live2d_wm"
ORIG_UI = os.path.join(ROOT, "orig_ui.html")
LOGO    = os.path.join(ROOT, "warning_logo.png")
OUT     = os.path.join(ROOT, "ui_win7.html")

html = open(ORIG_UI, "r", encoding="utf-8").read()
assert 'id="warn"' not in html, "ui.html 已有警告页？"
assert 'id="splash"' in html and 'splashXhc' in html, "不是原版 ui.html"

b64 = base64.b64encode(open(LOGO, "rb").read()).decode("ascii")
LOGO_URI = "data:image/png;base64," + b64

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
  setTimeout(function(){ if (!warnShown) window.showWarn(); }, 9000);
})();
</script>
""" % LOGO_URI

assert "</body>" in html
html = html.replace("</body>", WARN_HTML + "</body>", 1)

OLD = '  s.classList.add("gone"); setTimeout(()=>s.remove(), 600);'
NEW = '  s.classList.add("gone"); setTimeout(()=>{ if(s) s.remove(); showWarn(); }, 650);'
assert OLD in html, "tryHideSplash 结构不匹配，注入中止"
html = html.replace(OLD, NEW, 1)

open(OUT, "w", encoding="utf-8").write(html)
print("written", OUT, "bytes", len(html.encode("utf-8")))
print("has warn:", 'id="warn"' in html, "| has splashXhc:", 'splashXhc' in html,
      "| has showWarn:", 'showWarn' in html, "| hook:", 'if(s) s.remove(); showWarn();' in html)
