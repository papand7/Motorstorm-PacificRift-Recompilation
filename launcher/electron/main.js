// MotorStorm: Pacific Rift launcher (Electron). The game is built on the player's PC from the player's own disc: the
// install service (service/service.js, JSON lines on stdin/stdout, as the NightFire launcher's service) checks the
// player's decrypted EBOOT.elf files by their hashes, lifts the PPU/SPU code, fetches the pinned build tools, builds
// and installs. This window draws its progress, plays the game, edits settings.ini (read by the port at start-up,
// beside the exe, and by its in-game PC Settings page; environment variables win; docs/SETTINGS.md) and makes HD
// textures (texpack.py, Real-ESRGAN). The launcher does not decrypt anything and holds no keys.
// Nothing here carries game content: the game's files, the player's decrypted EBOOT.elf files, the lifted code and
// the built exe stay on the player's PC.
const { app, BrowserWindow, ipcMain, dialog, shell, safeStorage } = require('electron');
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
// Portable: the window's own data (Chromium's caches) goes under ROOT too, not %APPDATA%. The launcher keeps none of
// its state there (launcher.json and settings.ini hold it), so nothing needs to move from an earlier launcher's folder.
app.setPath('userData', path.join(ROOT, 'launcher-data'));
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
const saves = require('./service/saves');   // Import save: the player's PS3 / RPCS3 saves into the port's save folder
const SAVE_BACKUPS = path.join(PLAY, 'saves', 'backups');
// Settings > Launcher updates: the Public / Private channel (update.json) and the Private channel's GitHub token, kept
// only as safeStorage (Windows DPAPI) output in update-token.bin: never in plain text, never logged, never sent to the
// window (updates.js)
const updates = require('./updates');
const UPDATE_PREFS = () => path.join(app.getPath('userData'), 'update.json');
const updateTokens = () => updates.tokenStore(path.join(app.getPath('userData'), 'update-token.bin'), safeStorage);
let lastUpdate = null;   // the last check's result (its release page is the only one 'update:open' opens)

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
// its result file and quits by itself; the page then shows BENCH_DIR\<mode>.json (fly: two runs, Happy Jungle then
// Wildfire, combined by bench.runSteps). Nothing of the player's settings changes.
let benchMode = null;   // the benchmark running now
let benchStep = null;   // its run now: { index, count, map: the fly map's name, retry }
let benchStopped = false;   // Stop pressed during a benchmark: the run now ends, the next ones do not start
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
    return { installed: installed(), playing: !!(game || dumper || benchMode), running: benchMode, step: benchStep, modes: bench.MODES, results: benchResults(),
             host: { cpu: (os.cpus()[0] || {}).model || '', ram_bytes: os.totalmem() } };   // fallbacks when the game names none
}
function runBench(mode) {
    if (!bench.MODES[mode]) return { ok: false, message: 'Unknown benchmark.' };
    if (game || dumper || collector) return { ok: false, message: 'The game is already running: close it first.' };
    if (svcState && svcState.busy) return { ok: false, message: 'The install is running: wait for it to finish.' };
    if (!buildOf('stable')) return { ok: false, message: 'Install the game first (Install page).' };
    if (benchMode) return { ok: false, message: 'A benchmark is already running.' };
    // the steps (bench.benchSteps: fly = one game run per map, one after the other; race = one run), each run's result
    // in BENCH_DIR\<step file>, the benchmark's own (fly: the maps combined) in BENCH_DIR\<mode>.json
    const out = path.join(BENCH_DIR, `${mode}.json`);
    const steps = bench.benchSteps(mode);
    try {
        fs.mkdirSync(BENCH_DIR, { recursive: true });
        fs.rmSync(out, { force: true });
        for (const s of steps) fs.rmSync(path.join(BENCH_DIR, s.file), { force: true });
        if (mode === 'race') {
            const files = gameFiles();
            if (!files || !fs.existsSync(files)) return { ok: false, message: 'The game files are not set: install the game first.' };
            bench.prepareRace(files, bench.overlayDir(startEnv('stable'), readCfg(), PLAY));
        }
    } catch (e) { return { ok: false, message: e.message }; }
    benchMode = mode; benchStopped = false; benchStep = null;
    // one game run: resolves when the game has closed, with its result file (or null) and its log (bench.runSteps
    // retries a run whose log shows the start-up Present() Timeout once)
    const runOne = step => new Promise(resolve => {
        const file = path.join(BENCH_DIR, step.file);
        fs.rmSync(file, { force: true });
        let settled = false;
        const done = (code, why) => {
            if (settled) return;
            settled = true;
            game = null;
            let log = '';
            try { log = fs.readFileSync(path.join(PLAY, 'game.log'), 'latin1'); } catch { /* no log */ }
            send('game', { running: false, code });
            resolve({ result: bench.readResult(file), code, why, log });
        };
        try { game = startGame('stable', bench.benchEnv(mode, file, step.boot)); } catch (e) { done(-1, e.message); return; }
        game.on('exit', code => done(code));
        game.on('error', e => done(-1, e.message));
        send('game', { running: true });
    });
    bench.runSteps(mode, {
        runOne,
        cancelled: () => benchStopped,
        onStep: s => { benchStep = { index: s.index, count: s.count, map: s.map && s.map.name, retry: s.retry }; send('bench', { running: mode, step: benchStep }); },
        onResult: (step, r) => {   // each run's own result file (written by the game, or the failure) for the record
            if (step.file !== `${mode}.json`) try { fs.writeFileSync(path.join(BENCH_DIR, step.file), JSON.stringify(r, null, 2)); } catch { /* read-only */ }
        },
    }).catch(e => ({ version: 1, benchmark: mode, ok: false, error: e.message, settings: [] })).then(r => {
        r.at = new Date().toISOString();
        try { fs.writeFileSync(out, JSON.stringify(r, null, 2)); } catch { /* read-only folder */ }
        benchMode = null; benchStep = null;
        send('bench', { running: null, mode, result: r });
    });
    return { ok: true };
}

// ---- textures: the game saves each distinct texture it draws (RSX_TEX_DUMP); texpack.py upscales them
// The scripts run in the launcher's own Python with the pinned numpy and Pillow and Real-ESRGAN, each fetched the
// first time (service/texdeps.js, toolchain.json "textures"); never a system Python. Off Windows: the system's python3.
const texdeps = require('./service/texdeps');
const TOOLS = path.join(ROOT, 'tools');
function prepareTextures(need, onReady, onFail) {
    // a stand-in for the job while its tools download: Stop aborts the download, the page shows it as running
    const ac = new AbortController();
    const job = { kill: () => ac.abort() };
    if (!WIN) {
        setImmediate(() => onReady({ python: 'python3', esrgan: null, env: { ...process.env, PYTHONUTF8: '1', PYTHONUNBUFFERED: '1' } }));
        return job;
    }
    const toolchain = JSON.parse(fs.readFileSync(path.join(RES || path.resolve(__dirname, '..'), 'toolchain.json'), 'utf8'));
    texdeps.ensure({ toolchain, toolsDir: TOOLS, downloadsDir: path.join(ROOT, 'downloads'), need, signal: ac.signal,
                     say: line => send('pack', { line }), log: () => {} })
        .then(t => (ac.signal.aborted ? onFail('Stopped.') : onReady(t)), e => onFail(e.message));
    return job;
}
function runPacker(args) {
    if (packer) return { ok: false, message: 'The HD pack is already being made.' };
    const fail = line => { packer = null; send('pack', { done: true, code: -1, line }); };
    packer = prepareTextures('all', t => {
        const esrgan = t.esrgan ? ['--esrgan', t.esrgan] : [];
        packer = spawn(t.python, [TEXPACK, ...args, ...esrgan], { cwd: PLAY, windowsHide: true, env: t.env });
        const out = line => send('pack', { line });
        readline.createInterface({ input: packer.stdout }).on('line', out);
        readline.createInterface({ input: packer.stderr }).on('line', out);
        packer.on('exit', code => { packer = null; send('pack', { done: true, code }); });
        packer.on('error', e => fail(e.message));
    }, fail);
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
// Python runs it, with numpy (its 32-bit colour textures need it; without it they were skipped). It prints its totals.
function runCollectAll() {
    if (collector) return { ok: false, message: 'Already collecting.' };
    if (game || dumper) return { ok: false, message: 'Close the game first.' };
    const files = gameFiles();
    if (!files || !fs.existsSync(files)) return { ok: false, message: 'The game files are not set: install the game first (or set the disc files folder on the Settings page).' };
    fs.mkdirSync(DUMP, { recursive: true });
    const fail = line => { collector = null; send('pack', { done: true, code: -1, line }); };
    collector = prepareTextures('python', t => {
        collector = spawn(t.python, [TEXCOLLECT, '--play', PLAY, '--game', files], { cwd: PLAY, windowsHide: true, env: t.env });
        const out = line => send('pack', { line });
        readline.createInterface({ input: collector.stdout }).on('line', out);
        readline.createInterface({ input: collector.stderr }).on('line', out);
        collector.on('exit', code => { collector = null; send('pack', { done: true, code, line: code === 0 ? 'Done: the textures are in the dump folder.' : `The collection stopped (exit ${code}).` }); });
        collector.on('error', e => fail(e.message));
    }, fail);
    send('pack', { line: 'Reading your game archive: this takes about a minute (the game is not started).' });
    return { ok: true };
}

// ---- saves: the folder the game keeps them in is the one its start environment names (PS3_GAMEDATA_ROOT, bench.js
// gameEnv), so an import lands where Play's game looks. The last scan stays here: the page names a save by its index.
let saveScan = [];
let saveKeys = null;   // the player's save-tool keys (readKeyFolder), for this session only; never written anywhere
const gamedataRoot = () => startEnv('stable').PS3_GAMEDATA_ROOT;
function savesInfo() {
    const root = gamedataRoot();
    return { folder: saves.savedataDir(root), current: saves.currentSaves(root).map(saves.summary), keys: !!saveKeys,
             backups: saves.listBackups(SAVE_BACKUPS).map(b => ({ name: b.name, dir: b.dir, at: b.at, reason: b.reason, save: b.info && saves.summary(b.info) })),
             found: saveScan.map(saves.summary), playing: !!(game || dumper) };
}
function saveGuard() {
    if (game || dumper) return 'Close the game first: it reads and writes its save while it runs.';
    return null;
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
            // Import save, driven: MS_SHOT_SAVES=<folder> stands in for the folder dialog, MS_SHOT_SAVES_IMPORT=<n> imports
            // the n-th save found (its confirmation answered yes)
            if (process.env.MS_SHOT_SAVES) {
                const step = async (js, name) => {
                    await win.webContents.executeJavaScript(js);
                    await wait(1500);
                    fs.writeFileSync(path.join(process.env.MS_SHOT, `launcher_${name}.png`), (await win.webContents.capturePage()).toPNG());
                };
                await win.webContents.executeJavaScript(`show('play'); window.confirm = () => true; 0`);
                await wait(900);
                await step(`document.querySelector('#save-import').click()`, 'saves_found');
                if (process.env.MS_SHOT_SAVES_IMPORT)
                    await step(`document.querySelector('[data-import="${Number(process.env.MS_SHOT_SAVES_IMPORT)}"]').click()`, 'saves_imported');
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
    const err = settings.save(PLAY, patch.values || {}, patch.keys || {}, patch.playerName);   // playerName: undefined = unchanged
    if (err) return { ok: false, message: err };
    // paths stay in motorstorm.cfg
    const cfg = {};
    if (patch.files) cfg.PS3_VFS_ROOT = patch.files;   // the disc files folder the game reads from (overrides the install's)
    if (patch.clearFiles) cfg.PS3_VFS_ROOT = (playInfo() || {}).vfs_root || '';   // back to the install's
    if (Object.keys(cfg).length) writeCfg(cfg);
    return { ok: true, ...settingsState() };
});
ipcMain.handle('experimental:load', () => ({ items: settings.experimentalLoad(PLAY) }));
ipcMain.handle('experimental:save', (_, values) => {
    if (game || dumper) return { ok: false, message: 'Close the game first: it reads these settings when it starts.' };
    const err = settings.experimentalSave(PLAY, values || {});
    return err ? { ok: false, message: err } : { ok: true, items: settings.experimentalLoad(PLAY) };
});
ipcMain.handle('game:play', (_, which) => play('stable'));
ipcMain.handle('game:stop', () => { if (benchMode) benchStopped = true; if (game) game.kill(); return { ok: true }; });
ipcMain.handle('bench:info', () => benchInfo());
ipcMain.handle('bench:run', (_, mode) => runBench(mode));
ipcMain.handle('textures:info', () => texturesInfo());
ipcMain.handle('saves:info', () => savesInfo());
ipcMain.handle('saves:scan', async () => {
    const shot = !app.isPackaged && process.env.MS_SHOT && process.env.MS_SHOT_SAVES;   // a test's pictures (createWindow)
    const r = shot ? { canceled: false, filePaths: [shot] }
                   : await dialog.showOpenDialog(win, { title: 'Choose a save: its folder, or a folder above it (USB PS3\\SAVEDATA, RPCS3 dev_hdd0)', properties: ['openDirectory'] });
    if (r.canceled) return { ok: false, message: '' };
    saveScan = saves.findSaves(r.filePaths[0]);
    return { ok: true, picked: r.filePaths[0], ...savesInfo() };
});
ipcMain.handle('saves:keys', async () => {
    const r = await dialog.showOpenDialog(win, { title: 'Choose your save tool folder (pfdtool or Bruteforce Save Data: global.conf and games.conf)', properties: ['openDirectory'] });
    if (r.canceled) return { ok: false, message: '' };
    try { saveKeys = saves.readKeyFolder(r.filePaths[0]); } catch (e) { return { ok: false, message: e.message }; }
    return { ok: true, ...savesInfo() };
});
ipcMain.handle('saves:import', (_, index) => {
    const busy = saveGuard();
    if (busy) return { ok: false, message: busy };
    const found = saveScan[index];
    if (!found) return { ok: false, message: 'Choose the save again.' };
    try {
        const fresh = saves.inspectSave(found.path);   // as it is now (it may have changed since the scan)
        const r = saves.importSave(fresh, { gamedataRoot: gamedataRoot(), backupsRoot: SAVE_BACKUPS, keys: saveKeys });
        return { ok: true, result: r, ...savesInfo() };
    } catch (e) { return { ok: false, message: e.message }; }
});
ipcMain.handle('saves:restore', (_, name) => {
    const busy = saveGuard();
    if (busy) return { ok: false, message: busy };
    try { return { ok: true, result: saves.restoreBackup(String(name), { gamedataRoot: gamedataRoot(), backupsRoot: SAVE_BACKUPS }), ...savesInfo() }; }
    catch (e) { return { ok: false, message: e.message }; }
});
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
function updateInfo() {
    const t = updateTokens(), ch = updates.readPrefs(UPDATE_PREFS()).channel;
    return { version: app.getVersion(), channel: ch, channels: Object.entries(updates.CHANNELS).map(([id, c]) => ({ id, label: c.label, repo: c.repo })),
             hasToken: t.has(), encryption: t.available(), last: lastUpdate };
}
ipcMain.handle('update:info', () => updateInfo());
ipcMain.handle('update:channel', (_, ch) => {
    updates.writePrefs(UPDATE_PREFS(), { channel: ch });
    lastUpdate = null;
    return { ok: true, ...updateInfo() };
});
// the token comes from the window once and goes straight into safeStorage; only { ok, message } goes back
ipcMain.handle('update:token', (_, token) => {
    try { updateTokens().save(token); lastUpdate = null; return { ok: true, ...updateInfo() }; }
    catch (e) { return { ok: false, message: updates.scrub(e.message, typeof token === 'string' ? token.trim() : ''), ...updateInfo() }; }
});
ipcMain.handle('update:forget', () => { updateTokens().clear(); lastUpdate = null; return { ok: true, ...updateInfo() }; });
// auto: the launcher's own check at start (the Private channel only; Public makes none, as before)
ipcMain.handle('update:check', async (_, auto) => {
    const ch = updates.readPrefs(UPDATE_PREFS()).channel;
    if (auto && ch !== 'private') return { status: 'off', channel: ch };
    let token = null;
    if (updates.CHANNELS[ch].token) {
        const t = updateTokens();
        token = t.load();
        if (!token && t.has()) {
            lastUpdate = { status: 'bad-token', channel: ch, message: 'The stored access token cannot be read on this Windows account. Enter it again under Settings > Launcher updates. No update check was made.' };
            return lastUpdate;
        }
    }
    lastUpdate = await updates.checkForUpdate({ channel: ch, currentVersion: app.getVersion(), token });
    return lastUpdate;
});
ipcMain.handle('update:open', () => {
    if (!lastUpdate || lastUpdate.status !== 'available') return { ok: false, message: 'Check for updates first.' };
    shell.openExternal(lastUpdate.update.url);   // a https://github.com/<channel repo>/releases/ page (updates.selectUpdate)
    return { ok: true };
});
ipcMain.handle('open', (_, what) => shell.openPath(
    what === 'textures' ? path.join(PLAY, 'textures') : what === 'saves' ? saves.savedataDir(gamedataRoot()) : what === 'log' ? path.join(ROOT, 'launcher.log') : what === 'root' ? ROOT : PLAY));

app.whenReady().then(() => { fs.mkdirSync(ROOT, { recursive: true }); createWindow(); startService(); });
app.on('before-quit', () => {
    app.isQuitting = true;
    if (game) game.kill();
    if (svc) { command({ cmd: 'quit' }); svc.stdin.end(); }
});
app.on('window-all-closed', () => app.quit());
