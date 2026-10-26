# -*- coding: utf-8 -*-
import base64, io

HERE = "C:/Users/xihaochen/WorkBuddy/2026-08-12-17-01-00/live2d_wm"
adv = base64.b64encode(open(HERE + "/splash_advanced.png", "rb").read()).decode()
xhc = base64.b64encode(open(HERE + "/splash_xhc.png", "rb").read()).decode()

css = io.open(HERE + "/preview_v240.html", encoding="utf-8", newline="").read()
i = css.find("#splash{")
j = css.find("#barwrap{")
splash_css = css[i:j]

html = (
"<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">\n"
"<title>v2.4.0 开屏演示</title>\n"
"<style>\n"
"html,body{margin:0;height:100%;background:linear-gradient(135deg,#e8f7ff 0%,#e6faf3 55%,#f3f0ff 100%);\n"
"  font-family:\"Segoe UI\",system-ui,\"PingFang SC\",\"Microsoft YaHei\",sans-serif}\n"
+ splash_css +
"#splash{position:fixed;inset:0;z-index:60;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:38px}\n"
"#replay{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);z-index:70;\n"
"  padding:8px 18px;border:none;border-radius:9px;background:#0ea5e9;color:#fff;font-weight:700;cursor:pointer}\n"
"</style></head><body>\n"
"<div id=\"splash\"><div id=\"splashBox\"><img id=\"splashImg\" alt=\"ATECH\"><img id=\"splashXhc\" alt=\"XHC Software\"></div>"
"<div id=\"barwrap\"><div id=\"bar\"><div id=\"fill\"></div><div id=\"sheen\"></div></div>"
"<div id=\"status\">正在初始化…</div></div></div>\n"
"<button id=\"replay\" onclick=\"replay()\">重播</button>\n"
"<script>\n"
"const ADV='data:image/png;base64," + adv + "';\n"
"const XHC='data:image/png;base64," + xhc + "';\n"
"function play(){\n"
"  const s=document.getElementById('splash');\n"
"  s.classList.remove('gone','stage2');\n"
"  const im=document.getElementById('splashImg'), xh=document.getElementById('splashXhc');\n"
"  im.src=ADV; xh.src=XHC;\n"
"  setTimeout(function(){ s.classList.add('stage2'); }, 1450);\n"
"}\n"
"function replay(){ play(); }\n"
"window.addEventListener('load', play);\n"
"</script>\n"
"</body></html>\n"
)

io.open(HERE + "/splash_demo.html", "w", encoding="utf-8", newline="").write(html)
print("splash_demo.html written,", len(html), "bytes")
