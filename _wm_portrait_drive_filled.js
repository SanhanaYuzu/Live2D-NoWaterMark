/* 高清全身立绘导出：把 renderer 放大到目标高度、模型撑满画布，手动跑帧后整幅读像素。
   输出 O.png（dataURL）+ O.size + 模型原始尺寸。2100 = 目标高度(px)。 */
(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const waitFor = async (fn, ms) => { const t0 = performance.now();
    while (performance.now() - t0 < ms) { if (fn()) return true; await sleep(150); } return false; };
  const O = { errs: [] };
  const TARGET_H = 2100;
  try {
    if (typeof PV === "undefined") { O.errs.push("PV 未定义"); return O; }
    if (!PV.model) { document.querySelector('.mode[data-mode="preview"]').click(); }
    if (!await waitFor(() => !!PV.model, 150000)) { O.errs.push("模型未加载"); return O; }
    await sleep(400);
    const app = PV.app, gl = app.renderer.gl;
    const m = PV.model;
    const sx0 = m.scale.x || 1, sy0 = m.scale.y || 1;
    const iw = m.width / sx0, ih = m.height / sy0;
    O.modelBox = [iw, ih];
    if (!(iw > 1 && ih > 1)) { O.errs.push("模型尺寸异常 " + iw + "x" + ih); return O; }

    // 目标画布：高度 TARGET_H，宽度按模型宽高比
    const H = Math.round(TARGET_H);
    const W = Math.max(64, Math.round(TARGET_H * iw / ih));
    app.renderer.resize(W, H);
    const s = Math.min(W / iw, H / ih) * 0.985;
    m.scale.set(s, s);
    m.position.set((W - iw * s) / 2, (H - ih * s) / 2);
    // 关掉可能存在的舞台位移/缩放影响：直接把模型放在 stage 原点系
    try { m.update(1 / 30); } catch (e) { }
    const frame = () => {
      try { PIXI.Ticker.shared.update(); } catch (e) { }
      try { app.ticker.update(); } catch (e) { }
      try { PV.model.update(1 / 30); } catch (e) { }
      try { PV.model.internalModel.update(1 / 30, performance.now()); } catch (e) { }
      app.renderer.render(app.stage);
    };
    frame(); frame(); frame();
    O.size = [W, H];
    const dw = gl.drawingBufferWidth, dh = gl.drawingBufferHeight;
    O.glSize = [dw, dh];
    const buf = new Uint8Array(dw * dh * 4);
    gl.readPixels(0, 0, dw, dh, gl.RGBA, gl.UNSIGNED_BYTE, buf);
    const cv = document.createElement("canvas"); cv.width = dw; cv.height = dh;
    const ctx = cv.getContext("2d"); const img = ctx.createImageData(dw, dh);
    for (let y = 0; y < dh; y++) {
      const srow = dh - 1 - y;
      const so = (srow * dw) * 4, d = y * dw * 4;
      for (let x = 0; x < dw * 4; x++) img.data[d + x] = buf[so + x];
    }
    ctx.putImageData(img, 0, 0);
    O.png = cv.toDataURL("image/png");
  } catch (e) { O.errs.push(String(e && e.message || e)); }
  return O;
})()
