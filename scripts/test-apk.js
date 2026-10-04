// Controla o app dentro do emulador pelo protocolo de depuração do Chrome (sem Playwright).
const fs = require('fs'); const { execSync } = require('child_process');
const screencap = name => { try { execSync('adb exec-out screencap -p > out/' + name, { timeout: 30000 }); } catch (e) {} };
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
  let fechou = false; ws.onclose = () => { fechou = true; };   // o Android encerrou o app (ou a página caiu)
  ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); }
    else if (d.method === 'Runtime.consoleAPICalled') fs.appendFileSync('out/console.txt', d.params.type + ': ' + d.params.args.map(a => a.value ?? a.description ?? '').join(' ') + '\n');
    else if (d.method === 'Runtime.exceptionThrown') fs.appendFileSync('out/console.txt', 'ERRO: ' + JSON.stringify(d.params.exceptionDetails).slice(0, 600) + '\n'); };
  const send = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  await send('Runtime.enable');
  const ev = async expr => { const r = await Promise.race([send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true }), sleep(30000).then(() => ({ result: { result: { value: 'SEM RESPOSTA (tela travada)' } } }))]); if (r.result && r.result.exceptionDetails) return 'EXC ' + JSON.stringify(r.result.exceptionDetails).slice(0, 300); return r.result && r.result.result ? r.result.result.value : null; };
  const waitFor = async (expr, ms) => { const t = Date.now(); while (Date.now() - t < ms) { if (fechou) throw new Error('o app foi encerrado no meio do teste'); if (await ev(expr) === true) return Date.now() - t; await sleep(1000); } return -1; };
  const shot = async name => { const r = await Promise.race([send('Page.captureScreenshot', { format: 'png' }), sleep(20000).then(() => ({}))]); if (r.result && r.result.data) fs.writeFileSync('out/' + name, Buffer.from(r.result.data, 'base64')); };
  const vivo = async () => { if (fechou) return false; for (let i = 0; i < 3; i++) { if (await ev('1 + 1') === 2) return true; } return false; };
  return { ev, waitFor, shot, ws, send, vivo };
}
async function testPhoto(s, file, tag) {
  const b64 = fs.readFileSync(file).toString('base64');
  const t0 = Date.now();
  await s.ev("(async () => { const b = await (await fetch('data:image/jpeg;base64," + b64 + "')).blob(); const f = new File([b], '" + tag + ".jpg', { type: 'image/jpeg' }); const dt = new DataTransfer(); dt.items.add(f); const inp = document.getElementById('file'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); return true; })()");
  const tShow = await s.waitFor("document.getElementById('capName').textContent === '" + tag + ".jpg' && document.getElementById('view').width > 100", 60000);
  log('[' + tag + '] foto na tela: ' + (tShow < 0 ? 'NÃO APARECEU' : (Date.now() - t0) + ' ms'));
  if (!(await s.vivo())) throw new Error('a página parou de responder logo depois de abrir a foto');
  const tIA = await s.waitFor("/Melhorada pela IA Revela|clássico/.test(document.getElementById('heroT').textContent)", 90000);
  log('[' + tag + '] IA Revela: ' + (tIA < 0 ? 'NÃO RODOU' : await s.ev("document.getElementById('heroT').textContent + ' | conta da rede ' + window.__tm.tom + ' ms | ' + document.getElementById('heroS').textContent.slice(0, 140)")));
  await s.ev("document.getElementById('toast').textContent = ''; document.getElementById('saveBtn').click(); true");
  const tS0 = await s.waitFor("/salva|Não consegui/.test(document.getElementById('toast').textContent)", 180000);
  log('[' + tag + '] salvar logo que a foto apareceu: ' + (tS0 < 0 ? 'SEM RESPOSTA em 3 min' : tS0 + ' ms') + ' | aviso: ' + await s.ev("document.getElementById('toast').textContent"));
  const tAI = await s.waitFor("document.getElementById('aiPill').hidden", 360000);
  log('[' + tag + '] IAs em segundo plano terminaram: ' + (tAI < 0 ? 'NÃO TERMINARAM em 6 min | etapa: ' + await s.ev("document.getElementById('aiPillT').textContent") : (Date.now() - t0) + ' ms'));
  if (!(await s.vivo())) throw new Error('a página parou de responder durante as IAs de apoio');
  log('[' + tag + '] tempos no aparelho (ms): ' + await s.ev("JSON.stringify(Object.fromEntries(Object.entries(window.__tm).filter(([k, v]) => typeof v === 'number')))"));
  log('[' + tag + '] o que o app fez: ' + await s.ev("[...document.querySelectorAll('#notes li')].map(l => l.textContent).slice(0, 3).join(' || ').slice(0, 500)"));
  await s.shot(tag + '-editado.png'); screencap(tag + '-tela-real.png');
  // meu gosto: nas duas primeiras fotos o contraste sobe 0,20 antes de salvar; a terceira tem de abrir já com parte disso
  if (tag === 'retrato2') log('[' + tag + '] meu gosto: ' + await s.ev("document.getElementById('gostoHint').textContent + ' | caixa visível = ' + !document.getElementById('gostoBox').hidden + ' | a explicação cita o gosto = ' + /Seu gosto/.test(document.getElementById('notes').textContent)"));
  else { await s.ev("document.querySelector('.tabbtn[data-tab=ajustar]').click(); document.querySelector('#adjChips .chip[data-k=contrast]').click(); true"); await sleep(400); log('[' + tag + '] contraste antes de salvar: ' + await s.ev("(() => { const r = document.getElementById('adjRange'), a = +r.value; r.value = (a + 0.2).toFixed(2); r.dispatchEvent(new Event('input', { bubbles: true })); return a + ' -> ' + r.value; })()")); await s.ev("document.querySelector('.tabbtn[data-tab=looks]').click(); true"); await sleep(900); }
  await s.ev("document.getElementById('toast').textContent = ''; document.getElementById('saveBtn').click(); true");
  const tSave = await s.waitFor("/salva|Não consegui/.test(document.getElementById('toast').textContent)", 180000);
  log('[' + tag + '] salvar: ' + (tSave < 0 ? 'SEM RESPOSTA' : tSave + ' ms') + ' | aviso: ' + await s.ev("document.getElementById('toast').textContent"));
  await sleep(3000); screencap(tag + '-salvo-tela-real.png'); await s.ev("document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape'})); true"); await sleep(1500);
}
(async () => {
  let pg = await connect(); await sleep(8000); pg = await connect();
  const s = await session(pg);
  log('url:', await s.ev('location.href'), '| nativo:', await s.ev('!!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform())'), '| vários núcleos:', await s.ev('self.crossOriginIsolated'), '| núcleos:', await s.ev('navigator.hardwareConcurrency'));
  log('tela:', await s.ev("innerWidth + '×' + innerHeight + ' px de página | densidade ' + devicePixelRatio + ' | tela física ' + screen.width + '×' + screen.height + ' | largura visível ' + Math.round(visualViewport.width) + ' | documento ' + document.documentElement.scrollWidth"));
  log('service worker ativo:', await s.ev('!!(navigator.serviceWorker && navigator.serviceWorker.controller)'));
  log('plugins nativos:', await s.ev('Object.keys((window.Capacitor && window.Capacitor.Plugins) || {}).join(",")'));
  log('núcleos da IA e preparo:', await s.ev("typeof SharedArrayBuffer !== 'undefined'"));
  log('IAs prontas em', await s.waitFor("/pronta|indispon/.test(document.getElementById('segStat').textContent)", 120000), 'ms |', await s.ev("document.getElementById('segStat').textContent"));
  await testPhoto(s, 'scripts/teste-retrato.jpg', 'retrato');
  await testPhoto(s, 'scripts/teste-paisagem.jpg', 'paisagem');
  // troca de céu na paisagem: o recorte vem da IA de cena, que já rodou ao abrir a foto
  await s.ev("document.getElementById('quickCeu').click(); true"); await sleep(1000);
  const t0c = Date.now(); await s.ev("document.querySelector('#ceuGrid .fchip[data-f=ceu-por]').click(); true");
  const tC = await s.waitFor("/Céu trocado|Não achei céu|ainda está reconhecendo/.test(document.getElementById('ceuMsg').textContent)", 60000), dC = Date.now() - t0c; await sleep(2500);
  log('trocar céu (pôr do sol):', tC < 0 ? 'NÃO RESPONDEU' : 'respondeu em ' + dC + ' ms | ' + await s.ev("document.getElementById('ceuMsg').textContent + ' | montar o céu ' + window.__tm.fundo + ' ms | render ' + window.__tm.render + ' ms'")); screencap('ceu-tela-real.png');
  await s.ev("document.querySelector('#ceuGrid .fchip[data-f=\"\"]').click(); document.getElementById('toolBack').click(); document.querySelector('.tabbtn[data-tab=looks]').click(); true"); await sleep(1500);
  const t1 = Date.now(); await s.ev("document.getElementById('aiFast').click(); true");
  const tA = await s.waitFor("/Pronto em|Não deu|Cancelado/.test(document.getElementById('aiSub').textContent)", 480000);
  log('IA de detalhe (Só fundo):', tA < 0 ? 'NÃO TERMINOU em 8 min' : (Date.now() - t1) + ' ms', '|', await s.ev("document.getElementById('aiSub').textContent"));
  // Fundo de cinema: a profundidade agora só é medida quando o botão é tocado
  await testPhoto(s, 'scripts/teste-retrato.jpg', 'retrato2');
  const t2 = Date.now(); await s.ev("document.querySelector('#quick .chip[data-k=dof]').click(); true"); await sleep(1500);
  const tD = await s.waitFor("document.getElementById('aiPill').hidden && !document.getElementById('quickMsg').textContent", 240000);
  log('Fundo de cinema (profundidade sob demanda):', tD < 0 ? 'NÃO TERMINOU em 4 min | ' + await s.ev("document.getElementById('quickMsg').textContent") : (Date.now() - t2) + ' ms'); await sleep(2500); await s.shot('fundo-de-cinema.png');
  await s.ev("document.querySelector('#quick .chip[data-k=dof]').click(); true"); await sleep(1500);
  // copiar o look de outra foto (a paisagem de teste serve de referência para o retrato)
  const refB64 = fs.readFileSync('scripts/teste-paisagem.jpg').toString('base64'), t3 = Date.now();
  await s.ev("(async () => { const b = await (await fetch('data:image/jpeg;base64," + refB64 + "')).blob(); const f = new File([b], 'ref.jpg', { type: 'image/jpeg' }); const dt = new DataTransfer(); dt.items.add(f); const inp = document.getElementById('refFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); return true; })()");
  const tL = await s.waitFor("/Look copiado/.test(document.getElementById('heroT').textContent)", 60000);
  log('copiar look:', tL < 0 ? 'NÃO APLICOU' : (Date.now() - t3) + ' ms | ' + await s.ev("document.getElementById('heroT').textContent + ' | guardados: ' + document.querySelectorAll('.look.ref').length")); await sleep(2500); await s.shot('look-copiado.png');
  await s.ev("document.querySelector('.look[data-id=\"\"]').click(); true"); await sleep(1500);
  // borracha mágica: pinta um traço com o dedo e apaga (o modelo MI-GAN roda no aparelho)
  await s.ev("document.getElementById('quickErase').click(); true"); await sleep(1200);
  const vb = JSON.parse(await s.ev("JSON.stringify((r => ({ x: r.left, y: r.top, w: r.width, h: r.height }))(document.getElementById('view').getBoundingClientRect()))"));
  await s.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: vb.x + vb.w * 0.15, y: vb.y + vb.h * 0.12, id: 0 }] });
  for (const f of [0.2, 0.25, 0.3, 0.35]) { await s.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: vb.x + vb.w * f, y: vb.y + vb.h * 0.12, id: 0 }] }); await sleep(60); }
  await s.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] }); await sleep(800);
  log('borracha: marcação feita com o dedo =', await s.ev("!document.getElementById('erGo').disabled"));
  // dois dedos dentro da borracha: aproxima a foto sem deixar marca; depois um dedo pinta com a foto ampliada
  const vc = { x: vb.x + vb.w / 2, y: vb.y + vb.h * 0.45 }, dois = d => [{ x: vc.x - d, y: vc.y, id: 0 }, { x: vc.x + d, y: vc.y, id: 1 }];
  await s.ev("document.getElementById('erClear').click(); true"); await sleep(600);
  await s.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: dois(30) });
  for (const d of [45, 60, 75]) { await s.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: dois(d) }); await sleep(60); }
  await s.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] }); await sleep(800);
  log('borracha: pinça dentro da ferramenta: zoom =', await s.ev("document.getElementById('view').style.transform || 'sem zoom'"), '| deixou marca =', await s.ev("!document.getElementById('erGo').disabled"));
  await s.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: vb.x + vb.w * 0.3, y: vb.y + vb.h * 0.2, id: 0 }] });
  for (const f of [0.4, 0.5, 0.6]) { await s.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: vb.x + vb.w * f, y: vb.y + vb.h * 0.2, id: 0 }] }); await sleep(40); }
  await s.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  // o dedo saiu da foto em movimento: o toque seguinte no botão Apagar tem que valer (o navegador costuma engolir)
  await sleep(250); const tb = JSON.parse(await s.ev("JSON.stringify((r => ({ x: r.left + r.width / 2, y: r.top + r.height / 2 }))(document.getElementById('erGo').getBoundingClientRect()))"));
  const t4 = Date.now(); await s.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: tb.x, y: tb.y, id: 0 }] }); await s.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  const tT = await s.waitFor("!document.getElementById('loading').hidden || /Apagado em|Não deu|Pinte primeiro/.test(document.getElementById('erMsg').textContent)", 4000);
  log('borracha: toque em Apagar logo depois do traço', tT < 0 ? 'NÃO REGISTROU (apagando por comando)' : 'registrou');
  if (tT < 0) await s.ev("document.getElementById('erGo').click(); true");
  const tE = await s.waitFor("/Apagado em|Não deu|Pinte primeiro/.test(document.getElementById('erMsg').textContent)", 420000);
  log('borracha mágica (com a foto ampliada):', tE < 0 ? 'NÃO TERMINOU em 7 min' : (Date.now() - t4) + ' ms | ' + await s.ev("document.getElementById('erMsg').textContent"), '| zoom depois de apagar =', await s.ev("document.getElementById('view').style.transform || 'sem zoom'"));
  await s.waitFor("document.getElementById('aiPill').hidden", 240000); await sleep(1500); await s.shot('borracha.png'); screencap('borracha-tela-real.png');
  log('borracha: botão Ver antes visível =', await s.ev("!document.getElementById('erCmp').hidden"));
  await s.ev("document.getElementById('erUndo').click(); true"); await sleep(1500); await s.waitFor("document.getElementById('aiPill').hidden", 240000);
  log('borracha: desfazer =', await s.ev("document.getElementById('erMsg').textContent"));
  await s.ev("if (document.getElementById('view').style.transform) window.revelaBack(); document.getElementById('toolBack').click(); document.querySelector('.tabbtn[data-tab=looks]').click(); true"); await sleep(1000);
  // fundo de estúdio: troca o cenário atrás da pessoa (usa a separação que a IA já fez ao abrir a foto)
  await s.ev("document.getElementById('quickFundo').click(); true"); await sleep(1000);
  const t5 = Date.now(); await s.ev("document.querySelector('#fdGrid .fchip[data-f=escuro]').click(); true");
  const tF = await s.waitFor("/fundo de estúdio|Não achei pessoa|ainda está separando/.test(document.getElementById('fdMsg').textContent)", 60000), dF = Date.now() - t5; await sleep(2500);
  log('fundo de estúdio:', tF < 0 ? 'NÃO RESPONDEU' : 'respondeu em ' + dF + ' ms | ' + await s.ev("document.getElementById('fdMsg').textContent + ' | montar o fundo ' + window.__tm.fundo + ' ms | render ' + window.__tm.render + ' ms'")); screencap('fundo-tela-real.png');
  await s.ev("document.getElementById('toast').textContent = ''; document.getElementById('saveBtn').click(); true");
  const tS5 = await s.waitFor("/salva|Não consegui/.test(document.getElementById('toast').textContent)", 180000);
  log('salvar com fundo de estúdio:', tS5 < 0 ? 'SEM RESPOSTA em 3 min' : tS5 + ' ms | ' + await s.ev("document.getElementById('toast').textContent"));
  // uma foto como fundo (a paisagem de teste), com o desfoque de lente
  const t6 = Date.now();
  await s.ev("(async () => { const b = await (await fetch('data:image/jpeg;base64," + refB64 + "')).blob(); const f = new File([b], 'fundo.jpg', { type: 'image/jpeg' }); const dt = new DataTransfer(); dt.items.add(f); const inp = document.getElementById('fdFile'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true })); return true; })()");
  const tG = await s.waitFor("/sua foto/.test(document.getElementById('fdMsg').textContent)", 60000), dG = Date.now() - t6; await sleep(2500);
  log('foto como fundo:', tG < 0 ? 'NÃO APLICOU' : 'aplicou em ' + dG + ' ms | ' + await s.ev("'montar o fundo ' + window.__tm.fundo + ' ms | render ' + window.__tm.render + ' ms | desfoque visível = ' + !document.getElementById('fdBlurRow').hidden")); screencap('fundo-foto-tela-real.png');
  await s.ev("document.querySelector('#fdGrid .fchip[data-f=\"\"]').click(); document.getElementById('toolBack').click(); document.querySelector('.tabbtn[data-tab=looks]').click(); true"); await sleep(1500);
  // expandir: a foto vira Story 9:16 com as bordas completadas pela IA da borracha, sem cortar; depois desfaz
  await s.ev("document.querySelector('.tabbtn[data-tab=formato]').click(); document.querySelector('.fmt[data-id=story]').click(); true"); await sleep(1200);
  const t7 = Date.now(); await s.ev("document.getElementById('fmtExpand').click(); true");
  const tX = await s.waitFor("/Bordas completadas|Não deu|já está/.test(document.getElementById('fmtMsg').textContent)", 420000), dX = Date.now() - t7;
  await s.waitFor("document.getElementById('aiPill').hidden", 240000); await sleep(1500);
  log('expandir para Story:', tX < 0 ? 'NÃO TERMINOU em 7 min' : dX + ' ms | ' + await s.ev("document.getElementById('fmtMsg').textContent.slice(0, 120) + ' | tamanho ' + document.getElementById('capSize').textContent")); screencap('expandir-tela-real.png');
  await s.ev("document.getElementById('fmtExpand').click(); true"); await sleep(1500);
  log('expandir: desfazer =', await s.ev("document.getElementById('fmtExpand').textContent + ' | tamanho ' + document.getElementById('capSize').textContent"));
  await s.ev("document.querySelector('.fmt[data-id=orig]').click(); document.querySelector('.tabbtn[data-tab=looks]').click(); true"); await sleep(1500);
  // zoom por pinça com dois dedos de verdade (eventos de toque)
  const bx = JSON.parse(await s.ev("JSON.stringify((r => ({ x: r.left + r.width / 2, y: r.top + r.height / 2 }))(document.getElementById('view').getBoundingClientRect()))"));
  const pts = d => [{ x: bx.x - d, y: bx.y, id: 0 }, { x: bx.x + d, y: bx.y, id: 1 }];
  await s.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: pts(30) });
  for (const d of [45, 60, 80, 100]) { await s.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: pts(d) }); await sleep(60); }
  await s.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] }); await sleep(800);
  log('pinça com dois dedos: zoom =', await s.ev("document.getElementById('view').style.transform || 'sem zoom'"), '| zoom da página:', await s.ev('visualViewport.scale')); screencap('zoom-tela-real.png');
  // botão Voltar do Android: 1º desfaz o zoom, 2º fecha a ferramenta, 3º volta de aba, 4º avisa; o app não pode fechar
  const voltar = async () => { try { execSync('adb shell input keyevent 4', { timeout: 20000 }); } catch (e) {} await sleep(1500); };
  await voltar(); log('Voltar 1 (zoom):', await s.ev("document.getElementById('view').style.transform || 'zoom desfeito'"));
  await s.ev("document.querySelector('.tabbtn[data-tab=ferramentas]').click(); document.querySelector('.tool[data-tool=adjust]').click(); true"); await sleep(800);
  await voltar(); log('Voltar 2 (ferramenta aberta): lista de ferramentas visível =', await s.ev("!document.getElementById('toolList').hidden"));
  await voltar(); log('Voltar 3 (aba): Looks selecionada =', await s.ev("document.querySelector('.tabbtn[data-tab=looks]').getAttribute('aria-selected')"));
  await voltar(); log('Voltar 4 (sair): aviso =', await s.ev("document.getElementById('toast').textContent"), '| app continua aberto =', await s.ev("document.visibilityState"));
  let foco = ''; try { foco = execSync('adb shell dumpsys activity activities', { timeout: 20000 }).toString().split(/\r?\n/).filter(l => /mResumedActivity|topResumedActivity/.test(l)).join(' ').trim().slice(0, 200); } catch (e) {}
  log('atividade em primeiro plano:', foco);
  s.ws.close(); log('TESTE COMPLETO'); process.exit(0);
})().catch(e => { log('ERRO', e.message); process.exit(1); });
