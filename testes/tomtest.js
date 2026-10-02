// Confere a conta da IA Revela em JavaScript contra o PyTorch: mesmos 62 números e mesmas cores.
// uso: node tomtest.js <index.html> <revela_tom.bin> <revela_tom_teste.json>
const fs = require('fs');
const [html, binP, jsonP] = process.argv.slice(2);
const s = fs.readFileSync(html, 'utf8');
const a = s.indexOf('  function tomThumb('), b = s.indexOf('  function tomCompute()');
if (a < 0 || b < 0) { console.log('não achei as funções no index.html'); process.exit(1); }
const api = new Function(s.slice(a, b) + '\nreturn { tomThumb, tomHist, tomConv, tomForward, tomParams, tomPixel, lumaOf };')();
// leitura do arquivo igual à do app (tomLoad)
const raw = fs.readFileSync(binP), buf = raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength);
const hd = new Uint32Array(buf, 0, 16); if (hd[0] !== 0x31545652) throw new Error('arquivo inválido');
const K = hd[2], NB = hd[3], NS = hd[4], nc = hd[5], HH = hd[6 + nc], FH = hd[7 + nc], NP = hd[8 + nc], NH = NB * 4 + NS;
const f = new Float32Array(buf, 64); let o = 0; const take = n => { const x = f.subarray(o, o + n); o += n; return x; };
const conv = []; let ci = 3; for (let l = 0; l < nc; l++) { const co = hd[6 + l]; conv.push({ ci, co, w: take(co * ci * 9), b: take(co) }); ci = co; }
const fin = ci * 2 + HH, hist = { w: take(HH * NH), b: take(HH) }, fc1 = { w: take(FH * fin), b: take(FH) }, fc2 = { w: take(NP * FH), b: take(NP) };
if (o !== f.length) throw new Error('tamanho inesperado: ' + o + ' de ' + f.length);
const net = { K, NB, NS, NH, HH, FH, NP, fin, conv, hist, fc1, fc2 };
console.log('rede: K', K, '| convoluções', conv.map(c => c.co).join(','), '| histograma', NH, '->', HH, '| oculta', FH, '| saídas', NP);

const T = JSON.parse(fs.readFileSync(jsonP, 'utf8')), n = 128 * 128;
// a imagem de teste vem em HWC 0..255; o app usa CHW 0..1
const img = new Float32Array(3 * n); for (let i = 0; i < n; i++) for (let c = 0; c < 3; c++) img[c * n + i] = T.img[i * 3 + c] / 255;
const h = api.tomHist(img, net); let dh = 0; for (let i = 0; i < NH; i++) dh = Math.max(dh, Math.abs(h[i] - T.hist[i]));
const t0 = process.hrtime.bigint(), rawOut = api.tomForward(img, h, net), ms = Number(process.hrtime.bigint() - t0) / 1e6;
const P = api.tomParams(rawOut, K), flat = [...P.M, ...P.cv[0], ...P.cv[1], ...P.cv[2], P.sat, P.vib];
let dp = 0; for (let i = 0; i < flat.length; i++) dp = Math.max(dp, Math.abs(flat[i] - T.params[i]));
let dc = 0; T.cores.forEach((c, i) => { const out = api.tomPixel(P, c[0], c[1], c[2]); for (let k = 0; k < 3; k++) dc = Math.max(dc, Math.abs(out[k] - T.saida[i][k])); });
// miniatura por média de área: imagem 256×256 de blocos deve dar a média de cada bloco 2×2
const big = new Uint8ClampedArray(256 * 256 * 4); for (let i = 0; i < 256 * 256; i++) { const x = i % 256, y = (i / 256) | 0; big[i * 4] = (x & 1) ? 200 : 100; big[i * 4 + 1] = (y & 1) ? 50 : 150; big[i * 4 + 2] = 30; big[i * 4 + 3] = 255; }
const th = api.tomThumb(big, 256, 256), okTh = Math.abs(th[0] - 150 / 255) < 1e-6 && Math.abs(th[n] - 100 / 255) < 1e-6 && Math.abs(th[2 * n] - 30 / 255) < 1e-6;
const small = api.tomThumb(new Uint8ClampedArray(40 * 30 * 4).fill(128), 40, 30), okSmall = small.every(v => Math.abs(v - 128 / 255) < 1e-6);
console.log('histograma: diferença máx', dh.toExponential(2));
console.log('62 parâmetros: diferença máx', dp.toExponential(2), '| conta em', ms.toFixed(0), 'ms');
console.log('cores de teste: diferença máx', dc.toExponential(2));
console.log('miniatura 256→128:', okTh ? 'ok' : 'ERRADA', '| miniatura de foto 40×30:', okSmall ? 'ok' : 'ERRADA');
const ok = dh < 1e-5 && dp < 2e-4 && dc < 2e-4 && okTh && okSmall;
console.log(ok ? 'PASSOU' : 'FALHOU'); process.exit(ok ? 0 : 1);
