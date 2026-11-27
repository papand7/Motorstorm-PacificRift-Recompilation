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

// Screens (dual / triple monitors): a Display choice, Single by default, labels or 1/2/3 read back; the port reads the
// same key and labels (pc_settings.h pcs_screens, k_pcs_screens) and turns them into PS3RECOMP_VK_SPAN
{
    const sd = fs.mkdtempSync(path.join(os.tmpdir(), 'ms-screens-'));
    const sini = path.join(sd, 'settings.ini');
    const sc = S.SCHEMA.find(x => x.key === 'screens');
    assert.ok(sc && sc.group === 'Display' && sc.def === 'Single');
    assert.deepStrictEqual(sc.choices, ['Single', 'Dual', 'Triple']);
    assert.strictEqual(S.load(sd).values.screens, 'Single');
    assert.strictEqual(S.save(sd, { screens: 'Triple' }), null);
    assert.ok(/^screens = Triple$/m.test(fs.readFileSync(sini, 'utf8')));
    fs.writeFileSync(sini, 'screens = 2\r\n');
    assert.strictEqual(S.load(sd).values.screens, 'Dual');
    assert.ok(S.save(sd, { screens: 'Quad' }));
    const ps = fs.readFileSync(path.join(__dirname, '..', '..', 'port-vkgame', 'pc_settings.h'), 'utf8');
    assert.ok(ps.includes('"screens"') || /strncmp\(p, "screens"/.test(ps), 'pc_settings.h reads screens');
    assert.ok(ps.includes('{ "Single", "Dual", "Triple" }'), 'pc_settings.h has the same labels');
    fs.rmSync(sd, { recursive: true, force: true });
}

// Player name: PSN online ID rules (3-16 letters, digits, - or _, starting with a letter), saved as "playername = <name>",
// read back, removed when emptied, untouched when not posted; invalid names are refused and the file is not changed.
// The port reads the same key with the same rules (pc_settings.h pcs_player_name / pcs_name_valid).
{
    const pd = fs.mkdtempSync(path.join(os.tmpdir(), 'ms-player-'));
    const pini = path.join(pd, 'settings.ini');
    for (const ok of ['Abc', 'Racer_01', 'Mud-Pig', 'abcdefghijklmnop', '  Padded  '])
        assert.ok(!S.checkPlayerName(ok).error, ok);
    assert.strictEqual(S.checkPlayerName('  Padded  ').name, 'Padded');
    assert.strictEqual(S.checkPlayerName('').name, '');
    for (const [bad, why] of [['ab', '3 characters'], ['abcdefghijklmnopq', '16 characters'], ['1abc', 'start with a letter'],
                              ['_abc', 'start with a letter'], ['ab c', 'only letters'], ['abc!', 'only letters'], ['Jörg', 'only letters']])
        assert.ok(S.checkPlayerName(bad).error && S.checkPlayerName(bad).error.includes(why), bad);
    // unset: no line, empty in load, no error
    let p = S.load(pd);
    assert.deepStrictEqual([p.playerName, p.playerNameError], ['', null]);
    // set, beside other settings and lines the launcher does not know
    fs.writeFileSync(pini, '; the game\r\nfsr = Off\r\nfuture_key = 7\r\n');
    assert.strictEqual(S.save(pd, { fsr: 'Quality' }, {}, 'Racer_01'), null);
    let text = fs.readFileSync(pini, 'utf8');
    assert.ok(/^playername = Racer_01\r$/m.test(text) && text.includes('fsr = Quality') && text.includes('future_key = 7'));
    p = S.load(pd);
    assert.deepStrictEqual([p.playerName, p.playerNameError], ['Racer_01', null]);
    // not posted (the Cheats page saves without it): kept
    assert.strictEqual(S.save(pd, { unlocktracks: 'On' }, {}), null);
    assert.strictEqual(S.load(pd).playerName, 'Racer_01');
    // changed in place (one line), any case of the key read
    assert.strictEqual(S.save(pd, {}, {}, 'Mud-Pig'), null);
    text = fs.readFileSync(pini, 'utf8');
    assert.strictEqual((text.match(/^playername = /gm) || []).length, 1);
    assert.strictEqual(S.load(pd).playerName, 'Mud-Pig');
    // invalid: refused with a message, nothing written (the other settings in the same save are not written either)
    const before = fs.readFileSync(pini, 'utf8');
    const err = S.save(pd, { fsr: 'Performance' }, {}, 'no spaces');
    assert.ok(err && /Player name "no spaces"/.test(err));
    assert.strictEqual(fs.readFileSync(pini, 'utf8'), before);
    // emptied: every playername line removed, the rest kept
    fs.appendFileSync(pini, 'PlayerName = Old\r\n');
    assert.strictEqual(S.save(pd, {}, {}, '  '), null);
    text = fs.readFileSync(pini, 'utf8');
    assert.ok(!/playername/i.test(text) && text.includes('future_key = 7') && text.includes('unlocktracks = On'));
    assert.strictEqual(S.load(pd).playerName, '');
    // a bad line written by hand: shown with its error (the game ignores it)
    fs.appendFileSync(pini, 'playername = 9lives\r\n');
    p = S.load(pd);
    assert.ok(p.playerName === '9lives' && /start with a letter/.test(p.playerNameError));
    // the port: same key, same rules, and the two variables it sets
    const ps = fs.readFileSync(path.join(__dirname, '..', '..', 'port-vkgame', 'pc_settings.h'), 'utf8');
    assert.ok(ps.includes('"playername"') && ps.includes('#define PCS_NAME_MAX 16'));
    assert.ok(ps.includes('"PS3_NP_ONLINE_ID"') && ps.includes('"PS3_USER_NAME"'));
    fs.rmSync(pd, { recursive: true, force: true });
}

fs.rmSync(dir, { recursive: true, force: true });
console.log('settings: all checks passed');

// Frame generation (port RSX_FRAMEGEN): Off by default and written as a label; Light and On read back by label and by
// value; On's DLL is reported missing on its own, Light needs none; nothing else changes with it.
{
    const fs2 = require('fs'), os2 = require('os'), path2 = require('path');
    const d = fs2.mkdtempSync(path2.join(os2.tmpdir(), 'fg-'));
    const fg = S.SCHEMA.find(x => x.key === 'framegen');
    assert.ok(fg && fg.def === 'Off' && fg.group === 'Upscaling');
    assert.deepStrictEqual(fg.choices, ['Off', 'Light', 'On']);
    assert.deepStrictEqual(fg.values, ['', 'light', '1']);
    let l = S.load(d);
    assert.strictEqual(l.values.framegen, 'Off');
    assert.ok(l.missing.framegen && /frame generation DLL/.test(l.missing.framegen));
    assert.strictEqual(S.save(d, { framegen: 'Light' }, {}), null);
    const t = fs2.readFileSync(path2.join(d, 'settings.ini'), 'utf8');
    assert.ok(/^framegen = Light$/m.test(t));
    l = S.load(d);
    assert.strictEqual(l.values.framegen, 'Light');
    assert.strictEqual(l.values.fsrmode, 'FSR 1');          // not changed for it
    assert.strictEqual(l.values.hdr, 'Off');
    fs2.writeFileSync(path2.join(d, 'settings.ini'), 'framegen = 1\n');
    assert.strictEqual(S.load(d).values.framegen, 'On');   // by value
    fs2.writeFileSync(path2.join(d, 'amd_fidelityfx_framegeneration_vk.dll'), '');
    assert.strictEqual(S.load(d).missing.framegen, null);
    console.log('framegen settings ok');
}
// Audio thread: a Performance switch, On by default, written as its label; the port reads the same key
// (pc_settings.h pcs_audio_thread, pcs_mspr_drop) and only Off changes anything
{
    const ad = fs.mkdtempSync(path.join(os.tmpdir(), 'ms-audiothread-'));
    const aini = path.join(ad, 'settings.ini');
    const at = S.SCHEMA.find(x => x.key === 'audiothread');
    assert.ok(at && at.group === 'Performance' && at.def === 'On', 'audiothread switch');
    assert.strictEqual(S.load(ad).values.audiothread, 'On');
    assert.strictEqual(S.save(ad, { audiothread: 'Off' }), null);
    assert.ok(/^audiothread = Off$/m.test(fs.readFileSync(aini, 'utf8')));
    assert.strictEqual(S.load(ad).values.audiothread, 'Off');
    const ps = fs.readFileSync(path.join(__dirname, '..', '..', 'port-vkgame', 'pc_settings.h'), 'utf8');
    assert.ok(ps.includes('"audiothread"') && ps.includes('pcs_mspr_drop'), 'pc_settings.h reads audiothread');
    const tp = S.SCHEMA.find(x => x.key === 'threadplace');
    assert.ok(tp && tp.group === 'Performance' && tp.def === 'Off', 'threadplace switch');
    assert.strictEqual(S.save(ad, { threadplace: 'Auto' }), null);
    assert.ok(/^threadplace = Auto$/m.test(fs.readFileSync(aini, 'utf8')));
    assert.strictEqual(S.load(ad).values.threadplace, 'Auto');
    assert.ok(ps.includes('"threadplace"') && ps.includes('pcs_thread_place'), 'pc_settings.h reads threadplace');
    fs.rmSync(ad, { recursive: true, force: true });
    console.log('audiothread settings ok');
}

// Experimental switches: environment variables in motorstorm.cfg; off removes them; other cfg lines stay
{
    const ed = fs.mkdtempSync(path.join(os.tmpdir(), 'ms-exp-'));
    const cfgf = path.join(ed, 'motorstorm.cfg');
    S.writeCfg(cfgf, { PS3_VFS_ROOT: 'C:\game' });
    assert.ok(S.experimentalLoad(ed).every(i => i.on === false), 'all off by default');
    assert.strictEqual(S.experimentalSave(ed, { spulanes: true, spuhwfloat: true }), null);
    const c = S.readCfg(cfgf);
    assert.deepStrictEqual([c.PS3_SPU_HOST_LANES, c.PS3_SPU_HOST_LANES_WIDE, c.PS3_SPU_HWFLOAT, c.PS3_VFS_ROOT], ['6', '1', '1', 'C:\game']);
    const on = Object.fromEntries(S.experimentalLoad(ed).map(i => [i.key, i.on]));
    assert.deepStrictEqual(on, { spuhwfloat: true, spulanes: true, spudmarepeat: false });
    assert.strictEqual(S.experimentalSave(ed, { spulanes: false }), null);
    const c2 = S.readCfg(cfgf);
    assert.ok(!('PS3_SPU_HOST_LANES' in c2) && !('PS3_SPU_HOST_LANES_WIDE' in c2) && c2.PS3_SPU_HWFLOAT === '1' && c2.PS3_VFS_ROOT === 'C:\game');
    assert.ok(/^Unknown/.test(S.experimentalSave(ed, { nope: true })));
    fs.rmSync(ed, { recursive: true, force: true });
    console.log('experimental settings ok');
}
