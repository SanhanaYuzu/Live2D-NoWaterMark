/* 整帧渲染探针（后台可用）：手动 render + readPixels，返回 PNG dataURL。
   不依赖 rAF/可见性 —— hidden 页面的 WebGL 上下文照常工作。 */
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
    // 渲染两帧（第二帧保险），紧邻 readPixels（无 preserveDrawingBuffer）
    app.renderer.render(app.stage);
    app.renderer.render(app.stage);
    const buf = new Uint8Array(w * h * 4);
    gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf);
    // WebGL 原点是左下 → 翻转成图像方向
    const cv = document.createElement("canvas");
    cv.width = w; cv.height = h;
    const ctx = cv.getContext("2d");
    const img = ctx.createImageData(w, h);
    for (let y = 0; y < h; y++) {
      const src = (h - 1 - y) * w * 4, dst = y * w * 4;
      for (let x = 0; x < w * 4; x++) img.data[dst + x] = buf[src + x];
    }
    ctx.putImageData(img, 0, 0);
    O.frame = cv.toDataURL("image/png");
    O.size = [w, h];
    O.covered = (() => {   // 不透明像素占比（渲染真有内容的旁证）
      let n = 0, tot = w * h;
      for (let k = 3; k < buf.length; k += 4) if (buf[k] > 8) n++;
      return +(n / tot).toFixed(5);
    })();
    O.modelInfo = { drawables: PV.dr.count, params: PV.pa.count, parts: PV.pt.count };
  } catch (e) {
    O.errs.push("驱动异常: " + (e && e.message ? e.message : String(e)));
  }
  return O;
})()
