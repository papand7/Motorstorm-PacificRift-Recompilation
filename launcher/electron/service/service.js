// The install service: JSON lines in (commands), JSON lines out (events), as the NightFire launcher's service.
// Run by the launcher's own exe as Node (ELECTRON_RUN_AS_NODE=1), or by node for tests:
//   node service.js --root <work folder> --meta <folder with game.json, toolchain.json> --source <source snapshot folder>
// Commands: {cmd:'state'} {cmd:'set', disc?, elf100?} {cmd:'scan'} {cmd:'install', agreed}
//           {cmd:'autodecrypt', confirmed:true} (RPCS3, after the player's confirmation: autodecrypt.js)
//           {cmd:'cancel'} {cmd:'clean', what:'build'|'all'} {cmd:'quit'}
// Events:   {ev:'state', ...} {ev:'step', step, detail, fraction} {ev:'log', line} {ev:'done', ok, message} {ev:'error', message}
'use strict';
const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { Builder } = require('./builder');

function arg(name, def) {
    const i = process.argv.indexOf('--' + name);
    return i > 0 && process.argv[i + 1] ? process.argv[i + 1] : def;
}

const root = path.resolve(arg('root', path.join(process.cwd(), 'MotorStorm')));
const meta = path.resolve(arg('meta', path.join(__dirname, '..', '..')));
const source = path.resolve(arg('source', path.join(__dirname, '..', '..', '..', 'build', 'launcher-source')));
fs.mkdirSync(root, { recursive: true });

const logFile = path.join(root, 'launcher.log');
const emit = ev => process.stdout.write(JSON.stringify(ev) + '\n');
// one handle for the whole run: a build writes hundreds of thousands of compiler lines, and reopening the file for
// each of them (appendFileSync) is slow on Windows
let logFd = null;
try { logFd = fs.openSync(logFile, 'a'); } catch { /* the log is best effort */ }
const log = (line, { fileOnly = false } = {}) => {
    if (logFd != null) { try { fs.writeSync(logFd, `${new Date().toISOString()} ${line}\n`); } catch { /* best effort */ } }
    if (fileOnly) return;   // compiler warnings: launcher.log only, not the window (Builder.buildLog)
    emit({ ev: 'log', line });
};

const builder = new Builder({ root, meta, source, emit, log });

async function handle(cmd) {
    switch (cmd.cmd) {
        case 'state': return builder.sendState();
        case 'set': return builder.set(cmd);
        case 'scan': return builder.scan();
        case 'install': return builder.install(cmd);
        case 'cancel': return builder.cancel();
        case 'clean': return builder.clean(cmd.what);
        case 'autodecrypt': return builder.autoDecrypt(cmd);
        case 'quit': builder.cancel(); setTimeout(() => process.exit(0), 200); return;
        default: emit({ ev: 'error', message: `unknown command ${cmd.cmd}` });
    }
}

readline.createInterface({ input: process.stdin }).on('line', line => {
    let cmd;
    try { cmd = JSON.parse(line); } catch { return; }
    handle(cmd).catch(e => { log(`error: ${e.stack || e.message}`); emit({ ev: 'error', message: e.message }); });
});
process.stdin.on('end', () => { builder.cancel(); setTimeout(() => process.exit(0), 200); });
log(`service: root ${root}, meta ${meta}, source ${source}`);
builder.scan().catch(e => emit({ ev: 'error', message: e.message }));
