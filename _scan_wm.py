# -*- coding: utf-8 -*-
"""对解压出来的模型做一次「水印嫌疑」全量盘点：参数 / 部件 / 网格 / 贴图。
只读，不写任何文件。"""
import io, json, os, sys, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import live2d_preview, live2d_wm_web as W

MODELS = [
    ("花嫁小狐免费版", os.path.join(HERE, "_work", "花嫁小狐免费版", "花嫁小狐免费版")),
    ("薄巧_体验版",   os.path.join(HERE, "_work", "薄巧_体验版", "薄巧_体验版")),
]

# 宽泛嫌疑词（中文站常见署名/售卖/试用写法都覆盖）
SUS = ["水印", "署名", "签名", "作者", "版权", "制作", "标注", "标示", "标识",
       "免费", "体验", "试用", "购买", "获取", "解锁", "正版", "付费", "付款",
       "淘宝", "店铺", "爱发电", "afdian", "淘宝", "qq", "微信", "b站", "bilibili",
       "商店", "下载", "关注", "点赞", "投币", "demo", "sample", "trial", "free",
       "logo", "watermark", "wm", "credit", "mark", "copyright", "shop", "store",
       "buy", "purchase", "notice", "info", "提示", "提示语", "官方"]
def sus(t):
    s = str(t or "").lower()
    return [k for k in SUS if k in s]

for name, root in MODELS:
    print("=" * 78)
    print("模型:", name, root)
    prv = live2d_preview.PreviewServer(HERE, W.APP_VER, W.APP_NAME,
                                       wm_hit=W.hit_name, moc_parser=W.Moc3)
    prv.set_root(root)
    st = prv.state()
    print("state:", {k: st.get(k) for k in ("root", "model", "moc3", "cdi3")})
    m = prv.meta()
    if not m.get("ok"):
        print("!! meta 失败:", m.get("msg")); continue
    print("counts:", m.get("counts"), "| locate:", m.get("locate"), "| anchored:", m.get("anchored"))

    params = m.get("params") or []
    print("\n--- 参数 %d 个，命中嫌疑词的 ---" % len(params))
    hitp = 0
    for p in params:
        ks = sus(p.get("name")) + sus(p.get("pid")) + sus(p.get("group"))
        if ks:
            hitp += 1
            print("  [%s] id=%s  name=%r group=%r min=%s max=%s def=%s wm=%s"
                  % (",".join(sorted(set(ks))), p.get("pid"), p.get("name"), p.get("group"),
                     p.get("min"), p.get("max"), p.get("def"), p.get("wm")))
    print("  命中参数数:", hitp)

    parts = m.get("parts") or []
    print("\n--- 部件 %d 个，命中嫌疑词的 ---" % len(parts))
    hitq = 0
    for p in parts:
        ks = sus(p.get("name")) + sus(p.get("pid"))
        if ks:
            hitq += 1
            print("  [%s] id=%s name=%r wm=%s" % (",".join(sorted(set(ks))), p.get("pid"), p.get("name"), p.get("wm")))
    print("  命中部件数:", hitq)

    meshes = m.get("meshes") or []
    print("\n--- 网格 %d 个，命中嫌疑词的 ---" % len(meshes))
    hitm = 0
    for d in meshes:
        ks = sus(d.get("id")) + sus(d.get("name"))
        if ks:
            hitm += 1
            print("  [%s] d=%s id=%r tex=%s verts=%s" % (",".join(sorted(set(ks))), d.get("d"), d.get("id"), d.get("tex"), d.get("verts")))
    print("  命中网格数:", hitm)
    print("\n贴图:", (m.get("urls") or {}).get("textures"))
