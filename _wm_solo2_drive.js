
(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const waitFor = async (fn, ms) => { const t0=performance.now();
    while (performance.now()-t0<ms){ if(fn()) return true; await sleep(150);} return false; };
  const O = { errs: [] };
  try {
    if (typeof PV === "undefined") { O.errs.push("PV 未定义"); return O; }
    if (!PV.model) { document.querySelector('.mode[data-mode="preview"]').click(); }
    if (!await waitFor(() => !!PV.model, 150000)) { O.errs.push("模型未加载"); return O; }
    await sleep(300);
    const app = PV.app, gl = app.renderer.gl;
    const w = app.renderer.width, h = app.renderer.height;
    O.size = [w, h];
    const frame = () => {
      try { PIXI.Ticker.shared.update(); } catch(e){}
      try { app.ticker.update(); } catch(e){}
      try { PV.model.update(1/30); } catch(e){}
      try { PV.model.internalModel.update(1/30, performance.now()); } catch(e){}
      app.renderer.render(app.stage);
      const buf = new Uint8Array(w*h*4);
      gl.readPixels(0,0,w,h,gl.RGBA,gl.UNSIGNED_BYTE,buf);
      return buf;
    };
    const toPNG = (buf) => {
      const cv = document.createElement("canvas"); cv.width=w; cv.height=h;
      const ctx = cv.getContext("2d"); const img = ctx.createImageData(w,h);
      for (let y=0;y<h;y++){ const s=(h-1-y)*w*4, d=y*w*4;
        for (let x=0;x<w*4;x++) img.data[d+x]=buf[s+x]; }
      ctx.putImageData(img,0,0); return cv.toDataURL("image/png");
    };
    const cm = PV.cm, pt = PV.pt;
    const orig = [];
    for (let i=0;i<pt.count;i++) orig.push(pt.opacities[i]);
    for (let i=0;i<pt.count;i++){ try{cm.setPartOpacityByIndex(i,0);}catch(e){} }
    O.emptyFrame = toPNG(frame());            // 全隐藏 → 应为空
    const solo = {};
    for (const p of [6, 15, 11]) {             // 脸组 / 后脑勺组 / 腿组
      try{ cm.setPartOpacityByIndex(p, 1); }catch(e){}
      solo[pt.ids[p]] = toPNG(frame());
      try{ cm.setPartOpacityByIndex(p, 0); }catch(e){}
    }
    O.solo = solo;
    for (let i=0;i<pt.count;i++){ try{cm.setPartOpacityByIndex(i, orig[i]===undefined?1:orig[i]);}catch(e){} }
  } catch (e) { O.errs.push(String(e && e.message || e)); }
  return O;
})()
