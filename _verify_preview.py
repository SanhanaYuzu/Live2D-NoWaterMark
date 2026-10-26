# -*- coding: utf-8 -*-
"""预览服务 HTTP 层端到端校验。

设计纪律：
  · 正对照 + 负向对照 都必有；
  · 绝不碰生产模型 —— 复制 moc3/cdi3/model3 到隔离目录后再做写入测试；
  · 穿越测试走裸 socket 发原始请求行，绕开 urllib 的 URL 归一化（否则测试本身失真）；
  · 断言要能解释，失败打印真值而不是「FAIL」。
"""
import hashlib
import json
import os
import shutil
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import live2d_preview as LP
import live2d_wm_web as LW

WORK = os.path.join(HERE, "_e2e")

# fixture 解析：外置盘上的 Nostria 优先，不在就退回项目内固定 fixture。
# （踩过：原来的 E:\Nostria-试用版 随外置盘掉线，整个校验脚本直接跑不起来。）
# 期望值都是实测标定出来的真值，不是从被测代码反推的。
FIXTURES = [
    {"src": r"E:\Nostria-试用版", "moc": "Nostria.moc3", "cdi": "Nostria.cdi3.json",
     "m3": "Nostria.model3.json", "expect": {"params": 804, "parts": 362, "textures": 10}},
    {"src": os.path.join(HERE, "_fixture_ui"), "moc": "悠小喵.moc3", "cdi": "悠小喵.cdi3.json",
     "m3": "悠小喵.pv.model3.json", "expect": {"params": 168, "parts": 64, "textures": 2}},
]


def pick_fixture():
    for fx in FIXTURES:
        if all(os.path.isfile(os.path.join(fx["src"], fx[k])) for k in ("moc", "cdi", "m3")):
            return fx
    raise SystemExit("找不到可用 fixture（试过：%s）" % [f["src"] for f in FIXTURES])


FX = pick_fixture()
SRC = FX["src"]
EXP = FX["expect"]

PASS, FAIL = [], []


def ok(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    if isinstance(detail, (bytes, bytearray)):
        detail = detail[:200].decode("utf-8", "replace")
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  — " + str(detail)) if detail else ""), flush=True)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


BASE = ""
TOKEN = ""


def http(path, token=None, data=None, timeout=60, headers=None):
    req = urllib.request.Request(BASE + path, method="POST" if data is not None else "GET")
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-NWM-Token", token)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def raw_get(raw_path, timeout=20, method="GET"):
    """裸 socket：发原始请求行，确保 .. 不被任何客户端归一化。"""
    host = "127.0.0.1"
    port = int(BASE.rsplit(":", 1)[1])
    s = socket.create_connection((host, port), timeout=timeout)
    try:
        req = ("%s %s HTTP/1.1\r\nHost: %s:%d\r\nConnection: close\r\n\r\n"
               % (method, raw_path, host, port)).encode("latin1")
        s.sendall(req)
        buf = b""
        while True:
            b = s.recv(65536)
            if not b:
                break
            buf += b
            if len(buf) > 4096:      # 只要状态行 + 头就够
                break
    finally:
        s.close()
    line = buf.split(b"\r\n", 1)[0].decode("latin1", "replace")
    try:
        code = int(line.split(" ")[1])
    except Exception:
        code = -1
    return code, line


# ─────────────── 准备隔离副本 ───────────────
print("=" * 78)
print("准备隔离测试目录（不碰生产模型）")
print("  fixture 来源 = %s（%s）" % (SRC, FX["m3"]))
if os.path.isdir(WORK):
    old = WORK + "_old_%s" % time.strftime("%H%M%S")
    os.rename(WORK, old)                     # 项目惯例：os.rename 归档，不用 rm
    print("  旧目录已归档 -> %s" % os.path.basename(old))
os.makedirs(WORK, exist_ok=True)
for fn in (FX["moc"], FX["cdi"], FX["m3"]):
    shutil.copy2(os.path.join(SRC, fn), os.path.join(WORK, fn))
PROD_MOC = os.path.join(SRC, FX["moc"])
TEST_MOC = os.path.join(WORK, FX["moc"])
PROD_SHA_BEFORE = sha(PROD_MOC)
TEST_SHA_BEFORE = sha(TEST_MOC)
print("  生产 moc3 sha256 = %s  （收尾复核未变）" % PROD_SHA_BEFORE[:16])
print("  测试 moc3 sha256 = %s" % TEST_SHA_BEFORE[:16])

srv = LP.PreviewServer(HERE, LW.APP_VER, LW.APP_NAME, wm_hit=LW.hit_name,
                       moc_parser=LW.Moc3, log=lambda s: None)
srv.start()
BASE = "http://127.0.0.1:%d" % srv.port
TOKEN = srv.token
print("=" * 78)
print("服务已启动 %s" % BASE)

# ─────────────── A. 鉴权 ───────────────
print("-" * 78)
print("A. /api 鉴权（负向对照为主）")
st, body, _ = http("/api/ping")
ok("A1 无 token → 403", st == 403, "实际 %d %s" % (st, body[:60]))
st, _, _ = http("/api/ping?t=wrongtoken")
ok("A2 错 token → 403", st == 403, "实际 %d" % st)
st, body, _ = http("/api/ping", token=TOKEN)
ok("A3 头 token → 200 ok", st == 200 and json.loads(body).get("ok") is True,
   "实际 %d %s" % (st, body[:70]))
st, body, _ = http("/api/ping?t=" + TOKEN)
ok("A4 query token → 200 ok", st == 200 and json.loads(body).get("ok") is True, "实际 %d" % st)
code, line = raw_get("/api/ping?t=" + TOKEN)
ok("A5 裸请求带 token → 200", code == 200, line)
code, line = raw_get("/api/ping")
ok("A6 裸请求无 token → 403", code == 403, line)
st, _, hdr = http("/api/ping", token=TOKEN)
ok("A7 不返回任何 CORS 头", not any(k.lower().startswith("access-control") for k in hdr),
   "CORS 头=%s" % [k for k in hdr if k.lower().startswith("access-control")])
try:
    _req = urllib.request.Request(BASE + "/api/param_write", method="OPTIONS")
    _req.add_header("Origin", "https://evil.example")
    _req.add_header("Access-Control-Request-Method", "POST")
    _req.add_header("Access-Control-Request-Headers", "x-nwm-token")
    with urllib.request.urlopen(_req, timeout=10) as r:
        st = r.status
except urllib.error.HTTPError as e:
    st = e.code
ok("A8 跨站预检 OPTIONS → 4xx（不给预检）", st >= 400, "实际 %d" % st)
# 裸请求确认 OPTIONS 真被拒
code, line = raw_get("/api/param_write", method="OPTIONS")
ok("A8b 裸 OPTIONS → 405", code == 405, line)
# 未带 token 的写操作必须被拒（真正的危害面）
st, body, _ = http("/api/param_write", data={"items": [{"pid": "ParamEyeBallX", "value": 1}]})
ok("A9 无 token 的写操作 → 403 且不动文件", st == 403 and sha(TEST_MOC) == TEST_SHA_BEFORE,
   "st=%d sha_same=%s" % (st, sha(TEST_MOC) == TEST_SHA_BEFORE))

# ─────────────── B. 静态资源字节一致性 ───────────────
print("-" * 78)
print("B. 静态资源（字节级）")
st, body, _ = http("/")
disk_ui = open(os.path.join(HERE, "ui.html"), "rb").read()
ok("B1 / → ui.html 字节完全一致", st == 200 and body == disk_ui,
   "serve=%d disk=%d" % (len(body), len(disk_ui)))
for name in ("pixi.min.js", "live2dcubismcore.min.js", "pixi-live2d-display.min.js", "logo.png"):
    st, body, _ = http("/vendor/" + name)
    d = open(os.path.join(HERE, "web", name), "rb").read()
    ok("B2 /vendor/%s 字节一致" % name, st == 200 and body == d,
       "serve=%d disk=%d" % (len(body), len(d)))
st, _, _ = http("/logo.png")
ok("B3 /logo.png 别名可用", st == 200, "实际 %d" % st)
st, _, _ = http("/vendor/ui.html")
ok("B4 白名单外 /vendor/ui.html → 404", st == 404, "实际 %d" % st)
st, _, _ = http("/vendor/../ui.html")
ok("B5 /vendor/../ui.html → 404（basename 白名单挡住）", st == 404, "实际 %d" % st)

# ─────────────── C. 目录绑定 + 元数据 ───────────────
print("-" * 78)
print("C. 目录绑定与元数据")
st, body, _ = http("/api/state", token=TOKEN)
ok("C0 绑定前 root 为空串", json.loads(body).get("root") == "",
   "root=%r" % json.loads(body).get("root"))
st, body, _ = http("/model/" + urllib.parse.quote(FX["m3"]))
ok("C1 未绑定目录时 /model → 409", st == 409, "实际 %d" % st)
st, body, _ = http("/api/meta", token=TOKEN)
ok("C2 未绑定目录时 meta.ok=False", json.loads(body).get("ok") is False, body[:80])
st, body, _ = http("/api/set_dir", token=TOKEN, data={"dir": WORK})
d = json.loads(body)
ok("C3 set_dir 成功并发现 1 个 model3.json",
   d.get("ok") and d["state"]["models"] == [FX["m3"]], body[:130])
st, body, _ = http("/api/set_dir", token=TOKEN, data={"dir": r"E:\__不存在的目录__"})
ok("C4 set_dir 不存在目录 → ok=False", json.loads(body).get("ok") is False, body[:80])
st, body, _ = http("/api/set_model", token=TOKEN, data={"rel": "不存在.model3.json"})
ok("C5 set_model 非法 rel → ok=False", json.loads(body).get("ok") is False, body[:80])

st, body, _ = http("/api/meta", token=TOKEN)
meta = json.loads(body)
ok("C6 /api/meta ok", meta.get("ok") is True, body[:150])
print("      counts=%s  ms=%s" % (json.dumps(meta.get("counts"), ensure_ascii=False), meta.get("ms")))
ok("C7 参数 %d 个" % EXP["params"], meta["counts"]["params"] == EXP["params"], str(meta["counts"]["params"]))
ok("C8 部件 %d 个" % EXP["parts"], meta["counts"]["parts"] == EXP["parts"], str(meta["counts"]["parts"]))
ok("C9 贴图 %d 张" % EXP["textures"], meta["counts"]["textures"] == EXP["textures"], str(meta["counts"]["textures"]))
p0 = meta["params"][0]
if FX["moc"].startswith("Nostria"):
    ok("C10 参数名/分组与 cdi3 对齐（Nostria 实值）",
       p0["pid"] == "ParamEyeBallX" and p0["name"] == "眼珠 X" and p0["gname"] == "哎哎九轴一下",
       json.dumps(p0, ensure_ascii=False))
else:
    ok("C10 全部参数都有 id，且 cdi3 提供了显示名（%s）" % FX["m3"],
       all(p["pid"] for p in meta["params"])
       and all(p["name"] for p in meta["params"]),
       "首项 = %s" % json.dumps(p0, ensure_ascii=False))
bad = [p["pid"] for p in meta["params"] if not (p["min"] <= p["def"] <= p["max"] and p["min"] < p["max"])]
ok("C11 全部参数 min<def<max", not bad, "越界 %d 个：%s" % (len(bad), bad[:4]))
ok("C12 参数 idx 连续 0..%d" % (EXP["params"] - 1),
   [p["i"] for p in meta["params"]] == list(range(EXP["params"])),
   "首尾=%s,%s" % (meta["params"][0]["i"], meta["params"][-1]["i"]))
ok("C13 moc3 绝对路径不回传给前端",
   "moc3" in meta and not os.path.isabs(meta["moc3"]), "moc3=%r" % meta.get("moc3"))
st, body, _ = http("/api/meta", token=TOKEN)
ok("C14 二次读 meta 命中缓存", json.loads(body).get("ms", 999) <= meta.get("ms", 0),
   "首次 %s ms" % meta.get("ms"))

# ─────────────── D. /model 文件服务与路径安全 ───────────────
print("-" * 78)
print("D. /model 文件服务与路径安全（裸 socket）")
st, body, hdr = http("/model/" + urllib.parse.quote(FX["m3"]))
disk = open(os.path.join(WORK, FX["m3"]), "rb").read()
ok("D1 model3.json 字节一致", st == 200 and body == disk, "serve=%d disk=%d" % (len(body), len(disk)))
st, body, hdr = http("/model/" + urllib.parse.quote(FX["moc"]), timeout=120)
ok("D2 moc3 字节一致（%d B）" % len(body),
   st == 200 and hashlib.sha256(body).hexdigest() == TEST_SHA_BEFORE,
   "serve=%s expect=%s" % (hashlib.sha256(body).hexdigest()[:16], TEST_SHA_BEFORE[:16]))
ok("D3 moc3 Content-Type = octet-stream",
   hdr.get("Content-Type", "").startswith("application/octet-stream"), hdr.get("Content-Type"))
st, body, hdr = http("/model/" + urllib.parse.quote(FX["cdi"]))
ok("D4 cdi3 Content-Type = json",
   st == 200 and "json" in hdr.get("Content-Type", ""), hdr.get("Content-Type"))
for name, p in (("D5 URL 编码穿越", "/model/%2e%2e%2f%2e%2e%2fWindows%2fwin.ini"),
                ("D6 明文 .. 穿越", "/model/../../Windows/win.ini"),
                ("D7 反斜杠穿越", "/model/..%5c..%5cWindows%5cwin.ini"),
                ("D8 三重穿越", "/model/../../../etc/passwd")):
    code, line = raw_get(p)
    ok("%s → 非 200" % name, code != 200, line)
code, line = raw_get("/model/" + urllib.parse.quote(FX["moc"]))
ok("D9 正常路径裸请求 → 200（阳性对照）", code == 200, line)
st, _, _ = http("/model/" + urllib.parse.quote("不存在.bin"))
ok("D10 不存在文件 → 404", st == 404, "实际 %d" % st)
st, _, _ = http("/model/")
ok("D11 /model/ 空路径 → 非 200", st != 200, "实际 %d" % st)

# ─────────────── E. 参数写入 + 备份可被主程序还原 ───────────────
print("-" * 78)
print("E. 参数写入 / 备份 / 还原")
# 只挑 def 严格位于 min/max 内部的参数，保证写入一定产生变化
T = [p for p in meta["params"] if p["min"] < p["def"] < p["max"]]
ok("E0 存在可用于测试的参数（def 严格在范围内）", len(T) >= 2,
   "可用 %d 个，前两个=%s" % (len(T), [p["pid"] for p in T[:2]]))
T0, T1 = T[0], T[1]
items = [{"pid": T0["pid"], "value": T0["max"]},
         {"pid": T1["pid"], "value": T1["min"]},
         {"pid": "不存在的参数", "value": 1.0}]
n_bk_before = len([x for x in os.listdir(WORK) if x.startswith("_wm_backup_")])
st, body, _ = http("/api/param_write", token=TOKEN, data={"items": items}, timeout=90)
w = json.loads(body)
ok("E1 写入返回 ok", w.get("ok") is True, body[:220])
print("      changed=%s skipped=%s unknown=%s backup=%s"
      % (w.get("changed"), w.get("skipped"), w.get("unknown"), w.get("backup_name")))
ok("E2 changed == 2", w.get("changed") == 2, "changed=%s" % w.get("changed"))
ok("E3 不存在的 pid 进 unknown", w.get("unknown") == ["不存在的参数"], str(w.get("unknown")))
ok("E4 写入内容与请求一致（new==max / new==min）",
   abs(w["applied"][0]["new"] - T0["max"]) < 1e-4 and abs(w["applied"][1]["new"] - T1["min"]) < 1e-4,
   json.dumps(w["applied"], ensure_ascii=False))
TEST_SHA_AFTER = sha(TEST_MOC)
ok("E5 写后 moc3 sha256 变化", TEST_SHA_AFTER != TEST_SHA_BEFORE,
   "%s -> %s" % (TEST_SHA_BEFORE[:12], TEST_SHA_AFTER[:12]))
ok("E6 文件长度未变（就地改 float32）",
   os.path.getsize(TEST_MOC) == os.path.getsize(PROD_MOC), str(os.path.getsize(TEST_MOC)))
n_bk_after = len([x for x in os.listdir(WORK) if x.startswith("_wm_backup_")])
ok("E7 恰好新增 1 个备份", n_bk_after == n_bk_before + 1,
   "%d -> %d" % (n_bk_before, n_bk_after))

bdir = w.get("backup") or ""
bk = os.path.join(bdir, FX["moc"])
ok("E8 备份目录含原 moc3 且字节等于写入前",
   os.path.isfile(bk) and sha(bk) == TEST_SHA_BEFORE, "backup=%s" % os.path.basename(bdir))

# 差异必须是「恰好 2 段 × 4 字节」
new = open(TEST_MOC, "rb").read()
orig = open(bk, "rb").read()
ok("E9 文件长度一致（可比对）", len(new) == len(orig), "%d vs %d" % (len(new), len(orig)))
spans, i, n = [], 0, min(len(new), len(orig))
while i < n:
    if new[i] != orig[i]:
        j = i
        while j < n and new[j] != orig[j]:
            j += 1
        spans.append((i, j - i))
        i = j
    else:
        i += 1
# 按 4 字节对齐归到 float32 槽位（0.0→1.0 只改第 2/3 字节，所以裸 diff 段是 2 字节而非 4）
slots = set()
for (off, ln) in spans:
    for b in range(off, off + ln):
        slots.add((b // 4) * 4)
want = set(int(a["offset"]) for a in w["applied"])
ok("E10 变化恰好落在请求的 %d 个 float32 槽位（按 4 字节对齐）" % len(want),
   slots == want and len(want) == 2, "实际槽位=%s 期望=%s 裸差异段=%s" % (sorted(slots), sorted(want), spans))
import struct as _st
vals = [_st.unpack_from("<f", new, o)[0] for o in sorted(want)]
ok("E10b 各槽位读回的 float 等于请求值",
   sorted(vals) == sorted([float(a["new"]) for a in w["applied"]]),
   "读回=%s 请求=%s" % (vals, [a["new"] for a in w["applied"]]))

# 主程序能否识别并还原？
tool = LW.Tool()
tool.set_dir(WORK)
bks = tool.list_backups()
ok("E11 主程序 list_backups 认识预览产生的备份",
   any(os.path.basename(b["dir"]) == os.path.basename(bdir) for b in bks),
   "识别 %d 个：%s" % (len(bks), [b["name"] for b in bks]))
r = tool.restore(bdir)
ok("E12 主程序 restore 成功", r.get("ok") and r.get("restored", 0) >= 1,
   json.dumps(r, ensure_ascii=False))
ok("E13 还原后 sha256 回到写入前", sha(TEST_MOC) == TEST_SHA_BEFORE,
   "%s vs %s" % (sha(TEST_MOC)[:12], TEST_SHA_BEFORE[:12]))

# 幂等 / 边界
st, body, _ = http("/api/param_write", token=TOKEN, data={"items": [
    {"pid": T0["pid"], "value": T0["max"]},
    {"pid": T1["pid"], "value": T1["min"]}]}, timeout=90)
w2 = json.loads(body)
ok("E14 还原后再写同值 → changed=2（证明确实回滚了）", w2.get("changed") == 2,
   "changed=%s" % w2.get("changed"))
nb = len([x for x in os.listdir(WORK) if x.startswith("_wm_backup_")])
st, body, _ = http("/api/param_write", token=TOKEN, data={"items": [
    {"pid": T0["pid"], "value": T0["max"]}]}, timeout=90)
w3 = json.loads(body)
na = len([x for x in os.listdir(WORK) if x.startswith("_wm_backup_")])
ok("E15 值无变化 → changed=0 且不产生新备份",
   w3.get("changed") == 0 and na == nb, "changed=%s 备份 %d->%d" % (w3.get("changed"), nb, na))
st, body, _ = http("/api/param_write", token=TOKEN, data={"items": []}, timeout=30)
ok("E16 空 items → ok=False", json.loads(body).get("ok") is False, body[:80])
st, body, _ = http("/api/param_write", token=TOKEN, data={"items": [
    {"pid": T1["pid"], "value": -9e12}]}, timeout=90)
w4 = json.loads(body)
if w4.get("applied"):
    ok("E17 超范围值被 clamp 到 min",
       abs(w4["applied"][0]["new"] - T1["min"]) < 1e-4,
       "new=%s min=%s" % (w4["applied"][0]["new"], T1["min"]))
else:
    ok("E17 超范围值被 clamp 到 min", True, "当前已是 min，被 skip（changed=%s）" % w4.get("changed"))
st, body, _ = http("/api/backups", token=TOKEN)
bl = json.loads(body)
ok("E18 /api/backups 列出备份", bl.get("ok") and len(bl["backups"]) >= 2,
   json.dumps([b["name"] for b in bl["backups"]], ensure_ascii=False))
ok("E19 元数据缓存已在写后失效（moc3_sig 变化）",
   json.loads(http("/api/meta", token=TOKEN)[1])["moc3_sig"] != meta["moc3_sig"],
   "%s -> %s" % (meta["moc3_sig"], json.loads(http("/api/meta", token=TOKEN)[1])["moc3_sig"]))

# ─────────────── F. 并发 ───────────────
print("-" * 78)
print("F. 并发（ThreadingHTTPServer）")
res = []


def worker():
    s, b, _ = http("/model/" + urllib.parse.quote(FX["moc"]), timeout=120)
    res.append((s, len(b)))


ths = [threading.Thread(target=worker) for _ in range(4)]
t0 = time.time()
for t in ths:
    t.start()
for t in ths:
    t.join()
ok("F1 4 线程并发取 moc3 全 200 且长度一致",
   len(res) == 4 and all(s == 200 for s, _ in res) and len(set(l for _, l in res)) == 1,
   "%.1fs %s" % (time.time() - t0, res))

srv.stop()

# ─────────────── G. 生产文件未被触碰 ───────────────
print("-" * 78)
print("G. 生产文件未被触碰")
ok("G1 生产 moc3 sha256 未变", sha(PROD_MOC) == PROD_SHA_BEFORE,
   "%s -> %s" % (PROD_SHA_BEFORE[:16], sha(PROD_MOC)[:16]))

print("=" * 78)
print("PASS=%d  FAIL=%d" % (len(PASS), len(FAIL)))
for f in FAIL:
    print("  !! " + f)
sys.exit(len(FAIL))
