/* 逐部件隐藏定位水印（后台可用）：
   基准帧 → 逐部件 hide → ticker.update()×2 → render → readPixels →
   统计「文字区」内 alpha 掉落像素数 → 恢复。
   只测量；断言在 Python 侧。文字区由 Python 注入（渲染像素比例坐标）。 */
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
      // ⚠ 模型 autoUpdate 挂在 Ticker.shared（motionManager 读 shared.lastTime），
      //   hidden 页面 rAF 不触发 → 必须手动双 ticker + 直调 internalModel.update 兜底
      try { PIXI.Ticker.shared.update(); } catch (e) { }
      try { app.ticker.update(); } catch (e) { }
      try { PV.model.update(1 / 30); } catch (e) { }
      try { PV.model.internalModel.update(1 / 30, performance.now()); } catch (e) { }
      app.renderer.render(app.stage);
      const buf = new Uint8Array(w * h * 4);
      gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf);
      return buf;
    };

    // 文字区（比例坐标，y 自顶部）→ 像素框
    const bx = { u0: 0.40, u1: 0.62, vt0: 0.12, vt1: 0.52 };
    const px0 = Math.floor(bx.u0 * w), px1 = Math.ceil(bx.u1 * w);
    const py0 = Math.floor(bx.vt0 * h), py1 = Math.ceil(bx.vt1 * h);   // 顶部起算
    O.boxPx = { x0: px0, x1: px1, yTop0: py0, yTop1: py1, w: w, h: h };

    const diffInBox = (A, B) => {
      let changed = 0, alphaLost = 0;
      for (let y = py0; y < Math.min(py1, h); y++) {
        const row = (h - 1 - y) * w;            // readPixels 原点在左下 → 翻到顶部起算
        for (let x = px0; x < Math.min(px1, w); x++) {
          const i = (row + x) * 4 + 3;
          const a0 = A[i], a1 = B[i];
          if (Math.abs(a0 - a1) > 24) { changed++; if (a1 < a0) alphaLost++; }
        }
      }
      return { changed: changed, lost: alphaLost };
    };

    const base = RENDER();
    O.baseCovered = (() => { let n = 0; for (let k = 3; k < base.length; k += 4) if (base[k] > 8) n++; return +(n / (w * h)).toFixed(4); })();

    const pt = PV.pt, results = [];
    const orig = [];
    for (let i = 0; i < pt.count; i++) orig.push(pt.opacities[i]);
    for (let p = 0; p < pt.count; p++) {
      try { PV.cm.setPartOpacityByIndex(p, 0); } catch (e) { }
      const f = RENDER();
      try { PV.cm.setPartOpacityByIndex(p, orig[p] === undefined ? 1 : orig[p]); } catch (e) { }
      const d = diffInBox(base, f);
      if (d.changed > 0) {
        // 该部件包含的 drawable（隐藏后不可见的）
        const inv = [];
        for (let dd = 0; dd < PV.dr.count; dd++) {
          const v = PV.dr.dynamicFlagIsVisible ? PV.dr.dynamicFlagIsVisible[dd] : null;
        }
        results.push({ part: p, partId: pt.ids[p], changed: d.changed, lost: d.lost });
      }
    }
    // 重排一次拿「命中部件包含的 drawable」：对 top 命中部件重新隐藏并记录不可见 drawable
    results.sort((a, b) => b.changed - a.changed);
    const top = results.filter(r => r.changed > 20).slice(0, 4);
    for (const t of top) {
      const pi = PV.pt.ids.indexOf(t.partId);
      try { PV.cm.setPartOpacityByIndex(pi, 0); } catch (e) { }
      app.ticker.update(); app.ticker.update();
      app.renderer.render(app.stage);
      const vis = [];
      for (let dd = 0; dd < PV.dr.count; dd++) {
        const v = PV.dr.dynamicFlagIsVisible ? PV.dr.dynamicFlagIsVisible[dd] : true;
        if (!v) vis.push(dd);
      }
      t.drawablesHidden = vis;
      try { PV.cm.setPartOpacityByIndex(pi, orig[pi] === undefined ? 1 : orig[pi]); } catch (e) { }
      app.ticker.update();
    }
    O.results = results.sort((a, b) => b.changed - a.changed).slice(0, 12);
    O.top = top;
    O.partIds = Array.from(pt.ids);
  } catch (e) {
    O.errs.push("驱动异常: " + (e && e.message ? e.message : String(e)));
  }
  return O;
})()
