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
    { key: 'resolution', group: 'Display', label: 'Resolution', choices: ['480p', '720p', '1080p', '1440p', '2160p'], def: '720p', values: ['0.667', '1', '1.5', '2', '3'] },
    { key: 'vsync', group: 'Display', label: 'Vertical sync', choices: ['On', 'Off'], def: 'Off', values: ['1', '0'] },
    { key: 'dynres', group: 'Display', label: 'Dynamic resolution (the game\'s own)', choices: ['On', 'Off'], def: 'Off' },
    // one game window over two or three side-by-side monitors of the same height, or one Surround / Eyefinity display
    // that wide (PS3RECOMP_VK_SPAN, libs/video rsx_multiscreen.h): wider view, HUD and menus on the middle screen.
    // Launcher only (the game's Display page is full); the port reads it at start (pc_settings.h pcs_screens).
    { key: 'screens', group: 'Display', label: 'Screens (dual / triple monitors)', choices: ['Single', 'Dual', 'Triple'], def: 'Single', values: ['1', '2', '3'] },
    { key: 'framerate', group: 'Display', label: 'Frame rate', choices: ['30 FPS', '45 FPS', '60 FPS', '80 FPS', '120 FPS', '144 FPS', '180 FPS'], def: '30 FPS', values: ['30', '45', '60', '80', '120', '144', '180'], alias: { variable: '60 FPS', '60fps': '60 FPS' } },
    { key: 'fsrmode', group: 'Upscaling', label: 'Upscaler', choices: ['FSR 1', 'FSR 3.1'], def: 'FSR 1', values: ['1', '3'] },
    { key: 'fsr', group: 'Upscaling', label: 'Upscaling (FSR)', choices: ['Off', 'Ultra Quality', 'Quality', 'Balanced', 'Performance'],
      def: 'Off', values: ['off', 'ultra', 'quality', 'balanced', 'performance'] },
    { key: 'hdr', group: 'Upscaling', label: 'HDR output', choices: ['Off', 'On'], def: 'Off', values: ['0', '1'] },
    // Frame generation (port libs/video rsx_vk_framegen.h, RSX_FRAMEGEN, read at start): one generated frame between two real
    // ones. Light: the port's own motion-vector pass; On: AMD FSR 3.1 frame generation (amd_fidelityfx_framegeneration_vk.dll).
    // Both need Upscaler FSR 3.1 with a quality (not Off) and HDR off; nothing else is changed for it. The game's own page has
    // it as the last Performance row (port pc_pages.h).
    { key: 'framegen', group: 'Upscaling', label: 'Frame generation', choices: ['Off', 'Light', 'On'], def: 'Off', values: ['', 'light', '1'] },
    { key: 'motionblur', group: 'Graphics', label: 'Motion blur', choices: ['On', 'Off'], def: 'On' },
    { key: 'aniso', group: 'Graphics', label: 'Anisotropic filtering', choices: ['Original', '2x', '4x', '8x', '16x'], def: 'Original' },
    { key: 'textures', group: 'Graphics', label: 'HD texture pack', choices: ['Off', 'On'], def: 'Off' },
    { key: 'pbr', group: 'Graphics', label: 'Physically based materials', choices: ['Off', 'On'], def: 'Off' },
    // no 'rtshadow': ray-traced shadows are hidden (slow, and not working with Enhanced lighting); RSX_RT_SHADOW=1 by hand still works
    // Lowest: the shortest draw distance (port pc_settings.h: LOD bias +2, cull x2.5, shadow range 120 m); the old values 1/-1/-2 still read
    { key: 'lod', group: 'Graphics', label: 'Level of detail / draw distance', choices: ['Lowest', 'Low', 'Original', 'High', 'Ultra'], def: 'Original',
      values: ['2', '1', '', '-1', '-2'] },
    { key: 'lighting', group: 'Graphics', label: 'Fidelity', choices: ['Original', 'Enhanced'], def: 'Enhanced' },
    // Off skips the game's own shadow casters (port rsx_shadow_off.h, MSPR_NO_SHADOWS). Shown only with Fidelity Original
    // (launcher ui/app.js; the game's page: port pc_settings.h pcs_row_hidden). Not posted while hidden, so its value is kept.
    { key: 'shadows', group: 'Graphics', label: 'Shadows', choices: ['On', 'Off'], def: 'On', values: ['0', '1'] },
    // the game's button prompts as key caps of the player's keys (port pc_prompts.h); Auto: keys unless a gamepad or wheel is connected
    { key: 'prompts', group: 'Graphics', label: 'Button prompts', choices: ['Keyboard', 'Controller', 'Auto'], def: 'Keyboard', values: ['keyboard', 'controller', 'auto'] },
    // Volumetric fog (port rsx_vk_scenefx.h RSX_FX_VOLFOG, read at start). Saved as chosen; the game applies it only with
    // Fidelity Enhanced (pc_settings.h pcs_row_unused), and its own page is the Effects page (pc_pages.h).
    { key: 'volfog', group: 'Graphics', label: 'Volumetric fog (Enhanced only)', choices: ['Off', 'On'], def: 'Off', values: ['0', '1'] },
    // Wheel ruts (port rsx_ruts.h RSX_FX_RUTS, read at start): only where the game lays its own tyre tracks. As volfog: Enhanced only.
    { key: 'ruts', group: 'Graphics', label: 'Wheel ruts (Enhanced only)', choices: ['Off', 'On'], def: 'Off', values: ['0', '1'] },
    // Effects quality (port rsx_vk_scenefx.h RSX_FX_QUALITY): Light drops AO and light shafts, Minimal also the sun contact shadows.
    { key: 'fxquality', group: 'Graphics', label: 'Effects quality (Enhanced only)', choices: ['Full', 'Light', 'Minimal'], def: 'Full', values: ['0', '1', '2'] },
    // Extra particles (port rsx_particles.h RSX_FX_PARTICLES, read at start): dust, mud clods and spray from the wheels, an
    // added layer over the Enhanced scene. High by default; Fidelity Original never draws them (port pc_settings.h pcs_row_unused).
    { key: 'particles', group: 'Graphics', label: 'Extra particles (Enhanced only)', choices: ['Off', 'Low', 'High'], def: 'High', values: ['0', '1', '2'] },
    // Performance (the game's Performance page, port pc_pages.h): opt-in savings for small GPUs and handhelds. Each default is
    // today's look and sets nothing; nothing here is chosen for the player (the Low-end button in ui/app.js only fills the
    // page). Variables and measured effects: docs/SETTINGS.md, port pc_settings.h.
    { key: 'shadowq', group: 'Performance', label: 'Shadow quality', choices: ['High', 'Medium', 'Low'], def: 'High', values: ['', '4096', '3072'] },
    { key: 'texq', group: 'Performance', label: 'Texture quality', choices: ['Full', 'Half', 'Quarter'], def: 'Full', values: ['', '1', '2'] },
    { key: 'fxdensity', group: 'Performance', label: 'Effects density', choices: ['Full', 'Reduced', 'Low', 'Minimal'], def: 'Full', values: ['', '0.6', '0.35', '0.3'] },
    { key: 'oppdetail', group: 'Performance', label: 'Opponent detail', choices: ['Full', 'Reduced', 'Low'], def: 'Full', values: ['', '1.5', '2.7'] },
    { key: 'drsfloor', group: 'Performance', label: 'Dynamic resolution floor', choices: ['50% (Original)', '40%', '33%'], def: '50% (Original)', values: ['', '0.4', '0.33'] },
    { key: 'debris', group: 'Performance', label: 'Wreck debris (gameplay feel)', choices: ['On', 'Off'], def: 'On', values: ['', '0'] },
    { key: 'boostblur', group: 'Performance', label: 'Boost blur', choices: ['On', 'Off'], def: 'On', values: ['', '0'] },
    // Audio on its own thread (port audio_thread.cpp, the audiothread patch in MSPR_PATCH): the game's audio update runs
    // beside the frame instead of on the main thread. On by default; Off takes the patch out of the list. Launcher only
    // (the game's Performance page is full); the port reads it at start (pc_settings.h pcs_audio_thread).
    { key: 'audiothread', group: 'Performance', label: 'Audio on its own thread', choices: ['On', 'Off'], def: 'On', values: ['1', '0'] },
    // CPU thread placement (port cpu_placement.h, PS3_CPU_PLACEMENT): on a CPU with fast and slow cores (Ryzen AI Zen 5 + Zen 5c,
    // Intel P + E cores) the game's main and render threads stay on the fast cores and its file, movie and audio-mix threads on
    // the slow ones. No change on a CPU whose cores are all alike. Off by default. Launcher only (pc_settings.h pcs_thread_place).
    { key: 'threadplace', group: 'Performance', label: 'CPU thread placement (hybrid CPUs)', choices: ['Off', 'Auto'], def: 'Off', values: ['0', 'auto'] },
    // Racing wheel (libs/input pad_wheel.h; the finer wheel.* keys are in docs/SETTINGS.md, not choices)
    { key: 'wheelmode', group: 'Wheel', label: 'Racing wheel', choices: ['Auto', 'Any Device', 'Off'], def: 'Auto', values: ['auto', 'any', 'off'] },
    { key: 'wheelrange', group: 'Wheel', label: 'Steering range', choices: ['Device', '180 deg', '270 deg', '360 deg', '540 deg', '720 deg', '900 deg'], def: '270 deg', values: ['device', '180', '270', '360', '540', '720', '900'] },
    { key: 'wheeldeadzone', group: 'Wheel', label: 'Steering deadzone', choices: ['0%', '1%', '2%', '3%', '5%', '8%'], def: '1%', values: ['0', '1', '2', '3', '5', '8'] },
    { key: 'wheelcurve', group: 'Wheel', label: 'Steering curve', choices: ['Linear', 'Soft', 'Softer', 'Sharp', 'Sharper'], def: 'Linear', values: ['0', '1', '2', '3', '4'] },
    { key: 'wheelpedals', group: 'Wheel', label: 'Pedals', choices: ['Profile', 'Separate', 'Combined'], def: 'Profile', values: ['profile', 'separate', 'combined'] },
    { key: 'wheelpedaldir', group: 'Wheel', label: 'Pedal direction', choices: ['Auto', 'Normal', 'Inverted'], def: 'Auto', values: ['auto', 'normal', 'inverted'] },
    { key: 'wheelffb', group: 'Wheel', label: 'Force feedback', choices: ['Off', 'Centering', 'Rumble', 'Both'], def: 'Off', values: ['off', 'center', 'rumble', 'both'] },
    { key: 'wheelffbstrength', group: 'Wheel', label: 'Force feedback strength', choices: ['20%', '40%', '60%', '80%', '100%'], def: '60%', values: ['20', '40', '60', '80', '100'] },
    // Cheats (their own tab, not the Settings page): the game reads them at start (port pc_menu.cpp); off by default.
    // unlockvehicles: vehicle classes and tickets. The game also reads the first version's key, unlockall (load below).
    { key: 'unlockvehicles', group: 'Cheats', label: 'Unlock all vehicles', choices: ['Off', 'On'], def: 'Off', values: ['0', '1'], old: 'unlockall' },
    // unlocktracks: the Free Play track list (the Festival and Time Trial lists are not covered yet)
    { key: 'unlocktracks', group: 'Cheats', label: 'Unlock all tracks', choices: ['Off', 'On'], def: 'Off', values: ['0', '1'] },
];
const ACTIONS = [
    ['accelerate', 'W, 2'], ['brake', 'S, 1'], ['steerleft', 'A'], ['steerright', 'D'], ['handbrake', 'Space'],
    ['cross', 'Enter, Ctrl'], ['square', 'Q'], ['triangle', 'E'], ['circle', 'X'], ['l1', 'none'], ['r1', 'none'],
    ['start', 'P'], ['select', 'C'],
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

// Player name ("playername = <name>"): the name other players see in network play. The game used the PSN online ID;
// the port turns this line into PS3_NP_ONLINE_ID and PS3_USER_NAME at start (port pc_settings.h pcs_player_name,
// pcs_player_env). The same rules as a PSN online ID and as the port: 3 to 16 letters, digits, '-' or '_', starting
// with a letter. Empty = no name (the game's defaults).
const PLAYER_NAME_RE = /^[A-Za-z][A-Za-z0-9_-]{2,15}$/;
// text -> { name } (trimmed; '' for none) or { error }
function checkPlayerName(text) {
    const name = String(text == null ? '' : text).trim();
    if (!name || PLAYER_NAME_RE.test(name)) return { name };
    let why;
    if (name.length < 3) why = 'at least 3 characters';
    else if (name.length > 16) why = 'at most 16 characters';
    else if (!/^[A-Za-z]/.test(name)) why = 'it must start with a letter';
    else why = 'only letters (A-Z), digits, - and _ (no spaces or accents)';
    return { error: `Player name "${name}": ${why}. Like a PSN online ID: 3 to 16 letters, digits, - or _, starting with a letter.` };
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

// patch: { key: label } -> the whole file written back (lines it does not name kept, in place; a null label removes
// the key's lines)
function writeIni(file, patch) {
    const { lines } = readIni(file);
    const out = lines ? lines.slice() : ['# MotorStorm: Pacific Rift settings (the in-game Options > PC Settings page and the launcher write this file)'];
    while (out.length && out[out.length - 1] === '') out.pop();
    const left = { ...patch };
    for (let i = 0; i < out.length; i++) {
        const m = /^\s*([^#;=\s][^=]*?)\s*=/.exec(out[i]);
        if (!m) continue;
        const k = m[1].toLowerCase();
        if (patch[k] === null) { out.splice(i--, 1); delete left[k]; continue; }
        if (k in left) { out[i] = `${k} = ${left[k]}`; delete left[k]; }
    }
    for (const [k, v] of Object.entries(left)) if (v !== null) out.push(`${k} = ${v}`);
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
// "Availability")
function load(playDir) {
    const ini = path.join(playDir, 'settings.ini');
    const migrated = migrate(ini, path.join(playDir, 'motorstorm.cfg'));
    const { map } = readIni(ini);
    const values = {};
    for (const s of SCHEMA) values[s.key] = labelFor(s, map[s.key] != null ? map[s.key] : s.old && map[s.old]) || s.def;
    const keys = {};
    for (const [a, def] of ACTIONS) keys[a] = map['key.' + a] != null ? map['key.' + a] : def;
    const cfg = readCfg(path.join(playDir, 'motorstorm.cfg'));
    const missing = {
        fsrmode: fs.existsSync(path.join(cfg.RSX_FSR3_DIR || playDir, 'amd_fidelityfx_loader_vk.dll')) ? null : 'FSR 3.1 needs AMD\'s DLLs (installed with the game)',
        framegen: fs.existsSync(path.join(cfg.RSX_FSR3_DIR || playDir, 'amd_fidelityfx_framegeneration_vk.dll')) ? null : 'On needs AMD\'s frame generation DLL (installed with the game); Light works without it',
        textures: fs.existsSync(path.join(playDir, 'textures', 'pack')) ? null : 'no HD pack yet (HD textures page)',
        pbr: fs.existsSync(path.join(playDir, 'textures', 'pack')) ? null : 'needs an HD pack with PBR maps',
    };
    const playerName = map.playername != null ? map.playername.trim() : '';
    return { values, keys, schema: SCHEMA, actions: ACTIONS, missing, file: ini, migrated, pcmenu: fs.existsSync(path.join(playDir, 'pcmenu', 'pcmenu.json')),
             playerName, playerNameError: checkPlayerName(playerName).error || null };
}

// values: { key: label }, keys: { action: "W, 2" }, playerName (undefined: unchanged; '' removes it) -> settings.ini;
// returns an error text or null (nothing is written then)
function save(playDir, values = {}, keys = {}, playerName) {
    const patch = {};
    if (playerName !== undefined) {
        const p = checkPlayerName(playerName);
        if (p.error) return p.error;
        patch.playername = p.name || null;
    }
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

module.exports = { SCHEMA, ACTIONS, load, save, readCfg, writeCfg, readIni, writeIni, parseBinding, migrate, checkPlayerName };
