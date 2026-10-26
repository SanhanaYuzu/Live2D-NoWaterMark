/* 页面侧驱动（作为 CDP Runtime.evaluate 的 expression 注入）。
   原则：这里只「测量 + 模拟真实用户操作」，不写任何断言 —— 断言全部在 Python 侧，
   保证证据可复核、阈值可调整。所有结论都以原始数值返回。 */
(async () => {
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  // ⚠ rAF 必须带超时兜底 —— 窗口被最小化/遮挡时 Chromium 会挂起渲染，
  //   requestAnimationFrame **永不触发**，裸 `await raf()` 会把整个驱动永久挂起
  //   （第三轮就真的卡死了 5 分钟，靠 CDP 的 evaluate timeout 才救回来）。
  //   降级成定时等待后，驱动会继续跑，然后由像素断言诚实地判失败，而不是无声挂起。
  let rafFallbacks = 0, rafCalls = 0;
  // ⚠ 兜底必须在「谁先落地」上判定。原来写成 sleep(...).then(()=>rafFallbacks++)，
  //   而 sleep 无论胜负都会到点触发 → 计数器必然等于调用次数，指标完全失效
  //   （实测踩过：ticker FPS=61 却报「20/20 全部降级」，还因此改错了阈值）。
  //   这里用 won 标志只在 rAF 真正没赢时才计数。
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
  const step = (k, v) => { O[k] = v; };

  try {
    /* ---------- 0. 页面与预览初始化状态 ---------- */
    if (typeof PV === "undefined") { O.errs.push("PV 未定义（脚本未执行）"); return O; }
    O.visibility = { state: document.visibilityState, hidden: document.hidden,
                     hasFocus: document.hasFocus(),
                     rafWorks: await (async () => { let hit = false;
                       await Promise.race([new Promise(r => requestAnimationFrame(() => { hit = true; r(); })),
                                           sleep(1000)]); return hit; })() };
    O.url = location.href.replace(/t=[^&]+/, "t=<token>");
    O.proto = location.protocol;
    O.pvOk = PV.ok;
    O.tokenLen = String(PV.token || "").length;
    O.base = PV.base;
    O.paneDisplayClean = getComputedStyle($("#panePreview")).display;
    O.modeClean = document.body.dataset.mode || "";
    O.verTag = ($("#verTag") || {}).textContent || "";
    O.wmKeysAligned = (typeof WM_KEYS !== "undefined" && WM_KEYS.indexOf("watermark") >= 0);
    O.docTitle = document.title;

    /* ---------- 1. 从「去水印」切到「预览与编辑」（真实点击） ---------- */
    const mb = $('.mode[data-mode="preview"]');
    if (!mb) { O.errs.push("找不到预览模式按钮"); return O; }
    mb.click();
    await sleep(120);
    O.modeAfterSwitch = document.body.dataset.mode;
    O.paneDisplayPreview = getComputedStyle($("#panePreview")).display;
    O.modeBtnOn = mb.classList.contains("on");

    const loaded = await waitFor(() => !!PV.model, 150000);
    O.loaded = loaded;
    O.loadingFlag = PV.loading;
    O.hintHtml = ($("#pvHint") || {}).innerText || "";
    O.tagText = ($("#pvTag") || {}).textContent || "";
    if (!loaded) { O.errs.push("模型在 150s 内未加载完成"); return O; }

    /* ---------- 2. 元数据 / 裸 core 数据面（与 /api/meta 对照的原始值） ---------- */
    const m = PV.meta;
    O.meta = {
      model: m.model, moc3: m.moc3, cdi3: m.cdi3, anchored: m.anchored, locate: m.locate,
      counts: m.counts, ms: m.ms, moc3_bytes: m.moc3_bytes, moc3_sig: m.moc3_sig,
      root_has_abs: typeof m.root === "string" && m.root.indexOf(":") >= 0,   // root 允许是绝对路径
      moc3_is_abs: typeof m.moc3 === "string" && m.moc3.indexOf(":") >= 0,    // moc3 必须只是相对路径
      url_count: (m.urls.textures || []).length,
      url_moc3: m.urls.moc3, url_model3: m.urls.model3,
    };
    O.core = {
      paCount: PV.pa.count, ptCount: PV.pt.count, drCount: PV.dr.count,
      paIds0: Array.from(PV.pa.ids).slice(0, 4),
      ptIds0: Array.from(PV.pt.ids).slice(0, 4),
      drTex: Array.from(PV.dr.textureIndices).slice(0, 16),
      paTypes: Array.from(PV.pa.types).slice(0, 4),
      canvas: { w: PV.raw.canvasinfo.CanvasWidth, h: PV.raw.canvasinfo.CanvasHeight,
                ppu: PV.ppu, ox: PV.ox, oy: PV.oy },
      hasIdxMethods: (typeof PV.cm.getParameterValueByIndex === "function"),
      rawHasNoGetParam: (typeof PV.raw.getParameterCount === "undefined"),
    };
    O.stage = {
      canvasW: PV.app.renderer.screen.width, canvasH: PV.app.renderer.screen.height,
      res: PV.app.renderer.resolution,
      ovW: PV.ov.width, ovH: PV.ov.height,
      rectW: Math.round($("#pvStage").getBoundingClientRect().width),
      rectH: Math.round($("#pvStage").getBoundingClientRect().height),
      modelW: PV.baseW, modelH: PV.baseH, scale: PV.model.scale.x,
      zoomLabel: ($("#pvZoom") || {}).textContent || "",
      rendererType: PV.app.renderer.type,
      tickerStarted: PV.app.ticker.started,
      maxFPS: PV.app.ticker.maxFPS,
    };
    O.countsText = ($("#pvCounts") || {}).textContent || "";
    O.loadMs = PV.loadMs;
    O.logTail = ($$("#log > *").slice(-6)).map(e => e.innerText || "");

    /* ---------- 3. 参数列表 / 滑块接线（曾漏绑事件的地方） ---------- */
    O.paramTab = {
      rows: $$("#pvList .pv-row").length,
      sliders: $$("#pvList .pv-rng").length,
      labels: $$("#pvList .vl").length,
      foot: ($("#pvFoot") || {}).innerText || "",
      writeDisabled: !!($("#pvWrite") && $("#pvWrite").disabled),
      resetDisabled: !!($("#pvResetAll") && $("#pvResetAll").disabled),
    };

    /* ---------- 4. 参数驱动自检（6 个抽样参数，看画面像素是否真的变） ---------- */
    const total = PV.pa.count;
    const picks = [1, Math.floor(total * 0.2), Math.floor(total * 0.4),
                   Math.floor(total * 0.6), Math.floor(total * 0.8), total - 1];
    O.pixels0 = pvOpaqueRatio();
    const drive = [];
    for (const i of picks) {
      try {
        const p = PV.pByI[i];
        const before = PV.pa.values[i];
        const base = pvOpaqueRatio();
        PV.cm.setParameterValueByIndex(i, PV.pa.maximumValues[i]);
        await raf();
        const now = pvOpaqueRatio();
        PV.cm.setParameterValueByIndex(i, before);
        await raf();
        drive.push({ i, pid: p ? p.pid : "?", before: +before.toFixed(4),
                     max: +PV.pa.maximumValues[i].toFixed(4),
                     pixBase: base, pixMax: now,
                     moved: Math.abs(now - base) > 1e-5 });
      } catch (e) { drive.push({ i, err: String(e.message) }); }
    }
    O.drive = drive;
    O.driveMoved = drive.filter(d => d.moved).length;

    /* ---------- 5. 用 UI 滑块真的拖一个「能改画面」的参数 ---------- */
    const cand = drive.filter(d => d.moved && d.pid !== "?" && PV.pByI[d.i]
                                  && (PV.pByI[d.i].max - PV.pByI[d.i].def) > 1e-3);
    O.sliderPick = cand.length ? cand[0].i : null;
    if (O.sliderPick !== null) {
      const i = O.sliderPick, p = PV.pByI[i];
      const row = $('#pvList .pv-row[data-i="' + i + '"]');
      const rng = row && row.querySelector(".pv-rng");
      O.sliderRowFound = !!rng;
      if (rng) {
        O.sliderBefore = {
          core: +PV.cm.getParameterValueByIndex(i).toFixed(5),
          px: pvOpaqueRatio(),
          label: (row.querySelector(".vl") || {}).textContent,
          edits: PV.edits.size,
        };
        rng.value = String(p.max);
        rng.dispatchEvent(new Event("input", { bubbles: true }));
        rng.dispatchEvent(new Event("change", { bubbles: true }));
        await raf(); await raf();
        O.sliderAfter = {
          core: +PV.cm.getParameterValueByIndex(i).toFixed(5),
          px: pvOpaqueRatio(),
          label: (row.querySelector(".vl") || {}).textContent,
          edits: PV.edits.size,
          hasEdit: PV.edits.has(i),
          editVal: PV.edits.has(i) ? +PV.edits.get(i).toFixed(5) : null,
          footHtml: ($("#pvEditCount") || {}).textContent || "",
          writeDisabled: !!($("#pvWrite") && $("#pvWrite").disabled),
        };
      }
    }

    /* ---------- 6. 参数行点选（sel 高亮） ---------- */
    if (O.sliderPick !== null) {
      const row = $('#pvList .pv-row[data-i="' + O.sliderPick + '"]');
      if (row) {
        row.click();
        await sleep(80);
        O.paramSel = { kind: PV.sel && PV.sel.kind, i: PV.sel && PV.sel.i,
                       rowSel: !!$("#pvList .pv-row.sel") };
      }
    }

    /* ---------- 7. 部件树：勾选框 / 隔离 / 恢复（含 opacities 与像素双证据） ---------- */
    const partTabBtn = $('.pv-tab[data-t="part"]');
    O.partPixels0 = pvOpaqueRatio();
    if (partTabBtn) {
      partTabBtn.click();
      await sleep(120);
      const boxes = $$("#pvList .pv-vis");
      O.partTab = { rows: $$("#pvList .pv-row").length, boxes: boxes.length,
                    tabOn: partTabBtn.classList.contains("on"),
                    foot: ($("#pvFoot") || {}).innerText || "" };
      const pi = boxes.length > 3 ? 3 : 0;
      if (boxes[pi]) {
        const pIdx = +boxes[pi].dataset.p;
        O.partHide = { idx: pIdx, opBefore: +PV.pt.opacities[pIdx].toFixed(4) };
        boxes[pi].click();                       // 真实激活：取消勾选 = 隐藏
        await sleep(250);
        O.partHide.inSet = PV.hideParts.has(pIdx);
        O.partHide.opAfter = +PV.pt.opacities[pIdx].toFixed(4);
        O.partHide.pxHid = pvOpaqueRatio();
        O.partHide.savedOp0 = PV.partOp0[pIdx] !== undefined ? +PV.partOp0[pIdx].toFixed(4) : null;
        O.partHide.count = ($("#pvHideCount") || {}).textContent;
        O.partHide.rowLabel = (boxes[pi].closest(".pv-row").querySelector(".vl") || {}).textContent;
        // 隔离：点行
        const row = boxes[pi].closest(".pv-row");
        row.click();
        await sleep(300);
        O.partIso = { setSize: PV.hideParts.size, ptCount: PV.pt.count,
                      targetHidden: PV.hideParts.has(pIdx),
                      othersHidden: PV.hideParts.size === PV.pt.count - 1,
                      pxIso: pvOpaqueRatio() };
        // 恢复：全部显示
        const sa = $("#pvShowAll");
        if (sa) { sa.click(); await sleep(320); }
        O.partShowAll = { setSize: PV.hideParts.size,
                          opBack: +PV.pt.opacities[pIdx].toFixed(4),
                          pxBack: pvOpaqueRatio(),
                          count: ($("#pvHideCount") || {}).textContent };
      }
    }

    /* ---------- 8. 网格页：点选 + 红色线框真的画到 overlay 上 ---------- */
    const meshTabBtn = $('.pv-tab[data-t="mesh"]');
    if (meshTabBtn) {
      meshTabBtn.click();
      await sleep(120);
      const rows = $$("#pvList .pv-row");
      O.meshTab = { rows: rows.length, foot: ($("#pvFoot") || {}).innerText || "" };
      // 选一个顶点数足够、且贴图编号明确的网格
      let pickRow = null;
      for (const r of rows) {
        const d = +r.dataset.m;
        if (PV.dr.vertexCounts[d] >= 6) { pickRow = r; break; }
      }
      if (!pickRow) pickRow = rows[0];
      if (pickRow) {
        const d = +pickRow.dataset.m;
        const ctx0 = PV.ovctx || (PV.ovctx = PV.ov.getContext("2d"));
        ctx0.clearRect(0, 0, PV.ov.width, PV.ov.height);
        O.overlayBeforeBlank = true;
        pickRow.click();
        await raf(); await raf(); await sleep(120);
        const pos = PV.dr.vertexPositions[d], idx = PV.dr.indices[d];
        const pts = [];
        let nan = 0, inside = 0;
        const w = PV.app.renderer.screen.width, h = PV.app.renderer.screen.height;
        for (let k = 0; k < pos.length / 2; k++) {
          const g = pvProject(pos[k * 2], pos[k * 2 + 1]);
          if (!isFinite(g[0]) || !isFinite(g[1])) nan++;
          else { pts.push([+g[0].toFixed(1), +g[1].toFixed(1)]);
                 if (g[0] >= 0 && g[0] <= w && g[1] >= 0 && g[1] <= h) inside++; }
        }
        const img = ctx0.getImageData(0, 0, PV.ov.width, PV.ov.height).data;
        let red = 0, any = 0;
        for (let k = 0; k < img.length; k += 4) {
          if (img[k + 3] > 0) { any++; if (img[k] > 150 && img[k + 1] < 140) red++; }
        }
        O.mesh = {
          d: d, verts: pos.length / 2, tris: idx ? idx.length / 3 : 0,
          nanPts: nan, insidePts: inside, samplePts: pts.slice(0, 5),
          ovAny: any, ovRed: red, ovPx: PV.ov.width * PV.ov.height,
          sel: PV.sel && PV.sel.kind === "mesh" ? PV.sel.i : null,
          footHasIso: !!$("#pvIsoPart"),
        };
        // 关掉开关后线框应消失（负向对照）
        const cb = $("#pvOvOn");
        if (cb) {
          cb.checked = false; cb.onchange();
          await raf(); await raf(); await sleep(100);
          const img2 = ctx0.getImageData(0, 0, PV.ov.width, PV.ov.height).data;
          let any2 = 0;
          for (let k = 3; k < img2.length; k += 4) if (img2[k] > 0) any2++;
          O.mesh.ovAnyAfterToggleOff = any2;
          cb.checked = true; cb.onchange();
          await raf(); await raf();
        }
        // 隔离所属部件（真实按钮）
        const iso = $("#pvIsoPart");
        if (iso) {
          iso.click(); await sleep(250);
          O.meshIso = { tab: PV.tab, setSize: PV.hideParts.size, ptCount: PV.pt.count };
          const sa2 = $("#pvShowAll");
          if (sa2) { sa2.click(); await sleep(200); }
        }
      }
    }

    /* ---------- 9. 贴图页：缩略图 + UV 高亮 ---------- */
    const texTabBtn = $('.pv-tab[data-t="tex"]');
    if (texTabBtn) {
      // 先回到网格页确保「有且仅有一个网格被选中」，再切贴图页验证高亮跟随。
      // ⚠ 不能无脑点第一行：网格行的语义是「再点一次取消选中」，
      //   若第 8 步已选中同一行，再点一次会得到 sel=null（第一轮就因此误报 4 条 FAIL）。
      if (meshTabBtn) {
        meshTabBtn.click(); await sleep(100);
        const rows = $$("#pvList .pv-row");
        const keep = PV.sel && PV.sel.kind === "mesh" ? PV.sel.i : null;
        const target = rows.find(r => +r.dataset.m !== keep && PV.dr.vertexCounts[+r.dataset.m] >= 6)
                    || rows.find(r => +r.dataset.m !== keep) || rows[0];
        if (target) { target.click(); await sleep(200); }
        O.meshPickBeforeTex = { d: +target.dataset.m, sel: PV.sel ? PV.sel.i : null };
      }
      texTabBtn.click();
      await sleep(1200);   // 等贴图加载
      const imgs = $$("#pvList img[data-texk]");
      const sizes = $$("#pvList [data-texsize]").map(e => e.textContent);
      let polyTot = 0, polySvgs = 0, uvMin = null, uvMax = null, polyBox = null;
      (PV.texSvg || []).forEach(s => {
        if (!s) return;
        const n = s.querySelectorAll("polygon").length;
        polyTot += n; if (n) polySvgs++;
      });
      // UV 必须落在 0..1（否则 polygon 会被 viewBox 裁掉，看起来「有元素但看不见」）
      const dSel = PV.sel && PV.sel.kind === "mesh" ? PV.sel.i : null;
      if (dSel !== null) {
        const uvs = PV.dr.vertexUvs[dSel];
        if (uvs && uvs.length) {
          uvMin = Infinity; uvMax = -Infinity;
          for (let k = 0; k < uvs.length; k++) { if (uvs[k] < uvMin) uvMin = uvs[k]; if (uvs[k] > uvMax) uvMax = uvs[k]; }
          uvMin = +uvMin.toFixed(4); uvMax = +uvMax.toFixed(4);
        }
        const ti = PV.dr.textureIndices[dSel];
        const svg = (PV.texSvg || [])[ti];
        const pg = svg && svg.querySelector("polygon");
        if (pg) { const b = pg.getBoundingClientRect();
                  polyBox = [Math.round(b.width), Math.round(b.height)]; }
      }
      O.tex = {
        items: $$("#pvList .pv-texitem").length,
        imgs: imgs.length,
        natural: imgs.map(i => i.naturalWidth + "x" + i.naturalHeight),
        complete: imgs.map(i => i.complete),
        sizes: sizes,
        metaTex: PV.meta.counts.textures,
        polyTot: polyTot, polySvgs: polySvgs,
        uvMin: uvMin, uvMax: uvMax, polyBox: polyBox,
        selKeptAcrossTab: PV.sel ? PV.sel.i : null,
        svgSized: (PV.texSvg || []).filter(s => s && s.getBoundingClientRect().width > 10).length,
        foot: ($("#pvFoot") || {}).innerText || "",
        wmOnlyDisabled: !!($("#pvWmOnly") && $("#pvWmOnly").disabled),
      };
    }

    /* ---------- 10. 动作 / 表情：真实时钟下是否真的改变参数 ---------- */
    const mBtns = $$("#pvMotions button");
    O.motionBtns = { total: mBtns.length, labels: mBtns.slice(0, 8).map(b => b.textContent) };
    const snap = () => Array.from(PV.pa.values);
    const diffCount = (a, b) => { let n = 0; for (let i = 0; i < a.length; i++) if (Math.abs(a[i] - b[i]) > 1e-4) n++; return n; };
    const motionBtn = $$("#pvMotions [data-m]")[0] || mBtns[0];
    if (motionBtn) {
      const a = snap();
      motionBtn.click();
      await sleep(900);
      const b = snap();
      O.motion = { label: motionBtn.textContent, changed: diffCount(a, b),
                   changedIdx: (() => { const o = []; for (let i = 0; i < a.length && o.length < 8; i++) if (Math.abs(a[i]-b[i]) > 1e-4) o.push([PV.pa.ids[i], +a[i].toFixed(3), +b[i].toFixed(3)]); return o; })() };
    }
    const eBtn = $$("#pvMotions [data-exp]")[0];
    if (eBtn) {
      const a = snap();
      eBtn.click();
      await sleep(700);
      const b = snap();
      O.expression = { label: eBtn.textContent, changed: diffCount(a, b),
                       cls: eBtn.className };
    }

    /* ---------- 11. 暂停 / 继续（真实按钮） ---------- */
    const pb = $("#pvPause");
    if (pb) {
      pb.click(); await sleep(80);
      O.pause = { started: PV.app.ticker.started, text: pb.textContent, flag: PV.paused };
      pb.click(); await sleep(80);
      O.pause.startedBack = PV.app.ticker.started;
      O.pause.textBack = pb.textContent;
    }

    /* ---------- 12. 缩放 / 适应 ---------- */
    O.zoom = { label: ($("#pvZoom") || {}).textContent, scaleBefore: +PV.model.scale.x.toFixed(5),
               fitSBefore: +PV.fitS.toFixed(5), userZoomBefore: !!PV.userZoom,
               screen: [PV.app.renderer.screen.width, PV.app.renderer.screen.height] };
    $("#pvStage").dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
    await sleep(200);
    // ⚠ fitS 必须在双击**之后**读 —— 它会被 pvFit() 改写，读成双击前的值会得出错误结论
    O.zoom.scaleAfterDbl = +PV.model.scale.x.toFixed(5);
    O.zoom.fitSAfter = +PV.fitS.toFixed(5);
    O.zoom.userZoomAfter = !!PV.userZoom;
    O.zoom.labelAfter = ($("#pvZoom") || {}).textContent;
    O.zoom.fitsInBox = (PV.baseH * PV.model.scale.x) <= PV.app.renderer.screen.height + 0.5;
    // 用户手动滚轮缩放后，resize 不应再自动适应（负向对照）
    const st8 = $("#pvStage");
    const r8 = st8.getBoundingClientRect();
    st8.dispatchEvent(new WheelEvent("wheel", { deltaY: -120, bubbles: true, cancelable: true,
                                                clientX: r8.left + r8.width/2,
                                                clientY: r8.top + r8.height/2 }));
    await sleep(120);
    O.zoom.afterWheel = { scale: +PV.model.scale.x.toFixed(5), userZoom: !!PV.userZoom,
                          label: ($("#pvZoom") || {}).textContent };
    const ff = $("#pvFit");
    if (ff) { ff.click(); await sleep(180); }
    O.zoom.afterFitBtn = { scale: +PV.model.scale.x.toFixed(5), fitS: +PV.fitS.toFixed(5),
                           userZoom: !!PV.userZoom, label: ($("#pvZoom") || {}).textContent };

    /* ---------- 13. 渲染自检面板（真实按钮；自检是异步的，等按钮恢复） ---------- */
    const db = $("#pvDiag");
    if (db) {
      db.click();
      await waitFor(() => db.textContent !== "自检中…" && db.disabled === false, 30000);
      await sleep(200);
      const dl = $("#pvInfo");
      O.diag = { dtCount: dl.querySelectorAll("dt").length,
                 btnText: db.textContent,
                 rows: Array.from(dl.querySelectorAll("dt")).map((dt, k) => [
                   dt.textContent, dl.querySelectorAll("dd")[k].textContent]) };
    }

    /* ---------- 14. 真实帧率（预览是否流畅的硬指标） ---------- */
    await sleep(1800);
    O.fps = {
      ticker: PV.app.ticker.FPS !== undefined ? +PV.app.ticker.FPS.toFixed(1) : null,
      shared: (window.PIXI && PIXI.Ticker && PIXI.Ticker.shared)
              ? +PIXI.Ticker.shared.FPS.toFixed(1) : null,
      maxFPS: PV.app.ticker.maxFPS,
      screen: [Math.round(PV.app.renderer.screen.width), Math.round(PV.app.renderer.screen.height)],
      textures: PV.meta.counts.textures,
    };

    /* ---------- 15. 搜索过滤（真实输入） ---------- */
    if (texTabBtn) { $('.pv-tab[data-t="param"]').click(); await sleep(100); }
    const sb = $("#pvSearch");
    if (sb) {
      const all = $$("#pvList .pv-row").length;
      sb.value = "ParamEyeLOpen";
      sb.dispatchEvent(new Event("input", { bubbles: true }));
      await sleep(400);
      O.search = { all: all, filtered: $$("#pvList .pv-row").length };
      sb.value = "";
      sb.dispatchEvent(new Event("input", { bubbles: true }));
      await sleep(400);
      O.search.back = $$("#pvList .pv-row").length;
    }
    // 「只看水印」：与元数据命中数做结构性对照（不要预设「本模型命中 0」）
    const wb = $("#pvWmOnly");
    if (wb) {
      wb.click(); await sleep(400);
      O.wmOnly = { on: PV.wmOnly, rows: $$("#pvList .pv-row").length,
                   wmParamCount: PV.meta.counts.wm_params, label: wb.textContent,
                   hits: (PV.meta.params || []).filter(p => p.wm).slice(0, 6)
                           .map(p => p.pid + "=" + (p.name || "")) };
      wb.click(); await sleep(400);
      O.wmOnly.rowsBack = $$("#pvList .pv-row").length;
    }
    // 负向对照：搜一个绝不存在的串 → 0 行 + 空态提示
    if (sb) {
      sb.value = "__绝不存在的参数zzz__";
      sb.dispatchEvent(new Event("input", { bubbles: true }));
      await sleep(400);
      O.searchNone = { rows: $$("#pvList .pv-row").length,
                       hasEmpty: !!$("#pvList .pv-empty"),
                       emptyText: (($("#pvList .pv-empty") || {}).innerText || "").slice(0, 60) };
      sb.value = "";
      sb.dispatchEvent(new Event("input", { bubbles: true }));
      await sleep(400);
    }

    /* ---------- 15. 无 token 的 API 访问（页面侧负向对照） ---------- */
    try {
      const r = await fetch(PV.base + "/api/meta");
      O.apiNoToken = { status: r.status, ok: r.ok, body: (await r.text()).slice(0, 80) };
    } catch (e) { O.apiNoToken = { threw: String(e.message) }; }
    try {
      const r2 = await fetch(PV.base + "/api/backups", { headers: { "X-NWM-Token": PV.token } });
      const j2 = await r2.json();
      O.backupsBefore = { status: r2.status, n: (j2.backups || []).length,
                          names: (j2.backups || []).map(b => b.name) };
    } catch (e) { O.backupsBefore = { threw: String(e.message) }; }

    /* ---------- 16. 写入路径：先测「取消」不落盘，再测真实写入 ---------- */
    // 16a 取消
    const editsBefore = PV.edits.size;
    const sigBefore = PV.meta.moc3_sig;
    const wallA = Date.now();
    $("#pvWrite").click();
    await sleep(200);
    O.writeModal = { exists: !!$(".mask .modal"),
                     okText: (($(".mask .modal [data-ok]") || {}).textContent || ""),
                     bodyHasMoc3: (($(".mask .modal p") || {}).innerText || "").indexOf(PV.meta.moc3) >= 0,
                     bodyLen: (($(".mask .modal p") || {}).innerText || "").length };
    const cancelBtn = $(".mask .modal [data-x]");
    if (cancelBtn) { cancelBtn.click(); await sleep(200); }
    O.writeCancel = { modalGone: !$(".mask .modal"), editsKept: PV.edits.size === editsBefore,
                      sigSame: PV.meta.moc3_sig === sigBefore, ms: Date.now() - wallA };

    // 16b 真实写入
    const item = [];
    PV.edits.forEach((v, i) => { const p = PV.pByI[i]; if (p) item.push({ pid: p.pid, value: v }); });
    O.writeRequest = { n: item.length, first: item[0] || null };
    $("#pvWrite").click();
    await sleep(250);
    const okBtn = $(".mask .modal [data-ok]");
    const wallB = Date.now();
    if (okBtn) okBtn.click();
    const done = await waitFor(() => !$(".mask .modal") || PV.edits.size === 0, 60000);
    O.writeDone = done;
    O.writeWaitMs = Date.now() - wallB;
    await sleep(400);
    O.writeAfter = {
      edits: PV.edits.size,
      sigBefore: sigBefore,
      sigAfter: PV.meta.moc3_sig,
      sigChanged: PV.meta.moc3_sig !== sigBefore,
      modalGone: !$(".mask .modal"),
      logTail: $$("#log > *").slice(-8).map(e => e.innerText || ""),
      countsText: ($("#pvCounts") || {}).textContent || "",
    };
    try {
      const r3 = await fetch(PV.base + "/api/backups", { headers: { "X-NWM-Token": PV.token } });
      const j3 = await r3.json();
      O.backupsAfter = { n: (j3.backups || []).length, names: (j3.backups || []).map(b => b.name) };
    } catch (e) { O.backupsAfter = { threw: String(e.message) }; }

    /* ---------- 17. 撤销改动按钮（断电保护：无改动时应无副作用） ---------- */
    const rb = $("#pvResetAll");
    if (rb) {
      rb.click(); await sleep(200);
      O.resetAfterWrite = { edits: PV.edits.size, px: pvOpaqueRatio() };
    }

    /* ---------- 18. 收尾摆回「网格页 + 红色线框」状态，供截图取证 ---------- */
    if (meshTabBtn) {
      meshTabBtn.click(); await sleep(150);
      const r9 = $$("#pvList .pv-row").filter(r => PV.dr.vertexCounts[+r.dataset.m] >= 6)[0]
              || $$("#pvList .pv-row")[0];
      if (r9) { r9.click(); await sleep(200); }
      O.finalTab = PV.tab;
    }

    O.finalErrs = O.errs;
    O.rafFallbacks = rafFallbacks;
    O.rafCalls = rafCalls;
    O.visibilityEnd = { state: document.visibilityState, hasFocus: document.hasFocus() };
    return O;
  } catch (e) {
    O.fatal = String(e && e.message || e);
    O.fatalStack = String(e && e.stack || "").slice(0, 900);
    O.errs.push(O.fatal);
    return O;
  }
})()
