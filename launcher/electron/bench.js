// The Benchmark page's launcher side. The game runs each benchmark itself (port-vkgame/bench_run.h, MSPR_BENCH): it
// measures, writes a JSON result and quits. The launcher only starts it the way Play does, plus the benchmark's own
// variables, and reads the result.
//   fly   the disc's own benchmark configs, one game run each, one after the other (FLY_MAPS): a camera flight over
//         Happy Jungle (configs/benchmark_happyJungle.cfg), then one over the lava track Wildfire
//         (configs/benchmark_Wildfire.cfg), no cars. The launcher combines the two results (combineFly).
//   race  a 16-car race on Kanaloa Bay with the game's AI driving every car, yours included. Its config is made here at
//         run time from the player's own disc (MS2.PSARC configs/aggression_race.cfg and benchmark_happyJungle.cfg),
//         by a few edits whose result is checked against the SHA-256 of the tested config (raceCfgFromDisc); nothing
//         of the game is carried by the launcher. It goes into the overlay folder the game already reads (PS3_VFS_OVERLAY,
//         the PC Settings pages' folder), so the start environment does not change apart from BENCH_KEYS.
// The player's settings are never touched: settings.ini is read by the game as on Play, and none of BENCH_KEYS is a
// variable settings.ini owns (the game skips a setting whose variable is already set: test_bench.js checks this).
'use strict';
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const crypto = require('crypto');

// the only variables a benchmark adds to Play's start environment
const BENCH_KEYS = ['MSPR_BENCH', 'MSPR_BENCH_OUT', 'PS3_DEV_GUEST_STR'];
// the boot config's pointer in the 1.00 ELF (0x0109AD4C -> "configs/ms2_config.cfg"); the game refuses another image
const GUEST_STR = '0109AD4C:configs/ms2_config.cfg:';
const RACE_CFG = 'configs/mspr_bench_race.cfg';
// SHA-256 of the race config this makes (line ends as LF): the config the race benchmark was tested with
const RACE_CFG_SHA256 = 'ad53497b0901ee9f2956f00e16ad68adcdeafdd6eb148be1e0706851eefe6a85';
// fly: the maps, in the order they run; each run's result is BENCH_DIR\fly_<id>.json, the combined one fly.json
const FLY_MAPS = [
    { id: 'happyJungle', name: 'Happy Jungle', boot: 'configs/benchmark_happyJungle.cfg' },
    { id: 'wildfire', name: 'Wildfire', boot: 'configs/benchmark_Wildfire.cfg' },
];
const MODES = {
    fly: { title: 'Fly-through', maps: FLY_MAPS },
    race: { title: 'Race with AI racers', boot: RACE_CFG },
};
// the game runs a benchmark makes, in order: [{ map: null | a FLY_MAPS entry, boot, file: the run's result file name }]
function benchSteps(mode) {
    if (!MODES[mode]) throw new Error(`unknown benchmark ${mode}`);
    if (MODES[mode].maps) return MODES[mode].maps.map(m => ({ map: m, boot: m.boot, file: `${mode}_${m.id}.json` }));
    return [{ map: null, boot: MODES[mode].boot, file: `${mode}.json` }];
}
// the start-up failure a run is retried once for: the game closed without a result and its log has this line
const BOOT_TIMEOUT_LINE = 'GcKernel::Present() Timeout';

// ---- a PSARC (zlib blocks; entry 0 lists the member names; members are found by the MD5 of the upper-case name)
function readPsarcMembers(file, names) {
    const fd = fs.openSync(file, 'r');
    try {
        const read = (pos, n) => { const b = Buffer.alloc(n); const got = fs.readSync(fd, b, 0, n, pos); return got === n ? b : b.subarray(0, got); };
        const head = read(0, 32);
        if (head.toString('latin1', 0, 4) !== 'PSAR' || head.toString('latin1', 8, 12) !== 'zlib') throw new Error('not a zlib PSARC');
        const tocLen = head.readUInt32BE(12), entryLen = head.readUInt32BE(16), count = head.readUInt32BE(20), block = head.readUInt32BE(24);
        if (entryLen !== 30) throw new Error('unexpected PSARC entry length');
        const toc = read(32, count * 30);
        const blocks = read(32 + count * 30, tocLen - 32 - count * 30);
        const member = i => {
            const e = toc.subarray(i * 30, i * 30 + 30);
            const z = e.readUInt32BE(16);
            const size = e.readUIntBE(20, 5), off = e.readUIntBE(25, 5);
            const parts = [];
            let pos = off, have = 0;
            for (let k = 0; have < size; k++) {
                const n = blocks.readUInt16BE((z + k) * 2) || block;
                let c = read(pos, n);
                pos += n;
                if (n !== block) { try { c = zlib.inflateSync(c); } catch { /* a block stored raw */ } }
                parts.push(c);
                have += c.length;
            }
            return Buffer.concat(parts).subarray(0, size);
        };
        const byHash = new Map();
        for (let i = 0; i < count; i++) byHash.set(toc.toString('hex', i * 30, i * 30 + 16), i);
        const out = {};
        for (const n of names) {
            const i = byHash.get(crypto.createHash('md5').update(n.toUpperCase(), 'latin1').digest('hex'));
            if (i === undefined) throw new Error(`${n} is not in the archive`);
            out[n] = member(i);
        }
        return out;
    } finally { fs.closeSync(fd); }
}

// ---- the race config from the disc's: the aggression race (1 HUMAN + 14 AI on track_happy_jungle) becomes a standard
// 2-lap race (the packman file names the laps) with 15 AI, the benchmark's environment, the human in viewport 0
function raceCfgEdit(aggression, benchmark) {
    const eol = aggression.includes('\r\n') ? '\r\n' : '\n';
    const L = aggression.split(/\r?\n/);
    const one = (re, what) => {
        const at = L.map((l, i) => re.test(l) ? i : -1).filter(i => i >= 0);
        if (at.length !== 1) throw new Error(`the disc's race config: ${what} found ${at.length} times`);
        return at[0];
    };
    const env = /<Environment name="([^"]+)"\s*\/>/.exec(benchmark);
    if (!env) throw new Error("the disc's benchmark config has no Environment");
    const e = one(/<Environment name="[^"]*"\s*\/>/, 'Environment');
    L[e] = L[e].replace(/name="[^"]*"/, `name="${env[1]}"`);
    const h = one(/<Player [^>]*control="HUMAN"/, 'the HUMAN player');
    L[h] = L[h].replace(/ location="LOCAL" \/>/, ' location="LOCAL" viewport="0" />');
    const players = L.map((l, i) => /^\s*<Player /.test(l) ? i : -1).filter(i => i >= 0);
    if (players.length !== 15) throw new Error(`the disc's race config: ${players.length} players, expected 15`);
    const ai = players.find(i => /control="AI"/.test(L[i]));
    const lastName = /name="([^"]*?)(\d+)"/.exec(L[players[players.length - 1]]);   // "Monkey15" -> "Monkey16"
    if (!lastName) throw new Error("the disc's race config: the last player's name has no number");
    L.splice(players[players.length - 1] + 1, 0, L[ai].replace(/name="[^"]*"/, `name="${lastName[1]}${Number(lastName[2]) + 1}"`));
    const r = one(/<RaceSettings [^>]*racetype="Aggression"/, 'RaceSettings');
    L[r] = L[r].replace('racetype="Aggression"', 'racetype="Standard"');
    L.splice(r + 1, 0, L[r].replace(/<RaceSettings .*$/, '<Packmanager filename="data/events/light_fantastic.packman"/>'));
    const g = one(/<GUIFile name="osd-aggression\.gui"\s*\/>/, 'GUIFile');
    L[g] = L[g].replace('osd-aggression.gui', 'osd.gui');
    return L.filter(l => !/^\s*<Rule /.test(l)).join(eol);
}
// the edits, then the check that the result is the tested config
function raceCfgFromDisc(aggression, benchmark) {
    const text = raceCfgEdit(aggression, benchmark);
    const sha = crypto.createHash('sha256').update(text.replace(/\r\n/g, '\n'), 'utf8').digest('hex');
    if (sha !== RACE_CFG_SHA256) throw new Error(`the race config made from your disc is not the tested one (SHA-256 ${sha.slice(0, 12)}...)`);
    return text;
}

// ---- the start environment, shared by Play and the benchmarks (main.js startGame): the launcher's own environment,
// the build's (play.json), the game files folder, the saves folder, then extra. A benchmark variable inherited from
// the launcher's own environment is dropped, so Play never runs a benchmark.
function gameEnv({ processEnv, build, cfg, play, playDir }, extra = {}) {
    const env = { ...processEnv };
    for (const k of BENCH_KEYS) delete env[k];
    Object.assign(env, (build && build.env) || {}, extra);
    if (!env.PS3_VFS_ROOT && !(cfg && cfg.PS3_VFS_ROOT) && play && play.vfs_root) env.PS3_VFS_ROOT = play.vfs_root;
    if (!env.PS3_GAMEDATA_ROOT) env.PS3_GAMEDATA_ROOT = path.join(playDir, 'saves', 'v100');
    return env;
}

// the benchmark's own variables (BENCH_KEYS, nothing else); boot: the step's config (benchSteps), default the first
function benchEnv(mode, outFile, boot) {
    const steps = benchSteps(mode);
    const b = boot || steps[0].boot;
    if (!steps.some(s => s.boot === b)) throw new Error(`${b} is not a config of the ${mode} benchmark`);
    return { MSPR_BENCH: mode, MSPR_BENCH_OUT: outFile, PS3_DEV_GUEST_STR: GUEST_STR + b };
}

// ---- running a benchmark: its steps one after the other. runOne(step, try) starts the game for the step (main.js
// runBench) and resolves when it has closed: { result: readResult's or null, code, why, log: the game's log text }.
// A step whose game closed without a result while its log shows the start-up Present() Timeout runs once more.
// cancelled(): Stop was pressed; the step running ends "Stopped." and the steps not run yet are not started.
// onStep({ index, count, map, retry }) before each game start. Returns the race's own result, or for fly the maps'
// combined one (combineFly); the result of each step also goes to onResult(step, result) as it ends.
async function runSteps(mode, { runOne, cancelled = () => false, onStep = () => {}, onResult = () => {} }) {
    const steps = benchSteps(mode);
    const results = [];
    for (let i = 0; i < steps.length; i++) {
        const step = steps[i];
        const t0 = Date.now();
        let r = null, tries = 0;
        while (!r) {
            if (cancelled()) { r = failed(mode, 'Stopped.'); break; }
            onStep({ index: i, count: steps.length, map: step.map, retry: tries > 0 });
            const got = (await runOne(step, tries)) || {};
            tries++;
            r = got.result || null;
            if (r) break;
            const boot = typeof got.log === 'string' && got.log.includes(BOOT_TIMEOUT_LINE);
            if (cancelled()) r = failed(mode, 'Stopped.');
            else if (boot && tries < 2) continue;   // the known occasional start-up timeout: once more
            else r = failed(mode, got.why || (boot
                ? `The game stopped at start-up (Present() Timeout), ${tries} times (exit code ${got.code}).`
                : `The game closed without a result (exit code ${got.code}).`));
        }
        r.duration_s = Math.round((Date.now() - t0) / 1000);
        r.tries = tries;
        if (step.map) { r.map = step.map.id; r.map_name = step.map.name; }
        onResult(step, r);
        results.push(r);
    }
    return MODES[mode].maps ? combineFly(results) : results[0];
}
function failed(mode, error) { return { version: 1, benchmark: mode, ok: false, error, settings: [] }; }

// the fly maps' results (in FLY_MAPS order, each with map and map_name) as one: each map's own result under maps and,
// when every map has one, the combined numbers: the average over all measured frames of all maps (frames / seconds),
// min = the lowest map min, max = the highest map max. GPU, CPU, RAM and settings: the first map's that names them.
function combineFly(maps) {
    const pick = k => (maps.find(m => m[k] && (!Array.isArray(m[k]) || m[k].length)) || {})[k];
    const ok = maps.length > 0 && maps.every(m => m.ok);
    const r = { version: 1, benchmark: 'fly', ok,
                error: ok ? null : maps.filter(m => !m.ok).map(m => `${m.map_name || m.map}: ${m.error || 'no result'}`).join(' '),
                gpu: pick('gpu') || '', cpu: pick('cpu') || '', ram_bytes: pick('ram_bytes') || 0, settings: pick('settings') || [],
                maps };
    if (ok) {
        const frames = maps.reduce((a, m) => a + (m.frames || 0), 0);
        const seconds = maps.reduce((a, m) => a + (m.seconds || 0), 0);
        r.frames = frames;
        r.seconds = Math.round(seconds * 100) / 100;
        r.fps = { min: Math.min(...maps.map(m => m.fps.min)), max: Math.max(...maps.map(m => m.fps.max)),
                  avg: frames > 0 && seconds > 0 ? frames / seconds : maps.reduce((a, m) => a + m.fps.avg, 0) / maps.length };
        r.pipelines_built = maps.reduce((a, m) => a + (m.pipelines_built || 0), 0);
        r.pipelines_ms = maps.reduce((a, m) => a + (m.pipelines_ms || 0), 0);
    }
    return r;
}

// the overlay folder the game will read, the way it picks it (pc_menu.cpp pcmenu_boot, then motorstorm.cfg):
// a set PS3_VFS_OVERLAY wins, then the PC Settings pages' folder beside the exe, then motorstorm.cfg's line
function overlayDir(env, cfg, playDir) {
    if (env.PS3_VFS_OVERLAY) return env.PS3_VFS_OVERLAY;
    const pc = path.join(playDir, 'pcmenu');
    if (fs.existsSync(pc)) return pc;
    return (cfg && cfg.PS3_VFS_OVERLAY) || pc;
}

// race: the config from the player's disc into the overlay folder; returns its path
function prepareRace(gameFiles, overlay) {
    const archive = ['MS2.PSARC', 'ms2.psarc'].map(n => path.join(gameFiles, 'PS3_GAME', 'USRDIR', n)).find(p => fs.existsSync(p));
    if (!archive) throw new Error(`MS2.PSARC is not in ${path.join(gameFiles, 'PS3_GAME', 'USRDIR')}`);
    const m = readPsarcMembers(archive, ['/Configs/aggression_race.cfg', '/Configs/benchmark_happyJungle.cfg']);
    const text = raceCfgFromDisc(m['/Configs/aggression_race.cfg'].toString('utf8'), m['/Configs/benchmark_happyJungle.cfg'].toString('utf8'));
    const out = path.join(overlay, ...RACE_CFG.split('/'));
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, text);
    return out;
}

// the game's result file (bench_run.h bench_write_json), checked; null when missing or unreadable
// (the combined fly result: each of its maps checked the same way)
function readResult(file) {
    let r;
    try { r = JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return null; }
    return checkResult(r, true);
}
function checkResult(r, top) {
    if (!r || typeof r !== 'object' || !MODES[r.benchmark]) return null;
    if (r.ok) {
        const f = r.fps || {};
        if (![f.min, f.max, f.avg].every(x => typeof x === 'number' && isFinite(x))) return null;
    }
    if (r.maps !== undefined) {
        if (!top || !Array.isArray(r.maps) || !r.maps.length || !r.maps.every(m => checkResult(m, false))) return null;
        if (!!r.ok !== r.maps.every(m => m.ok)) return null;
    }
    if (!Array.isArray(r.settings)) r.settings = [];
    return r;
}

module.exports = { BENCH_KEYS, MODES, FLY_MAPS, BOOT_TIMEOUT_LINE, RACE_CFG, benchSteps, runSteps, combineFly, RACE_CFG_SHA256, readPsarcMembers, raceCfgEdit, raceCfgFromDisc, gameEnv, benchEnv, overlayDir, prepareRace, readResult };
