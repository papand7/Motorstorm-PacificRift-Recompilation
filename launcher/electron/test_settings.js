// node test_settings.js: settings.ini read-modify-write, the one-time migration from motorstorm.cfg, key bindings.
'use strict';
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const S = require('./settings');

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ms-settings-'));
const cfg = path.join(dir, 'motorstorm.cfg'), ini = path.join(dir, 'settings.ini');

// migration: the old launcher's lines move to settings.ini as labels, paths stay in the cfg
fs.writeFileSync(cfg, '# old\nRSX_FSR=quality\nRSX_FSR_MODE=3\nRSX_HDR=1\nPS3RECOMP_VK_FULLSCREEN=1\nRSX_PRESENT_INTERVAL=0\n' +
                      `RSX_TEX_PACK=${dir}\\textures\\pack\nRSX_TEX_PBR=1\nPS3_VFS_ROOT=C:\\game\n`);
let s = S.load(dir);
assert.strictEqual(s.migrated, true);
assert.deepStrictEqual([s.values.fsr, s.values.fsrmode, s.values.hdr, s.values.display, s.values.vsync, s.values.textures, s.values.pbr],
                       ['Quality', 'FSR 3.1', 'On', 'Fullscreen', 'Off', 'On', 'On']);
const left = S.readCfg(cfg);
assert.deepStrictEqual(Object.keys(left), ['PS3_VFS_ROOT']);
assert.strictEqual(S.load(dir).migrated, false, 'migrates once');

// the port's own lines (any case, values instead of labels, comments, unknown keys) are read and kept
fs.writeFileSync(ini, '; written by the game\r\nFSR = balanced\r\nResolution=1.5\r\nfuture_key = 7\r\nkey.accelerate = Up, W\r\n');
s = S.load(dir);
assert.strictEqual(s.values.fsr, 'Balanced');
assert.strictEqual(s.values.resolution, '1080p');
assert.strictEqual(s.values.aniso, 'Original', 'missing key = default');
assert.strictEqual(s.keys.accelerate, 'Up, W');
assert.strictEqual(s.keys.brake, 'S, 1');

// save: whole file through .tmp, known keys changed in place, others kept, new ones appended
assert.strictEqual(S.save(dir, { fsr: 'Performance', rtshadow: 'On' }, { brake: 'Ctrl , 0x20' }), null);
const text = fs.readFileSync(ini, 'utf8');
assert.ok(text.includes('fsr = Performance') && !/FSR = balanced/.test(text));
assert.ok(text.includes('future_key = 7') && text.includes('; written by the game'));
assert.ok(text.includes('rtshadow = On') && text.includes('key.brake = Ctrl, 0x20'));
assert.ok(!fs.existsSync(ini + '.tmp'));

// refused: unknown choices, three keys, Esc
assert.ok(S.save(dir, { fsr: 'Ultra Mega' }));
assert.ok(S.save(dir, {}, { brake: 'A, B, C' }));
assert.ok(S.save(dir, {}, { brake: 'Esc' }));
assert.strictEqual(S.parseBinding(' w , f12 '), 'w, f12');

fs.rmSync(dir, { recursive: true, force: true });
console.log('settings: all checks passed');
