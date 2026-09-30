// Controla o app dentro do emulador pelo protocolo de depuração do Chrome (sem Playwright).
const fs = require('fs');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = (...a) => { const t = a.join(' '); console.log(t); fs.appendFileSync('out/resultado.txt', t + '\n'); };
async function connect() {
  for (let i = 0; i < 30; i++) {
    try { const l = await (await fetch('http://localhost:9222/json')).json(); const pg = l.find(t => t.type === 'page' && /localhost/.test(t.url)); if (pg) return pg; } catch (e) {}
    await sleep(2000);
  }
  throw new Error('página do app não apareceu');
}
async function session(pg) {
  const ws = new WebSocket(pg.webSocketDebuggerUrl); let id = 0; const pend = new Map();
  await new Promise((ok, no) => { ws.onopen = ok; ws.onerror = no; });
  ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); }
    else if (d.method === 'Runtime.consoleAPICalled') fs.appendFileSync('out/console.txt', d.params.type + ': ' + d.params.args.map(a => a.value ?? a.description ?? '').join(' ') + '\n');
    else if (d.method === 'Runtime.exceptionThrown') fs.appendFileSync('out/console.txt', 'ERRO: ' + JSON.stringify(d.params.exceptionDetails).slice(0, 600) + '\n'); };
  const send = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  await send('Runtime.enable');
  const ev = async expr => { const r = await Promise.race([send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true }), sleep(30000).then(() => ({ result: { result: { value: 'SEM RESPOSTA (tela travada)' } } }))]); if (r.result && r.result.exceptionDetails) return 'EXC ' + JSON.stringify(r.result.exceptionDetails).slice(0, 300); return r.result && r.result.result ? r.result.result.value : null; };
  const waitFor = async (expr, ms) => { const t = Date.now(); while (Date.now() - t < ms) { if (await ev(expr) === true) return Date.now() - t; await sleep(1000); } return -1; };
  const shot = async name => { const r = await send('Page.captureScreenshot', { format: 'png' }); if (r.result && r.result.data) fs.writeFileSync('out/' + name, Buffer.from(r.result.data, 'base64')); };
  return { ev, waitFor, shot, ws };
}
async function testPhoto(s, file, tag) {
  const b64 = fs.readFileSync(file).toString('base64');
  const t0 = Date.now();
  await s.ev("(async () => { const b = await (await fetch('data:image/jpeg;base64," + b64 + "')).blob(); const f = new File([b], '" + tag + ".jpg', { type: 'image/jpeg' }); const dt = new DataTransfer(); dt.items.add(f); const inp = document.getElementById('file'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); return true; })()");
  const tShow = await s.waitFor("document.getElementById('capName').textContent === '" + tag + ".jpg' && document.getElementById('view').width > 100", 60000);
  log('[' + tag + '] foto na tela: ' + (tShow < 0 ? 'NÃO APARECEU' : (Date.now() - t0) + ' ms'));
  await s.ev("document.getElementById('toast').textContent = ''; document.getElementById('saveBtn').click(); true");
  const tS0 = await s.waitFor("/salva|Não consegui/.test(document.getElementById('toast').textContent)", 180000);
  log('[' + tag + '] salvar logo que a foto apareceu: ' + (tS0 < 0 ? 'SEM RESPOSTA em 3 min' : tS0 + ' ms') + ' | aviso: ' + await s.ev("document.getElementById('toast').textContent"));
  const tAI = await s.waitFor("document.getElementById('aiPill').hidden", 360000);
  log('[' + tag + '] IAs em segundo plano terminaram: ' + (tAI < 0 ? 'NÃO TERMINARAM em 6 min | etapa: ' + await s.ev("document.getElementById('aiPillT').textContent") : (Date.now() - t0) + ' ms'));
  log('[' + tag + '] o que o app fez: ' + await s.ev("[...document.querySelectorAll('#notes li')].map(l => l.textContent).slice(0, 3).join(' || ').slice(0, 500)"));
  await s.shot(tag + '-editado.png');
  await s.ev("document.getElementById('toast').textContent = ''; document.getElementById('saveBtn').click(); true");
  const tSave = await s.waitFor("/salva|Não consegui/.test(document.getElementById('toast').textContent)", 180000);
  log('[' + tag + '] salvar: ' + (tSave < 0 ? 'SEM RESPOSTA' : tSave + ' ms') + ' | aviso: ' + await s.ev("document.getElementById('toast').textContent"));
  await sleep(3000); await s.shot(tag + '-salvo.png');
}
(async () => {
  let pg = await connect(); await sleep(8000); pg = await connect();
  const s = await session(pg);
  log('url:', await s.ev('location.href'), '| nativo:', await s.ev('!!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform())'), '| vários núcleos:', await s.ev('self.crossOriginIsolated'), '| núcleos:', await s.ev('navigator.hardwareConcurrency'));
  log('service worker ativo:', await s.ev('!!(navigator.serviceWorker && navigator.serviceWorker.controller)'));
  log('plugins nativos:', await s.ev('Object.keys((window.Capacitor && window.Capacitor.Plugins) || {}).join(",")'));
  log('IAs prontas em', await s.waitFor("/pronta|indispon/.test(document.getElementById('segStat').textContent)", 120000), 'ms |', await s.ev("document.getElementById('segStat').textContent"));
  await testPhoto(s, 'scripts/teste-retrato.jpg', 'retrato');
  await testPhoto(s, 'scripts/teste-paisagem.jpg', 'paisagem');
  const t1 = Date.now(); await s.ev("document.getElementById('aiFast').click(); true");
  const tA = await s.waitFor("/Pronto em|Não deu|Cancelado/.test(document.getElementById('aiSub').textContent)", 480000);
  log('IA de detalhe (Só fundo):', tA < 0 ? 'NÃO TERMINOU em 8 min' : (Date.now() - t1) + ' ms', '|', await s.ev("document.getElementById('aiSub').textContent"));
  s.ws.close();
})().catch(e => { log('ERRO', e.message); process.exit(1); });
