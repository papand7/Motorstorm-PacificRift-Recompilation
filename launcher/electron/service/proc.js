// A child process whose output lines go to the log; its exit code back. Running ones are remembered so Stop can end
// them (the whole tree on Windows: cmake's and ninja's compilers too).
'use strict';
const { spawn } = require('child_process');
const readline = require('readline');

const running = new Set();

function run(cmd, args, { cwd, env, log, onLine, stdin, windowsVerbatimArguments } = {}) {
    return new Promise(resolve => {
        let child;
        try {
            child = spawn(cmd, args, { cwd, env, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'], windowsVerbatimArguments });
        } catch (e) {
            if (log) log(`${cmd}: ${e.message}`);
            return resolve(-1);
        }
        running.add(child);
        const line = l => { if (log) log(l); if (onLine) onLine(l); };
        readline.createInterface({ input: child.stdout }).on('line', line);
        readline.createInterface({ input: child.stderr }).on('line', line);
        child.stdin.on('error', () => {});
        if (stdin != null) child.stdin.write(stdin);
        child.stdin.end();
        child.on('error', e => { if (log) log(`${cmd}: ${e.message}`); });
        child.on('close', code => { running.delete(child); resolve(code == null ? -1 : code); });
    });
}

function killAll() {
    for (const c of running) {
        if (process.platform === 'win32') spawn('taskkill', ['/pid', String(c.pid), '/T', '/F'], { windowsHide: true });
        else { try { c.kill(); } catch { /* gone */ } }
    }
}

module.exports = { run, killAll };
