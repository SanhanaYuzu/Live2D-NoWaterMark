/* 数据级复验：指定 drawable 的 dr.indices 是否全 0。占位符 __DLIST__ */
(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const waitFor = async (fn, ms) => { const t0 = performance.now();
    while (performance.now() - t0 < ms) { if (fn()) return true; await sleep(150); } return false; };
  const O = { errs: [], idx: {} };
  const LIST = __DLIST__;
  try {
    if (typeof PV === "undefined") { O.errs.push("PV 未定义"); return O; }
    if (!PV.model) { document.querySelector('.mode[data-mode="preview"]').click(); }
    if (!await waitFor(() => !!PV.model, 150000)) { O.errs.push("模型未加载"); return O; }
    await sleep(300);
    const dr = PV.dr;
    for (const d of LIST) {
      try {
        const ix = dr.indices[d];
        let nz = 0;
        for (let k = 0; k < ix.length; k++) if (ix[k] !== 0) nz++;
        O.idx["d" + d + "_" + dr.ids[d]] = { len: ix.length, nonzero: nz,
          max: ix.length ? (ix[ix.length - 1]) : -1 };
      } catch (e) { O.idx["d" + d] = { err: String(e) }; }
    }
  } catch (e) { O.errs.push(String(e && e.message || e)); }
  return O;
})()
