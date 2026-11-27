// node test_bench.js: the Benchmark page's launcher side (bench.js).
//   - the benchmark's start environment is Play's plus BENCH_KEYS only, the values of every other key equal;
//   - no benchmark key is a variable settings.ini owns (port pc_settings.h) or the build's start environment sets
//     (PLAY_ENV), so the game applies the player's settings exactly as on Play;
//   - an inherited benchmark variable never reaches Play;
//   - the race config edits (on a made-up config), the PSARC reader (on a made-up archive), the result file check;
//   - the steps: fly runs Happy Jungle then Wildfire, one start-up Present() Timeout retried once, the combined numbers
//     (average over all frames, lower min, higher max), one map failed (its error and the other's result), Stop;
//   - with the developer's private disc files present (never in the public tree), the race config made from them is
//     the tested one, from the extracted files and from MS2.PSARC itself.
// Every input here is synthetic unless a private file exists; nothing from the game is in this file.
'use strict';
const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const zlib = require('zlib');
const B = require('./bench');
const { PLAY_ENV } = require('./service/builder');

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ms bench '));
const playDir = path.join(tmp, 'play');

// ---- the start environment
const processEnv = { PATH: 'C:\\Windows', USERPROFILE: 'C:\\Users\\x', MSPR_BENCH: 'race', PS3_DEV_GUEST_STR: 'stale' };
const ctx = { processEnv, build: { env: { ...PLAY_ENV, RSX_RT_DXC: 'C:\\x\\dxc.exe' } }, cfg: { PS3_VFS_ROOT: 'D:\\game' },
              play: { vfs_root: 'D:\\game' }, playDir };
const play = B.gameEnv(ctx);
for (const k of B.BENCH_KEYS) assert.ok(!(k in play), `Play never inherits ${k}`);
for (const mode of Object.keys(B.MODES)) for (const step of B.benchSteps(mode)) {
    const out = path.join(playDir, 'benchmark', step.file);
    const be = B.gameEnv(ctx, B.benchEnv(mode, out, step.boot));
    const added = Object.keys(be).filter(k => !(k in play)).sort();
    assert.deepStrictEqual(added, [...B.BENCH_KEYS].sort(), `${mode}: only the benchmark keys are added`);
    assert.deepStrictEqual(Object.keys(play).filter(k => !(k in be)), [], `${mode}: nothing of Play's is removed`);
    for (const k of Object.keys(play)) assert.strictEqual(be[k], play[k], `${mode}: ${k} as on Play`);
    assert.strictEqual(be.MSPR_BENCH, mode);
    assert.strictEqual(be.MSPR_BENCH_OUT, out);
    assert.strictEqual(be.PS3_DEV_GUEST_STR, `0109AD4C:configs/ms2_config.cfg:${step.boot}`);
}
// fly: Happy Jungle, then Wildfire, each its own result file; race: one run, its own boot config
assert.deepStrictEqual(B.benchSteps('fly').map(s => [s.map.name, s.boot, s.file]),
    [['Happy Jungle', 'configs/benchmark_happyJungle.cfg', 'fly_happyJungle.json'],
     ['Wildfire', 'configs/benchmark_Wildfire.cfg', 'fly_wildfire.json']]);
assert.deepStrictEqual(B.benchSteps('race').map(s => [s.map, s.boot, s.file]), [[null, B.RACE_CFG, 'race.json']]);
assert.strictEqual(B.benchEnv('fly', 'x').PS3_DEV_GUEST_STR, '0109AD4C:configs/ms2_config.cfg:configs/benchmark_happyJungle.cfg');
assert.throws(() => B.benchEnv('lap', 'x'));
assert.throws(() => B.benchEnv('race', 'x', 'configs/benchmark_Wildfire.cfg'), /not a config/);

// ---- no benchmark key is owned by settings.ini or set by the build's start environment
for (const k of B.BENCH_KEYS) assert.ok(!(k in PLAY_ENV), `${k} is not in PLAY_ENV`);
const pcs = path.join(__dirname, '..', '..', 'port-vkgame', 'pc_settings.h');   // the port (the developer tree; the source snapshot has it too)
if (fs.existsSync(pcs)) {
    const owned = new Set((fs.readFileSync(pcs, 'utf8').match(/"[A-Z][A-Z0-9_]{2,}"/g) || []).map(s => s.slice(1, -1)));
    assert.ok(owned.has('RSX_RES_SCALE') && owned.has('MSPR_PATCH') && owned.has('RSX_LIGHTING'), 'pc_settings.h parsed');
    for (const k of B.BENCH_KEYS) assert.ok(!owned.has(k), `${k} is not a settings.ini variable`);
    for (const k of B.BENCH_KEYS) assert.ok(!k.startsWith('RSX_') && !k.startsWith('PAD_'), k);
} else console.log('test_bench: no port-vkgame/pc_settings.h here, settings ownership not checked');

// ---- the overlay folder the game reads: a set variable, then <play>/pcmenu when it exists, then motorstorm.cfg's
fs.mkdirSync(playDir, { recursive: true });
assert.strictEqual(B.overlayDir({ PS3_VFS_OVERLAY: 'E:\\ov' }, { PS3_VFS_OVERLAY: 'F:\\x' }, playDir), 'E:\\ov');
assert.strictEqual(B.overlayDir({}, { PS3_VFS_OVERLAY: 'F:\\x' }, playDir), 'F:\\x');
assert.strictEqual(B.overlayDir({}, {}, playDir), path.join(playDir, 'pcmenu'));
fs.mkdirSync(path.join(playDir, 'pcmenu'));
assert.strictEqual(B.overlayDir({}, { PS3_VFS_OVERLAY: 'F:\\x' }, playDir), path.join(playDir, 'pcmenu'));

// ---- the race config edits on a made-up config with the same shape (CRLF kept)
const P = (n, c, v = 'car_A') => `<Player name="P${n}" vehicle="${v}" character="ch" control="${c}" location="LOCAL" />`;
const mine = ['<?xml version="1.0"?>', '<Config>', '    <World name="w1"/>', '    <Environment name="sky_old"/>',
    '  ' + P(1, 'HUMAN'), ...Array.from({ length: 14 }, (_, i) => P(i + 2, 'AI', i < 2 ? 'car_A' : 'car_B')), '    ',
    '    <RaceSettings filename="default" racetype="Aggression"/>', '    <GUIFile name="osd-aggression.gui"/>',
    '    <Rule token="T" comp="gt" value="1" scope="Competitor" outcome="success"/>', '', '</Config>', ''].join('\r\n');
const bench = '<Config>\r\n    <World name="w1"/>\r\n    <Environment name="Sky_New_Midday"/>\r\n</Config>\r\n';
const ed = B.raceCfgEdit(mine, bench);
const lines = ed.split('\r\n');
assert.ok(!ed.replace(/\r\n/g, '').includes('\n'), 'CRLF kept');
assert.ok(lines.includes('    <Environment name="Sky_New_Midday"/>'));
assert.ok(lines.includes('  ' + P(1, 'HUMAN').replace(' />', ' viewport="0" />')));
assert.strictEqual(lines.filter(l => /<Player /.test(l)).length, 16);
assert.strictEqual(lines.filter(l => /control="AI"/.test(l)).length, 15);
assert.ok(lines.includes(P(16, 'AI')), 'the 16th player: a copy of the first AI player');
const rs = lines.indexOf('    <RaceSettings filename="default" racetype="Standard"/>');
assert.ok(rs > 0 && lines[rs + 1] === '    <Packmanager filename="data/events/light_fantastic.packman"/>');
assert.ok(lines.includes('    <GUIFile name="osd.gui"/>') && !ed.includes('<Rule '));
assert.throws(() => B.raceCfgFromDisc(mine, bench), /not the tested one/);
assert.throws(() => B.raceCfgEdit(mine.replace('control="HUMAN"', 'control="AI"'), bench), /HUMAN/);
assert.throws(() => B.raceCfgEdit(mine, '<Config/>'), /Environment/);
assert.throws(() => B.raceCfgEdit(mine.replace(P(15, 'AI', 'car_B') + '\r\n', ''), bench), /14 players/);

// ---- the PSARC reader on a made-up archive: one compressed member, one stored raw, the names list (entry 0)
function psarc(members, block = 64) {   // members: [name, Buffer]
    const datas = [Buffer.from(members.map(m => m[0]).join('\n'))].concat(members.map(m => m[1]));
    const names = [null].concat(members.map(m => m[0]));
    const lens = [], chunks = [], entries = [];
    for (let i = 0; i < datas.length; i++) {
        const d = datas[i];
        const z = lens.length;
        let off = chunks.reduce((a, c) => a + c.length, 0);
        for (let p = 0; p < d.length; p += block) {
            const raw = d.subarray(p, p + block);
            const c = i === 2 ? raw : zlib.deflateSync(raw);   // member 2 stored raw (its blocks are full-size or the tail)
            const stored = raw.length === block && c === raw;
            lens.push(stored ? 0 : c.length);
            chunks.push(c);
        }
        entries.push({ md5: names[i] ? crypto.createHash('md5').update(names[i].toUpperCase(), 'latin1').digest() : Buffer.alloc(16), z, size: d.length, off });
    }
    const tocLen = 32 + 30 * entries.length + 2 * lens.length;
    const head = Buffer.alloc(32);
    head.write('PSAR', 0, 'latin1'); head.writeUInt32BE(0x00010004, 4); head.write('zlib', 8, 'latin1');
    head.writeUInt32BE(tocLen, 12); head.writeUInt32BE(30, 16); head.writeUInt32BE(entries.length, 20); head.writeUInt32BE(block, 24);
    const toc = Buffer.alloc(30 * entries.length);
    entries.forEach((e, i) => { e.md5.copy(toc, i * 30); toc.writeUInt32BE(e.z, i * 30 + 16); toc.writeUIntBE(e.size, i * 30 + 20, 5); toc.writeUIntBE(e.off + tocLen, i * 30 + 25, 5); });
    const lb = Buffer.alloc(2 * lens.length);
    lens.forEach((n, i) => lb.writeUInt16BE(n, i * 2));
    return Buffer.concat([head, toc, lb, ...chunks]);
}
const a = Buffer.from('alpha '.repeat(40)), b = Buffer.from('beta-raw-'.repeat(15));
const arc = path.join(tmp, 'T.PSARC');
fs.writeFileSync(arc, psarc([['/Configs/a.cfg', a], ['/data/b.bin', b]]));
const got = B.readPsarcMembers(arc, ['/configs/A.cfg', '/data/b.bin']);
assert.ok(got['/configs/A.cfg'].equals(a), 'compressed member, name case ignored');
assert.ok(got['/data/b.bin'].equals(b), 'stored member');
assert.throws(() => B.readPsarcMembers(arc, ['/nope']), /not in the archive/);

// ---- the result file (port bench_run.h bench_write_json)
const res = path.join(tmp, 'r.json');
const sample = { version: 1, benchmark: 'race', ok: true, error: null, gpu: 'GPU X', cpu: 'CPU Y', ram_bytes: 34359738368,
                 fps: { min: 41, max: 63, avg: 50.2, low1: 24.6, low01: 18.7 }, frame_ms: { p50: 20, p95: 30, p99: 36, max: 60 },
                 frames: 4500, seconds: 89.9, whole_seconds: 89, settings: [{ key: 'framerate', name: 'Frame Rate', value: '60 FPS', applied: true }] };
fs.writeFileSync(res, JSON.stringify(sample));
const r = B.readResult(res);
assert.ok(r && r.ok && r.fps.min === 41 && r.gpu === 'GPU X' && r.settings.length === 1);
fs.writeFileSync(res, JSON.stringify({ ...sample, fps: { avg: 50 } }));
assert.strictEqual(B.readResult(res), null, 'ok without min/max');
fs.writeFileSync(res, JSON.stringify({ version: 1, benchmark: 'fly', ok: false, error: 'no HotSpot', gpu: '', cpu: '', ram_bytes: 0 }));
assert.ok(B.readResult(res).error === 'no HotSpot' && Array.isArray(B.readResult(res).settings));
fs.writeFileSync(res, '{ broken');
assert.strictEqual(B.readResult(res), null);
assert.strictEqual(B.readResult(path.join(tmp, 'missing.json')), null);

// ---- running the steps (bench.runSteps) with a stand-in for the game: sequence, retry, combine, a failed map, Stop
const mapRes = (min, max, frames, seconds, extra = {}) => ({ version: 1, benchmark: 'fly', ok: true, error: null, gpu: 'GPU X',
    cpu: 'CPU Y', ram_bytes: 17179869184, fps: { min, max, avg: frames / seconds, low1: min / 2, low01: min / 3 },
    frames, seconds, settings: [{ key: 'framerate', name: 'Frame Rate', value: '60 FPS', applied: true }], ...extra });
const TIMEOUT_LOG = 'boot...\nGc ERROR: GcKernel::Present() Timeout!\n';
async function runFake(mode, script, cancelAfter = Infinity) {
    const calls = [], stepsSeen = [], perStep = [];
    let n = 0;
    const r = await B.runSteps(mode, {
        runOne: async (step, attempt) => { calls.push([step.boot, attempt]); n++; return script[n - 1]; },
        cancelled: () => n >= cancelAfter,
        onStep: s => stepsSeen.push(`${s.index + 1}/${s.count}${s.map ? ' ' + s.map.name : ''}${s.retry ? ' retry' : ''}`),
        onResult: (step, res) => perStep.push([step.file, res.ok]),
    });
    return { r, calls, stepsSeen, perStep };
}
const HJ = 'configs/benchmark_happyJungle.cfg', WF = 'configs/benchmark_Wildfire.cfg';
const fileOf = (f, x) => { const p = path.join(tmp, f); fs.writeFileSync(p, JSON.stringify(x)); return p; };
(async () => {
    // both maps: Happy Jungle first, then Wildfire; combined avg = all frames / all seconds, min the lower, max the higher
    let t = await runFake('fly', [{ result: mapRes(28, 33, 900, 30), code: 0 },
                                  { result: mapRes(22, 40, 1500, 60, { pipelines_built: 3, pipelines_ms: 1200 }), code: 0 }]);
    assert.deepStrictEqual(t.calls, [[HJ, 0], [WF, 0]]);
    assert.deepStrictEqual(t.stepsSeen, ['1/2 Happy Jungle', '2/2 Wildfire']);
    assert.deepStrictEqual(t.perStep, [['fly_happyJungle.json', true], ['fly_wildfire.json', true]]);
    assert.ok(t.r.ok && t.r.benchmark === 'fly' && t.r.error === null);
    assert.deepStrictEqual(t.r.maps.map(m => [m.map, m.map_name, m.fps.min, m.fps.max, m.tries]),
                           [['happyJungle', 'Happy Jungle', 28, 33, 1], ['wildfire', 'Wildfire', 22, 40, 1]]);
    assert.strictEqual(t.r.frames, 2400);
    assert.strictEqual(t.r.seconds, 90);
    assert.strictEqual(t.r.fps.min, 22);
    assert.strictEqual(t.r.fps.max, 40);
    assert.ok(Math.abs(t.r.fps.avg - 2400 / 90) < 1e-9, 'the average over all frames, not the mean of the two averages');
    assert.ok(Math.abs(t.r.fps.avg - (30 + 25) / 2) > 0.1);
    assert.ok(t.r.gpu === 'GPU X' && t.r.settings.length === 1 && t.r.pipelines_built === 3);
    assert.ok(B.readResult(fileOf('c.json', t.r)) && B.readResult(fileOf('c.json', t.r)).maps.length === 2, 'the combined file reads back');

    // Happy Jungle hits the start-up Present() Timeout once: run again, then Wildfire
    t = await runFake('fly', [{ result: null, code: 1, log: TIMEOUT_LOG }, { result: mapRes(30, 31, 900, 30), code: 0 },
                              { result: mapRes(29, 31, 870, 30), code: 0 }]);
    assert.deepStrictEqual(t.calls, [[HJ, 0], [HJ, 1], [WF, 0]]);
    assert.deepStrictEqual(t.stepsSeen, ['1/2 Happy Jungle', '1/2 Happy Jungle retry', '2/2 Wildfire']);
    assert.ok(t.r.ok && t.r.maps[0].tries === 2 && t.r.maps[1].tries === 1 && t.r.frames === 1770);

    // retried only once: two timeouts on Wildfire -> Wildfire's error, Happy Jungle's result kept, no combined numbers
    t = await runFake('fly', [{ result: mapRes(30, 31, 900, 30), code: 0 }, { result: null, code: 1, log: TIMEOUT_LOG },
                              { result: null, code: 1, log: TIMEOUT_LOG }]);
    assert.deepStrictEqual(t.calls, [[HJ, 0], [WF, 0], [WF, 1]]);
    assert.ok(!t.r.ok && t.r.maps[0].ok && !t.r.maps[1].ok && !t.r.fps && t.r.frames === undefined);
    assert.match(t.r.maps[1].error, /Present\(\) Timeout\), 2 times/);
    assert.match(t.r.error, /^Wildfire: /);
    assert.ok(t.r.gpu === 'GPU X', 'GPU from the map that ran');
    let back = B.readResult(fileOf('p.json', t.r));
    assert.ok(back && !back.ok && back.maps[0].fps.avg === 30, 'a partial result reads back with the good map');

    // a map failing another way (the game's own error file, or no file without the timeout line): not retried
    const own = { version: 1, benchmark: 'fly', ok: false, error: 'the camera flight did not end', gpu: '', cpu: '', ram_bytes: 0, settings: [] };
    t = await runFake('fly', [{ result: own, code: 3 }, { result: mapRes(25, 35, 1200, 40), code: 0 }]);
    assert.deepStrictEqual(t.calls, [[HJ, 0], [WF, 0]]);
    assert.ok(!t.r.ok && t.r.maps[0].error === 'the camera flight did not end' && t.r.maps[1].ok && t.r.maps[1].fps.max === 35);
    assert.match(t.r.error, /^Happy Jungle: the camera flight did not end$/);
    t = await runFake('fly', [{ result: null, code: 5, log: 'crash' }, { result: mapRes(25, 35, 1200, 40), code: 0 }]);
    assert.deepStrictEqual(t.calls, [[HJ, 0], [WF, 0]]);
    assert.match(t.r.maps[0].error, /without a result \(exit code 5\)/);

    // Stop during the first map: Wildfire never starts, both "Stopped.", no retry even with the timeout line
    t = await runFake('fly', [{ result: null, code: 1, log: TIMEOUT_LOG }], 1);
    assert.deepStrictEqual(t.calls, [[HJ, 0]]);
    assert.ok(!t.r.ok && t.r.maps.length === 2 && t.r.maps.every(m => m.error === 'Stopped.'));
    // Stop during Wildfire: Happy Jungle's result kept
    t = await runFake('fly', [{ result: mapRes(30, 31, 900, 30), code: 0 }, { result: null, code: 1 }], 2);
    assert.ok(!t.r.ok && t.r.maps[0].ok && t.r.maps[1].error === 'Stopped.');

    // race: one run, its own result (no maps), retried on the start-up timeout like fly
    const race = { ...mapRes(28, 31, 2700, 90), benchmark: 'race' };
    t = await runFake('race', [{ result: null, code: 1, log: TIMEOUT_LOG }, { result: race, code: 0 }]);
    assert.deepStrictEqual(t.calls, [[B.RACE_CFG, 0], [B.RACE_CFG, 1]]);
    assert.ok(t.r.ok && t.r.benchmark === 'race' && t.r.maps === undefined && t.r.map === undefined && t.r.frames === 2700);

    // combined results that do not hold together are refused
    back = JSON.parse(JSON.stringify(B.combineFly([{ ...mapRes(1, 2, 10, 5), map: 'happyJungle', map_name: 'Happy Jungle' }])));
    assert.ok(B.readResult(fileOf('k.json', back)));
    assert.strictEqual(B.readResult(fileOf('k.json', { ...back, ok: false })), null, 'ok must match the maps');
    assert.strictEqual(B.readResult(fileOf('k.json', { ...back, maps: [] })), null);
    assert.strictEqual(B.readResult(fileOf('k.json', { ...back, maps: [{ ...back.maps[0], fps: {} }] })), null);
    assert.strictEqual(B.readResult(fileOf('k.json', { ...back, maps: [{ ...back.maps[0], maps: [] }] })), null, 'no nesting');
    privateFiles();
})().catch(e => { console.error(e); process.exit(1); });

// ---- private only: the developer's disc files (never in the public tree)
function privateFiles() {
const ROOT = path.join(__dirname, '..', '..');
const xa = path.join(ROOT, 'generated', 'analysis', 'distance', 'x', 'Configs_aggression_race.cfg');
const xb = path.join(ROOT, 'generated', 'analysis', 'distance', 'x', 'Configs_benchmark_happyJungle.cfg');
if (fs.existsSync(xa) && fs.existsSync(xb)) {
    B.raceCfgFromDisc(fs.readFileSync(xa, 'utf8'), fs.readFileSync(xb, 'utf8'));
    console.log('test_bench: the race config from the extracted disc files is the tested one');
}
const disc = path.join(ROOT, 'original', 'game');
if (fs.existsSync(path.join(disc, 'PS3_GAME', 'USRDIR', 'MS2.PSARC'))) {
    const f = B.prepareRace(disc, path.join(tmp, 'overlay'));
    assert.strictEqual(f, path.join(tmp, 'overlay', 'configs', 'mspr_bench_race.cfg'));
    console.log('test_bench: the race config from MS2.PSARC is the tested one');
}
fs.rmSync(tmp, { recursive: true, force: true });
console.log('test_bench: ok');
}
