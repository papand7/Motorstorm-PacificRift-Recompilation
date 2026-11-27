// node test_bench.js: the Benchmark page's launcher side (bench.js).
//   - the benchmark's start environment is Play's plus BENCH_KEYS only, the values of every other key equal;
//   - no benchmark key is a variable settings.ini owns (port pc_settings.h) or the build's start environment sets
//     (PLAY_ENV), so the game applies the player's settings exactly as on Play;
//   - an inherited benchmark variable never reaches Play;
//   - the race config edits (on a made-up config), the PSARC reader (on a made-up archive), the result file check;
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
for (const mode of Object.keys(B.MODES)) {
    const out = path.join(playDir, 'benchmark', `${mode}.json`);
    const be = B.gameEnv(ctx, B.benchEnv(mode, out));
    const added = Object.keys(be).filter(k => !(k in play)).sort();
    assert.deepStrictEqual(added, [...B.BENCH_KEYS].sort(), `${mode}: only the benchmark keys are added`);
    assert.deepStrictEqual(Object.keys(play).filter(k => !(k in be)), [], `${mode}: nothing of Play's is removed`);
    for (const k of Object.keys(play)) assert.strictEqual(be[k], play[k], `${mode}: ${k} as on Play`);
    assert.strictEqual(be.MSPR_BENCH, mode);
    assert.strictEqual(be.MSPR_BENCH_OUT, out);
    assert.strictEqual(be.PS3_DEV_GUEST_STR, `0109AD4C:configs/ms2_config.cfg:${B.MODES[mode].boot}`);
}
assert.ok(B.MODES.race.boot === B.RACE_CFG && B.MODES.fly.boot === 'configs/benchmark_happyJungle.cfg');
assert.throws(() => B.benchEnv('lap', 'x'));

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

// ---- private only: the developer's disc files (never in the public tree)
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
