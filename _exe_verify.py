# -*- coding: utf-8 -*-
import io, re, sys, marshal, hashlib
from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
EXE, PYZ = sys.argv[1], sys.argv[2]
rep, fails = [], []
def R(s): rep.append(str(s))
def CHK(c, label, extra=""):
    if not c: fails.append(label)
    R("%-4s %s %s" % ("PASS" if c else "FAIL", label, extra)); return bool(c)

r = CArchiveReader(EXE)
disk = io.open("ui.html", encoding="utf-8").read()
emb_raw = r.extract("ui.html")
emb = emb_raw.decode("utf-8")
db, eb = disk.encode("utf-8"), emb.encode("utf-8")
R("disk ui.html = %d B | embedded = %d B" % (len(db), len(eb)))
CHK(hashlib.sha256(db).hexdigest() == hashlib.sha256(eb).hexdigest(),
    "内嵌 ui.html 与磁盘字节完全一致(sha256)", hashlib.sha256(eb).hexdigest()[:16])

# 时间轴：直接按原文匹配（3450 那行 v24 已重写为 splSay("就绪") 形式 → 断言同步为原文）
for frag in ['}, 240);', '}, 260);', 'setTimeout(splashStage2, 1450);',
             '}, 1470);', '}, 2450);', 'splSay("就绪"), 3450);', '}, 4200);']:
    CHK(frag in emb, "时间轴原文 %s" % frag)

# 选择器唯一性：行首锚定（子串法会把 "#splash.stage2 #splashImg{" 误算进去）
for sel in ["#splashImg{", "#splashXhc{", "#splash{", "#barwrap{", "#bar{",
            "#fill{", "#sheen{", "#status{", "#splash.gone{", "#splashBox{"]:
    n = len(re.findall(r"(?m)^\s*" + re.escape(sel), emb))
    CHK(n == 1, "行首唯一 %s" % sel, "= %d" % n)
R("   （对照）子串法 #splashImg{ = %d  ← 含 '#splash.stage2 #splashImg{' 组合选择器" % emb.count("#splashImg{"))

# nwm_auth：递归遍历所有嵌套 code 常量
pyz = ZlibArchiveReader(PYZ)
_d = pyz.extract("nwm_auth")
c = _d if hasattr(_d, "co_name") else marshal.loads(_d[8:])
if hasattr(c, "co_name"):
    pass
else:
    c = marshal.loads(c)
allconsts, allnames, codes = set(), set(), []
def walk(co, depth=0):
    codes.append(co.co_name)
    for k in co.co_consts:
        if hasattr(k, "co_name"):
            walk(k, depth+1)
        elif isinstance(k, str):
            allconsts.add(k)
    allnames.update(co.names if hasattr(co, "names") else co.co_names)
walk(c)
R("nwm_auth code 对象 %d 个" % len(codes))
CHK("tiers" in allconsts, "nwm_auth 含字符串常量 'tiers'", "(%d 个字符串常量)" % len(allconsts))
CHK("activations" in allconsts, "对照: 含 'activations'")
CHK("__no_such_key_zz__" not in allconsts, "负向对照: 捏造键不存在")

# live2d_wm_web：splash_tier 定位（权威检查，替代按常量猜名）
w = marshal.loads(r.extract("live2d_wm_web"))
def find(co, name):
    if co.co_name == name: return co
    for k in co.co_consts:
        if hasattr(k, "co_name"):
            g = find(k, name)
            if g: return g
st = find(w, "splash_tier")
CHK(st is not None, "定位 splash_tier code 对象")
if st:
    nn = set(st.co_names)
    CHK("auth_state" not in nn, "splash_tier 不调 auth_state", "← 负向对照")
    CHK("read_state" in nn, "splash_tier 调 read_state")
    R("     co_names = %s" % sorted(nn))
R("   （说明）上层 '含 splash_tier' 因方法名在嵌套 code 内，顶层常量查不到 → 该检查已作废")

# ===== v2.4.0 预览与编辑：渲染库 + live2d_preview + Moc3 参数区字节码 =====
import os
VENDORS = ["pixi.min.js", "live2dcubismcore.min.js", "pixi-live2d-display.min.js"]
for v in VENDORS:
    p = os.path.join("web", v)
    if not os.path.exists(p):
        CHK(False, "磁盘缺 %s" % p); continue
    try:
        emb_v = r.extract(v)          # spec 平铺到根，所以名字不带 web/
    except Exception as e:
        CHK(False, "exe 内缺 %s" % v, repr(e)); continue
    d_h = hashlib.sha256(io.open(p, "rb").read()).hexdigest()
    e_h = hashlib.sha256(emb_v).hexdigest()
    CHK(d_h == e_h, "内嵌渲染库与磁盘一致 %s" % v, e_h[:16])
for fake in ["__neg_pixi__.js", "web/pixi.min.js"]:   # 负向：捏造名 & 带目录前缀都不该在
    try:
        r.extract(fake); CHK(False, "负向: %s 不应存在" % fake)
    except Exception:
        CHK(True, "负向: %s 不存在（正确）" % fake)

lp = pyz.extract("live2d_preview")
lc = lp if hasattr(lp, "co_name") else marshal.loads(lp[8:])
lnames = set()
def walk2(co):
    lnames.update(co.co_names if hasattr(co, "co_names") else ())
    for k in co.co_consts:
        if hasattr(k, "co_name"): walk2(k)
walk2(lc)
CHK("PreviewServer" in lnames, "live2d_preview 含 PreviewServer")
CHK("res_path" in lnames, "live2d_preview 含 res_path")
CHK("__no_such_class_zz__" not in lnames, "负向: live2d_preview 捏造名不存在")

w2 = find(w, "Moc3")
CHK(w2 is not None, "定位 Moc3 类 code 对象")
if w2:
    mnames = set()
    for k in w2.co_consts:
        if hasattr(k, "co_name"): mnames.add(k.co_name)
    for fn in ["_slot_valid", "locate_params", "set_default"]:
        CHK(fn in mnames, "Moc3.%s 在字节码" % fn)
    CHK("__neg_fn_zz__" not in mnames, "负向: Moc3 捏造方法不存在")
    R("     Moc3 方法数 = %d" % len(mnames))

R("")
R("== FAIL 数 = %d ==" % len(fails))
if fails: R("失败项: " + "; ".join(fails))
io.open("_verify2_report.txt", "w", encoding="utf-8").write("\n".join(rep))
print("DONE fails=%d" % len(fails))
