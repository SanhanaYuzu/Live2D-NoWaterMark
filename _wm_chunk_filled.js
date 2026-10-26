/* 分块定位文字三角形：对指定 mesh，把 indices 按 8 块逐块单独置零 → solo 渲染。
   每块出一张 PNG（键 chunk_<d>_<c>_png），另出一张基线（不清零）。
   占位符: 4 [29, 30, 31, 38] */
(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const waitFor = async (fn, ms) => { const t0 = performance.now();
    while (performance.now() - t0 < ms) { if (fn()) return true; await sleep(150); } return false; };
  const O = { errs: [], shots: {} };
  const WM_PART = 4;
  const LIST = [29, 30, 31, 38];
  const NCHUNK = 8;
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
    };
    const toPNG = () => {
      const buf = new Uint8Array(w * h * 4);
      gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf);
      const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
      const ctx = cv.getContext("2d"); const img = ctx.createImageData(w, h);
      for (let y = 0; y < h; y++) { const s = (h - 1 - y) * w * 4, d = y * w * 4;
        for (let x = 0; x < w * 4; x++) img.data[d + x] = buf[s + x]; }
      ctx.putImageData(img, 0, 0); return cv.toDataURL("image/png");
    };
    // 只留水印部件
    const orig = [];
    for (let i = 0; i < pt.count; i++) orig.push(pt.opacities[i]);
    for (let i = 0; i < pt.count; i++) {
      try { cm.setPartOpacityByIndex(i, i === WM_PART ? 1 : 0); } catch (e) { }
    }
    // 其它可见 drawable 全部置 0（只剩目标组）
    const groupVisible = [];
    for (let d = 0; d < dr.count; d++) {
      if (dr.opacities && dr.opacities[d] > 0.3) groupVisible.push(d);
    }
    O.group = groupVisible;
    const soloOne = (t) => {
      frame();
      const saved = {};
      for (const d of groupVisible) {
        if (d !== t) { saved[d] = dr.opacities[d]; dr.opacities[d] = 0; }
      }
      app.renderer.render(app.stage);
      const png = toPNG();
      for (const d of Object.keys(saved)) dr.opacities[d] = saved[d];
      return png;
    };
    // 对每个 mesh：基线 + 分块
    for (const d of LIST) {
      const ix = dr.indices[d];
      const savedIdx = Array.from(ix);
      const n = ix.length;
      O.shots["base_d" + d + "_png"] = soloOne(d);
      for (let c = 0; c < NCHUNK; c++) {
        const a = Math.floor(n * c / NCHUNK), b = Math.floor(n * (c + 1) / NCHUNK);
        frame();
        for (const dd of groupVisible) { if (dd !== d && dr.opacities) dr.opacities[dd] = 0; }
        for (let k = a; k < b; k++) ix[k] = 0;
        app.renderer.render(app.stage);
        O.shots["chunk_d" + d + "_c" + c + "_png"] = toPNG();
        for (let k = a; k < b; k++) ix[k] = savedIdx[k];
      }
      for (let k = 0; k < n; k++) ix[k] = savedIdx[k];
    }
    // 还原部件
    for (let i = 0; i < pt.count; i++) {
      try { cm.setPartOpacityByIndex(i, orig[i] === undefined ? 1 : orig[i]); } catch (e) { }
    }
    frame();
  } catch (e) { O.errs.push(String(e && e.message || e)); }
  return O;
})()
