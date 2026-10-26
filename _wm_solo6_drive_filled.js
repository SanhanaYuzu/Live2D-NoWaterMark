/* 对指定 drawable 列表逐个 solo 渲染（dr.opacities 直写），拍全幅帧。
   占位符: [27, 28, 29, 30, 31, 32, 33, 36, 37, 38, 117, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 139, 140] = [387,388,389,390,391,392] */
(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const waitFor = async (fn, ms) => { const t0 = performance.now();
    while (performance.now() - t0 < ms) { if (fn()) return true; await sleep(150); } return false; };
  const O = { errs: [], solos: {} };
  const LIST = [27, 28, 29, 30, 31, 32, 33, 36, 37, 38, 117, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 139, 140];
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
    const ids = dr.ids ? dr.ids : null;
    // 1. 隐藏其它部件，保留指定部件（黑底，只留目标组）。占位符 4
    const WM_PART = 4;
    const orig = [];
    for (let i = 0; i < pt.count; i++) orig.push(pt.opacities[i]);
    for (let i = 0; i < pt.count; i++) { try { cm.setPartOpacityByIndex(i, i === WM_PART ? 1 : 0); } catch (e) { } }
    frame();
    // 2. 逐个 solo
    for (const t of LIST) {
      const keep = new Set();
      try {
        const mk = dr.masks ? dr.masks[t] : null;
        if (mk) for (const m of mk) keep.add(m);
      } catch (e) { }
      frame();
      for (let d = 0; d < (dr.opacities ? dr.opacities.length : 0); d++) {
        if (d !== t && !keep.has(d) && dr.opacities) {
          try { if (dr.opacities[d] > 0) dr.opacities[d] = 0; } catch (e) { }
        }
      }
      app.renderer.render(app.stage);
      O.solos["solo_d" + t + "_" + (ids ? ids[t] : "?") + "_png"] = toPNG();
    }
    // 3. 还原
    for (let i = 0; i < pt.count; i++) {
      try { cm.setPartOpacityByIndex(i, orig[i] === undefined ? 1 : orig[i]); } catch (e) { }
    }
    frame();
  } catch (e) { O.errs.push(String(e && e.message || e)); }
  return O;
})()
