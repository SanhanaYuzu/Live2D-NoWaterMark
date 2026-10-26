/* 逐部件 solo：部件 i=1 其余=0 → 渲染 → 裁文字带。占位符 __BAND__ 不用，固定比例 */
(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const waitFor = async (fn, ms) => { const t0 = performance.now();
    while (performance.now() - t0 < ms) { if (fn()) return true; await sleep(150); } return false; };
  const O = { errs: [], solos: {} };
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
    const bx0 = Math.floor(w * 0.34), bx1 = Math.ceil(w * 0.72);
    const by0 = Math.floor(h * 0.03), by1 = Math.ceil(h * 0.68);
    O.box = [bx0, by0, bx1, by1];
    const cropPNG = () => {
      const buf = new Uint8Array(w * h * 4);
      gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf);
      const cw = bx1 - bx0, ch = by1 - by0;
      const cv = document.createElement("canvas"); cv.width = cw; cv.height = ch;
      const ctx = cv.getContext("2d"); const img = ctx.createImageData(cw, ch);
      for (let y = 0; y < ch; y++) {
        const srow = by1 - 1 - y;
        const s = (srow * w + bx0) * 4, d = y * cw * 4;
        for (let x = 0; x < cw * 4; x++) img.data[d + x] = buf[s + x];
      }
      ctx.putImageData(img, 0, 0); return cv.toDataURL("image/png");
    };
    const orig = [];
    for (let i = 0; i < pt.count; i++) orig.push(pt.opacities[i]);
    for (let i = 0; i < pt.count; i++) {
      for (let j = 0; j < pt.count; j++) {
        try { cm.setPartOpacityByIndex(j, j === i ? 1 : 0); } catch (e) { }
      }
      frame();
      O.solos["part" + String(i).padStart(3, "0") + "_png"] = cropPNG();
    }
    for (let i = 0; i < pt.count; i++) {
      try { cm.setPartOpacityByIndex(i, orig[i] === undefined ? 1 : orig[i]); } catch (e) { }
    }
    frame();
  } catch (e) { O.errs.push(String(e && e.message || e)); }
  return O;
})()
