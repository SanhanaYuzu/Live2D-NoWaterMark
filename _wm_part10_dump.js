/* 隐藏指定部件，dump 被它带走的 drawable 明细（id/tex/uvBoxPx/masks/maskedBy/vertCount）
   + 落一张隐藏帧。占位符: __PARTIDX__ */
(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const waitFor = async (fn, ms) => { const t0 = performance.now();
    while (performance.now() - t0 < ms) { if (fn()) return true; await sleep(150); } return false; };
  const O = { errs: [] };
  const TARGET = __PARTIDX__;
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
      return null; // 不取像素，只要状态更新
    };
    const toPNG = () => {
      app.renderer.render(app.stage);
      const buf = new Uint8Array(w * h * 4);
      gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf);
      const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
      const ctx = cv.getContext("2d"); const img = ctx.createImageData(w, h);
      for (let y = 0; y < h; y++) { const s = (h - 1 - y) * w * 4, d = y * w * 4;
        for (let x = 0; x < w * 4; x++) img.data[d + x] = buf[s + x]; }
      ctx.putImageData(img, 0, 0); return cv.toDataURL("image/png");
    };
    const snap = () => (dr.opacities ? Array.from(dr.opacities) : []);
    const origPart = pt.opacities[TARGET];
    frame();
    const A = snap();
    try { cm.setPartOpacityByIndex(TARGET, 0); } catch (e) { }
    frame();
    const B = snap();
    O.hiddenFrame = toPNG();
    O.targetName = pt.ids ? pt.ids[TARGET] : ("#" + TARGET);
    // masks / maskedBy
    const masksOf = {};
    for (let d = 0; d < dr.count; d++) {
      const m = dr.masks ? dr.masks[d] : null;
      if (m && m.length) masksOf[d] = Array.from(m);
    }
    const TEXS = [4096, 4096, 4096, 4096, 4096, 4096];
    const dropped = [];
    for (let d = 0; d < B.length && d < A.length; d++) {
      if (A[d] - B[d] > 0.3) dropped.push(d);
    }
    O.dropped = dropped;
    O.detail = dropped.map(d => {
      const uv = dr.vertexUvs[d];
      let mnu = 1, mxu = 0, mnv = 1, mxv = 0, cnt = 0;
      for (let k = 0; k + 1 < uv.length; k += 2) {
        const u = uv[k], v = uv[k + 1]; cnt++;
        if (u < mnu) mnu = u; if (u > mxu) mxu = u;
        if (v < mnv) mnv = v; if (v > mxv) mxv = v;
      }
      const tw = TEXS[dr.textureIndices[d]] || 4096, th = tw;
      const by = [];
      for (const [d2, m2] of Object.entries(masksOf)) if (m2.indexOf(d) >= 0) by.push(+d2);
      return { d: d, id: dr.ids[d], tex: dr.textureIndices[d],
               uvBoxPx: [Math.round(mnu * tw), Math.round((1 - mxv) * th),
                         Math.round(mxu * tw), Math.round((1 - mnv) * th)],
               masks: masksOf[d] || [], maskedBy: by,
               vertCount: dr.vertexCounts[d], opBefore: A[d], opAfter: B[d] };
    });
    try { cm.setPartOpacityByIndex(TARGET, origPart === undefined ? 1 : origPart); } catch (e) { }
    frame();
  } catch (e) { O.errs.push(String(e && e.message || e)); }
  return O;
})()
