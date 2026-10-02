// confere a sintaxe do JavaScript embutido no index.html e as quebras de linha
const fs = require('fs');
const p = process.argv[2], s = fs.readFileSync(p, 'utf8');
const m = s.match(/<script>\r?\n([\s\S]*)<\/script>/);
console.log('linhas', s.split('\n').length, '| CR', (s.match(/\r/g) || []).length, '| bytes', Buffer.byteLength(s));
try { new Function(m[1]); console.log('sintaxe ok,', m[1].length, 'caracteres de script'); }
catch (e) { console.log('ERRO de sintaxe:', e.message); process.exit(1); }
