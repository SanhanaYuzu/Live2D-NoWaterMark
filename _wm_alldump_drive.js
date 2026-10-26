/* dump 全部 drawable 的顶点数 / UV 数组（供离线三角形分类）。
   输出较大，注意 onlyUV。 */
(async () => {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const waitFor = async (fn, ms) => { const t0 = performance.now();
    while (performance.now() - t0 < ms) { if (fn()) return true; await sleep(150); } return false; };
  const O = { errs: [], meshes: {} };
  try {
    if (typeof PV === "undefined") { O.errs.push("PV 未定义"); return O; }
    if (!PV.model) { document.querySelector('.mode[data-mode="preview"]').click(); }
    if (!await waitFor(() => !!PV.model, 150000)) { O.errs.push("模型未加载"); return O; }
    await sleep(300);
    const dr = PV.dr;
    for (let d = 0; d < dr.count; d++) {
      const uv = dr.vertexUvs[d];
      const ix = dr.indices[d];
      O.meshes["d" + d + "_" + dr.ids[d]] = {
        tex: dr.textureIndices[d],
        vertCount: dr.vertexCounts[d],
        idxLen: ix ? ix.length : 0,
        uvs: Array.from(uv),
        masks: dr.masks ? Array.from(dr.masks[d] || []) : [],
      };
    }
  } catch (e) { O.errs.push(String(e && e.message || e)); }
  return O;
})()
