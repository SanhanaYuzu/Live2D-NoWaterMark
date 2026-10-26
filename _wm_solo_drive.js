/* 逐部件 solo 渲染：所有 part 隐藏 → 逐个显示 → render → readPixels。
   返回每个 part 的：可见像素数 / 灰色像素数 / bbox / PNG 缩略（仅可疑的返回全帧太贵，
   这里返回每 part 的 AlphaMask+颜色统计，帧图由 Python 侧另行 solo 拍）。 */
(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const waitFor = async (fn, ms) => {
    const t0 = performance.now();
    while (performance.now() - t0 < ms) { if (fn()) return true; await sleep(150); }
    return false;
  };
  const O = { errs: [] };
  try {
    if (typeof PV === "undefined") { O.errs.push("PV 未定义"); return O; }
    if (!PV.model) {
      const mb = document.querySelector('.mode[data-mode="preview"]');
      if (!mb) { O.errs.push("找不到预览模式按钮"); return O; }
      mb.click();
    }
    if (!await waitFor(() => !!PV.model, 150000)) { O.errs.push("模型未加载"); return O; }
    await sleep(300);

    const app = PV.app, gl = app.renderer.gl;
    if (!gl) { O.errs.push("无 WebGL 上下文"); return O; }
    const w = app.renderer.width, h = app.renderer.height;
    O.size = [w, h];

    const RENDER = () => {
      try { PIXI.Ticker.shared.update(); } catch (e) { }
      try { app.ticker.update(); } catch (e) { }
      try { PV.model.update(1 / 30); } catch (e) { }
      try { PV.model.internalModel.update(1 / 30, performance.now()); } catch (e) { }
      app.renderer.render(app.stage);
      const buf = new Uint8Array(w * h * 4);
      gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf);
      return buf;
    };

    const pt = PV.pt, cm = PV.cm;
    const orig = [];
    for (let i = 0; i < pt.count; i++) orig.push(pt.opacities[i]);
    // 全部隐藏
    for (let i = 0; i < pt.count; i++) { try { cm.setPartOpacityByIndex(i, 0); } catch (e) { } }

    const statFrame = (buf) => {
      let n = 0, gray = 0;
      let minx = w, maxx = -1, miny = h, maxy = -1;   // y 顶部起算
      for (let y = 0; y < h; y++) {
        const row = (h - 1 - y) * w;
        for (let x = 0; x < w; x++) {
          const i = (row + x) * 4;
          if (buf[i + 3] > 8) {
            n++;
            const r = buf[i], g = buf[i + 1], b = buf[i + 2];
            if (Math.abs(r - g) < 24 && Math.abs(g - b) < 24 && 40 < (r + g + b) / 3 < 235) gray++;
            if (x < minx) minx = x; if (x > maxx) maxx = x;
            if (y < miny) miny = y; if (y > maxy) maxy = y;
          }
        }
      }
      return { n: n, gray: gray, bbox: [minx, miny, maxx, maxy] };
    };

    const parts = [];
    for (let p = 0; p < pt.count; p++) {
      try { cm.setPartOpacityByIndex(p, orig[p] === undefined ? 1 : orig[p]); } catch (e) { }
      const buf = RENDER();
      const st = statFrame(buf);
      st.part = p; st.partId = pt.ids[p];
      parts.push(st);
      try { cm.setPartOpacityByIndex(p, 0); } catch (e) { }
    }
    // 恢复
    for (let i = 0; i < pt.count; i++) { try { cm.setPartOpacityByIndex(i, orig[i] === undefined ? 1 : orig[i]); } catch (e) { } }
    O.parts = parts;
  } catch (e) {
    O.errs.push("驱动异常: " + (e && e.message ? e.message : String(e)));
  }
  return O;
})()
