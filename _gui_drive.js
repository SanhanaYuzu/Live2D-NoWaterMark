/* GUI（打包 exe 内 WebView2）专用驱动。
   与浏览器 E2E 的驱动不同：这里要在真实的 pywebview 宿主里
   ① 通过 pywebview JS 桥绑定模型目录（等价用户点「选择模型文件夹」）
   ② 真实点击切到「预览与编辑」并加载模型
   ③ 用页面自带的「渲染自检」读 GPU/Vulkan 真值（真实 gl.readPixels + unmasked renderer）
   ④ 真实驱动一个参数 / 隐藏一个部件，验证「编辑」在打包环境里也生效
   纪律不变：只测量，不写断言；断言在 Python 侧。 */
(async () => {
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  let rafFallbacks = 0, rafCalls = 0;
  const raf = (ms) => {
    rafCalls++;
    let won = false;
    return Promise.race([
      new Promise(r => requestAnimationFrame(() => { won = true; r(); })),
      sleep(ms || 1200),
    ]).then(() => { if (!won) rafFallbacks++; });
  };
  const waitFor = async (fn, ms) => {
    const t0 = performance.now();
    while (performance.now() - t0 < ms) { if (fn()) return true; await sleep(120); }
    return false;
  };
  const O = { errs: [] };
  try {
    if (typeof PV === "undefined") { O.errs.push("PV 未定义"); return O; }

    /* ---------- 0. 宿主环境（证明这是 exe 里的 WebView2，不是外部浏览器） ---------- */
    O.env = {
      url: location.href.replace(/t=[^&]+/, "t=<token>"),
      origin: location.origin,
      protocol: location.protocol,
      ua: navigator.userAgent,
      isWebView2: /Edg\//.test(navigator.userAgent),
      hasPywebviewBridge: !!(window.pywebview && window.pywebview.api),
      bridgeKeys: (window.pywebview && window.pywebview.api)
        ? Object.keys(window.pywebview.api).slice(0, 40) : [],
      verTag: ($("#verTag") || {}).textContent || "",
      docTitle: document.title,
      vis: document.visibilityState,
      rafWorks: await (async () => { let hit = false;
        await Promise.race([new Promise(r => requestAnimationFrame(() => { hit = true; r(); })),
                            sleep(1000)]); return hit; })(),
    };
    /* ---------- 1. 渲染库真的被引入（v2.4.0 修掉的头号缺陷） ---------- */
    const scripts = $$("script[src]").map(s => s.getAttribute("src"));
    O.libs = {
      scriptSrcs: scripts,
      cubismCore: typeof Live2DCubismCore !== "undefined",
      pixi: typeof PIXI !== "undefined",
      pixiVer: (typeof PIXI !== "undefined" && PIXI.VERSION) || "",
      live2dDisplay: (typeof PIXI !== "undefined" && !!(PIXI.live2d && PIXI.live2d.Live2DModel)),
      pvOk: PV.ok,
      tokenLen: String(PV.token || "").length,
      base: PV.base,
    };
    if (!O.libs.pixi) { O.errs.push("打包后 PIXI 未加载"); return O; }
    O.rafBefore = { calls: rafCalls, fallbacks: rafFallbacks };

    /* ---------- 2. 走真实桥：绑定模型目录（= 用户点「选择模型文件夹」） ---------- */
    const api = window.pywebview.api;
    if (!api) { O.errs.push("无 pywebview 桥"); return O; }
    const fx = "%FIXTURE%";
    // 负向探针：不存在的目录必须被拒绝（证明桥真的在校验，而不是无脑 ok）
    O.setDirNeg = await api.set_dir("Z:/__no_such_dir_zz__");
    O.setDir = await api.set_dir(fx);
    O.previewUrl = typeof api.preview_url === "function" ? await api.preview_url() : null;
    O.state = await (await fetch(PV.base + "/api/state", { headers: { "X-NWM-Token": PV.token } })).json();
    if (!O.state.root) { O.errs.push("set_dir 后 /api/state 仍无 root"); return O; }

    /* ---------- 3. 真实点击切到预览页并加载模型 ---------- */
    const mb = $('.mode[data-mode="preview"]');
    if (!mb) { O.errs.push("找不到预览模式按钮"); return O; }
    mb.click();
    await sleep(150);
    O.modeAfterSwitch = document.body.dataset.mode;
    PV.meta = null;
    if (!PV.loading) pvLoad();
    const loaded = await waitFor(() => !!PV.model, 150000);
    O.loaded = loaded;
    O.tagText = ($("#pvTag") || {}).textContent || "";
    O.hint = ($("#pvHint") || {}).innerText || "";
    if (!loaded) { O.errs.push("模型在 150s 内未加载：tag=" + O.tagText); return O; }

    /* ---------- 4. 元数据 / 裸 core / WebGL 真值 ---------- */
    const m = PV.meta || {};
    O.meta = { model: m.model, moc3: m.moc3, counts: m.counts, ms: m.ms,
               moc3_bytes: m.moc3_bytes, moc3_sig: m.moc3_sig, locate: m.locate,
               url_textures: ((m.urls || {}).textures || []).length };
    O.gpu = {
      rendererType: PV.app.renderer.type,
      isWebGL: !!(PV.app.renderer.gl),
      glVersion: null, glRenderer: null, glVendor: null, maxTex: null,
    };
    try {
      const gl = PV.app.renderer.gl;
      O.gpu.glVersion = gl.getParameter(gl.VERSION);
      const dbg = gl.getExtension("WEBGL_debug_renderer_info");
      O.gpu.glRenderer = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
      O.gpu.glVendor = dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR);
      O.gpu.maxTex = gl.getParameter(gl.MAX_TEXTURE_SIZE);
      O.gpu.isWebGL2 = (typeof WebGL2RenderingContext !== "undefined") && (gl instanceof WebGL2RenderingContext);
    } catch (e) { O.gpu.err = String(e.message); }

    O.stage = { canvasW: PV.app.renderer.screen.width, canvasH: PV.app.renderer.screen.height,
                rectW: Math.round($("#pvStage").getBoundingClientRect().width),
                rectH: Math.round($("#pvStage").getBoundingClientRect().height),
                modelW: PV.baseW, modelH: PV.baseH, scale: PV.model.scale.x,
                fitsW: (PV.baseW * PV.model.scale.x) <= PV.app.renderer.screen.width + 1,
                fitsH: (PV.baseH * PV.model.scale.x) <= PV.app.renderer.screen.height + 1,
                zoomLabel: ($("#pvZoom") || {}).textContent || "" };
    O.pixels0 = pvOpaqueRatio();

    /* ---------- 5. 参数编辑真的驱动画面（打包环境里） ---------- */
    const total = PV.pa.count;
    const drive = [];
    for (const i of [1, Math.floor(total * 0.3), Math.floor(total * 0.7)]) {
      try {
        const before = PV.pa.values[i];
        const base = pvOpaqueRatio();
        PV.cm.setParameterValueByIndex(i, PV.pa.maximumValues[i]);
        await raf(); await raf(); await sleep(80);
        const now = pvOpaqueRatio();
        PV.cm.setParameterValueByIndex(i, before);
        await raf();
        drive.push({ i: i, pid: (PV.pByI[i] || {}).pid, base: base, max: now,
                     moved: Math.abs(now - base) > 1e-5 });
      } catch (e) { drive.push({ i: i, err: String(e.message) }); }
    }
    O.drive = drive;
    O.driveMoved = drive.filter(d => d.moved).length;

    /* ---------- 6. 部件显隐/恢复（v2.4.0 修掉的「隐藏后回不来」） ---------- */
    const partTab = $('.pv-tab[data-t="part"]');
    if (partTab) {
      partTab.click();
      await sleep(200);
      const boxes = $$("#pvList .pv-vis");
      O.partTab = { rows: $$("#pvList .pv-row").length, boxes: boxes.length };
      const bx = boxes.length > 2 ? boxes[2] : boxes[0];
      if (bx) {
        const pIdx = +bx.dataset.p;
        const p0 = +PV.pt.opacities[pIdx].toFixed(4);
        bx.click();
        await sleep(250);
        const hid = +PV.pt.opacities[pIdx].toFixed(4);
        const pxH = pvOpaqueRatio();
        const sa = $("#pvShowAll");
        if (sa) { sa.click(); await sleep(320); }
        O.part = { idx: pIdx, opBefore: p0, opHidden: hid, savedOp0: PV.partOp0[pIdx] !== undefined,
                   opBack: +PV.pt.opacities[pIdx].toFixed(4), pxHid: pxH, pxBack: pvOpaqueRatio(),
                   setSizeAfterShowAll: PV.hideParts.size };
      }
      const pt = $('.pv-tab[data-t="param"]'); if (pt) { pt.click(); await sleep(150); }
    }

    /* ---------- 7. 页面自带「渲染自检」：真实跑一遍并读回结果 ---------- */
    const db = $("#pvDiag");
    if (db) {
      if (db.disabled) {   // 未激活会禁用；直接调用函数拿真值
        O.diagDisabled = true;
        await pvDiag(true);
      } else {
        db.click();
        await waitFor(() => !db.disabled, 60000);
        await sleep(300);
      }
      const dl = $("#pvInfo");
      const rows = [];
      Array.from(dl.querySelectorAll("dt")).forEach(dt => {
        const dd = dt.nextElementSibling;
        rows.push([dt.textContent.trim(), dd ? dd.textContent.trim() : ""]);
      });
      O.diag = { rows: rows, rowCount: rows.length };
    }

    /* ---------- 8. 真实帧率 ---------- */
    const t0 = PV.app.ticker.lastTime || 0;
    const f0 = PV.app.ticker.FPS;
    let cnt = 0;
    const onTick = () => { cnt++; };
    PV.app.ticker.add(onTick);
    await sleep(1500);
    PV.app.ticker.remove(onTick);
    O.fps = { tickerFPS: +PV.app.ticker.FPS.toFixed(1), ticksDuring1p5s: cnt,
              shared: (PIXI.Ticker && PIXI.Ticker.shared) ? +PIXI.Ticker.shared.FPS.toFixed(1) : null };
    O.rafAfter = { calls: rafCalls, fallbacks: rafFallbacks };
  } catch (e) {
    O.errs.push("驱动异常: " + (e && e.message ? e.message : String(e)));
  }
  return O;
})()
