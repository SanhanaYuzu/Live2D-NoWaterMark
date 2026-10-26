/* 运行时置零指定 drawable 的 indices → 渲染整帧对照。
   输出 base_png（原样）与 patched_png（置零后）。占位符 [155, 208, 209, 302, 303, 304] */
(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const waitFor = async (fn, ms) => { const t0 = performance.now();
    while (performance.now() - t0 < ms) { if (fn()) return true; await sleep(150); } return false; };
  const O = { errs: [] };
  const LIST = [155, 208, 209, 302, 303, 304];
  try {
    if (typeof PV === "undefined") { O.errs.push("PV 未定义"); return O; }
    if (!PV.model) { document.querySelector('.mode[data-mode="preview"]').click(); }
    if (!await waitFor(() => !!PV.model, 150000)) { O.errs.push("模型未加载"); return O; }
    await sleep(400);
    const app = PV.app, gl = app.renderer.gl;
    const w = app.renderer.width, h = app.renderer.height;
    O.size = [w, h];
    const dr = PV.dr;
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
    frame();
    O.base_png = toPNG();
    const saved = {};
    for (const d of LIST) {
      const ix = dr.indices[d];
      saved[d] = Array.from(ix);
      for (let k = 0; k < ix.length; k++) ix[k] = 0;
    }
    frame();
    O.patched_png = toPNG();
    for (const d of LIST) {
      const ix = dr.indices[d];
      for (let k = 0; k < ix.length; k++) ix[k] = saved[d][k];
    }
    // 信息
    O.info = {};
    for (const d of LIST) {
      O.info["d" + d + "_" + dr.ids[d]] = {
        idxLen: dr.indices[d].length,
        masks: dr.masks ? Array.from(dr.masks[d] || []) : [],
        tex: dr.textureIndices[d],
        vertCount: dr.vertexCounts[d],
      };
    }
  } catch (e) { O.errs.push(String(e && e.message || e)); }
  return O;
})()
