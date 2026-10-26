/* 逐部件隐藏 + 配对差分：定位"哪个部件带走胸前文字"。
   每个部件：A=当前帧 → 隐藏部件 i → B=帧 → 差分（全帧采样 + 胸前框精确）。
   同时记录被部件 i 带走的 drawable（opacities 掉 >0.3）。
   对胸前差分大的部件落 diff PNG（键名 *_png，由 Python 解码）。 */
(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const waitFor = async (fn, ms) => { const t0 = performance.now();
    while (performance.now() - t0 < ms) { if (fn()) return true; await sleep(150); } return false; };
  const O = { errs: [], parts: [] };
  try {
    if (typeof PV === "undefined") { O.errs.push("PV 未定义"); return O; }
    if (!PV.model) { document.querySelector('.mode[data-mode="preview"]').click(); }
    if (!await waitFor(() => !!PV.model, 150000)) { O.errs.push("模型未加载"); return O; }
    await sleep(300);
    const app = PV.app, gl = app.renderer.gl;
    const w = app.renderer.width, h = app.renderer.height;
    O.size = [w, h];
    const cm = PV.cm, pt = PV.pt, dr = PV.dr;
    const frame = () => {
      try { PIXI.Ticker.shared.update(); } catch (e) { }
      try { app.ticker.update(); } catch (e) { }
      try { PV.model.update(1 / 30); } catch (e) { }
      try { PV.model.internalModel.update(1 / 30, performance.now()); } catch (e) { }
      app.renderer.render(app.stage);
      const buf = new Uint8Array(w * h * 4);
      gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf);
      return buf;
    };
    // 胸前文字框（比例坐标，来自默认帧目测：x 0.38-0.66, y 0.08-0.63）
    const bx0 = Math.floor(w * 0.38), bx1 = Math.ceil(w * 0.66);
    const by0 = Math.floor(h * 0.08), by1 = Math.ceil(h * 0.63);
    O.box = [bx0, by0, bx1, by1];
    const boxDiff = (A, B) => {
      let n = 0;
      for (let y = by0; y < by1; y++) {
        let base = (y * w + bx0) * 4;
        for (let x = bx0; x < bx1; x++, base += 4) {
          const d1 = Math.abs(A[base] - B[base]), d2 = Math.abs(A[base + 1] - B[base + 1]),
                d3 = Math.abs(A[base + 2] - B[base + 2]);
          if (Math.max(d1, d2, d3) > 40) n++;
        }
      }
      return n;
    };
    const fullDiff = (A, B) => {  // 每 2px 采样
      let n = 0;
      for (let y = 0; y < h; y += 2) {
        let base = (y * w) * 4;
        for (let x = 0; x < w; x += 2, base += 8) {
          const d1 = Math.abs(A[base] - B[base]), d2 = Math.abs(A[base + 1] - B[base + 1]),
                d3 = Math.abs(A[base + 2] - B[base + 2]);
          if (Math.max(d1, d2, d3) > 40) n++;
        }
      }
      return n * 4;
    };
    const toPNG = (buf) => {
      const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
      const ctx = cv.getContext("2d"); const img = ctx.createImageData(w, h);
      for (let y = 0; y < h; y++) { const s = (h - 1 - y) * w * 4, d = y * w * 4;
        for (let x = 0; x < w * 4; x++) img.data[d + x] = buf[s + x]; }
      ctx.putImageData(img, 0, 0); return cv.toDataURL("image/png");
    };
    const diffPNG = (A, B) => {  // 差分幅度可视化
      const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
      const ctx = cv.getContext("2d"); const img = ctx.createImageData(w, h);
      for (let i = 0; i < w * h * 4; i += 4) {
        const d = Math.max(Math.abs(A[i] - B[i]), Math.abs(A[i + 1] - B[i + 1]),
                           Math.abs(A[i + 2] - B[i + 2]));
        const v = Math.min(255, d * 3);
        img.data[i] = v; img.data[i + 1] = v; img.data[i + 2] = v; img.data[i + 3] = 255;
      }
      ctx.putImageData(img, 0, 0); return cv.toDataURL("image/png");
    };

    const orig = [];
    for (let i = 0; i < pt.count; i++) orig.push(pt.opacities[i]);
    const pids = (pt.ids && pt.ids.length === pt.count) ? Array.from(pt.ids) : null;
    let shots = 0;
    for (let i = 0; i < pt.count; i++) {
      const snapA = dr.opacities ? Array.from(dr.opacities) : [];
      const A = frame();
      try { cm.setPartOpacityByIndex(i, 0); } catch (e) { }
      const B = frame();
      const snapB = dr.opacities ? Array.from(dr.opacities) : [];
      const dropped = [];
      for (let d = 0; d < snapB.length && d < snapA.length; d++)
        if (snapA[d] - snapB[d] > 0.3) dropped.push(d);
      const bd = boxDiff(A, B), fd = fullDiff(A, B);
      const rec = { i: i, name: pids ? pids[i] : "", box: bd, full: fd, dropped: dropped };
      if (bd > 150 && shots < 12) { rec.diff_png = diffPNG(A, B); shots++; }
      O.parts.push(rec);
      try { cm.setPartOpacityByIndex(i, orig[i] === undefined ? 1 : orig[i]); } catch (e) { }
    }
    frame();  // 恢复态再跑一帧
    O.parts.sort((a, b) => b.box - a.box);
  } catch (e) { O.errs.push(String(e && e.message || e)); }
  return O;
})()
