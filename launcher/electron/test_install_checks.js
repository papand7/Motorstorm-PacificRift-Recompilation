// node test_install_checks.js: the install's disc and EBOOT.elf checks and the ThinLTO link flags (issues #6, #7).
// Every input here is synthetic: a made-up PARAM.SFO and made-up "ELF" bytes, nothing from the game.
'use strict';
const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const disc = require('./service/disc');
const { Builder, ltoLinkerFlags } = require('./service/builder');

const game = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'game.json'), 'utf8'));
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ms install checks '));   // a space on purpose

// a PARAM.SFO with UTF-8 string entries only (the fields checkGame reads)
function sfo(fields) {
    const names = Object.keys(fields);
    const keyTable = Buffer.concat(names.map(k => Buffer.from(k + '\0')));
    const values = names.map(k => { const v = Buffer.from(fields[k] + '\0', 'utf8'); return Buffer.concat([v, Buffer.alloc((4 - v.length % 4) % 4)]); });
    const keysAt = 20 + 16 * names.length, valuesAt = keysAt + keyTable.length + ((4 - keyTable.length % 4) % 4);
    const head = Buffer.alloc(valuesAt);
    head.writeUInt32BE(0x00505346, 0); head.writeUInt32LE(0x101, 4);
    head.writeUInt32LE(keysAt, 8); head.writeUInt32LE(valuesAt, 12); head.writeUInt32LE(names.length, 16);
    let ko = 0, vo = 0;
    names.forEach((k, i) => {
        const at = 20 + 16 * i, len = Buffer.byteLength(fields[k], 'utf8') + 1;
        head.writeUInt16LE(ko, at); head.writeUInt16LE(0x204, at + 2);
        head.writeUInt32LE(len, at + 4); head.writeUInt32LE(values[i].length, at + 8); head.writeUInt32LE(vo, at + 12);
        ko += k.length + 1; vo += values[i].length;
    });
    keyTable.copy(head, keysAt);
    return Buffer.concat([head, ...values]);
}

// a disc folder: PS3_GAME/PARAM.SFO and an (empty) USRDIR/EBOOT.BIN
function discFolder(name, titleId) {
    const root = path.join(tmp, name), usr = path.join(root, 'PS3_GAME', 'USRDIR');
    fs.mkdirSync(usr, { recursive: true });
    fs.writeFileSync(path.join(root, 'PS3_GAME', 'PARAM.SFO'), sfo({ TITLE: 'MOTORSTORM\u00ae: PACIFIC RIFT', TITLE_ID: titleId, APP_VER: '01.00' }));
    fs.writeFileSync(path.join(usr, 'EBOOT.BIN'), '');
    return root;
}

(async () => {
    // #7: the Europe disc (BCES00129) is accepted like the USA disc, with the same program hash
    for (const id of ['BCUS98155', 'BCES00129']) {
        const r = await disc.checkGame(await disc.openGame(discFolder(id, id)), game);
        assert.strictEqual(r.ok, true, `${id} accepted: ${r.error}`);
        assert.strictEqual(r.titleId, id);
        assert.ok(r.release.includes(id), r.release);
    }
    const us = game.discs.find(d => d.title_id === 'BCUS98155'), eu = game.discs.find(d => d.title_id === 'BCES00129');
    assert.deepStrictEqual(eu.eboot_elf, us.eboot_elf, 'the Europe disc is accepted only for the same EBOOT.elf');

    // another release is refused with the releases that do build named (not "MOTORSTORM: PACIFIC RIFT, not MotorStorm: Pacific Rift")
    const other = await disc.checkGame(await disc.openGame(discFolder('other', 'BCJS30024')), game);
    assert.strictEqual(other.ok, false);
    assert.ok(/BCJS30024/.test(other.error) && /BCUS98155/.test(other.error) && /BCES00129/.test(other.error), other.error);

    // checkElf compares against the chosen disc's eboot_elf (two made-up discs with different programs)
    const meta = path.join(tmp, 'meta'), root = path.join(tmp, 'root');
    fs.mkdirSync(meta); fs.mkdirSync(root);
    const progA = Buffer.from('program A'), progB = Buffer.from('program B, longer');
    const want = b => ({ size: b.length, sha256: crypto.createHash('sha256').update(b).digest('hex') });
    fs.writeFileSync(path.join(meta, 'game.json'), JSON.stringify({ title: 't', discs: [
        { name: 'A', title_id: 'AAAA00001', eboot_elf: want(progA) }, { name: 'B', title_id: 'BBBB00002', eboot_elf: want(progB) }], builds: {} }));
    fs.writeFileSync(path.join(meta, 'toolchain.json'), '{}');
    const elf = path.join(tmp, 'EBOOT.elf');
    fs.writeFileSync(elf, progB);
    const b = new Builder({ root, meta, source: tmp, emit: () => {}, log: () => {} });
    b.cfg.elf100 = elf;
    assert.strictEqual((await b.checkElf(100)).ok, false, 'no disc chosen: the first disc decides');
    b.discInfo = { ok: true, disc: b.game.discs[1] };
    assert.strictEqual((await b.checkElf(100)).ok, true, 'disc B chosen: its program');

    // #6: the LTO cache path stays one argument when the install folder has a space
    const f = ltoLinkerFlags(7, 'D:\\EMU D\\MotorStorm\\work\\build-stable\\lto-cache');
    assert.strictEqual(f, '/opt:lldltojobs=7 "/lldltocache:D:/EMU D/MotorStorm/work/build-stable/lto-cache"');

    fs.rmSync(tmp, { recursive: true, force: true });
    console.log('test_install_checks: all passed');
})().catch(e => { console.error(e); process.exit(1); });
