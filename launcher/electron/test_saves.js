// node test_saves.js: Import save (service/saves.js). Every input is synthetic: made-up PARAM.SFO / PARAM.PFD files,
// a made-up profile and random keys made here (no PS3 key, no game file, no player save).
'use strict';
const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const saves = require('./service/saves');

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ms saves '));   // a space on purpose
const write = (p, data) => { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, data); };
const sha = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const treeHash = dir => fs.readdirSync(dir).sort().map(n => n + ':' + sha(path.join(dir, n))).join(',');

// a PARAM.SFO: [key, value] pairs, strings (0x0204, with a reserved size) or u32 (0x0404)
function sfo(fields) {
    const names = fields.map(f => f[0]);
    const keyTable = Buffer.concat(names.map(k => Buffer.from(k + '\0')));
    const vals = fields.map(([, v, max]) => typeof v === 'number' ? (b => { b.writeUInt32LE(v); return b; })(Buffer.alloc(4))
                                                                  : Buffer.concat([Buffer.from(v + '\0', 'utf8')], max || 64));
    const keysAt = 20 + 16 * names.length, valuesAt = keysAt + keyTable.length + ((4 - keyTable.length % 4) % 4);
    const head = Buffer.alloc(valuesAt);
    head.writeUInt32BE(0x00505346, 0); head.writeUInt32LE(0x101, 4);
    head.writeUInt32LE(keysAt, 8); head.writeUInt32LE(valuesAt, 12); head.writeUInt32LE(names.length, 16);
    let ko = 0, vo = 0;
    fields.forEach(([k, v], i) => {
        const at = 20 + 16 * i;
        head.writeUInt16LE(ko, at); head.writeUInt16LE(typeof v === 'number' ? 0x404 : 0x204, at + 2);
        head.writeUInt32LE(typeof v === 'number' ? 4 : Buffer.byteLength(v, 'utf8') + 1, at + 4);
        head.writeUInt32LE(vals[i].length, at + 8); head.writeUInt32LE(vo, at + 12);
        ko += k.length + 1; vo += vals[i].length;
    });
    keyTable.copy(head, keysAt);
    return Buffer.concat([head, ...vals]);
}
const saveSfo = (dir, extra = []) => sfo([['CATEGORY', 'SD', 4], ['DETAIL', 'Game Save Data', 1024], ['SAVEDATA_DIRECTORY', dir, 64],
                                          ['SUB_TITLE', 'Brutal off-road racing!', 128], ['TITLE', 'MotorStorm®: Pacific Rift', 128], ...extra]);
const profile = (version, body = '') => Buffer.from(`<?xml version="1.0"?>\r\n<ProfileVersion version = "${version}"/>\r\n` +
    `<Chunk name = "festival">\r\n\r\n\t<Key name="rank"\t\tvalue = "7" />\r\n${body}\r\n</Chunk>\r\n\r\n`, 'latin1');
const PNG = Buffer.concat([Buffer.from('89504e470d0a1a0a', 'hex'), Buffer.alloc(24)]);

// a PS3 console's PARAM.PFD (version 3) for the given entries, each { name, size, encKey }
function pfd(entries) {
    const cap = 57, head = 0x60, table = 24 + cap * 8, out = Buffer.alloc(head + table + 114 * 0x110 + 114 * 20);
    out.writeBigUInt64BE(0x50464442n, 0); out.writeBigUInt64BE(3n, 8);
    out.writeBigUInt64BE(BigInt(cap), head); out.writeBigUInt64BE(114n, head + 8); out.writeBigUInt64BE(BigInt(entries.length), head + 16);
    entries.forEach((e, i) => {
        const at = head + table + i * 0x110;
        out.write(e.name, at + 8, 'latin1');
        if (e.encKey) e.encKey.copy(out, at + 0x50);
        out.writeBigUInt64BE(BigInt(e.size), at + 0x108);
    });
    return out;
}
// the inverse of saves' decryption, for the test only: the file key's encrypted form and the file's encrypted form
function encryptForPfd(plain, fileKey, secureId, sysconKey) {
    const iv = saves._crypto.secureHashKey(secureId).subarray(0, 16);
    const c = crypto.createCipheriv('aes-128-cbc', sysconKey, iv); c.setAutoPadding(false);
    const encKey = Buffer.concat([c.update(fileKey), c.final()]);
    const padded = Buffer.concat([plain, Buffer.alloc((16 - plain.length % 16) % 16)]);
    return { encKey, data: saves._crypto.pfdCrypt(padded, fileKey, false) };
}

(() => {
    // ---- the SFO reader and writer
    const s0 = saveSfo('BCES00129', [['*AUTOSAVE.DAT', 1], ['RPCS3_BLIST', 'AUTOSAVE.DAT/ICON0.PNG', 24]]);
    const p0 = saves.parseSfo(s0);
    assert.strictEqual(p0.str('SAVEDATA_DIRECTORY'), 'BCES00129');
    assert.strictEqual(p0.int('*AUTOSAVE.DAT'), 1);
    const s1 = saves.sfoSetString(s0, 'SAVEDATA_DIRECTORY', 'BLES00000');
    assert.strictEqual(s1.length, s0.length, 'the SFO keeps its layout');
    assert.strictEqual(saves.parseSfo(s1).str('SAVEDATA_DIRECTORY'), 'BLES00000');
    assert.strictEqual(saves.parseSfo(s1).str('TITLE'), 'MotorStorm®: Pacific Rift');
    assert.throws(() => saves.sfoSetString(s0, 'SAVEDATA_DIRECTORY', 'X'.repeat(80)), /does not fit/);
    assert.throws(() => saves.parseSfo(Buffer.from('not a psf at all, no')), /not a PSF/);
    const bad = Buffer.from(s0); bad.writeUInt32LE(0xFFFF0, 0x14 + 12);   // an entry's data outside the file
    assert.throws(() => saves.parseSfo(bad), /damaged/);

    // ---- the profile conversion: 1.03's "Beta 3" -> 1.00's "Beta 2", keys kept; others refused
    const b3 = profile('Beta 3', '\t<Key name="dlc.new"\t\tvalue = "1" />\r\n');
    const c3 = saves.profileFor100(b3);
    assert.strictEqual(c3.from, 'Beta 3');
    assert.strictEqual(c3.data.toString('latin1'), b3.toString('latin1').replace('"Beta 3"', '"Beta 2"'));
    assert.strictEqual(saves.profileFor100(profile('Beta 2')).from, undefined);
    assert.match(saves.profileFor100(profile('Beta 9')).error, /not one this game knows/);
    assert.match(saves.profileFor100(Buffer.from('garbage')).error, /not a MotorStorm/);

    // ---- a USB stick (PS3\SAVEDATA) and an RPCS3 dev_hdd0 with this game's saves and others'
    const usb = path.join(tmp, 'usb');
    const usbSave = path.join(usb, 'PS3', 'SAVEDATA', 'BCUS98155');
    write(path.join(usbSave, 'PARAM.SFO'), saveSfo('BCUS98155'));
    write(path.join(usbSave, 'AUTOSAVE.DAT'), profile('Beta 2'));
    write(path.join(usbSave, 'ICON0.PNG'), PNG);
    write(path.join(usb, 'PS3', 'SAVEDATA', 'BLES01234', 'PARAM.SFO'), sfo([['CATEGORY', 'SD', 4], ['SAVEDATA_DIRECTORY', 'BLES01234', 64], ['TITLE', 'Another game', 128]]));
    const hdd = path.join(tmp, 'rpcs3', 'dev_hdd0');
    const rpcs3Save = path.join(hdd, 'home', '00000001', 'savedata', 'BCES00129');
    write(path.join(rpcs3Save, 'PARAM.SFO'), s0);
    write(path.join(rpcs3Save, 'AUTOSAVE.DAT'), b3);
    write(path.join(rpcs3Save, 'ICON0.PNG'), PNG);
    write(path.join(hdd, 'game', 'BCES00129', 'PARAM.SFO'), sfo([['CATEGORY', 'GD', 4], ['TITLE', 'MotorStorm®: Pacific Rift Update', 128], ['TITLE_ID', 'BCES00129', 16]]));
    const tricky = path.join(usb, 'PS3', 'SAVEDATA', 'BCES00129-TIMEATTACK');
    write(path.join(tricky, 'PARAM.SFO'), saveSfo('BCES00129-TIMEATTACK'));
    write(path.join(tricky, 'GHOST.DAT'), 'ghost');
    fs.mkdirSync(path.join(tricky, 'SUBDIR'));   // a save never has folders

    const fromUsb = saves.findSaves(usb);
    assert.deepStrictEqual(fromUsb.map(s => s.dirName), ['BCUS98155', 'BCES00129-TIMEATTACK'], 'only this game\'s saves, the main save first');
    assert.strictEqual(fromUsb[0].region, 'USA');
    assert.ok(fromUsb[0].icon.startsWith('data:image/png;base64,'));
    assert.ok(fromUsb[1].problems.some(p => /SUBDIR/.test(p)), 'a folder inside a save is reported');
    assert.strictEqual(saves.summary(fromUsb[1]).target, 'BLES00000-TIMEATTACK');
    const fromHdd = saves.findSaves(path.join(tmp, 'rpcs3'));
    assert.deepStrictEqual(fromHdd.map(s => s.dirName), ['BCES00129'], 'game data (the update) is not a save');
    assert.strictEqual(fromHdd[0].kind, 'rpcs3');
    assert.deepStrictEqual(fromHdd[0].protected, ['AUTOSAVE.DAT']);
    assert.strictEqual(fromHdd[0].profileVersion, 'Beta 3');
    assert.deepStrictEqual(saves.findSaves(rpcs3Save).map(s => s.dirName), ['BCES00129'], 'the save folder itself');

    // ---- import: renamed for the port, SFO and profile converted, protected list kept, source untouched
    const gd = path.join(tmp, 'play', 'saves', 'v100'), backups = path.join(tmp, 'play', 'saves', 'backups');
    const before = treeHash(rpcs3Save);
    const r1 = saves.importSave(fromHdd[0], { gamedataRoot: gd, backupsRoot: backups });
    const slot = path.join(saves.savedataDir(gd), 'BLES00000');
    assert.strictEqual(r1.dir, 'BLES00000');
    assert.strictEqual(r1.backup, null);
    assert.deepStrictEqual(r1.converted, ['profile Beta 3 -> Beta 2', 'BCES00129 -> BLES00000']);
    assert.strictEqual(treeHash(rpcs3Save), before, 'the source save is not changed');
    assert.deepStrictEqual(fs.readdirSync(slot).sort(), ['AUTOSAVE.DAT', 'ICON0.PNG', 'PARAM.PFD', 'PARAM.SFO']);
    assert.strictEqual(fs.readFileSync(path.join(slot, 'PARAM.PFD'), 'latin1'), 'AUTOSAVE.DAT\n', 'the port\'s protected-file list');
    assert.strictEqual(saves.parseSfo(fs.readFileSync(path.join(slot, 'PARAM.SFO'))).str('SAVEDATA_DIRECTORY'), 'BLES00000');
    assert.ok(fs.readFileSync(path.join(slot, 'AUTOSAVE.DAT'), 'latin1').includes('version = "Beta 2"'));
    assert.deepStrictEqual(saves.currentSaves(gd).map(s => s.dirName), ['BLES00000']);
    assert.ok(!fs.readdirSync(saves.savedataDir(gd)).some(n => n.startsWith('.import')), 'no staging folder left');

    // a second import backs the first one up; restoring it backs up the second
    const r2 = saves.importSave(saves.inspectSave(usbSave), { gamedataRoot: gd, backupsRoot: backups });
    assert.ok(r2.backup && fs.existsSync(path.join(r2.backup, 'AUTOSAVE.DAT')));
    assert.ok(!fs.existsSync(path.join(slot, 'PARAM.PFD')), 'nothing left over from the replaced save');
    assert.strictEqual(saves.inspectSave(slot).profileVersion, 'Beta 2');
    const list = saves.listBackups(backups);
    assert.strictEqual(list.length, 1);
    assert.strictEqual(list[0].dir, 'BLES00000');
    const rr = saves.restoreBackup(list[0].name, { gamedataRoot: gd, backupsRoot: backups });
    assert.strictEqual(rr.dir, 'BLES00000');
    assert.ok(fs.readFileSync(path.join(slot, 'AUTOSAVE.DAT'), 'latin1').includes('dlc.new'), 'the RPCS3 save is back');
    assert.ok(!fs.existsSync(path.join(slot, 'backup.json')));
    assert.strictEqual(saves.listBackups(backups).length, 2);
    assert.throws(() => saves.restoreBackup('..\\..\\x', { gamedataRoot: gd, backupsRoot: backups }), /No such backup/);
    assert.throws(() => saves.importSave(fromUsb[1], { gamedataRoot: gd, backupsRoot: backups }), /cannot be used/);

    // ---- a PS3 console's save: protected file listed in a binary PARAM.PFD, decrypted with the player's tool keys
    const syscon = crypto.randomBytes(16), secureId = crypto.randomBytes(16), fileKey = crypto.randomBytes(16);
    const plain = profile('Beta 3', '\t<Key name="odd.length"\t\tvalue = "12345" />\r\n');
    const enc = encryptForPfd(plain, fileKey, secureId, syscon);
    const ps3 = path.join(tmp, 'usb2', 'PS3', 'SAVEDATA', 'BCES00129');
    write(path.join(ps3, 'PARAM.SFO'), saveSfo('BCES00129'));
    write(path.join(ps3, 'AUTOSAVE.DAT'), enc.data);
    write(path.join(ps3, 'PARAM.PFD'), pfd([{ name: 'PARAM.SFO', size: 100 }, { name: 'AUTOSAVE.DAT', size: plain.length, encKey: enc.encKey }]));
    const [console1] = saves.findSaves(path.join(tmp, 'usb2'));
    assert.strictEqual(console1.kind, 'ps3');
    assert.strictEqual(console1.encrypted, true);
    assert.deepStrictEqual(console1.protected, ['AUTOSAVE.DAT']);
    assert.strictEqual(console1.profileVersion, undefined, 'an encrypted profile is not read');
    assert.throws(() => saves.importSave(console1, { gamedataRoot: gd, backupsRoot: backups }), /encrypted: choose the folder/);
    const keyDir = path.join(tmp, 'tool');
    write(path.join(keyDir, 'global.conf'), `; Global settings\r\n\r\n[global]\r\nsyscon_manager_key=${syscon.toString('hex').toUpperCase()}\r\nkeygen_key=\r\n`);
    write(path.join(keyDir, 'games.conf'), `; Game settings\r\n\r\n; "SOMETHING"\r\n[BLES00001]\r\nsecure_file_id:*=${'00'.repeat(16)}\r\n\r\n` +
                                           `; "MOTORSTORM"\r\n[BCUS98155/BCES00129/BCJS30027] ;disc_hash_key=\r\nsecure_file_id:*=${secureId.toString('hex').toUpperCase()}\r\n`);
    const keys = saves.readKeyFolder(keyDir);
    assert.ok(keys.secureIds.BCES00129.equals(secureId) && keys.secureIds.BLES00001);
    const r3 = saves.importSave(console1, { gamedataRoot: gd, backupsRoot: backups, keys });
    assert.deepStrictEqual(r3.converted, ['decrypted AUTOSAVE.DAT', 'profile Beta 3 -> Beta 2', 'BCES00129 -> BLES00000']);
    assert.strictEqual(fs.readFileSync(path.join(slot, 'AUTOSAVE.DAT'), 'latin1'), plain.toString('latin1').replace('"Beta 3"', '"Beta 2"'),
                       'decrypted to the exact profile (its padding cut at the size PARAM.PFD gives)');
    assert.strictEqual(fs.readFileSync(path.join(slot, 'PARAM.PFD'), 'latin1'), 'AUTOSAVE.DAT\n', 'the binary PFD is not copied');
    // the wrong keys: refused, the slot not touched
    const slotBefore = treeHash(slot);
    const wrong = { ...keys, sysconKey: crypto.randomBytes(16) };
    assert.throws(() => saves.importSave(console1, { gamedataRoot: gd, backupsRoot: backups, keys: wrong }), /not the right ones/);
    assert.throws(() => saves.importSave(console1, { gamedataRoot: gd, backupsRoot: backups, keys: { ...keys, secureIds: {} } }), /no secure_file_id for BCES00129/);
    assert.strictEqual(treeHash(slot), slotBefore);
    assert.throws(() => saves.readKeyFolder(path.join(tmp, 'usb')), /no global.conf/);

    // ---- a damaged PARAM.PFD and a file name the port could not use are reported, never imported
    const broken = path.join(tmp, 'broken', 'BCUS98155');
    write(path.join(broken, 'PARAM.SFO'), saveSfo('BCUS98155'));
    const badPfd = pfd([{ name: 'AUTOSAVE.DAT', size: 1 }]); badPfd.writeBigUInt64BE(1000n, 0x60 + 16);
    write(path.join(broken, 'PARAM.PFD'), badPfd);
    write(path.join(broken, 'bad name.dat'), 'x');
    const [b] = saves.findSaves(path.join(tmp, 'broken'));
    assert.ok(b.problems.some(p => /damaged/.test(p)) && b.problems.some(p => /bad name/.test(p)), b.problems.join('; '));

    fs.rmSync(tmp, { recursive: true, force: true });
    console.log('test_saves: all checks passed');
})();
