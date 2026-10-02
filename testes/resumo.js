// Resume o report.json da bateria: tempos e quais regras entraram em cada foto.
const fs = require('fs');
const r = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const ok = r.filter(x => !x.fail), med = a => { const s = [...a].sort((x, y) => x - y); return s[s.length >> 1]; };
console.log('fotos', r.length, '| falhas', r.length - ok.length, '| tela (mediana)', med(ok.map(x => x.tShow)), 'ms | IAs de apoio (mediana)', med(ok.map(x => x.tAI)), 'ms | IA Revela (mediana)', med(ok.map(x => x.tm.tom || 0)), 'ms, máx', Math.max(...ok.map(x => x.tm.tom || 0)), 'ms');
const has = (x, re) => x.notes.some(n => re.test(n));
for (const [nome, re] of [['pele acinzentada (cor devolvida)', /acinzentada/], ['luz devolvida às pessoas', /devolvi .* EV de luz/], ['pessoas mais escuras que o cenário', /mais escuras que o cenário/], ['dentes', /^Dentes/], ['olhos', /^Olhos/], ['cena reconhecida', /reconheci na foto/]])
  console.log(nome.padEnd(36), ok.filter(x => has(x, re)).map(x => x.f.split('/')[1].replace(/\.\w+$/, '')).join(', ') || '-');
for (const x of ok) { const p = x.params || {}; if (process.argv[3]) console.log(x.f.padEnd(30), 'contraste', p.contrast, '| vibração', p.vibrance, '| rich', p.rich, '| luz pessoas', p.subjLight); }
