// The install service from a terminal (tests, developers): starts service.js, sends the commands, prints its events.
//   node cli.js --root <work folder> [--meta <dir>] [--source <dir>] [--disc <iso|folder>]
//               [--elf100 <EBOOT.elf of 1.00>] [--agree] [--install [--until <step>]]
// Without --install it only checks (scan) and prints the state.
'use strict';
const { spawn } = require('child_process');
const path = require('path');
const readline = require('readline');

const a = name => { const i = process.argv.indexOf('--' + name); return i > 0 ? process.argv[i + 1] : undefined; };
const has = name => process.argv.includes('--' + name);
const root = a('root');
if (!root) { console.error('usage: node cli.js --root <dir> [--disc p] [--elf100 p] [--agree] [--install [--until step]]'); process.exit(2); }
const args = [path.join(__dirname, 'service.js'), '--root', root];
if (a('meta')) args.push('--meta', a('meta'));
if (a('source')) args.push('--source', a('source'));
const svc = spawn(process.execPath, args, { stdio: ['pipe', 'pipe', 'inherit'] });
const send = c => svc.stdin.write(JSON.stringify(c) + '\n');
let lastStep = '';
let phase = 'set';
readline.createInterface({ input: svc.stdout }).on('line', line => {
    let ev;
    try { ev = JSON.parse(line); } catch { console.log(line); return; }
    if (ev.ev === 'log') console.log('  ' + ev.line);
    else if (ev.ev === 'step') { const s = `${ev.step} ${ev.detail || ''}`; if (s !== lastStep) { lastStep = s; console.log(`[${ev.fraction >= 0 ? Math.round(ev.fraction * 100) + '%' : '..'}] ${s}`); } }
    else if (ev.ev === 'error') console.log(`ERROR ${ev.message}`);
    else if (ev.ev === 'done') { console.log(`DONE ok=${ev.ok} ${ev.message}`); send({ cmd: 'quit' }); }
    else if (ev.ev === 'state') {
        const brief = { busy: ev.busy, built: ev.built, disc: ev.disc, elf100: ev.elf100,
                        steps: ev.steps.map(s => `${s.id}${s.done ? '+' : ''}`).join(' ') };
        console.log('STATE ' + JSON.stringify(brief));
        if (phase === 'scanned' && ev.after === 'set') {
            if (has('install')) { phase = 'installing'; send({ cmd: 'install', agreed: has('agree'), until: a('until') }); }
            else { phase = 'end'; send({ cmd: 'quit' }); }
        }
    }
});
svc.on('exit', code => process.exit(code || 0));
const set = { cmd: 'set' };
for (const k of ['disc', 'elf100']) if (a(k)) set[k] = path.resolve(a(k));
if (has('agree')) set.agreed = true;
send(set);
phase = 'scanned';
process.on('SIGINT', () => { send({ cmd: 'cancel' }); setTimeout(() => process.exit(1), 2000); });
