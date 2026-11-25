// The player's game: a disc image (.iso, ISO 9660 as a PS3 disc dumps to, already decrypted) or a folder with
// PS3_GAME (a disc copied to a PC, or a PS3's own dump). Only read here: the launcher never writes to it.
'use strict';
const fs = require('fs');
const fsp = require('fs/promises');
const path = require('path');
const crypto = require('crypto');

const SECTOR = 2048;

function record(buf, at) {
    const len = buf[at];
    if (!len) return null;
    return { length: len, sector: buf.readUInt32LE(at + 2), size: buf.readUInt32LE(at + 10), directory: !!(buf[at + 25] & 2),
             name: buf.subarray(at + 33, at + 33 + buf[at + 32]).toString('latin1').replace(/;\d+$/, '') };
}

async function readAt(fh, offset, size) {
    const b = Buffer.alloc(size);
    const { bytesRead } = await fh.read(b, 0, size, offset);
    if (bytesRead !== size) throw new Error(`the disc image ends early (at ${offset})`);
    return b;
}

// every file of the image, each with its extents in disc order (a file over 4 GB has several records)
async function listIso(iso) {
    const fh = await fsp.open(iso, 'r');
    try {
        const pvd = await readAt(fh, SECTOR * 16, SECTOR);
        if (pvd.subarray(1, 6).toString() !== 'CD001') throw new Error('not an ISO 9660 disc image');
        const files = new Map();
        const walk = async (dir, prefix, depth) => {
            if (depth > 16) return;
            const data = await readAt(fh, dir.sector * SECTOR, dir.size);
            for (let at = 0; at < data.length;) {
                const e = record(data, at);
                if (!e) { at = (Math.floor(at / SECTOR) + 1) * SECTOR; continue; }
                at += e.length;
                if (e.name === '\0' || e.name === '\x01') continue;
                const p = `${prefix}/${e.name}`;
                if (e.directory) await walk(e, p, depth + 1);
                else {
                    const key = p.toUpperCase();
                    if (!files.has(key)) files.set(key, { path: p, extents: [], size: 0 });
                    const f = files.get(key);
                    f.extents.push({ sector: e.sector, size: e.size });
                    f.size += e.size;
                }
            }
        };
        await walk(record(pvd, 156), '', 0);
        return [...files.values()];
    } finally { await fh.close(); }
}

function parseSfo(data) {
    if (data.readUInt32BE(0) !== 0x00505346) throw new Error('PARAM.SFO is not readable');
    const keys = data.readUInt32LE(8), values = data.readUInt32LE(12), out = {};
    for (let i = 0; i < data.readUInt32LE(16); i++) {
        const at = 20 + i * 16;
        const ko = keys + data.readUInt16LE(at);
        const key = data.subarray(ko, data.indexOf(0, ko)).toString();
        const vo = values + data.readUInt32LE(at + 12), len = data.readUInt32LE(at + 4);
        out[key] = data.readUInt16LE(at + 2) === 0x404 ? data.readUInt32LE(vo) : data.subarray(vo, vo + len).toString('utf8').replace(/\0+$/, '');
    }
    return out;
}

// the folder holding PS3_GAME, from what the player chose (that folder, PS3_GAME itself, or USRDIR)
function gameRoot(dir) {
    let d = path.resolve(dir);
    for (let i = 0; i < 3; i++) {
        if (fs.existsSync(path.join(d, 'PS3_GAME', 'PARAM.SFO'))) return d;
        d = path.dirname(d);
    }
    return null;
}

// a source of the game's files: { kind, path, files: [{path, size}], read(p) -> Buffer, stream(p) }
async function openGame(p) {
    const st = fs.statSync(p);
    if (st.isFile()) {
        const files = await listIso(p);
        const find = q => files.find(f => f.path.toUpperCase() === q.toUpperCase());
        const stream = async function* (q) {
            const f = find(q);
            if (!f) throw new Error(`the disc image has no ${q}`);
            for (const x of f.extents) {
                if (!x.size) continue;
                yield* fs.createReadStream(p, { start: x.sector * SECTOR, end: x.sector * SECTOR + x.size - 1, highWaterMark: 4 << 20 });
            }
        };
        const read = async q => { const parts = []; for await (const c of stream(q)) parts.push(c); return Buffer.concat(parts); };
        return { kind: 'iso', path: p, files: files.map(f => ({ path: f.path, size: f.size })), has: q => !!find(q), read, stream };
    }
    const root = gameRoot(p);
    if (!root) throw new Error('That folder has no PS3_GAME\\PARAM.SFO. Choose the folder with PS3_GAME in it, or a disc image (.iso).');
    const files = [];
    const walk = (dir, rel) => {
        for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
            const full = path.join(dir, e.name), r = `${rel}/${e.name}`;
            if (e.isDirectory()) walk(full, r);
            else if (e.isFile()) files.push({ path: r, size: fs.statSync(full).size });
        }
    };
    walk(path.join(root, 'PS3_GAME'), '/PS3_GAME');
    for (const n of ['PS3_DISC.SFB']) if (fs.existsSync(path.join(root, n))) files.push({ path: '/' + n, size: fs.statSync(path.join(root, n)).size });
    const local = q => path.join(root, ...q.split('/').filter(Boolean));
    const real = q => {   // a case-insensitive lookup (a copy may have other case)
        const f = files.find(x => x.path.toUpperCase() === q.toUpperCase());
        return f ? local(f.path) : null;
    };
    return { kind: 'folder', path: root, files, has: q => !!real(q),
             read: async q => { const r = real(q); if (!r) throw new Error(`the folder has no ${q}`); return fsp.readFile(r); },
             stream: async function* (q) { const r = real(q); if (!r) throw new Error(`the folder has no ${q}`); yield* fs.createReadStream(r, { highWaterMark: 4 << 20 }); } };
}

async function hashOf(src, q) {
    const h = crypto.createHash('sha256');
    let size = 0;
    for await (const c of src.stream(q)) { h.update(c); size += c.length; }
    return { sha256: h.digest('hex'), size };
}

// the disc as a helper: its PARAM.SFO (the title) and the files the game reads. Its EBOOT.BIN is not used: the program
// comes from the player's own decrypted EBOOT.elf files, checked by the install (builder.js checkElf).
async function checkGame(src, game) {
    if (!src.has('/PS3_GAME/PARAM.SFO')) return { ok: false, error: 'No PS3_GAME/PARAM.SFO: this is not a PS3 game disc.' };
    const sfo = parseSfo(await src.read('/PS3_GAME/PARAM.SFO'));
    const out = { title: sfo.TITLE, titleId: sfo.TITLE_ID, version: sfo.APP_VER || sfo.VERSION, kind: src.kind, path: src.path };
    const disc = game.discs.find(d => d.title_id === sfo.TITLE_ID);
    if (!disc) {
        // the title alone says little (every release of the game has its own TITLE_ID): name the releases that build
        const known = game.discs.map(d => d.name).join(', ');
        return { ...out, ok: false, error: `This disc is ${sfo.TITLE || 'another game'} (${sfo.TITLE_ID || 'no title ID'}), a release ` +
                 `the launcher cannot build yet. It builds: ${known}.` };
    }
    if (!src.has('/PS3_GAME/USRDIR/EBOOT.BIN')) return { ...out, ok: false, error: 'The game has no PS3_GAME/USRDIR/EBOOT.BIN.' };
    return { ...out, ok: true, release: disc.name, disc };
}

// every file of the game into dir (only what is not there already with its size): the game reads them from there
async function copyGame(src, dir, { skip = [], say, signal } = {}) {
    const want = src.files.filter(f => !skip.some(s => f.path.toUpperCase() === s.toUpperCase()));
    const total = want.reduce((n, f) => n + f.size, 0);
    let done = 0;
    for (const f of want) {
        if (signal && signal.aborted) throw new Error('cancelled');
        const to = path.join(dir, ...f.path.split('/').filter(Boolean));
        if (fs.existsSync(to) && fs.statSync(to).size === f.size) { done += f.size; continue; }
        await fsp.mkdir(path.dirname(to), { recursive: true });
        const tmp = to + '.part';
        const out = fs.createWriteStream(tmp);
        for await (const c of src.stream(f.path)) {
            if (signal && signal.aborted) { out.destroy(); throw new Error('cancelled'); }
            if (!out.write(c)) await new Promise(r => out.once('drain', r));
            done += c.length;
            if (say) say(f.path, total ? done / total : -1, done, total);
        }
        await new Promise((res, rej) => out.end(e => e ? rej(e) : res()));
        await fsp.rename(tmp, to);
    }
    return { files: want.length, bytes: total };
}

module.exports = { openGame, checkGame, copyGame, hashOf, parseSfo, gameRoot };
