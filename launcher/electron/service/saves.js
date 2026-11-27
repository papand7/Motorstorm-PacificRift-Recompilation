// Save import: the player's own MotorStorm: Pacific Rift saves from a PS3 (exported to USB) or from RPCS3, copied into
// the port's save folder so the game loads them.
//
// Where the port keeps saves (ps3recomp-vkgame libs/system/cellSaveData.c): $PS3_GAMEDATA_ROOT/dev_hdd0/home/00000001/
// savedata/<dir>, and the launcher sets PS3_GAMEDATA_ROOT to <play>\saves\v100 (bench.js gameEnv). <dir> is the title
// id the game is given by cellGameBootCheck: the port never reads the disc's PARAM.SFO, so that is the framework's
// default "BLES00000" for the USA and the Europe disc alike (libs/system/cellGame.c s_title_id); the game's main save
// is BLES00000 (AUTOSAVE.DAT, ICON0.PNG), its time-attack ghosts BLES00000-TIMEATTACK.
//
// What a save from elsewhere needs to load here:
//   * its folder renamed from <its title id>[-SUFFIX] to BLES00000[-SUFFIX], and SAVEDATA_DIRECTORY in its PARAM.SFO
//     with it. Both discs run the same program (game.json), so a save of any region is the same data.
//   * PARAM.PFD left out: the port keeps its own list of the save's protected files under that name (one name per
//     line); it is written from the source's list.
//   * a PS3 console's protected files (listed in its binary PARAM.PFD) decrypted. That needs the PS3's save-data key
//     and the game's secure file id, which this launcher does not carry: the player points it at the global.conf and
//     games.conf of their own save tool (pfdtool, Bruteforce Save Data). Without them such a save is shown but not
//     imported. RPCS3 stores files decrypted (it lists the protected ones in PARAM.SFO as "*NAME" = 1).
//
// The source save is only read. A save already in the target slot is copied to <play>\saves\backups\<time>-<dir>
// first, and can be put back (restoreBackup).
'use strict';
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// the game's title ids (its discs; pfdtool's games.conf groups these for this game) and the port's own
const TITLE_IDS = {
    BCUS98155: 'USA', BCES00129: 'Europe', BCJS30027: 'Japan', BCAS20035: 'Asia', BCAS20044: 'Asia', BCKS10041: 'Korea',
    BLES00000: 'this PC port',
};
const PORT_DIR = 'BLES00000';                 // the save folder name the port's game asks for
const USER_SAVEDATA = ['dev_hdd0', 'home', '00000001', 'savedata'];   // below PS3_GAMEDATA_ROOT

const LIMITS = { files: 64, fileBytes: 16 << 20, totalBytes: 64 << 20, sfoBytes: 64 << 10, pfdBytes: 1 << 20,
                 iconBytes: 1 << 20, scanDirs: 4000, scanDepth: 7 };
const NAME_RE = /^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,62}$/;          // a save's file names (no separators, no "..")
const DIR_RE = /^([A-Z]{4}\d{5})(-[A-Za-z0-9_\-]{1,22})?$/;     // <title id>[-SUFFIX], as the PS3 names save folders

class SaveError extends Error { get name() { return 'SaveError'; } }

// ---- PARAM.SFO (PSF: little-endian header and entry table, then key and data tables)
function parseSfo(buf) {
    if (!Buffer.isBuffer(buf) || buf.length < 20 || buf.length > LIMITS.sfoBytes) throw new SaveError('PARAM.SFO has a wrong size');
    if (buf.readUInt32BE(0) !== 0x00505346) throw new SaveError('PARAM.SFO is not a PSF file');
    const keysAt = buf.readUInt32LE(8), dataAt = buf.readUInt32LE(12), n = buf.readUInt32LE(16);
    if (n > 256 || 20 + 16 * n > buf.length || keysAt > buf.length || dataAt > buf.length) throw new SaveError('PARAM.SFO is damaged');
    const entries = [];
    for (let i = 0; i < n; i++) {
        const e = 20 + 16 * i;
        const keyAt = keysAt + buf.readUInt16LE(e), fmt = buf.readUInt16LE(e + 2);
        const len = buf.readUInt32LE(e + 4), max = buf.readUInt32LE(e + 8), at = dataAt + buf.readUInt32LE(e + 12);
        const keyEnd = buf.indexOf(0, keyAt);
        if (keyAt >= buf.length || keyEnd < 0 || len > max || at + max > buf.length) throw new SaveError('PARAM.SFO is damaged');
        entries.push({ key: buf.toString('latin1', keyAt, keyEnd), fmt, len, max, at, entry: e });
    }
    const find = k => entries.find(x => x.key === k);
    return {
        entries,
        str(k) { const x = find(k); if (!x || x.fmt !== 0x0204) return null; const end = buf.indexOf(0, x.at); return buf.toString('utf8', x.at, end >= 0 && end < x.at + x.len ? end : x.at + x.len); },
        int(k) { const x = find(k); return x && x.fmt === 0x0404 && x.len >= 4 ? buf.readUInt32LE(x.at) : null; },
        has: k => !!find(k),
    };
}
// a copy of the SFO with one UTF-8 string entry set (it must fit the entry's reserved size)
function sfoSetString(buf, key, value) {
    const sfo = parseSfo(buf);
    const x = sfo.entries.find(e => e.key === key);
    const v = Buffer.from(String(value) + '\0', 'utf8');
    if (!x || x.fmt !== 0x0204) throw new SaveError(`PARAM.SFO has no ${key}`);
    if (v.length > x.max) throw new SaveError(`${key} does not fit in PARAM.SFO`);
    const out = Buffer.from(buf);
    out.fill(0, x.at, x.at + x.max);
    v.copy(out, x.at);
    out.writeUInt32LE(v.length, x.entry + 4);
    return out;
}

// ---- PARAM.PFD: a PS3's binary one (version 3/4: header, signature, hash table, entries of 0x110 bytes), or the
// port's own text list of protected files
const PFD_MAGIC = 0x50464442n;
const PFD_ENTRY = 0x110;
function parsePfd(buf) {
    if (buf.length < 0x78 || buf.readBigUInt64BE(0) !== PFD_MAGIC) return null;
    const version = Number(buf.readBigUInt64BE(8));
    const tableAt = 0x60;                                    // magic, version, IV, encrypted signature (64 bytes)
    const cap = Number(buf.readBigUInt64BE(tableAt)), reserved = Number(buf.readBigUInt64BE(tableAt + 8));
    const used = Number(buf.readBigUInt64BE(tableAt + 16));
    if (cap > 4096 || reserved > 4096 || used > reserved) throw new SaveError('PARAM.PFD is damaged');
    const entriesAt = tableAt + 24 + cap * 8;
    if (entriesAt + used * PFD_ENTRY > buf.length) throw new SaveError('PARAM.PFD is damaged');
    const entries = [];
    for (let i = 0; i < used; i++) {
        const e = entriesAt + i * PFD_ENTRY;
        const nameEnd = buf.indexOf(0, e + 8);
        const name = buf.toString('latin1', e + 8, nameEnd >= 0 && nameEnd < e + 8 + 65 ? nameEnd : e + 8 + 65);
        entries.push({ name, key: buf.subarray(e + 0x50, e + 0x60), size: Number(buf.readBigUInt64BE(e + 0x108)) });
    }
    return { version, entries };
}
const portPfdNames = buf => buf.toString('latin1').split(/\r?\n/).filter(n => NAME_RE.test(n));

// ---- the profile (AUTOSAVE.DAT, XML text). The port runs the disc's program (1.00), which writes and accepts only
// <ProfileVersion version = "Beta 2"/>; the game's updates (1.03 is the last) write "Beta 3", and 1.00 answers such a
// save with "The save data is corrupted. Retry load?" (generated/analysis/save_import/RESULTS.md). A "Beta 3"
// profile keeps every 1.00 key and adds new ones (DLC packs, more statistics), so it is converted by setting its
// version line to "Beta 2"; the keys are kept as they are.
const PROFILE_100 = 'Beta 2';
const PROFILE_NEWER = ['Beta 3'];
function profileFor100(data) {
    const head = data.subarray(0, 256).toString('latin1');
    const m = /^<\?xml version="1\.0"\?>\r?\n<ProfileVersion version = "([^"]{1,32})"\/>/.exec(head);
    if (!m) return { error: 'AUTOSAVE.DAT is not a MotorStorm: Pacific Rift profile.' };
    if (m[1] === PROFILE_100) return { data };
    if (!PROFILE_NEWER.includes(m[1])) return { error: `The profile's version "${m[1]}" is not one this game knows.` };
    const at = head.indexOf(`"${m[1]}"`) + 1;
    return { data: Buffer.concat([data.subarray(0, at), Buffer.from(PROFILE_100, 'latin1'), data.subarray(at + m[1].length)]), from: m[1] };
}

// ---- protected-file decryption (the public PFD scheme, as pfdtool and Apollo implement it). The keys come from the
// player's own save tool at run time: none is in this source.
//   hash key  = the secure file id with fixed bytes at 1, 2, 5, 8 (20 bytes); its first 16 bytes are the IV
//   file key  = AES-128-CBC-decrypt(syscon manager key, IV, the entry's encrypted key), first block
//   block i   = AES-ECB-decrypt(file key, C_i) XOR AES-ECB-encrypt(file key, be64(i) || 0^8)
function secureHashKey(secureFileId) {
    const out = Buffer.alloc(20);
    for (let i = 0, j = 0; i < 20; i++) out[i] = { 1: 11, 2: 15, 5: 14, 8: 10 }[i] ?? secureFileId[j++];
    return out;
}
function aes(mode, decrypt, key, iv, data) {
    const c = (decrypt ? crypto.createDecipheriv : crypto.createCipheriv)(mode, key, iv);
    c.setAutoPadding(false);
    return Buffer.concat([c.update(data), c.final()]);
}
function pfdFileKey(encKey, secureFileId, sysconKey) {
    return aes('aes-128-cbc', true, sysconKey, secureHashKey(secureFileId).subarray(0, 16), encKey.subarray(0, 16));
}
function pfdCrypt(data, fileKey, decrypt) {
    const n = data.length & ~15;
    const ctr = Buffer.alloc(n);
    for (let i = 0; i < n / 16; i++) ctr.writeBigUInt64BE(BigInt(i), i * 16);
    const pad = aes('aes-128-ecb', false, fileKey, null, ctr);
    const xor = (a, b) => { const o = Buffer.alloc(a.length); for (let i = 0; i < a.length; i++) o[i] = a[i] ^ b[i]; return o; };
    return decrypt ? xor(aes('aes-128-ecb', true, fileKey, null, data.subarray(0, n)), pad)
                   : aes('aes-128-ecb', false, fileKey, null, xor(data.subarray(0, n), pad));
}
function decryptProtected(data, entry, secureFileId, sysconKey) {
    if (data.length < entry.size || data.length % 16) throw new SaveError(`${entry.name} is not the size PARAM.PFD gives`);
    return pfdCrypt(data, pfdFileKey(entry.key, secureFileId, sysconKey), true).subarray(0, entry.size);
}

// the keys from a pfdtool / Bruteforce Save Data folder: global.conf (syscon_manager_key) and games.conf
// ([ID/ID/...] sections with secure_file_id:*=...). Only these two values are read; nothing is stored.
function readKeyFolder(folder) {
    const read = name => { try { return fs.readFileSync(path.join(folder, name), 'latin1'); } catch { return null; } };
    const global = read('global.conf'), games = read('games.conf');
    if (global == null || games == null) throw new SaveError('That folder has no global.conf and games.conf (pfdtool or Bruteforce Save Data).');
    const m = /^\s*syscon_manager_key\s*=\s*([0-9A-Fa-f]{32})\s*$/m.exec(global);
    if (!m) throw new SaveError('global.conf has no syscon_manager_key.');
    const secureIds = {};
    let ids = [];
    for (const line of games.split(/\r?\n/)) {
        const sec = /^\s*\[([^\]]+)\]/.exec(line);
        if (sec) { ids = sec[1].split('/').map(s => s.trim()); continue; }
        const s = /^\s*secure_file_id:\*\s*=\s*([0-9A-Fa-f]{32})\s*$/.exec(line);
        if (s) for (const id of ids) secureIds[id] = Buffer.from(s[1], 'hex');
    }
    return { sysconKey: Buffer.from(m[1], 'hex'), secureIds, folder };
}

// ---- reading a save folder (any source); nothing is written
function lstatOk(p) { try { return fs.lstatSync(p); } catch { return null; } }
function inspectSave(dir) {
    const out = { path: dir, dirName: path.basename(dir), files: [], problems: [] };
    const sfoStat = lstatOk(path.join(dir, 'PARAM.SFO'));
    if (!sfoStat || !sfoStat.isFile()) return null;                  // not a save folder
    let total = 0;
    for (const name of fs.readdirSync(dir)) {
        const st = lstatOk(path.join(dir, name));
        if (!st) continue;
        if (st.isSymbolicLink() || !st.isFile()) { out.problems.push(`${name} is not a plain file`); continue; }
        if (!NAME_RE.test(name)) { out.problems.push(`${name}: not a save file name`); continue; }
        if (st.size > LIMITS.fileBytes) out.problems.push(`${name} is too large`);
        total += st.size;
        out.files.push({ name, size: st.size, mtime: st.mtimeMs });
    }
    if (out.files.length > LIMITS.files) out.problems.push('too many files');
    if (total > LIMITS.totalBytes) out.problems.push('the save is too large');
    let sfo;
    try { sfo = parseSfo(fs.readFileSync(path.join(dir, 'PARAM.SFO'))); } catch (e) { out.problems.push(e.message); return out; }
    out.title = sfo.str('TITLE') || '';
    out.subtitle = sfo.str('SUB_TITLE') || '';
    out.detail = sfo.str('DETAIL') || '';
    out.saveDir = sfo.str('SAVEDATA_DIRECTORY') || '';
    out.category = sfo.str('CATEGORY') || '';
    const id = DIR_RE.exec(out.saveDir) || DIR_RE.exec(out.dirName);
    out.titleId = id ? id[1] : '';
    out.suffix = id && id[2] ? id[2] : '';
    out.region = TITLE_IDS[out.titleId] || '';
    out.game = !!out.region || /pacific rift/i.test(out.title);
    if (out.category && out.category !== 'SD') out.problems.push(`not save data (CATEGORY ${out.category})`);
    out.date = Math.max(...out.files.map(f => f.mtime));
    // protection and where it came from
    const pfdFile = out.files.find(f => f.name === 'PARAM.PFD');
    out.protected = [];
    out.encrypted = false;
    out.kind = 'pc';
    if (pfdFile) {
        const buf = pfdFile.size <= LIMITS.pfdBytes ? fs.readFileSync(path.join(dir, 'PARAM.PFD')) : Buffer.alloc(0);
        let pfd = null;
        try { pfd = parsePfd(buf); } catch (e) { out.problems.push(e.message); }
        if (pfd) {
            out.kind = 'ps3';
            out.pfdVersion = pfd.version;
            out.pfd = pfd;
            out.protected = pfd.entries.map(e => e.name).filter(n => n !== 'PARAM.SFO');
            out.encrypted = out.protected.length > 0;
            for (const n of out.protected) if (!out.files.find(f => f.name === n)) out.problems.push(`${n} is listed in PARAM.PFD but missing`);
        } else out.protected = portPfdNames(buf);
    }
    if (sfo.has('RPCS3_BLIST') || sfo.entries.some(e => e.key.startsWith('*'))) {
        out.kind = 'rpcs3';
        out.protected = sfo.entries.filter(e => e.key.startsWith('*') && sfo.int(e.key)).map(e => e.key.slice(1));
    }
    if (!out.encrypted) {                                        // the profile's version line (plain saves only)
        const auto = out.files.find(f => f.name === 'AUTOSAVE.DAT');
        if (auto) {
            const head = Buffer.alloc(Math.min(256, auto.size));
            const fd = fs.openSync(path.join(dir, 'AUTOSAVE.DAT'), 'r');
            try { fs.readSync(fd, head, 0, head.length, 0); } finally { fs.closeSync(fd); }
            const v = /<ProfileVersion version = "([^"]{1,32})"/.exec(head.toString('latin1'));
            out.profileVersion = v ? v[1] : null;
        }
    }
    const icon = out.files.find(f => f.name === 'ICON0.PNG');
    if (icon && icon.size <= LIMITS.iconBytes) {
        const png = fs.readFileSync(path.join(dir, 'ICON0.PNG'));
        if (png.subarray(0, 8).equals(Buffer.from('89504e470d0a1a0a', 'hex'))) out.icon = 'data:image/png;base64,' + png.toString('base64');
    }
    return out;
}

// the MotorStorm: Pacific Rift saves in a folder the player picked: the save itself, or any folder above it (a USB
// stick's PS3\SAVEDATA, RPCS3's dev_hdd0 or savedata). Other games' saves are skipped; links are not followed.
function findSaves(root) {
    const found = [];
    let seen = 0;
    const walk = (dir, depth) => {
        if (seen++ > LIMITS.scanDirs) return;
        let info = null;
        try { info = inspectSave(dir); } catch { /* unreadable */ }
        if (info) { if (info.game && (!info.category || info.category === 'SD')) found.push(info); return; }   // game data (GD) is not a save
        if (depth >= LIMITS.scanDepth) return;
        let names;
        try { names = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
        for (const d of names) if (d.isDirectory() && !d.isSymbolicLink()) walk(path.join(dir, d.name), depth + 1);
    };
    walk(path.resolve(root), 0);
    return found.sort((a, b) => (a.suffix > b.suffix) - (a.suffix < b.suffix) || b.date - a.date);
}

// ---- the port's save folder, its backups
const savedataDir = gamedataRoot => path.join(gamedataRoot, ...USER_SAVEDATA);
const stamp = (d = new Date()) => d.toISOString().replace(/[-:]/g, '').replace('T', '-').slice(0, 15);
function copyDir(from, to) {
    fs.mkdirSync(to, { recursive: true });
    for (const name of fs.readdirSync(from)) {
        const st = fs.lstatSync(path.join(from, name));
        if (st.isFile()) fs.copyFileSync(path.join(from, name), path.join(to, name));
    }
}
function backup(slot, backupsRoot, reason) {
    if (!fs.existsSync(slot)) return null;
    const to = path.join(backupsRoot, `${stamp()}-${path.basename(slot)}`);
    let dest = to, k = 1;
    while (fs.existsSync(dest)) dest = `${to}-${k++}`;
    copyDir(slot, dest);
    fs.writeFileSync(path.join(dest, 'backup.json'), JSON.stringify({ dir: path.basename(slot), at: new Date().toISOString(), reason }, null, 1));
    return dest;
}
function listBackups(backupsRoot) {
    let names = [];
    try { names = fs.readdirSync(backupsRoot); } catch { return []; }
    return names.map(name => {
        let meta = {};
        try { meta = JSON.parse(fs.readFileSync(path.join(backupsRoot, name, 'backup.json'), 'utf8')); } catch { return null; }
        if (!DIR_RE.test(meta.dir || '')) return null;
        const info = (() => { try { return inspectSave(path.join(backupsRoot, name)); } catch { return null; } })();
        return { name, dir: meta.dir, at: meta.at, reason: meta.reason, info };
    }).filter(Boolean).sort((a, b) => (a.at < b.at) - (a.at > b.at));
}
function currentSaves(gamedataRoot) {
    const dir = savedataDir(gamedataRoot);
    let names = [];
    try { names = fs.readdirSync(dir); } catch { return []; }
    return names.filter(n => DIR_RE.test(n)).map(n => { try { return inspectSave(path.join(dir, n)); } catch { return null; } }).filter(Boolean);
}

// put a save into the port's folder. save: an inspectSave() result; keys: readKeyFolder() for an encrypted PS3 save.
// Returns { dir, backup, converted: [...] }.
function importSave(save, { gamedataRoot, backupsRoot, keys = null, reason = 'import', convertProfile = true }) {
    if (!save || !save.game) throw new SaveError('That is not a MotorStorm: Pacific Rift save.');
    if (save.problems.length) throw new SaveError(`The save cannot be used: ${save.problems.join('; ')}.`);
    if (!save.files.find(f => f.name === 'PARAM.SFO')) throw new SaveError('The save has no PARAM.SFO.');
    const target = PORT_DIR + save.suffix;
    const converted = [];
    // read everything first (the source is only read), decrypting a console's protected files
    const files = {};
    for (const f of save.files) {
        if (f.name === 'PARAM.PFD' || f.name === 'PARAM.SFO') continue;
        files[f.name] = fs.readFileSync(path.join(save.path, f.name));
    }
    if (save.encrypted) {
        if (!keys) throw new SaveError('This PS3 save is encrypted: choose the folder of your save tool (pfdtool or Bruteforce Save Data, with global.conf and games.conf) to decrypt it.');
        const id = keys.secureIds[save.titleId];
        if (!id) throw new SaveError(`games.conf has no secure_file_id for ${save.titleId}.`);
        for (const e of save.pfd.entries) {
            if (e.name === 'PARAM.SFO') continue;
            const plain = decryptProtected(files[e.name], e, id, keys.sysconKey);
            if (e.name === 'AUTOSAVE.DAT' && !plain.subarray(0, 5).equals(Buffer.from('<?xml')))
                throw new SaveError('AUTOSAVE.DAT did not decrypt to a profile: the keys in that folder are not the right ones.');
            files[e.name] = plain;
        }
        converted.push(`decrypted ${save.protected.join(', ')}`);
    }
    if (files['AUTOSAVE.DAT'] && convertProfile) {
        const r = profileFor100(files['AUTOSAVE.DAT']);
        if (r.error) throw new SaveError(r.error);
        if (r.from) { files['AUTOSAVE.DAT'] = r.data; converted.push(`profile ${r.from} -> ${PROFILE_100}`); }
    }
    let sfo =fs.readFileSync(path.join(save.path, 'PARAM.SFO'));
    if (save.saveDir !== target) { sfo = sfoSetString(sfo, 'SAVEDATA_DIRECTORY', target); converted.push(`${save.saveDir || save.dirName} -> ${target}`); }
    // write into a new folder beside the slot, then swap it in
    const root = savedataDir(gamedataRoot);
    fs.mkdirSync(root, { recursive: true });
    const slot = path.join(root, target);
    const staging = path.join(root, `.import-${process.pid}-${Date.now()}`);
    fs.mkdirSync(staging);
    try {
        for (const [name, data] of Object.entries(files)) fs.writeFileSync(path.join(staging, name), data);
        fs.writeFileSync(path.join(staging, 'PARAM.SFO'), sfo);
        if (save.protected.length) fs.writeFileSync(path.join(staging, 'PARAM.PFD'), save.protected.map(n => n + '\n').join(''));
        const kept = backup(slot, backupsRoot, reason);
        if (kept) fs.rmSync(slot, { recursive: true, force: true });
        fs.renameSync(staging, slot);
        return { dir: target, path: slot, backup: kept, converted };
    } catch (e) {
        fs.rmSync(staging, { recursive: true, force: true });
        throw e;
    }
}
// put a backup back (the save it replaces is backed up first)
function restoreBackup(name, { gamedataRoot, backupsRoot }) {
    if (!/^[\w.\-]+$/.test(name)) throw new SaveError('No such backup.');
    const info = inspectSave(path.join(backupsRoot, name));
    if (!info) throw new SaveError('No such backup.');
    const meta = JSON.parse(fs.readFileSync(path.join(backupsRoot, name, 'backup.json'), 'utf8'));
    if (!DIR_RE.test(meta.dir || '')) throw new SaveError('That backup does not name its save folder.');
    const slot = path.join(savedataDir(gamedataRoot), meta.dir);
    const kept = backup(slot, backupsRoot, 'restore');
    const staging = slot + `.restore-${Date.now()}`;
    copyDir(path.join(backupsRoot, name), staging);
    fs.rmSync(path.join(staging, 'backup.json'), { force: true });
    if (kept) fs.rmSync(slot, { recursive: true, force: true });
    fs.renameSync(staging, slot);
    return { dir: meta.dir, backup: kept };
}

// what the window shows of a save (no paths of the player's beyond the save's own, no file contents but the icon)
function summary(s) {
    return { path: s.path, dirName: s.dirName, titleId: s.titleId, region: s.region, suffix: s.suffix, title: s.title,
             subtitle: s.subtitle, detail: s.detail, date: s.date, kind: s.kind, encrypted: s.encrypted,
             protected: s.protected, profileVersion: s.profileVersion || null, problems: s.problems, icon: s.icon || null,
             target: PORT_DIR + (s.suffix || '') };
}

module.exports = { PORT_DIR, TITLE_IDS, SaveError, parseSfo, sfoSetString, parsePfd, inspectSave, findSaves, importSave,
                   restoreBackup, listBackups, currentSaves, savedataDir, readKeyFolder, summary, profileFor100, PROFILE_100,
                   _crypto: { secureHashKey, pfdFileKey, pfdCrypt, decryptProtected } };

// node service/saves.js scan <folder>
// node service/saves.js import <save folder> <gamedata root> [<backups folder>] [--keys <folder>] [--raw (no profile conversion)]
if (require.main === module) {
    const [cmd, a, b, c] = process.argv.slice(2).filter((x, i, all) => x !== '--keys' && x !== '--raw' && all[i - 1] !== '--keys');
    const ki = process.argv.indexOf('--keys');
    try {
        if (cmd === 'scan') {
            for (const s of findSaves(a)) console.log(JSON.stringify({ ...summary(s), icon: s.icon ? `${s.icon.length} chars` : null }));
        } else if (cmd === 'import') {
            const s = inspectSave(path.resolve(a));
            const r = importSave(s, { gamedataRoot: path.resolve(b), backupsRoot: path.resolve(c || path.join(b, '..', 'backups')),
                                      keys: ki > 0 ? readKeyFolder(process.argv[ki + 1]) : null,
                                      convertProfile: !process.argv.includes('--raw') });
            console.log(JSON.stringify(r));
        } else {
            console.log('usage: saves.js scan <folder> | import <save> <gamedata root> [<backups>] [--keys <folder>]');
            process.exitCode = 2;
        }
    } catch (e) { console.error(e.message); process.exitCode = 1; }
}
