import re, base64
b64 = base64.b64encode(open("warning_logo.png","rb").read()).decode("ascii")
LOGO = "data:image/png;base64," + b64

# ---------- 1) ui.html：把警告层 CSS 换成纯白浅色版 ----------
UI="ui.html"
html=open(UI,"r",encoding="utf-8").read()
NEW_WARN_CSS = """  /* ───── 法律警告（开屏 logo 之后、主界面之前；纯白浅色页）───── */
  #warn{position:fixed;inset:0;z-index:60;display:none;align-items:center;justify-content:center;
    background:#ffffff;padding:32px}
  #warn.show{display:flex;animation:warnIn .3s ease}
  #warn.gone{opacity:0;pointer-events:none;transition:opacity .3s ease}
  @keyframes warnIn{from{opacity:0}to{opacity:1}}
  #warnCard{max-width:600px;width:100%;background:#fff;display:flex;flex-direction:column;
    align-items:center;text-align:center}
  #warnTop{display:flex;flex-direction:column;align-items:center;gap:8px;margin-bottom:18px}
  #warnLogo{max-height:88px;max-width:320px;width:auto}
  #warnVer{font-size:12px;color:#9aa3b2;letter-spacing:.5px}
  #warnBody{padding:0 8px}
  #warnTitle{font-size:18px;font-weight:700;color:var(--ink);margin:0 0 8px;display:flex;
    align-items:center;justify-content:center;gap:8px}
  #warnTitle .dot{width:8px;height:8px;border-radius:50%;background:var(--warn);
    box-shadow:0 0 0 4px rgba(224,146,42,.16);flex:0 0 8px}
  #warnText{font-size:14px;line-height:1.8;color:#3a4456;margin:0}
  #warnText b{color:var(--ink)}
  #warnText .hl{color:var(--red);font-weight:700}
  #warnList{margin:14px auto 0;padding-left:18px;text-align:left;font-size:13px;line-height:1.75;
    color:#3a4456;display:inline-block}
  #warnList li{margin-bottom:4px}
  #warnFoot{margin-top:24px;display:flex;gap:14px;justify-content:center}
  #warnFoot button{font:inherit;font-size:14px;font-weight:600;padding:11px 26px;border-radius:10px;
    cursor:pointer;border:1px solid transparent;transition:.15s}
  #warnAgree{background:var(--acc);color:#fff}
  #warnAgree:hover{background:var(--acc2)}
  #warnQuit{background:#fff;color:var(--sub);border-color:var(--line)}
  #warnQuit:hover{color:var(--red);border-color:var(--red)}

"""
pat = re.compile(r"  /\* ───── 法律警告.*?\n\n  /\* ───── 主框架 ───── \*/", re.S)
m = pat.search(html)
assert m, "warn CSS block not found"
# 替换：保留末尾的「主框架」注释
html = html[:m.start()] + NEW_WARN_CSS + "  /* ───── 主框架 ───── */" + html[m.end():]
open(UI,"w",encoding="utf-8").write(html)
print("ui.html light CSS patched")

# ---------- 2) 独立预览页 warning.html：纯白浅色、像一张页而不是弹窗 ----------
PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Live2D 去水印工具 · 使用须知</title>
<style>
  *{box-sizing:border-box}
  html,body{height:100%;margin:0}
  body{font-family:"Segoe UI","Microsoft YaHei",system-ui,-apple-system,sans-serif;
    background:#ffffff;display:flex;align-items:center;justify-content:center;
    padding:32px;-webkit-font-smoothing:antialiased}
  .wrap{max-width:600px;width:100%;display:flex;flex-direction:column;align-items:center;text-align:center}
  .logo{max-height:88px;max-width:320px;width:auto;margin-bottom:18px}
  .ver{font-size:12px;color:#9aa3b2;letter-spacing:.5px;margin-bottom:18px}
  h3{font-size:18px;font-weight:700;color:#1f2733;margin:0 0 8px;display:flex;
    align-items:center;justify-content:center;gap:8px}
  h3 .dot{width:8px;height:8px;border-radius:50%;background:#e0922a;
    box-shadow:0 0 0 4px rgba(224,146,42,.16);flex:0 0 8px}
  p{font-size:14px;line-height:1.8;color:#3a4456;margin:0}
  p b{color:#1f2733}
  .hl{color:#e5484d;font-weight:700}
  ul{margin:14px auto 0;padding-left:18px;text-align:left;font-size:13px;line-height:1.75;
    color:#3a4456;display:inline-block}
  li{margin-bottom:4px}
  .foot{margin-top:24px;display:flex;gap:14px;justify-content:center}
  button{font:inherit;font-size:14px;font-weight:600;padding:11px 26px;border-radius:10px;
    cursor:pointer;border:1px solid transparent;transition:.15s}
  .agree{background:#3b6ef5;color:#fff}
  .agree:hover{background:#2850d8}
  .quit{background:#fff;color:#6b7686;border-color:#e6e9f0}
  .quit:hover{color:#e5484d;border-color:#e5484d}
</style>
</head>
<body>
  <div class="wrap">
    <img class="logo" src="{LOGO}" alt="XHC Software">
    <div class="ver">XHC Software™ · Live2D 去水印工具 v2.4.0</div>
    <h3><span class="dot"></span>使用须知与法律声明</h3>
    <p>本软件（含全部源代码、算法、模型与资源）的知识产权归 <b>XHC Software™ / 三花工坊（Sanhana Studio）</b> 所有，受《中华人民共和国著作权法》及国际条约保护。启动即代表你已阅读并同意以下条款：</p>
    <ul>
      <li><span class="hl">严禁二次贩卖 / 转售 / 出租 / 分发</span>本软件或其任何副本，包括但不限于打包售卖、加价倒卖、捆绑销售。</li>
      <li><span class="hl">严禁反编译 / 逆向工程 / 破解</span>本程序，或试图提取、还原其源代码、密钥与授权逻辑。</li>
      <li><span class="hl">严禁窃取 / 抄袭 / 搬运源码</span>用于二次开发、竞品或商业获利。</li>
      <li>违反上述任一条款，开发者将依法追究民事责任直至刑事责任，并保留向你索赔全部损失的权利。</li>
    </ul>
    <div class="foot">
      <button class="quit" onclick="window.close()">退出</button>
      <button class="agree" onclick="alert('（预览）已同意 —— 正式版将进入主程序')">我已阅读并同意</button>
    </div>
  </div>
</body>
</html>
"""
open("warning.html","w",encoding="utf-8").write(PAGE.replace("{LOGO}",LOGO))
print("warning.html light written")
