
// 最先注入：捕获脚本级错误（含库加载失败），一并上报
window.__err = [];
window.onerror = function(m, s, l, c){
  window.__err.push("onerror: " + m + " @ " + (s || "") + ":" + l);
  try { fetch("/__report", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({stage:"onerror", err: m, at: (s||"")+":"+l, ok:false})}); } catch(e){}
};
window.addEventListener("error", function(e){
  if (e && e.target && e.target.tagName === "SCRIPT"){
    window.__err.push("script-load-fail: " + (e.target.src || "?"));
    try { fetch("/__report", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({stage:"script-load-fail", err: e.target.src, ok:false})}); } catch(x){}
  }
}, true);

;
window.PIXI=undefined;
;

// 上报：主通道 POST 回本地服务（不依赖 pywebview 桥）；次通道桥（若可用）
function S(o){
  try { document.getElementById("dbg").textContent = JSON.stringify(o); } catch(e){}
  try { fetch("/__report", {method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify(o), keepalive:true}); } catch(e){}
  try { if (window.pywebview && pywebview.api && pywebview.api.report) pywebview.api.report(JSON.stringify(o)); } catch(e){}
}

(async () => {
  var out = { ok:false, ua: navigator.userAgent };
  try {
    out.pixiVer = (window.PIXI && PIXI.VERSION) || "none";
    out.hasCore = !!window.Live2DCubismCore;
    out.hasLive2DModel = !!(window.PIXI && PIXI.live2d && PIXI.live2d.Live2DModel);
    try {
      out.cubismVer = (window.Live2DCubismCore && Live2DCubismCore.Version.csmGetVersion)
        ? (function(v){ return [(v>>>24)&0xff,(v>>>16)&0xff,(v>>>8)&0xff,v&0xff].join("."); })(Live2DCubismCore.Version.csmGetVersion())
        : "obj";
    } catch(e){ out.cubismVer = "err:" + e.message; }
    S(Object.assign({stage:"libs"}, out));
    if (!out.hasLive2DModel) throw new Error("PIXI.live2d.Live2DModel 缺失");

    var app = new PIXI.Application({ view: document.getElementById("cv"),
      width: 900, height: 900, backgroundAlpha: 0, antialias: true, autoStart: false });
    out.rendererType = app.renderer && app.renderer.type;
    out.webgl = !!(app.renderer && app.renderer.gl);
    try { out.gpu = out.webgl ? (function(g){ var d=g.getExtension("WEBGL_debug_renderer_info");
        return d ? g.getParameter(d.UNMASKED_RENDERER_WEBGL) : "?"; })(app.renderer.gl) : "no-webgl"; }
    catch(e){ out.gpu = "err"; }
    S(Object.assign({stage:"app"}, out));

    S({ stage:"loading-model" });
    var model = await PIXI.live2d.Live2DModel.from("/__MODEL_JSON__",
      { autoInteract:false, idleMotionGroup:"__none__" });
    out.modelW = Math.round(model.width);
    out.modelH = Math.round(model.height);
    var core = model.internalModel.coreModel;
    out.params = core.getParameterCount ? core.getParameterCount() : -1;
    out.drawables = core.getDrawableCount ? core.getDrawableCount() : -1;
    out.partCount = core.getPartCount ? core.getPartCount() : -1;
    S(Object.assign({stage:"loaded"}, out));

    var sc = Math.min(880 / model.width, 880 / model.height);
    model.scale.set(sc);
    model.x = (900 - model.width * sc) / 2;
    model.y = (900 - model.height * sc) / 2;
    app.stage.addChild(model);
    app.render();
    S(Object.assign({stage:"rendered"}, out));

    // —— API 面探测：不猜方法名，把真实可用的接口列出来 ——
    function methods(o){ var r=[], p=o; while(p && p!==Object.prototype){
        Object.getOwnPropertyNames(p).forEach(function(k){ if(r.indexOf(k)<0) r.push(k); }); p=Object.getPrototypeOf(p); } return r; }
    out.coreCtor = (core.constructor && core.constructor.name) || "?";
    out.coreMethods = methods(core).filter(function(k){ return typeof core[k] === "function"; }).sort();
    out.coreProps = methods(core).filter(function(k){ try{ return typeof core[k] !== "function"; }catch(e){ return false; } }).sort();
    out.hasParametersObj = !!core.parameters;
    if (core.parameters){
      out.paramKeys = Object.keys(core.parameters);
      out.paramCount2 = core.parameters.count;
      var P = core.parameters;
      out.firstIds = [];
      if (P.ids) for (var q=0;q<Math.min(4,P.ids.length);q++) out.firstIds.push(String(P.ids[q]));
    }
    // drawable / part 侧（编辑器要用）
    out.drawableKeys = core.drawables ? Object.keys(core.drawables) : null;
    out.partsKeys = core.parts ? Object.keys(core.parts) : null;
    // 动作 / 表情（编辑器要用）
    try {
      var mm = model.internalModel.motionManager;
      out.motionGroups = mm && mm.groups ? Object.keys(mm.groups) : null;
      out.motionCounts = {};
      if (mm && mm.groups) for (var g in mm.groups) out.motionCounts[g] = mm.groups[g].length;
      out.expressionCount = (mm && mm.definitions && mm.definitions.expressions)
        ? mm.definitions.expressions.length : null;
    } catch(e){ out.motionErr = String(e.message); }

    // 用真实索引式接口驱动参数（core.parameters 不存在！必须索引式）
    var driven = [];
    try {
      var N = core.getParameterCount();
      for (var i2 = 0; i2 < N && driven.length < 4; i2++){
        if (core.getParameterMaximumValue(i2) > 1.5){
          var bid = core.getParameterValueByIndex(i2);
          core.setParameterValueByIndex(i2, core.getParameterMaximumValue(i2));
          driven.push([i2, +bid.toFixed(3), +core.getParameterValueByIndex(i2).toFixed(3),
                       +core.getParameterDefaultValue(i2).toFixed(3)]);
        }
      }
      model.update(0.016); app.render();
      out.driveVia = "setParameterValueByIndex";
    } catch(e){ out.driveErr = String(e.message); }
    out.drive = driven;

    // 部件显隐：setPartOpacityByIndex 是否真能隐藏
    try {
      var pn = core.getPartCount(), hid = null;
      for (var pi = 0; pi < pn; pi++){
        if (core.getPartOpacityByIndex(pi) > 0.9){ hid = pi; break; }
      }
      if (hid !== null){
        var b4 = core.getPartOpacityByIndex(hid);
        core.setPartOpacityByIndex(hid, 0);
        model.update(0.016); app.render();
        out.partHide = [hid, +b4.toFixed(3), +core.getPartOpacityByIndex(hid).toFixed(3)];
        core.setPartOpacityByIndex(hid, b4);
        model.update(0.016);
      }
    } catch(e){ out.partErr = String(e.message); }

    // 网格 -> 贴图映射（水印定位要用）
    try {
      var dn = core.getDrawableCount(), mp = [], texSet = {};
      for (var di = 0; di < dn; di++){
        var ti = core.getDrawableTextureIndices(di);
        texSet[ti] = (texSet[ti] || 0) + 1;
        if (mp.length < 3) mp.push([di, core.getDrawableId(di), ti, core.getDrawableVertexCount(di)]);
      }
      out.texHistogram = texSet;
      out.drawableSample = mp;
      out.meshApiOk = true;
      var d0u = core.getDrawableVertexUvs(0);
      out.uv0Len = d0u ? d0u.length : null;
    } catch(e){ out.meshErr = String(e.message); }

    // 真出像素的证据：读回帧缓冲 alpha
    try {
      var gl2 = app.renderer.gl, W2 = gl2.drawingBufferWidth, H2 = gl2.drawingBufferHeight;
      var px2 = new Uint8Array(W2 * H2 * 4);
      gl2.readPixels(0, 0, W2, H2, gl2.RGBA, gl2.UNSIGNED_BYTE, px2);
      var nz2 = 0; for (var k2 = 3; k2 < px2.length; k2 += 4) if (px2[k2] > 8) nz2++;
      out.opaqueRatio = +(nz2 / (W2 * H2)).toFixed(4);
    } catch(e){ out.opaqueRatio = "err:" + e.message; }
    out.ok = true;
    S(Object.assign({stage:"done"}, out));
  } catch(e) {
    out.err = String(e && e.message || e);
    out.stack = String(e && e.stack || "").split("\n").slice(0, 4).join(" | ");
    S(Object.assign({stage:"error"}, out));
  }
})();
