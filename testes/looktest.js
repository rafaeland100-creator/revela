// Confere a conta do "copiar look": depois da transferência, as medidas da foto têm de chegar perto das da referência.
// uso: node looktest.js <index.html>
const fs = require('fs');
const s = fs.readFileSync(process.argv[2], 'utf8');
const cut = (a, b) => { const i = s.indexOf(a), j = s.indexOf(b, i); if (i < 0 || j < 0) throw new Error('não achei: ' + a); return s.slice(i, j); };
const src = cut('  const LQ = [', '  let REFS = []') + cut('  function splineLut(pts) {', '  const isId = pts =>');
const api = new Function(src + '\nreturn { LQ, lookStats, lookPixel, lookBuild };')();
let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const N = 128 * 128;
// "foto": manchas de luz e cor variadas
function foto(tom, gama, sat, piso) {
  const px = new Float32Array(3 * N);
  for (let i = 0; i < N; i++) {
    const x = i % 128, y = (i / 128) | 0, base = 0.5 + 0.35 * Math.sin(x / 17 + tom) * Math.cos(y / 23) + 0.12 * (rnd() - 0.5);
    let l = Math.min(1, Math.max(0, base)); l = piso + (1 - piso) * Math.pow(l, gama);
    const h = (x / 128 + y / 311 + tom / 7) * 6.283, c = sat * 0.18 * (0.4 + 0.6 * Math.sin(y / 9 + x / 31) ** 2);
    px[i] = l + c * Math.cos(h); px[N + i] = l + c * Math.cos(h + 2.09); px[2 * N + i] = l + c * Math.cos(h + 4.19);
  }
  for (let i = 0; i < px.length; i++) px[i] = Math.min(1, Math.max(0, px[i]));
  return px;
}
const apply = (T, px) => { const o = new Float32Array(px.length); for (let i = 0; i < N; i++) { const v = api.lookPixel(T, px[i], px[N + i], px[2 * N + i]); o[i] = Math.min(1, Math.max(0, v[0])); o[N + i] = Math.min(1, Math.max(0, v[1])); o[2 * N + i] = Math.min(1, Math.max(0, v[2])); } return o; };
const dq = (a, b) => Math.max(...a.q.map((v, i) => Math.abs(v - b.q[i])));
const dt = (a, b) => Math.max(...a.geral.map((v, i) => Math.abs(v - b.geral[i])));
let ok = true;
const casos = [
  ['mesma foto como referência (não pode mudar)', foto(1, 1, 1, 0), foto(1, 1, 1, 0), 0.012, 0.004, 0.03],
  ['referência escura e contrastada', foto(1, 1, 1, 0), foto(3, 1.9, 1, 0), 0.06, 0.02, 0.2],
  ['referência clara e fosca (preto levantado)', foto(1, 1, 1, 0), foto(3, 0.6, 0.5, 0.12), 0.06, 0.02, 0.2],
  ['referência muito colorida', foto(1, 1, 0.4, 0), foto(2, 1, 1.8, 0), 0.06, 0.02, 0.25],
];
for (const [nome, A, B, tq, tt, tc] of casos) {
  const sA = api.lookStats(A), sB = api.lookStats(B), T = api.lookBuild(sA, sB, A), sO = api.lookStats(apply(T, A));
  const r = { quantis: dq(sO, sB), tinta: dt(sO, sB), cor: Math.abs(sO.cm / sB.cm - 1) };
  const noLimite = T.s >= 2.199 || T.s <= 0.351;   // a quantidade de cor tem teto (2,2x) e piso (0,35x) de propósito
  const pass = r.quantis < tq && r.tinta < tt && (r.cor < tc || noLimite); ok = ok && pass;
  console.log((pass ? 'OK   ' : 'FALHA') + ' ' + nome.padEnd(46), '| luz: distância máx dos quantis', dq(sA, sB).toFixed(3), '->', r.quantis.toFixed(3), '| cor', sA.cm.toFixed(3), '->', sO.cm.toFixed(3), '(alvo', sB.cm.toFixed(3) + ')', '| s', T.s.toFixed(2));
}
// referência com tinta quente nas luzes e fria nas sombras (teal e laranja): o tom por faixa tem de aparecer
{
  const A = foto(1, 1, 0.6, 0), B = foto(1, 1, 0.6, 0);
  for (let i = 0; i < N; i++) { const y = 0.2126 * B[i] + 0.7152 * B[N + i] + 0.0722 * B[2 * N + i]; B[i] += 0.05 * y * y - 0.04 * (1 - y) * (1 - y); B[2 * N + i] += -0.05 * y * y + 0.05 * (1 - y) * (1 - y); }
  const sA = api.lookStats(A), sB = api.lookStats(B), T = api.lookBuild(sA, sB, A), sO = api.lookStats(apply(T, A));
  const quente = sO.band[2][0] - sO.band[2][2], frio = sO.band[0][2] - sO.band[0][0], alvoQ = sB.band[2][0] - sB.band[2][2], alvoF = sB.band[0][2] - sB.band[0][0];
  const q0 = sA.band[2][0] - sA.band[2][2], f0 = sA.band[0][2] - sA.band[0][0], fechouQ = (quente - q0) / (alvoQ - q0), fechouF = (frio - f0) / (alvoF - f0);
  const pass = fechouQ > 0.7 && fechouQ < 1.3 && fechouF > 0.7 && fechouF < 1.3; ok = ok && pass;
  console.log((pass ? 'OK   ' : 'FALHA') + ' sombras frias e brilhos quentes'.padEnd(47), '| brilhos: vermelho menos azul', (sA.band[2][0] - sA.band[2][2]).toFixed(3), '->', quente.toFixed(3), '(alvo', alvoQ.toFixed(3) + ') | sombras: azul menos vermelho', (sA.band[0][2] - sA.band[0][0]).toFixed(3), '->', frio.toFixed(3), '(alvo', alvoF.toFixed(3) + ') | caminho percorrido', Math.round(fechouQ * 100) + '% e', Math.round(fechouF * 100) + '%');
}
// referência em preto e branco: a foto tem de perder a cor
{
  const A = foto(1, 1, 1, 0), B = foto(2, 1.3, 0, 0), sA = api.lookStats(A), sB = api.lookStats(B), T = api.lookBuild(sA, sB, A), sO = api.lookStats(apply(T, A));
  const pass = sO.cm < 0.01; ok = ok && pass;
  console.log((pass ? 'OK   ' : 'FALHA') + ' referência em preto e branco'.padEnd(47), '| cor', sA.cm.toFixed(3), '->', sO.cm.toFixed(4));
}
// curva sempre crescente e dentro de 0..1
{
  const A = foto(1, 3, 1, 0), B = foto(2, 0.4, 1, 0.2), T = api.lookBuild(api.lookStats(A), api.lookStats(B), A); let mono = true;
  for (let i = 1; i < 256; i++) if (T.ly[i] < T.ly[i - 1] - 1e-6 || T.ly[i] > 1 || T.ly[i] < 0) mono = false;
  ok = ok && mono; console.log((mono ? 'OK   ' : 'FALHA') + ' curva de luz crescente e dentro da escala (caso extremo)');
}
console.log(ok ? 'PASSOU' : 'FALHOU'); process.exit(ok ? 0 : 1);
