# -*- coding: utf-8 -*-
"""用 CREATE_NEW_CONSOLE 独立控制台拉起 probe（模拟正常启动），绕开 Agent 进程的窗口/会话限制。"""
import subprocess, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
PY = r"C:/Users/xihaochen/AppData/Local/Python/pythoncore-3.14-64/python.exe"
out = os.path.join(HERE, "_run_wv2.log")
env = dict(os.environ); env["PYTHONPATH"] = "C:/tmp/pylibs"
env.pop("CODEBUDDY_SESSION_ID", None); env.pop("CLAUDE_SESSION_ID", None)
CREATE_NEW_CONSOLE = 0x00000010
DETACHED = 0x00000008
with open(out, "wb") as f:
    p = subprocess.Popen([PY, os.path.join(HERE, "_probe_render.py"),
                          r"E:/Nostria-试用版", "Nostria.model3.json", "webview"],
                         cwd=HERE, env=env, stdout=f, stderr=subprocess.STDOUT,
                         creationflags=CREATE_NEW_CONSOLE)
print("已用 CREATE_NEW_CONSOLE 拉起 pid=%s，等待…" % p.pid)
p.wait()
print("退出码 =", p.returncode)
