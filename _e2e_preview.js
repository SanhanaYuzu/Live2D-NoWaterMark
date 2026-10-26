/* CDP 运行器：把驱动脚本注入真实页面（Edge 或 pywebview 的 WebView2），
   回收原始测量值 + 页面报错 + 截图。
   用法: node _e2e_preview.js <debugPort> <outJson> <shotDir> [hostFilter] [driverFile]
   输出: 末行 RESULT_JSON <一行 JSON>；日志走 stdout。 */
const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = +(process.argv[2] || 9225);
const OUT = process.argv[3] || "_e2e_result.json";
const SHOTS = process.argv[4] || "shots";

function getJSON(url) {
  return new Promise((res, rej) => {
    http.get(url, (r) => { let d = ""; r.on("data", c => d += c); r.on("end", () => { try { res(JSON.parse(d)); } catch (e) { rej(e); } }); }).on("error", rej);
  });
}

class WS {
  constructor(url) { this.url = url; this.id = 0; this.pending = new Map(); this.onEvent = () => {}; }
  connect() {
    return new Promise((res, rej) => {
      const u = new URL(this.url);
      const req = http.request({
        host: u.hostname, port: u.port, path: u.pathname + u.search,
        headers: { Connection: "Upgrade", Upgrade: "websocket",
          "Sec-WebSocket-Key": Buffer.from(Math.random().toString()).toString("base64"),
          "Sec-WebSocket-Version": "13" } });
      req.on("upgrade", (r, socket) => {
        this.socket = socket;
        let buf = Buffer.alloc(0);
        socket.on("data", (c) => {
          buf = Buffer.concat([buf, c]);
          for (;;) {
            if (buf.length < 2) break;
            const l0 = buf[1] & 0x7f; let off = 2, len = l0;
            if (l0 === 126) { if (buf.length < 4) break; len = buf.readUInt16BE(2); off = 4; }
            else if (l0 === 127) { if (buf.length < 10) break; len = Number(buf.readBigUInt64BE(2)); off = 10; }
            if (buf.length < off + len) break;
            const p = buf.slice(off, off + len); buf = buf.slice(off + len);
            try {
              const m = JSON.parse(p.toString("utf8"));
              if (m.id && this.pending.has(m.id)) {
                const { res: R, rej: J } = this.pending.get(m.id);
                this.pending.delete(m.id); m.error ? J(new Error(JSON.stringify(m.error))) : R(m.result);
              } else if (m.method) this.onEvent(m.method, m.params || {});
            } catch (e) { }
          }
        });
        res();
      });
      req.on("error", rej); req.end();
    });
  }
  send(method, params) {
    const id = ++this.id;
    const payload = Buffer.from(JSON.stringify({ id, method, params: params || {} }));
    const mask = Buffer.from([0x12, 0x34, 0x56, 0x78]);
    const m = Buffer.from(payload); for (let i = 0; i < m.length; i++) m[i] ^= mask[i % 4];
    let h;
    if (payload.length < 126) h = Buffer.from([0x81, 0x80 | payload.length]);
    else if (payload.length < 65536) { h = Buffer.alloc(4); h[0] = 0x81; h[1] = 0x80 | 126; h.writeUInt16BE(payload.length, 2); }
    else { h = Buffer.alloc(10); h[0] = 0x81; h[1] = 0x80 | 127; h.writeBigUInt64BE(BigInt(payload.length), 2); }
    this.socket.write(Buffer.concat([h, mask, m]));
    return new Promise((R, J) => this.pending.set(id, { res: R, rej: J }));
  }
}

const pageErrs = [];
const pageLogs = [];

function pickPage(list, host) {
  const cands = list.filter(t => t.type === "page" && t.webSocketDebuggerUrl);
  return cands.find(t => (t.url || "").indexOf(host) >= 0) || cands[0];
}

(async () => {
  const host = process.argv[5] || "127.0.0.1";
  let list = [];
  for (let i = 0; i < 40; i++) {           // 等 Edge 起来（不固定 sleep 猜，轮询真实条件）
    try {
      list = await getJSON("http://127.0.0.1:" + PORT + "/json/list");
      if (list.some(t => t.type === "page" && t.webSocketDebuggerUrl)) break;
    } catch (e) { }
    await new Promise(r => setTimeout(r, 400));
  }
  const page = pickPage(list, host);
  if (!page) { console.log("找不到可调试页面"); console.log("RESULT_JSON " + JSON.stringify({ fatal: "no page" })); process.exit(2); }
  console.log("target = " + page.url);

  const ws = new WS(page.webSocketDebuggerUrl);
  await ws.connect();
  ws.onEvent = (method, p) => {
    if (method === "Runtime.exceptionThrown") {
      const d = (p.exceptionDetails || {});
      pageErrs.push(((d.exception && (d.exception.description || d.exception.value)) || d.text || "?") + "");
      console.log("  [page exception] " + ((d.exception && d.exception.description) || d.text || "?"));
    } else if (method === "Runtime.consoleAPICalled") {
      const txt = (p.args || []).map(a => a.value !== undefined ? a.value : (a.description || a.type)).join(" ");
      pageLogs.push(p.type + ": " + txt);
      if (p.type === "error" || p.type === "warning") console.log("  [console " + p.type + "] " + txt.slice(0, 300));
    } else if (method === "Log.entryAdded") {
      const e = p.entry || {};
      if (e.level === "error" || e.level === "warning") {
        pageLogs.push(e.level + ": " + (e.text || ""));
        console.log("  [log " + e.level + "] " + String(e.text || "").slice(0, 300));
      }
    }
  };
  await ws.send("Runtime.enable");
  await ws.send("Page.enable");
  try { await ws.send("Log.enable"); } catch (e) { }

  const evalRaw = (expression, awaitPromise) => ws.send("Runtime.evaluate", {
    expression, awaitPromise: !!awaitPromise, returnByValue: true, userGesture: true,
  });

  // 把测试用的浏览器窗口弄到前台并解除最小化。
  // 踩过的坑：沿用同一个 --user-data-dir 时，Edge 会还原上次的窗口状态（最小化），
  // 此时 document.visibilityState === "hidden"、rAF 不触发，整个测量体系失效。
  const wake = async (why) => {
    try {
      const w = await ws.send("Browser.getWindowForTarget", {});
      if (w && w.windowId !== undefined) {
        try { await ws.send("Browser.setWindowBounds", { windowId: w.windowId, bounds: { windowState: "normal" } }); } catch (e) { }
        try { await ws.send("Browser.setWindowBounds", { windowId: w.windowId, bounds: { windowState: "maximized" } }); } catch (e) { }
        console.log("  " + why + " → 已请求窗口复原（windowId=" + w.windowId + "）");
      }
    } catch (e) { console.log("  " + why + " → getWindowForTarget 失败：" + e.message); }
    try { await ws.send("Page.bringToFront"); } catch (e) { }
  };
  await wake("启动后");

  // 就绪等待（铁律：不用固定 sleep 猜时间，轮询真实信号）。
  // 判据是「页面脚本已执行」+「**rAF 真的会触发**」——后者才是所有像素/帧测量的前提；
  // document.visibilityState 只作参考（它和 rAF 并不总是同步）。
  console.log("等待页面就绪（轮询 readyState + PV + rAF 真的会触发）…");
  let ready = false, lastV = {};
  const tReady = Date.now();
  for (let i = 0; i < 150; i++) {
    try {
      const rr = await evalRaw(
        `(async()=>{let hit=false;await Promise.race([new Promise(r=>requestAnimationFrame(()=>{hit=true;r();})),new Promise(r=>setTimeout(r,700))]);` +
        `return {rs:document.readyState,pv:(typeof PV!=="undefined"),scripts:document.scripts.length,` +
        `hasCanvasApi:!!document.getElementById("pvCanvas"),vis:document.visibilityState,rafWorks:hit};})()`, true);
      const v = (rr.result && rr.result.value) || {};
      lastV = v;
      if (i % 5 === 0) console.log("  readyState=" + v.rs + " PV=" + v.pv + " scripts=" + v.scripts
                                   + " vis=" + v.vis + " raf=" + v.rafWorks);
      if (v.rs === "complete" && v.pv === true && v.hasCanvasApi === true && v.rafWorks === true) {
        ready = true;
        console.log("  就绪：visibilityState=" + v.vis + "，rAF 可用");
        break;
      }
      if (v.rs === "complete" && v.rafWorks !== true) await wake("rAF 未触发");
    } catch (e) { }
    await new Promise(r => setTimeout(r, 300));
  }
  if (!ready) {
    console.log("页面在 45s 内未达到可测量状态，最后一次探测 = " + JSON.stringify(lastV));
    console.log("RESULT_JSON " + JSON.stringify({ fatal: "页面不可测量（rAF 未触发/不可见）", last: lastV }));
    process.exit(5);
  }
  console.log("页面就绪，用时 " + ((Date.now() - tReady) / 1000).toFixed(1) + "s");

  const DRIVER = process.argv[6] || "_e2e_drive.js";
  const PFX = process.argv[7] || "e2e";   // 截图前缀：GUI 冒烟用 gui，避免覆盖浏览器 E2E 的取证图
  const expr = fs.readFileSync(path.join(__dirname, DRIVER), "utf8");
  console.log("注入驱动 " + DRIVER + "（" + expr.length + " 字符）…");
  const t0 = Date.now();
  let r;
  try {
    r = await ws.send("Runtime.evaluate", {
      expression: expr, awaitPromise: true, returnByValue: true,
      userGesture: true, timeout: 180000,
    });
  } catch (e) {
    console.log("evaluate 失败: " + e.message);
    console.log("RESULT_JSON " + JSON.stringify({ fatal: "evaluate: " + e.message }));
    process.exit(3);
  }
  const ms = Date.now() - t0;
  console.log("驱动完成，用时 " + (ms / 1000).toFixed(1) + "s");
  if (r.exceptionDetails) {
    console.log("页面侧异常: " + JSON.stringify(r.exceptionDetails).slice(0, 900));
  }
  const O = (r.result && r.result.value) || {};
  O.__driveMs = ms;
  O.__pageErrors = pageErrs;
  O.__pageLogs = pageLogs.slice(-60);

  // 驱动早退（例如 PV 未定义）→ 直接报出来，不要产出几十条「字段为 None」的误导性 FAIL
  if (O.fatal || (O.errs && O.errs.length)) {
    console.log("驱动未正常跑完：errs=" + JSON.stringify(O.errs || []) + " fatal=" + (O.fatal || ""));
    fs.writeFileSync(OUT, JSON.stringify(O, null, 1), "utf8");
    console.log("RESULT_JSON " + JSON.stringify(O));
    process.exit(6);
  }

  fs.mkdirSync(SHOTS, { recursive: true });
  const shot = async (name) => {
    try {
      const s = await ws.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
      const f = path.join(SHOTS, name);
      fs.writeFileSync(f, Buffer.from(s.data, "base64"));
      console.log("截图 → " + f);
    } catch (e) { console.log("截图失败 " + name + ": " + e.message); }
  };
  await shot(PFX + "_1_mesh_wireframe.png");

  const evalSmall = async (expression) => {
    try {
      const rr = await ws.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true, userGesture: true });
      return (rr.result && rr.result.value);
    } catch (e) { return "__ERR__ " + e.message; }
  };

  // ---- 真实视口缩小：验证「舞台变矮 → 模型重新适应」这条修复 ----
  //     这是被 E2E 抓到的真实缺陷：初始 fit 按旧尺寸算好后，舞台变矮却不再重新适应，
  //     模型被裁掉一截，而缩放标签仍写 100%。
  try {
    await ws.send("Emulation.setDeviceMetricsOverride",
                  { width: 1180, height: 620, deviceScaleFactor: 1, mobile: false });
    await new Promise(r => setTimeout(r, 1600));
    const after = await evalSmall(
      `({screen:[PV.app.renderer.screen.width,PV.app.renderer.screen.height],` +
      `rectH:Math.round(document.getElementById("pvStage").getBoundingClientRect().height),` +
      `scale:+PV.model.scale.x.toFixed(5),fitS:+PV.fitS.toFixed(5),userZoom:!!PV.userZoom,` +
      `label:document.getElementById("pvZoom").textContent,` +
      `modelH:+(PV.baseH*PV.model.scale.x).toFixed(1),modelW:+(PV.baseW*PV.model.scale.x).toFixed(1),` +
      `fitsH:(PV.baseH*PV.model.scale.x)<=PV.app.renderer.screen.height+1,` +
      `fitsW:(PV.baseW*PV.model.scale.x)<=PV.app.renderer.screen.width+1})`);
    O.viewportShrink = after;
    console.log("视口缩小后 -> " + JSON.stringify(after));
    await ws.send("Emulation.clearDeviceMetricsOverride");
    await new Promise(r => setTimeout(r, 900));
  } catch (e) { O.viewportShrink = { err: String(e.message) }; }

  // 贴图页（UV 高亮）
  console.log("切贴图页 -> " + JSON.stringify(await evalSmall(
    `(async()=>{document.querySelector('.pv-tab[data-t="tex"]').click();await new Promise(r=>setTimeout(r,1200));return {tab:PV.tab,polys:(PV.texSvg||[]).reduce((a,s)=>a+(s?s.querySelectorAll('polygon').length:0),0)};})()`)));
  await shot(PFX + "_2_texture_uv.png");
  // 参数页 + 只看水印关（因为本模型无水印参数，用搜索做个可看的过滤）
  console.log("切参数页 -> " + JSON.stringify(await evalSmall(
    `(async()=>{document.querySelector('.pv-tab[data-t="param"]').click();await new Promise(r=>setTimeout(r,500));const s=document.getElementById('pvSearch');s.value='Eye';s.dispatchEvent(new Event('input',{bubbles:true}));await new Promise(r=>setTimeout(r,600));return {tab:PV.tab,rows:document.querySelectorAll('#pvList .pv-row').length};})()`)));
  await shot(PFX + "_3_param_search.png");
  // 部件页
  console.log("切部件页 -> " + JSON.stringify(await evalSmall(
    `(async()=>{document.querySelector('.pv-tab[data-t="part"]').click();await new Promise(r=>setTimeout(r,600));return {tab:PV.tab,rows:document.querySelectorAll('#pvList .pv-row').length};})()`)));
  await shot(PFX + "_4_part_tree.png");
  // 切回去水印页，确认互不破坏
  const back = await evalSmall(
    `(async()=>{document.querySelector('.mode[data-mode="clean"]').click();await new Promise(r=>setTimeout(r,400));return {mode:document.body.dataset.mode,display:getComputedStyle(document.getElementById('panePreview')).display,modelAlive:!!PV.model,listAlive:PV.meta!==null,diag:document.getElementById('pvInfo').querySelectorAll('dt').length};})()`);
  console.log("切回去水印 -> " + JSON.stringify(back));
  O.modeBack = back;
  await shot(PFX + "_5_back_to_clean.png");

  fs.writeFileSync(OUT, JSON.stringify(O, null, 1), "utf8");
  console.log("原始测量值 → " + OUT);
  console.log("RESULT_JSON " + JSON.stringify(O));
  process.exit(0);
})().catch(e => {
  console.log("runner 异常: " + (e && e.stack || e));
  console.log("RESULT_JSON " + JSON.stringify({ fatal: String(e && e.message || e) }));
  process.exit(4);
});
