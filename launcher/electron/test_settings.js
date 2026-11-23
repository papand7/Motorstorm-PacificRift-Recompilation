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
assert.strictEqual(S.save(dir, { fsr: 'Performance', lod: 'High' }, { brake: 'Ctrl , 0x20' }), null);
const text = fs.readFileSync(ini, 'utf8');
assert.ok(text.includes('fsr = Performance') && !/FSR = balanced/.test(text));
assert.ok(text.includes('future_key = 7') && text.includes('; written by the game'));
assert.ok(text.includes('lod = High') && text.includes('key.brake = Ctrl, 0x20'));
// ray-traced shadows are hidden: no setting (RSX_RT_SHADOW only by hand)
assert.ok(!S.SCHEMA.some(x => x.key === 'rtshadow') && !('rtshadow' in S.load(dir).missing));
assert.ok(S.save(dir, { rtshadow: 'On' }), 'rtshadow is not a setting');
assert.ok(!fs.existsSync(ini + '.tmp'));

// frame rate: 30/45/60 (default 30); the old "Variable" and "60 FPS" patch values read as 60 FPS; vsync defaults Off
const fr = S.SCHEMA.find(x => x.key === 'framerate'), vs = S.SCHEMA.find(x => x.key === 'vsync');
assert.deepStrictEqual(fr.choices, ['30 FPS', '45 FPS', '60 FPS', '80 FPS', '120 FPS', '144 FPS', '180 FPS']);
assert.strictEqual(fr.def, '30 FPS');
assert.strictEqual(vs.def, 'Off');
fs.writeFileSync(ini, 'framerate = Variable\r\n');
assert.strictEqual(S.load(dir).values.framerate, '60 FPS');
fs.writeFileSync(ini, 'framerate = 45\r\n');
assert.strictEqual(S.load(dir).values.framerate, '45 FPS');
fs.writeFileSync(ini, 'framerate = 30 FPS\r\n');
assert.strictEqual(S.load(dir).values.framerate, '30 FPS');
fs.rmSync(ini);
assert.deepStrictEqual([S.load(dir).values.framerate, S.load(dir).values.vsync], ['30 FPS', 'Off']);
assert.strictEqual(S.save(dir, { framerate: '45 FPS', vsync: 'On' }), null);
assert.ok(/framerate = 45 FPS/.test(fs.readFileSync(ini, 'utf8')));
S.save(dir, { framerate: '60 FPS' });

// refused: unknown choices, three keys, Esc
assert.ok(S.save(dir, { fsr: 'Ultra Mega' }));
assert.ok(S.save(dir, {}, { brake: 'A, B, C' }));
assert.ok(S.save(dir, {}, { brake: 'Esc' }));
assert.strictEqual(S.parseBinding(' w , f12 '), 'w, f12');

// racing wheel: eight choice settings on the Wheel group, defaults as the port's (pc_settings.h), labels or values read back,
// the wheel.* lines the launcher does not know are kept through a save
const wk = S.SCHEMA.filter(x => x.group === 'Wheel');
assert.deepStrictEqual(wk.map(x => x.key), ['wheelmode', 'wheelrange', 'wheeldeadzone', 'wheelcurve', 'wheelpedals', 'wheelpedaldir', 'wheelffb', 'wheelffbstrength']);
assert.deepStrictEqual(wk.map(x => x.def), ['Auto', '270 deg', '1%', 'Linear', 'Profile', 'Auto', 'Off', '60%']);
fs.rmSync(ini, { force: true });
s = S.load(dir);
assert.strictEqual(s.values.wheelffb, 'Off', 'force feedback is off by default');
fs.writeFileSync(ini, 'wheelmode = any\r\nwheelrange = 540\r\nwheelffb = Both\r\nwheel.steer.axis = Rx\r\nwheel.button.3 = Circle\r\n');
s = S.load(dir);
assert.deepStrictEqual([s.values.wheelmode, s.values.wheelrange, s.values.wheelffb], ['Any Device', '540 deg', 'Both']);
assert.strictEqual(S.save(dir, { wheelpedals: 'Combined', wheelffb: 'Centering' }), null);
const wt = fs.readFileSync(ini, 'utf8');
assert.ok(wt.includes('wheelpedals = Combined') && wt.includes('wheelffb = Centering') && wt.includes('wheelrange = 540'));
assert.ok(wt.includes('wheel.steer.axis = Rx') && wt.includes('wheel.button.3 = Circle'), 'wheel.* lines kept');
assert.ok(S.save(dir, { wheelrange: '1000 deg' }));

// The driver's-eye camera (MSPR_CAM_COCKPIT) is not a setting: it is on by default in port-vkgame/main.cpp k_defaults.
{
    const cfgC = fs.readFileSync(path.join(__dirname, '..', '..', 'port-vkgame', 'pc_settings.h'), 'utf8');
    assert.ok(!cfgC.includes('"MSPR_CAM_COCKPIT"'), 'pc_settings.h has no cockpit row');
    assert.ok(!S.SCHEMA.some(d => d.key === 'cockpit'), 'launcher has no cockpit setting');
    const mainC = fs.readFileSync(path.join(__dirname, '..', '..', 'port-vkgame', 'main.cpp'), 'utf8');
    assert.ok(/\{ "MSPR_CAM_COCKPIT", "1" \}/.test(mainC), 'main.cpp defaults MSPR_CAM_COCKPIT to 1');
}

// Cheats: unlockvehicles is a Cheats-group switch, Off by default, written as its label; the first version's key
// (unlockall) is read when unlockvehicles is absent; the port reads the same keys (pc_settings.h)
{
    const cd = fs.mkdtempSync(path.join(os.tmpdir(), 'ms-cheats-'));
    const cini = path.join(cd, 'settings.ini');
    const uv = S.SCHEMA.find(x => x.key === 'unlockvehicles');
    assert.ok(uv && uv.group === 'Cheats' && uv.def === 'Off');
    assert.strictEqual(S.load(cd).values.unlockvehicles, 'Off');
    assert.strictEqual(S.save(cd, { unlockvehicles: 'On' }), null);
    assert.ok(/^unlockvehicles = On$/m.test(fs.readFileSync(cini, 'utf8')));
    assert.strictEqual(S.load(cd).values.unlockvehicles, 'On');
    assert.strictEqual(S.save(cd, { unlockvehicles: 'Off' }), null);
    assert.strictEqual(S.load(cd).values.unlockvehicles, 'Off');
    fs.writeFileSync(cini, 'fsr = Off\r\nunlockall = On\r\n');
    assert.strictEqual(S.load(cd).values.unlockvehicles, 'On', 'the old key is read');
    fs.writeFileSync(cini, 'unlockall = On\r\nunlockvehicles = Off\r\n');
    assert.strictEqual(S.load(cd).values.unlockvehicles, 'Off', 'the new key wins');
    assert.ok(S.save(cd, { unlockvehicles: 'Maybe' }));
    const ps = fs.readFileSync(path.join(__dirname, '..', '..', 'port-vkgame', 'pc_settings.h'), 'utf8');
    assert.ok(ps.includes('"unlockvehicles"') && ps.includes('"unlockall"'), 'pc_settings.h reads the same keys');
    // unlocktracks: its own switch, Off by default, independent of unlockvehicles
    const ut = S.SCHEMA.find(x => x.key === 'unlocktracks');
    assert.ok(ut && ut.group === 'Cheats' && ut.def === 'Off');
    fs.writeFileSync(cini, 'unlockvehicles = On\r\n');
    assert.strictEqual(S.load(cd).values.unlocktracks, 'Off');
    assert.strictEqual(S.save(cd, { unlocktracks: 'On' }), null);
    const lv = S.load(cd).values;
    assert.deepStrictEqual([lv.unlockvehicles, lv.unlocktracks], ['On', 'On']);
    assert.ok(/^unlocktracks = On$/m.test(fs.readFileSync(cini, 'utf8')));
    assert.ok(ps.includes('"unlocktracks"') || ps.includes('unlocktracks'), 'pc_settings.h reads unlocktracks');
    fs.rmSync(cd, { recursive: true, force: true });
}

fs.rmSync(dir, { recursive: true, force: true });
console.log('settings: all checks passed');
