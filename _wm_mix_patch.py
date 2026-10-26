# -*- coding: utf-8 -*-
"""混合网格水印外科清除（组合判据版）：
   三角形满足「UV 质心落在同贴图纯文字网格 UV 盒内」且「位置质心 y < 阈值」→ 索引置 0。
用法: python _wm_mix_patch.py <model.moc3> <ArtMeshId=y_thr,...>
依赖: _wm_uvraw_result.json（positions/indices，须为同一模型的原始 dump）
      _wm_alldump_result.json（全量 uvs）
"""
import io, json, os, struct, sys, time

TEX = 4096
PAD = 8.0
PURE = {  # 纯文字网格 -> 同贴图
    3: "d558_ArtMesh1595",
    5: "d559_ArtMesh1239",
    4: "d560_ArtMesh1644",
}

def fail(msg):
    print("FAIL:", msg); sys.exit(1)

def main():
    path = sys.argv[1]
    specs = []
    for part in sys.argv[2].split(","):
        k, v = part.split("=")
        specs.append((k, float(v)))

    HERE = os.path.dirname(os.path.abspath(__file__))
    alld = json.load(io.open(os.path.join(HERE, "_wm_alldump_result.json"), encoding="utf-8"))["meshes"]

    # 纯文字网格 UV 盒（texel，外扩 PAD）
    boxes = {}
    for tex, key in PURE.items():
        m = alld[key]
        vc = m["vertCount"]
        us = [m["uvs"][i*2] for i in range(vc)]
        vs = [m["uvs"][i*2+1] for i in range(vc)]
        boxes[tex] = (min(us)*TEX-PAD, min(vs)*TEX-PAD, max(us)*TEX+PAD, max(vs)*TEX+PAD)
    for tex, b in sorted(boxes.items()):
        print(f"纯文字 UV 盒 tex{tex}: [{b[0]:.1f},{b[1]:.1f}] - [{b[2]:.1f},{b[3]:.1f}]")

    d = bytearray(open(path, "rb").read())
    assert d[:4] == b"MOC3", "not a moc3"
    u32 = lambda off: struct.unpack_from("<I", d, off)[0]
    u16 = lambda off: struct.unpack_from("<H", d, off)[0]
    count_off = u32(0x40)
    A = u32(count_off + 4*4)
    n_posidx = u32(count_off + 4*16)
    print(f"artMeshes={A} positionIndices={n_posidx} filesize={len(d)}")

    cdi_path = path.replace(".moc3", ".cdi3.json")
    cdi = json.load(io.open(cdi_path, encoding="utf-8-sig"))
    params = cdi.get("Parameters") or []
    anchor = params[0]["Id"]
    pat = anchor.encode() + b"\x00" * (64 - len(anchor))
    occ = d.find(bytes(pat))
    if occ < 0: fail(f"锚点 {anchor} 未找到")
    base = occ
    while True:
        rec = d[base-64:base]; z = rec.find(b"\x00")
        if z > 0 and all(0x20 <= b < 0x7f or b >= 0x80 for b in rec[:z]): base -= 64
        else: break
    param_ids_slot = None
    for p in range(0x40, count_off, 4):
        if u32(p) == base: param_ids_slot = p; break
    if param_ids_slot is None: fail("param ids 槽未找到")
    am_ids_slot = param_ids_slot - 0x44
    ids_base = u32(am_ids_slot)
    def read_id(i):
        raw = d[ids_base + 64*i: ids_base + 64*i + 64]
        return raw.split(b"\x00")[0].decode("utf-8", "replace")
    ids = [read_id(i) for i in range(A)]
    vcnt_off = u32(am_ids_slot + 0x28)
    pib_off  = u32(am_ids_slot + 0x30)
    pic_off  = u32(am_ids_slot + 0x34)
    vcnt = [u32(vcnt_off + 4*i) for i in range(A)]
    pib  = [u32(pib_off  + 4*i) for i in range(A)]
    pic  = [u32(pic_off  + 4*i) for i in range(A)]

    section_hi = count_off
    cands = []
    for p in range(0x40, section_hi, 4):
        v = u32(p)
        if 0x40 <= v <= len(d) - 2*n_posidx and v % 2 == 0:
            cands.append(v)
    def mesh_ok(v, m):
        for k in range(0, pic[m], max(1, pic[m]//64)):
            if u16(v + 2*(pib[m]+k)) >= vcnt[m]: return False
        return True
    coarse = []
    stepm = max(1, A // 60)
    for v in sorted(set(cands), reverse=True):
        if all(pic[m] == 0 or u16(v + 2*pib[m]) < vcnt[m] for m in range(0, A, stepm)):
            coarse.append(v)
    idx_base = None
    for v in coarse:
        if all(mesh_ok(v, m) for m in range(A) if pic[m] > 0):
            idx_base = v; break
    if idx_base is None: fail("positionIndices 数组基址未定位")
    bad = sum(0 if mesh_ok(idx_base, m) else 1 for m in range(A))
    if bad: fail(f"全量校验失败 {bad} 个网格越界")
    print(f"positionIndices base=0x{idx_base:x}")

    raw = json.load(io.open(os.path.join(HERE, "_wm_uvraw_result.json"), encoding="utf-8"))
    dump = raw.get("dump") or {}

    ts = time.strftime("%Y%m%d_%H%M%S")
    bdir = os.path.join(os.path.dirname(path), f"_wm_backup_{ts}")
    os.makedirs(bdir, exist_ok=True)
    with open(os.path.join(bdir, os.path.basename(path)), "wb") as f:
        f.write(d)
    print(f"备份 → {bdir}")

    for mesh_id, thr in specs:
        ti = [i for i, s in enumerate(ids) if s == mesh_id]
        if len(ti) != 1: fail(f"目标 {mesh_id} 命中 {len(ti)} 个")
        t = ti[0]
        mkey = None
        for k in dump:
            if k.endswith("_" + mesh_id) or k == "d%d" % t:
                mkey = k; break
        if mkey is None: fail(f"运行时数据缺 {mesh_id}")
        pos = dump[mkey]["positions"]
        idx_arr = dump[mkey]["indices"]
        if len(idx_arr) != pic[t]: fail(f"{mesh_id} 索引数不符: 运行时 {len(idx_arr)} vs 文件 {pic[t]}")
        tex = dump[mkey]["tex"]
        box = boxes.get(tex)
        uvs = alld[mkey]["uvs"]
        if box is None: fail(f"{mesh_id} tex{tex} 无纯文字参照盒")
        ntri = pic[t] // 3
        zeroed = 0; ys = []
        for tri in range(ntri):
            i0, i1, i2 = idx_arr[3*tri], idx_arr[3*tri+1], idx_arr[3*tri+2]
            cy = (pos[2*i0+1] + pos[2*i1+1] + pos[2*i2+1]) / 3.0
            ys.append(cy)
            uc = (uvs[i0*2] + uvs[i1*2] + uvs[i2*2]) / 3.0 * TEX
            vcc = (uvs[i0*2+1] + uvs[i1*2+1] + uvs[i2*2+1]) / 3.0 * TEX
            if cy < thr and box[0] <= uc <= box[2] and box[1] <= vcc <= box[3]:
                off = idx_base + 2*(pib[t] + 3*tri)
                d[off] = 0; d[off+1] = 0
                d[off+2] = 0; d[off+3] = 0
                d[off+4] = 0; d[off+5] = 0
                zeroed += 1
        kept = ntri - zeroed
        below = sum(1 for y in ys if y < thr)
        mid = sum(1 for y in ys if thr <= y < thr + 0.15)
        above = sum(1 for y in ys if y >= thr + 0.15)
        print(f"{mesh_id}(#{t}) tex{tex}: tris={ntri} 清零={zeroed} 保留={kept} | y<thr={below} 中间带={mid} y>thr+0.15={above}")
    tmp = path + ".tmp_patch"
    with open(tmp, "wb") as f:
        f.write(d)
    os.replace(tmp, path)
    print("OK")

if __name__ == "__main__":
    main()
