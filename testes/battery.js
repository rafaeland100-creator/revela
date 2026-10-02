// Bateria de qualidade: roda o automático em todas as fotos de teste e monta pranchas antes/depois.
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
const SP = process.argv[2], OUT = SP + '/' + (process.argv[3] || 'outq'), URL = process.argv[4] || 'http://localhost:8765/index.html';
const EXE = process.env.USERPROFILE + '/AppData/Local/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-win64/chrome-headless-shell.exe';
const list = [];
for (const [dir, re] of [['images', /^(1|2|3|5|barba)\.jpg$|^4\.webp$/], ['pexels', /\.jpg$/], ['pexels2', /\.jpg$/]]) for (const f of fs.readdirSync(SP + '/' + dir).sort()) if (re.test(f)) list.push(dir + '/' + f);
(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch({ executablePath: EXE });
  const ctx = await b.newContext({ viewport: { width: 1400, height: 1000 } }); const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error' && !/TensorFlow|GL Driver|gl_context/.test(m.text())) errs.push('console: ' + m.text().slice(0, 200)); });
  await p.goto(URL); await p.waitForTimeout(6500);
  await p.waitForFunction(() => /pronta|indispon/.test(document.getElementById('segStat').textContent), null, { timeout: 90000 });
  const rep = [];
  for (const f of list) {
    const nm = path.basename(f), tag = f.replace(/\W/g, '_'), t0 = Date.now(), e0 = errs.length;
    try {
      await p.setInputFiles('#file', SP + '/' + f);
      await p.waitForFunction(n => document.getElementById('capName').textContent === n && document.getElementById('view').width > 50, nm, { timeout: 30000 });
      const tShow = Date.now() - t0;
      await p.waitForTimeout(400);
      await p.waitForFunction(() => document.getElementById('aiPill').hidden, null, { timeout: 180000 });
      const tAI = Date.now() - t0;
      await p.waitForTimeout(3500);
      const info = await p.evaluate(() => ({
        look: document.getElementById('heroT').textContent, size: document.getElementById('capSize').textContent,
        notes: [...document.querySelectorAll('#notes li')].map(l => l.textContent),
        stats: document.getElementById('stats').innerText.replace(/\n/g, '|'), tm: Object.assign({}, window.__tm),
        heap: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1e6) : null,
        params: Object.fromEntries([...document.querySelectorAll('.field[data-key]')].map(r => [r.dataset.key, r.querySelector('output').textContent]))
      }));
      await p.locator('#view').screenshot({ path: OUT + '/' + tag + '_after.png' });
      await p.evaluate(() => document.getElementById('cmpBtn').dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))); await p.waitForTimeout(450);
      await p.locator('#view').screenshot({ path: OUT + '/' + tag + '_before.png' });
      await p.evaluate(() => document.getElementById('cmpBtn').dispatchEvent(new PointerEvent('pointerup', { bubbles: true }))); await p.waitForTimeout(200);
      rep.push({ f, tag, tShow, tAI, ...info, errors: errs.slice(e0) });
      console.log(nm.padEnd(26), 'tela', String(tShow).padStart(5), 'ms | IAs', String(tAI).padStart(6), 'ms | heap', info.heap, 'MB |', info.look.replace('Pronta para o Instagram: ', ''), '|', (info.notes[0] || '').slice(0, 110));
    } catch (e) { rep.push({ f, tag, fail: e.message.slice(0, 200), errors: errs.slice(e0) }); console.log(nm.padEnd(26), 'FALHOU:', e.message.slice(0, 160)); }
  }
  fs.writeFileSync(OUT + '/report.json', JSON.stringify(rep, null, 1));
  // pranchas
  const b64 = x => 'data:image/png;base64,' + fs.readFileSync(x).toString('base64');
  const ok = rep.filter(r => !r.fail), per = 6;
  for (let s = 0; s * per < ok.length; s++) {
    const cells = ok.slice(s * per, s * per + per).map(r => `<div style="position:relative;display:flex;gap:3px;height:330px;justify-content:center;background:#000"><img src="${b64(OUT + '/' + r.tag + '_before.png')}" style="height:330px;max-width:372px;object-fit:contain"><img src="${b64(OUT + '/' + r.tag + '_after.png')}" style="height:330px;max-width:372px;object-fit:contain"><span style="position:absolute;left:6px;top:4px;color:#fff;font:600 12px sans-serif;text-shadow:0 0 4px #000,0 0 2px #000">${path.basename(r.f)} · antes | depois</span></div>`);
    fs.writeFileSync(OUT + '/_s.html', `<meta charset="utf-8"><body style="margin:0;background:#222;display:grid;grid-template-columns:1fr 1fr;gap:6px">${cells.join('')}</body>`);
    const p2 = await b.newPage({ viewport: { width: 1500, height: 1010 } }); await p2.goto('file:///' + OUT + '/_s.html'); await p2.waitForTimeout(1500); await p2.screenshot({ path: OUT + '/sheet' + s + '.png' }); await p2.close();
  }
  console.log('TOTAL', rep.length, 'falhas', rep.filter(r => r.fail).length, '| erros JS', errs.length, errs.slice(0, 8));
  await b.close();
})();
