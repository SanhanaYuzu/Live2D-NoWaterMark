(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const O = {};
  try {
    if (typeof PV === "undefined") { O.errs = ["PV 未定义"]; return O; }
    if (!PV.model) { document.querySelector('.mode[data-mode="preview"]').click(); }
    const t0 = performance.now();
    while (performance.now() - t0 < 60000 && !PV.model) await sleep(200);
    await sleep(300);
    const m = PV.model, im = m.internalModel;
    O.modelCtor = m.constructor && m.constructor.name;
    O.imCtor = im && im.constructor && im.constructor.name;
    O.imKeys = im ? Object.getOwnPropertyNames(Object.getPrototypeOf(im)).slice(0, 60) : null;
    O.ownKeys = im ? Object.keys(im).slice(0, 60) : null;
    O.children = m.children ? m.children.map(c => c.constructor && c.constructor.name) : null;
    try { O.meshesFn = typeof im.getMeshes; O.meshesLen = im.meshes ? im.meshes.length : -1; } catch (e) { O.meshesErr = String(e); }
    try { O.coreHasGetDrawable = typeof im.coreModel.getDrawableCount; } catch (e) { }
  } catch (e) { O.errs = [String(e)]; }
  return O;
})()
