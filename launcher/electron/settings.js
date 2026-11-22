// The player's settings: settings.ini beside the game exe (docs/SETTINGS.md). The port owns that file (its in-game
// PC Settings page rewrites all of it); the launcher reads it, changes the keys it knows and writes the whole file back
// through settings.ini.tmp and a rename. Choices are written as their labels. motorstorm.cfg keeps only paths and
// diagnostics (PS3_VFS_ROOT, PS3_HDD0_ROOT, PS3_VFS_OVERLAY, RSX_RT_DXC, RSX_FSR3_DIR, ...).
'use strict';
const fs = require('fs');
const path = require('path');

// key, the page it is on in the game, label, choices (labels; the first value of `values` pairs with each), default
const SCHEMA = [
    { key: 'display', group: 'Display', label: 'Display mode', choices: ['Windowed', 'Fullscreen'], def: 'Windowed', values: ['0', '1'] },
    { key: 'resolution', group: 'Display', label: 'Resolution', choices: ['720p', '1080p', '1440p', '2160p'], def: '720p', values: ['1', '1.5', '2', '3'] },
    { key: 'vsync', group: 'Display', label: 'Vertical sync', choices: ['On', 'Off'], def: 'Off', values: ['1', '0'] },
    { key: 'dynres', group: 'Display', label: 'Dynamic resolution (the game\'s own)', choices: ['On', 'Off'], def: 'Off' },
    { key: 'framerate', group: 'Display', label: 'Frame rate', choices: ['30 FPS', '45 FPS', '60 FPS', '80 FPS', '120 FPS', '144 FPS', '180 FPS'], def: '60 FPS', values: ['30', '45', '60', '80', '120', '144', '180'], alias: { variable: '60 FPS', '60fps': '60 FPS' } },
    { key: 'fsrmode', group: 'Upscaling', label: 'Upscaler', choices: ['FSR 1', 'FSR 3.1'], def: 'FSR 1', values: ['1', '3'] },
    { key: 'fsr', group: 'Upscaling', label: 'Upscaling (FSR)', choices: ['Off', 'Ultra Quality', 'Quality', 'Balanced', 'Performance'],
      def: 'Off', values: ['off', 'ultra', 'quality', 'balanced', 'performance'] },
    { key: 'hdr', group: 'Upscaling', label: 'HDR output', choices: ['Off', 'On'], def: 'Off', values: ['0', '1'] },
    { key: 'motionblur', group: 'Graphics', label: 'Motion blur', choices: ['On', 'Off'], def: 'On' },
    { key: 'aniso', group: 'Graphics', label: 'Anisotropic filtering', choices: ['Original', '2x', '4x', '8x', '16x'], def: 'Original' },
    { key: 'textures', group: 'Graphics', label: 'HD texture pack', choices: ['Off', 'On'], def: 'Off' },
    { key: 'pbr', group: 'Graphics', label: 'Physically based materials', choices: ['Off', 'On'], def: 'Off' },
    { key: 'rtshadow', group: 'Graphics', label: 'Ray-traced shadows', choices: ['Off', 'On'], def: 'Off' },
    { key: 'lod', group: 'Graphics', label: 'Level of detail', choices: ['Original', 'High', 'Ultra'], def: 'Original' },
    // Racing wheel (libs/input pad_wheel.h; the finer wheel.* keys are in docs/SETTINGS.md, not choices)
    { key: 'wheelmode', group: 'Wheel', label: 'Racing wheel', choices: ['Auto', 'Any Device', 'Off'], def: 'Auto', values: ['auto', 'any', 'off'] },
    { key: 'wheelrange', group: 'Wheel', label: 'Steering range', choices: ['Device', '180 deg', '270 deg', '360 deg', '540 deg', '720 deg', '900 deg'], def: '270 deg', values: ['device', '180', '270', '360', '540', '720', '900'] },
    { key: 'wheeldeadzone', group: 'Wheel', label: 'Steering deadzone', choices: ['0%', '1%', '2%', '3%', '5%', '8%'], def: '1%', values: ['0', '1', '2', '3', '5', '8'] },
    { key: 'wheelcurve', group: 'Wheel', label: 'Steering curve', choices: ['Linear', 'Soft', 'Softer', 'Sharp', 'Sharper'], def: 'Linear', values: ['0', '1', '2', '3', '4'] },
    { key: 'wheelpedals', group: 'Wheel', label: 'Pedals', choices: ['Profile', 'Separate', 'Combined'], def: 'Profile', values: ['profile', 'separate', 'combined'] },
    { key: 'wheelpedaldir', group: 'Wheel', label: 'Pedal direction', choices: ['Auto', 'Normal', 'Inverted'], def: 'Auto', values: ['auto', 'normal', 'inverted'] },
    { key: 'wheelffb', group: 'Wheel', label: 'Force feedback', choices: ['Off', 'Centering', 'Rumble', 'Both'], def: 'Off', values: ['off', 'center', 'rumble', 'both'] },
    { key: 'wheelffbstrength', group: 'Wheel', label: 'Force feedback strength', choices: ['20%', '40%', '60%', '80%', '100%'], def: '60%', values: ['20', '40', '60', '80', '100'] },
];
const ACTIONS = [
    ['accelerate', 'W, 2'], ['brake', 'S, 1'], ['steerleft', 'A'], ['steerright', 'D'], ['handbrake', 'Space'],
    ['cross', 'Z, Ctrl'], ['square', 'R'], ['triangle', 'F'], ['circle', 'X'], ['l1', 'Q'], ['r1', 'E'],
    ['start', 'Enter'], ['select', 'Tab'],
];
const KEY_NAMES = new Set(('Space Enter Tab Ctrl Shift Backspace Left Right Up Down Insert Delete Home End PageUp PageDown ' +
    'CapsLock Pause NumLock ScrollLock NumPlus NumMinus NumMultiply NumDivide NumDecimal Semicolon Equals Comma Minus ' +
    'Period Slash Backquote LBracket Backslash RBracket Quote none').toLowerCase().split(' '));
function validKey(k) {
    const s = k.trim().toLowerCase();
    return /^[a-z0-9]$/.test(s) || /^f([1-9]|1[0-9]|2[0-4])$/.test(s) || /^num[0-9]$/.test(s) || /^0x[0-9a-f]{1,2}$/.test(s) || KEY_NAMES.has(s);
}
// "W, 2": at most two keys, each a name docs/SETTINGS.md lists; returns the normalised text or null
function parseBinding(text) {
    const keys = String(text).split(',').map(s => s.trim()).filter(Boolean);
    if (!keys.length || keys.length > 2 || !keys.every(validKey)) return null;
    return keys.join(', ');
}

// the old motorstorm.cfg variables and how each becomes a settings.ini line (migration)
const FROM_CFG = {
    RSX_FSR: 'fsr', RSX_FSR_MODE: 'fsrmode', RSX_HDR: 'hdr', PS3RECOMP_VK_FULLSCREEN: 'display', RSX_PRESENT_INTERVAL: 'vsync',
};

function labelFor(item, raw) {
    if (raw == null) return null;
    const v = String(raw).trim().toLowerCase();
    let i = item.choices.findIndex(c => c.toLowerCase() === v);
    if (i < 0 && item.values) i = item.values.findIndex(c => c.toLowerCase() === v);
    if (i < 0 && item.alias && item.alias[v]) return item.alias[v];   // old file values (framerate: Variable)
    return i < 0 ? null : item.choices[i];
}

function readIni(file) {
    const map = {};
    let lines = [];
    try { lines = fs.readFileSync(file, 'utf8').split(/\r?\n/); } catch { return { map, lines: null }; }
    for (const l of lines) {
        const m = /^\s*([^#;=\s][^=]*?)\s*=\s*(.*?)\s*$/.exec(l);
        if (m) map[m[1].toLowerCase()] = m[2];
    }
    return { map, lines };
}

// patch: { key: label } -> the whole file written back (lines it does not name kept, in place)
function writeIni(file, patch) {
    const { lines } = readIni(file);
    const out = lines ? lines.slice() : ['# MotorStorm: Pacific Rift settings (the in-game Options > PC Settings page and the launcher write this file)'];
    while (out.length && out[out.length - 1] === '') out.pop();
    const left = { ...patch };
    for (let i = 0; i < out.length; i++) {
        const m = /^\s*([^#;=\s][^=]*?)\s*=/.exec(out[i]);
        if (!m) continue;
        const k = m[1].toLowerCase();
        if (k in left) { out[i] = `${k} = ${left[k]}`; delete left[k]; }
    }
    for (const [k, v] of Object.entries(left)) out.push(`${k} = ${v}`);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    const tmp = file + '.tmp';
    fs.writeFileSync(tmp, out.join('\r\n') + '\r\n');
    fs.renameSync(tmp, file);
}

// motorstorm.cfg: NAME=value, others kept
function readCfg(file) {
    const out = {};
    try {
        for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
            const m = /^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/.exec(line);
            if (m) out[m[1]] = m[2];
        }
    } catch { /* none yet */ }
    return out;
}
function writeCfg(file, patch) {
    const cur = { ...readCfg(file), ...patch };
    const lines = ['# MotorStorm: Pacific Rift paths and diagnostics (written by the launcher; the settings are in settings.ini)'];
    for (const [k, v] of Object.entries(cur)) if (v !== '' && v != null) lines.push(`${k}=${v}`);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    const tmp = file + '.tmp';
    fs.writeFileSync(tmp, lines.join('\n') + '\n');
    fs.renameSync(tmp, file);
}

// once: no settings.ini yet -> made from the old launcher's motorstorm.cfg lines, which are then removed from the cfg
function migrate(ini, cfgFile) {
    if (fs.existsSync(ini)) return false;
    const cfg = readCfg(cfgFile);
    const patch = {}, drop = {};
    for (const [v, key] of Object.entries(FROM_CFG)) {
        if (!(v in cfg)) continue;
        const label = labelFor(SCHEMA.find(s => s.key === key), cfg[v]);
        if (label) patch[key] = label;
        drop[v] = '';
    }
    if ('RSX_TEX_PACK' in cfg) { if (cfg.RSX_TEX_PACK) patch.textures = 'On'; drop.RSX_TEX_PACK = ''; }
    if ('RSX_TEX_PBR' in cfg) { if (cfg.RSX_TEX_PBR === '1') patch.pbr = 'On'; drop.RSX_TEX_PBR = ''; }
    if (!Object.keys(drop).length) return false;
    writeIni(ini, patch);
    writeCfg(cfgFile, drop);
    return true;
}

// what the page shows: each setting's label, and why a choice would not apply on this PC (docs/SETTINGS.md
// "Availability"; the GPU's ray tracing is known only to the game)
function load(playDir) {
    const ini = path.join(playDir, 'settings.ini');
    const migrated = migrate(ini, path.join(playDir, 'motorstorm.cfg'));
    const { map } = readIni(ini);
    const values = {};
    for (const s of SCHEMA) values[s.key] = labelFor(s, map[s.key]) || s.def;
    const keys = {};
    for (const [a, def] of ACTIONS) keys[a] = map['key.' + a] != null ? map['key.' + a] : def;
    const cfg = readCfg(path.join(playDir, 'motorstorm.cfg'));
    const dxc = cfg.RSX_RT_DXC || path.join(playDir, 'dxc', 'dxc.exe');
    const missing = {
        rtshadow: fs.existsSync(dxc) ? null : 'needs DXC (installed with the game)',
        fsrmode: fs.existsSync(path.join(cfg.RSX_FSR3_DIR || playDir, 'amd_fidelityfx_loader_vk.dll')) ? null : 'FSR 3.1 needs AMD\'s DLLs (installed with the game)',
        textures: fs.existsSync(path.join(playDir, 'textures', 'pack')) ? null : 'no HD pack yet (HD textures page)',
        pbr: fs.existsSync(path.join(playDir, 'textures', 'pack')) ? null : 'needs an HD pack with PBR maps',
    };
    return { values, keys, schema: SCHEMA, actions: ACTIONS, missing, file: ini, migrated, pcmenu: fs.existsSync(path.join(playDir, 'pcmenu', 'pcmenu.json')) };
}

// values: { key: label }, keys: { action: "W, 2" } -> settings.ini; returns an error text or null
function save(playDir, values = {}, keys = {}) {
    const patch = {};
    for (const [k, v] of Object.entries(values)) {
        const s = SCHEMA.find(x => x.key === k);
        const label = s && labelFor(s, v);
        if (!label) return `Unknown setting ${k} = ${v}`;
        patch[k] = label;
    }
    for (const [a, v] of Object.entries(keys)) {
        if (!ACTIONS.some(([x]) => x === a)) return `Unknown control ${a}`;
        const b = parseBinding(v);
        if (!b) return `"${v}" for ${a}: one or two keys, e.g. "W, 2" (letters, digits, F1-F24, Space, Enter, Ctrl, Shift, ...; Esc and Alt cannot be bound)`;
        patch['key.' + a] = b;
    }
    writeIni(path.join(playDir, 'settings.ini'), patch);
    return null;
}

module.exports = { SCHEMA, ACTIONS, load, save, readCfg, writeCfg, readIni, writeIni, parseBinding, migrate };
