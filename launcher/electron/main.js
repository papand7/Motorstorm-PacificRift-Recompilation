// MotorStorm: Pacific Rift launcher (Electron). The game is built on the player's PC from the player's own disc: the
// install service (service/service.js, JSON lines on stdin/stdout, as the NightFire launcher's service) checks the
// player's decrypted EBOOT.elf files by their hashes, lifts the PPU/SPU code, fetches the pinned build tools, builds
// and installs. This window draws its progress, plays the game, edits settings.ini (read by the port at start-up,
// beside the exe, and by its in-game PC Settings page; environment variables win; docs/SETTINGS.md) and makes HD
// textures (texpack.py, Real-ESRGAN). The launcher does not decrypt anything and holds no keys.
// Nothing here carries game content: the game's files, the player's decrypted EBOOT.elf files, the lifted code and
// the built exe stay on the player's PC.
const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const WIN = process.platform === 'win32';
const EXE = 'MotorStormPacificRiftRecomp' + (WIN ? '.exe' : '');
// the folder the launcher lives in (a portable exe runs from a temporary copy: PORTABLE_EXECUTABLE_DIR is the real one)
const LAUNCHER_DIR = process.env.PORTABLE_EXECUTABLE_DIR ||
    (app.isPackaged ? path.dirname(app.getPath('exe')) : (process.env.MS_LAUNCHER_DIR || path.resolve(__dirname, '..', 'dev')));
const ROOT = path.join(LAUNCHER_DIR, 'MotorStorm');          // everything the launcher makes
const PLAY = path.join(ROOT, 'play');                          // the installed game: exe, DLLs, motorstorm.cfg
const CFG = path.join(PLAY, 'motorstorm.cfg');
const DUMP = path.join(PLAY, 'textures', 'dump');
const PACK = path.join(PLAY, 'textures', 'pack');
const RES = app.isPackaged ? process.resourcesPath : null;
const TEXPACK = RES ? path.join(RES, 'tools', 'texpack.py')
                    : path.resolve(__dirname, '..', '..', 'generated', 'analysis', 'vksync', 'tools', 'texpack.py');
// developer-only: "install from a built folder" (copies a build made elsewhere: never in a launcher for players, since
// such a folder holds the lifted game code). On in an unpackaged launcher, or with MS_DEV_INSTALL=1.
const DEV = !app.isPackaged || process.env.MS_DEV_INSTALL === '1';

const settings = require('./settings');   // settings.ini (the player's) and motorstorm.cfg (paths, diagnostics)
const bench = require('./bench');         // the Benchmark page: start environment, the race config, the result
const os = require('os');
const BENCH_DIR = path.join(PLAY, 'benchmark');   // the game's result files, <mode>.json

let win = null;
let svc = null;        // the install service
let svcState = null;   // its last state event
let game = null;       // the running game process
let dumper = null;     // the game running to save its textures
let packer = null;     // texpack.py making the pack
let packOpts = null;   // its { scale, pbr }
let collector = null;  // texcollect.py saving every texture from the player's archive (no game running)
const TEXCOLLECT = RES ? path.join(RES, 'tools', 'texcollect', 'texcollect.py')
                       : path.resolve(__dirname, '..', '..', 'tools', 'texcollect', 'texcollect.py');

const send = (channel, data) => { if (win && !win.isDestroyed()) win.webContents.send(channel, data); };

// ---- the install service: run by this same exe as Node (ELECTRON_RUN_AS_NODE), so it needs nothing installed
function startService() {
    const script = path.join(__dirname, 'service', 'service.js');
    const source = RES ? path.join(RES, 'source') : path.resolve(__dirname, '..', '..', 'build', 'launcher-source');
    const meta = RES ? RES : path.resolve(__dirname, '..');   // game.json and toolchain.json
    svc = spawn(process.execPath, [script, '--root', ROOT, '--meta', meta, '--source', source],
                { windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'], env: { ...process.env, ELECTRON_RUN_AS_NODE: '1' } });
    readline.createInterface({ input: svc.stdout }).on('line', line => {
        let ev;
        try { ev = JSON.parse(line); } catch { return; }
        if (ev.ev === 'state') svcState = ev;
        send('svc', ev);
    });
    readline.createInterface({ input: svc.stderr }).on('line', line => send('svc', { ev: 'log', line }));
    svc.on('error', e => send('svc', { ev: 'error', message: `The install service did not start: ${e.message}` }));
    svc.on('exit', code => { svc = null; if (!app.isQuitting) send('svc', { ev: 'error', message: `The install service stopped (exit ${code}).` }); });
}
function command(cmd) { if (svc && svc.stdin.writable) svc.stdin.write(JSON.stringify(cmd) + '\n'); }

const readCfg = () => settings.readCfg(CFG);
const writeCfg = patch => settings.writeCfg(CFG, patch);
function settingsState() { return { ...settings.load(PLAY), texturePack: PACK, installed: installed() }; }

// the installed game: play\play.json names each build (stable 1.00): its exe, the
// player's decrypted EBOOT.elf it runs, and the environment it starts with
function playInfo() {
    try { return JSON.parse(fs.readFileSync(path.join(PLAY, 'play.json'), 'utf8')); } catch { return null; }
}
function buildOf(name) {
    const p = playInfo();
    const b = p && p.builds && p.builds[name];
    return b && fs.existsSync(path.join(PLAY, b.exe)) && b.elf && fs.existsSync(b.elf) ? b : null;
}
// the builds that can be played: stable (1.00) is required
function builds() {
    return { stable: !!buildOf('stable') };
}
function installed() { return !!buildOf('stable'); }

// ---- developer-only install: copy a folder built elsewhere (the exe and its DLLs) as the stable build. The decrypted
// ELF is chosen beside it.
function copyBuild(from) {
    fs.mkdirSync(PLAY, { recursive: true });
    if (!fs.existsSync(path.join(from, EXE))) throw new Error(`${EXE} is not in that folder`);
    const copied = [];
    for (const name of fs.readdirSync(from)) {
        if (name === EXE || /\.dll$/i.test(name)) {
            fs.copyFileSync(path.join(from, name), path.join(PLAY, name));
            copied.push(name);
        }
    }
    return copied;
}

// ---- playing: the chosen build in its folder, its decrypted EBOOT.elf as the argument, its own start environment
// (from play.json), its settings from settings.ini (paths from motorstorm.cfg)
// (bench.js gameEnv: the same composition for Play and the benchmarks, which add only bench.BENCH_KEYS)
function startEnv(which, extraEnv = {}) {
    return bench.gameEnv({ processEnv: process.env, build: buildOf(which), cfg: readCfg(), play: playInfo(), playDir: PLAY }, extraEnv);
}
function startGame(which, extraEnv) {
    const b = buildOf(which);
    const env = startEnv(which, extraEnv);
    // the launcher's icon for the game window (the game looks for game.ico beside its exe)
    try { fs.copyFileSync(path.join(__dirname, 'assets', 'icon.ico'), path.join(PLAY, 'game.ico')); } catch { /* no icon */ }
    // the game's own log (stdout and stderr), replaced each run, for reports and tuning
    let out = 'ignore';
    try { out = fs.openSync(path.join(PLAY, 'game.log'), 'w'); } catch { /* read-only folder: no log */ }
    const child = spawn(path.join(PLAY, b.exe), [b.elf], { cwd: PLAY, env, windowsHide: false, stdio: ['ignore', out, out] });
    if (typeof out === 'number') fs.closeSync(out);
    return child;
}
function play(which = 'stable') {
    if (game || dumper) return { ok: false, message: 'The game is already running.' };
    if (svcState && svcState.busy) return { ok: false, message: 'The install is running: wait for it to finish.' };
    if (!buildOf(which)) return { ok: false, message: 'Install the game first (Install page).' };
    game = startGame(which, {});
    game.on('exit', code => { game = null; send('game', { running: false, code }); });
    game.on('error', e => { game = null; send('game', { running: false, code: -1, message: e.message }); });
    send('game', { running: true });
    return { ok: true };
}

// ---- benchmarks: the stable build started as Play starts it, plus bench.BENCH_KEYS. The game measures, writes
// BENCH_DIR\<mode>.json and quits by itself; the page then shows that file. Nothing of the player's settings changes.
let benchMode = null;   // the benchmark running now
function benchResults() {
    const out = {};
    for (const m of Object.keys(bench.MODES)) {
        const f = path.join(BENCH_DIR, `${m}.json`);
        out[m] = bench.readResult(f);
        if (out[m]) try { out[m].at = fs.statSync(f).mtime.toISOString(); } catch { /* gone */ }
    }
    return out;
}
function benchInfo() {
    return { installed: installed(), playing: !!(game || dumper), running: benchMode, modes: bench.MODES, results: benchResults(),
             host: { cpu: (os.cpus()[0] || {}).model || '', ram_bytes: os.totalmem() } };   // fallbacks when the game names none
}
function runBench(mode) {
    if (!bench.MODES[mode]) return { ok: false, message: 'Unknown benchmark.' };
    if (game || dumper || collector) return { ok: false, message: 'The game is already running: close it first.' };
    if (svcState && svcState.busy) return { ok: false, message: 'The install is running: wait for it to finish.' };
    if (!buildOf('stable')) return { ok: false, message: 'Install the game first (Install page).' };
    const out = path.join(BENCH_DIR, `${mode}.json`);
    try {
        fs.mkdirSync(BENCH_DIR, { recursive: true });
        fs.rmSync(out, { force: true });
        if (mode === 'race') {
            const files = gameFiles();
            if (!files || !fs.existsSync(files)) return { ok: false, message: 'The game files are not set: install the game first.' };
            bench.prepareRace(files, bench.overlayDir(startEnv('stable'), readCfg(), PLAY));
        }
    } catch (e) { return { ok: false, message: e.message }; }
    const started = Date.now();
    game = startGame('stable', bench.benchEnv(mode, out));
    benchMode = mode;
    const done = (code, why) => {
        game = null; benchMode = null;
        let r = bench.readResult(out);
        if (!r) {   // the game closed without a result (stopped, or it failed before it could write one)
            r = { version: 1, benchmark: mode, ok: false, error: why || `The game closed without a result (exit code ${code}).`, settings: [] };
            try { fs.writeFileSync(out, JSON.stringify(r, null, 2)); } catch { /* read-only folder */ }
        }
        r.duration_s = Math.round((Date.now() - started) / 1000);
        r.at = new Date().toISOString();
        send('game', { running: false, code });
        send('bench', { running: null, mode, result: r });
    };
    game.on('exit', code => done(code));
    game.on('error', e => done(-1, e.message));
    send('game', { running: true });
    send('bench', { running: mode });
    return { ok: true };
}

// ---- textures: the game saves each distinct texture it draws (RSX_TEX_DUMP); texpack.py upscales them
function pythonCommand() {
    // the build's own Python (the launcher's tools folder), else the system's
    const own = path.join(ROOT, 'tools', 'python', 'python.exe');
    if (WIN && fs.existsSync(own)) return { cmd: own, pre: [] };
    return WIN ? { cmd: 'py', pre: ['-3'] } : { cmd: 'python3', pre: [] };
}
function runPacker(args) {
    if (packer) return { ok: false, message: 'The HD pack is already being made.' };
    const py = pythonCommand();
    packer = spawn(py.cmd, [...py.pre, TEXPACK, ...args], { cwd: PLAY, windowsHide: true, env: { ...process.env, PYTHONUTF8: '1', PYTHONUNBUFFERED: '1' } });
    const out = line => send('pack', { line });
    readline.createInterface({ input: packer.stdout }).on('line', out);
    readline.createInterface({ input: packer.stderr }).on('line', out);
    packer.on('exit', code => { packer = null; send('pack', { done: true, code }); });
    packer.on('error', e => { packer = null; send('pack', { done: true, code: -1, line: `${e.message} (Python with numpy and Pillow is needed)` }); });
    return { ok: true };
}
function texturesInfo() {
    const count = dir => { try { return fs.readdirSync(dir).filter(n => /\.dds$/i.test(n)).length; } catch { return 0; } };
    return { dumped: count(DUMP), pack: count(PACK), folder: PACK, playing: !!game, making: !!packer, collecting: !!dumper, collectingAll: !!collector,
             packOpts: packer ? packOpts : null };   // the running job's Size / PBR, so the page shows what it is making
}
// the game's files (the folder holding MS2.PSARC): the install's file root, or the one the player set
function gameFiles() {
    const p = playInfo();
    return readCfg().PS3_VFS_ROOT || (p && p.vfs_root) || '';
}
// "Collect all textures": texcollect.py on the player's own MS2.PSARC (the game does not start); the launcher's
// Python runs it (it uses the standard library only). It prints its totals when it ends.
function runCollectAll() {
    if (collector) return { ok: false, message: 'Already collecting.' };
    if (game || dumper) return { ok: false, message: 'Close the game first.' };
    const files = gameFiles();
    if (!files || !fs.existsSync(files)) return { ok: false, message: 'The game files are not set: install the game first (or set the disc files folder on the Settings page).' };
    const py = pythonCommand();
    fs.mkdirSync(DUMP, { recursive: true });
    collector = spawn(py.cmd, [...py.pre, TEXCOLLECT, '--play', PLAY, '--game', files], { cwd: PLAY, windowsHide: true, env: { ...process.env, PYTHONUTF8: '1' } });
    const out = line => send('pack', { line });
    readline.createInterface({ input: collector.stdout }).on('line', out);
    readline.createInterface({ input: collector.stderr }).on('line', out);
    collector.on('exit', code => { collector = null; send('pack', { done: true, code, line: code === 0 ? 'Done: the textures are in the dump folder.' : `The collection stopped (exit ${code}).` }); });
    collector.on('error', e => { collector = null; send('pack', { done: true, code: -1, line: `${e.message}` }); });
    send('pack', { line: 'Reading your game archive: this takes about a minute (the game is not started).' });
    return { ok: true };
}

function createWindow() {
    win = new BrowserWindow({
        width: 1120, height: 760, minWidth: 920, minHeight: 620, backgroundColor: '#f7ecd7', show: false,
        title: 'MotorStorm: Pacific Rift',
        icon: path.join(__dirname, 'assets', 'icon.png'),
        webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, sandbox: true },
    });
    win.removeMenu();
    win.loadFile(path.join(__dirname, 'ui', 'index.html'));
    win.once('ready-to-show', () => win.show());
    win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: 'deny' }; });
    // a test's pictures (not in a packaged launcher): MS_SHOT=<folder>, each page in turn, then quit
    if (process.env.MS_SHOT && !app.isPackaged) {
        win.webContents.once('did-finish-load', async () => {
            const wait = ms => new Promise(r => setTimeout(r, ms));
            await wait(2000);
            for (const page of (process.env.MS_SHOT_PAGES || 'play,install,settings,textures,benchmark,log').split(',')) {
                await win.webContents.executeJavaScript(`show(${JSON.stringify(page)})`);
                await wait(900);
                const img = await win.webContents.capturePage();
                fs.writeFileSync(path.join(process.env.MS_SHOT, `launcher_${page}.png`), img.toPNG());
            }
            app.quit();
        });
    }
}

ipcMain.handle('state', () => ({ dir: PLAY, root: ROOT, installed: installed(), builds: builds(), playing: !!game, dev: DEV, svc: svcState, play: playInfo() }));
ipcMain.on('svc', (_, cmd) => {
    // a build would replace the exe the game runs from
    if (cmd && cmd.cmd === 'install' && (game || dumper)) { send('svc', { ev: 'error', message: 'Close the game first.' }); return; }
    command(cmd);
});
ipcMain.handle('dev:install', async () => {
    if (!DEV) return { ok: false, message: 'Not in this launcher.' };
    if (game || dumper) return { ok: false, message: 'Close the game first.' };
    const r = await dialog.showOpenDialog(win, { title: 'Developer: choose the folder with the built game', properties: ['openDirectory'] });
    if (r.canceled) return { ok: false, message: 'Cancelled.' };
    const e = await dialog.showOpenDialog(win, { title: 'Developer: choose the decrypted EBOOT (.elf) the build was lifted from',
                                                 properties: ['openFile'], filters: [{ name: 'ELF', extensions: ['elf'] }] });
    if (e.canceled) return { ok: false, message: 'Cancelled.' };
    try {
        const copied = copyBuild(r.filePaths[0]);
        const prev = playInfo() || {};
        const stable = { label: 'Stable', version: '1.00', exe: EXE, elf: e.filePaths[0], env: {} };
        fs.writeFileSync(path.join(PLAY, 'play.json'), JSON.stringify({ ...prev, default: 'stable', builds: { ...(prev.builds || {}), stable }, dev: true }, null, 2));
        return { ok: true, copied };
    } catch (err) { return { ok: false, message: err.message }; }
});
ipcMain.handle('pick', async (_, kind) => {
    const opts = {
        iso: { title: 'Choose your MotorStorm: Pacific Rift disc image', properties: ['openFile'], filters: [{ name: 'PS3 disc image', extensions: ['iso'] }] },
        folder: { title: 'Choose the folder with PS3_GAME in it (your copied disc)', properties: ['openDirectory'] },
        elf: { title: 'Choose your decrypted EBOOT.elf', properties: ['openFile'], filters: [{ name: 'ELF', extensions: ['elf'] }] },
        files: { title: "Choose the game's disc files folder", properties: ['openDirectory'] },
    }[kind] || { title: 'Choose a folder', properties: ['openDirectory'] };
    const r = await dialog.showOpenDialog(win, opts);
    return r.canceled ? null : r.filePaths[0];
});
ipcMain.handle('settings:load', () => settingsState());
ipcMain.handle('settings:save', (_, patch) => {
    if (game || dumper) return { ok: false, message: 'Close the game first: it reads these settings when it starts.' };
    // the player's settings into settings.ini (labels; the game's own PC Settings page edits the same file)
    const err = settings.save(PLAY, patch.values || {}, patch.keys || {});
    if (err) return { ok: false, message: err };
    // paths stay in motorstorm.cfg
    const cfg = {};
    if (patch.files) cfg.PS3_VFS_ROOT = patch.files;   // the disc files folder the game reads from (overrides the install's)
    if (patch.clearFiles) cfg.PS3_VFS_ROOT = (playInfo() || {}).vfs_root || '';   // back to the install's
    if (Object.keys(cfg).length) writeCfg(cfg);
    return { ok: true, ...settingsState() };
});
ipcMain.handle('game:play', (_, which) => play('stable'));
ipcMain.handle('game:stop', () => { if (game) game.kill(); return { ok: true }; });
ipcMain.handle('bench:info', () => benchInfo());
ipcMain.handle('bench:run', (_, mode) => runBench(mode));
ipcMain.handle('textures:info', () => texturesInfo());
ipcMain.handle('textures:collect', () => {
    if (game || dumper) return { ok: false, message: 'Close the game first.' };
    if (!installed()) return { ok: false, message: 'Install the game first.' };
    fs.mkdirSync(DUMP, { recursive: true });
    dumper = startGame('stable', { RSX_TEX_DUMP: DUMP });   // the texture collection runs the stable build
    dumper.on('exit', () => { dumper = null; send('pack', { done: true, code: 0, line: 'Stopped collecting: play a few races, then make the pack.' }); });
    dumper.on('error', e => { dumper = null; send('pack', { done: true, code: -1, line: e.message }); });
    send('pack', { line: 'Collecting textures: play a few races. Each texture is saved the first time the game draws it.' });
    return { ok: true };
});
ipcMain.handle('textures:pack', (_, o) => {
    if (dumper || collector) return { ok: false, message: 'Stop collecting first.' };
    fs.mkdirSync(PACK, { recursive: true });
    const args = ['upscale', '--dump', DUMP, '--pack', PACK, '--scale', String(o.scale === 2 ? 2 : 4)];
    if (o.pbr) args.push('--pbr');
    const r = runPacker(args);
    if (r.ok) packOpts = { scale: o.scale === 2 ? 2 : 4, pbr: !!o.pbr };
    return r;
});
ipcMain.handle('textures:collectall', () => runCollectAll());
ipcMain.handle('textures:stop', () => {
    if (collector) collector.kill();
    if (dumper) dumper.kill();
    if (packer) packer.kill();
    return { ok: true };
});
ipcMain.handle('open', (_, what) => shell.openPath(
    what === 'textures' ? path.join(PLAY, 'textures') : what === 'log' ? path.join(ROOT, 'launcher.log') : what === 'root' ? ROOT : PLAY));

app.whenReady().then(() => { fs.mkdirSync(ROOT, { recursive: true }); createWindow(); startService(); });
app.on('before-quit', () => {
    app.isQuitting = true;
    if (game) game.kill();
    if (svc) { command({ cmd: 'quit' }); svc.stdin.end(); }
});
app.on('window-all-closed', () => app.quit());
