// "Decrypt automatically": at the player's request (a confirmation in the window first), the official RPCS3 Windows
// build is downloaded, used once to decrypt the player's own disc's EBOOT.BIN, and deleted again. The launcher itself
// holds no keys and no decryption code: RPCS3 (GPL-2.0, https://github.com/RPCS3/rpcs3) does the decryption, and it is
// never bundled or redistributed with the launcher.
//
//   1. the latest release of RPCS3/rpcs3-binaries-win (GitHub API, HTTPS): its one win64 .7z, checked by name, size
//      and SHA-256 (the release text's "<sha256>;<size>B", GitHub's asset digest and the .sha256 asset must agree)
//   2. unpacked by Windows' tar.exe (libarchive with liblzma reads .7z) into a new temporary folder under the launcher's
//      data folder, with a "portable" folder beside rpcs3.exe so all its config, cache and dev_hdd0 stay in there
//      (and TMP/TEMP pointed in there: its guest-memory sparse file)
//   3. the disc's EBOOT.BIN copied into that temporary folder (the disc is only read), then
//      `rpcs3.exe --allow-any-location --decrypt <copy>`: RPCS3 writes <copy without extension>.elf (rpcs3/Crypto/decrypt_binaries.cpp)
//   4. the ELF's size and SHA-256 against game.json; only a match is moved out, into <data>\decrypted\EBOOT.elf
//   5. the temporary folder (RPCS3, its archive, its config, the copy) removed, on success and on every failure
'use strict';
const fs = require('fs');
const fsp = require('fs/promises');
const path = require('path');
const tools = require('./tools');
const { run, killAll } = require('./proc');

const REPO = 'RPCS3/rpcs3-binaries-win';
const API_LATEST = `https://api.github.com/repos/${REPO}/releases/latest`;
const DOWNLOAD_PREFIX = `https://github.com/${REPO}/releases/download/`;
// rpcs3-v0.0.43-20663-0ca5eb0e_win64_msvc.7z (the x64 build; never an arm64 one)
const ASSET_RE = /^rpcs3-v\d+\.\d+\.\d+-\d+-[0-9a-f]{7,40}_win64(?:_msvc)?\.7z$/i;
const MAX_ARCHIVE = 300 << 20;          // RPCS3's 7z is ~37 MB: anything far larger is not it
const TMP_PREFIX = 'autodecrypt-';
const DECRYPT_TIMEOUT_MS = 5 * 60 * 1000;
const UA = { 'User-Agent': 'MotorStormLauncher', Accept: 'application/vnd.github+json' };

// a failure the window shows as it is (the rest get "Automatic decryption failed: ...")
class AutoDecryptError extends Error { get name() { return 'AutoDecryptError'; } }

const hex64 = s => { const m = /\b([0-9a-f]{64})\b/i.exec(String(s || '')); return m ? m[1].toLowerCase() : null; };

// the release's one Windows x64 archive and what it must be: { name, url, size, sha256s: [...], shaUrl }
function selectAsset(release) {
    if (!release || !Array.isArray(release.assets)) throw new AutoDecryptError('The RPCS3 release list could not be read.');
    const tag = String(release.tag_name || '');
    const found = release.assets.filter(a => ASSET_RE.test(String(a.name || '')));
    if (found.length !== 1) throw new AutoDecryptError(`The latest RPCS3 release has ${found.length} Windows x64 archives, not one: nothing was downloaded.`);
    const a = found[0];
    const url = String(a.browser_download_url || '');
    if (!url.startsWith(DOWNLOAD_PREFIX + encodeURIComponent(tag) + '/') && !url.startsWith(DOWNLOAD_PREFIX + tag + '/'))
        throw new AutoDecryptError(`The RPCS3 download is not on ${DOWNLOAD_PREFIX}: nothing was downloaded.`);
    if (!url.endsWith('/' + a.name)) throw new AutoDecryptError('The RPCS3 download link does not name its archive.');
    const size = Number(a.size);
    if (!(size > 0 && size < MAX_ARCHIVE)) throw new AutoDecryptError(`The RPCS3 archive has an unexpected size (${a.size}).`);
    const sha256s = [];
    if (typeof a.digest === 'string' && /^sha256:/i.test(a.digest)) sha256s.push(hex64(a.digest));
    // the release text: "<sha256>;<size>B"
    const m = /\b([0-9a-f]{64});(\d+)B\b/i.exec(String(release.body || ''));
    if (m) {
        if (Number(m[2]) !== size) throw new AutoDecryptError(`The RPCS3 release names ${m[2]} bytes, its archive has ${size}: nothing was downloaded.`);
        sha256s.push(m[1].toLowerCase());
    }
    const shaAsset = release.assets.find(x => x.name === a.name + '.sha256');
    const shaUrl = shaAsset && String(shaAsset.browser_download_url || '').startsWith(DOWNLOAD_PREFIX) ? shaAsset.browser_download_url : null;
    if (new Set(sha256s.filter(Boolean)).size > 1) throw new AutoDecryptError('The RPCS3 release names two different SHA-256s for its archive: nothing was downloaded.');
    return { name: a.name, url, size, tag, sha256s: sha256s.filter(Boolean), shaUrl };
}

// the network's errors in words a player can act on
function netError(e, what) {
    if (e instanceof AutoDecryptError) return e;
    const cause = e && e.cause && (e.cause.code || e.cause.message);
    if (e && e.name === 'AbortError') return new AutoDecryptError('cancelled');
    if (e && (e.name === 'TypeError' || /fetch failed|ENOTFOUND|ECONNREFUSED|ECONNRESET|ETIMEDOUT|EAI_AGAIN/.test(`${e.message} ${cause}`)))
        return new AutoDecryptError(`Could not reach GitHub to ${what} (no internet connection?${cause ? ' ' + cause : ''}).`);
    return new AutoDecryptError(`Could not ${what}: ${e.message}`);
}

async function getJson(url, signal) {
    const r = await fetch(url, { headers: UA, redirect: 'follow', signal });
    if (r.status === 403 || r.status === 429) throw new AutoDecryptError('GitHub refused the request for now (rate limit). Try again in an hour, or choose EBOOT.elf... yourself.');
    if (!r.ok) throw new AutoDecryptError(`GitHub answered HTTP ${r.status} for the RPCS3 release list.`);
    return r.json();
}
async function getText(url, signal) {
    const r = await fetch(url, { headers: { 'User-Agent': UA['User-Agent'] }, redirect: 'follow', signal });
    if (!r.ok) throw new AutoDecryptError(`HTTP ${r.status} for ${url}`);
    return r.text();
}

// the release to use, with its one SHA-256 (required)
async function resolveRelease({ signal, log } = {}) {
    let rel;
    try { rel = await getJson(API_LATEST, signal); } catch (e) { throw netError(e, 'look up the latest RPCS3 release'); }
    const asset = selectAsset(rel);
    if (asset.shaUrl) {
        try {
            const h = hex64(await getText(asset.shaUrl, signal));
            if (h) asset.sha256s.push(h);
        } catch (e) { if (log) log(`autodecrypt: the .sha256 file could not be read (${e.message}); the other checksums decide`); }
    }
    const set = new Set(asset.sha256s);
    if (set.size === 0) throw new AutoDecryptError('The RPCS3 release publishes no SHA-256 for its archive: nothing was downloaded.');
    if (set.size > 1) throw new AutoDecryptError('The RPCS3 release names two different SHA-256s for its archive: nothing was downloaded.');
    asset.sha256 = [...set][0];
    return asset;
}

// rpcs3.exe in the unpacked tree (at its top, or one folder down), never outside it
function findExe(dir) {
    const top = path.join(dir, 'rpcs3.exe');
    if (fs.existsSync(top)) return top;
    if (!fs.existsSync(dir)) return null;
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
        if (!e.isDirectory()) continue;
        const p = path.join(dir, e.name, 'rpcs3.exe');
        if (fs.existsSync(p)) return p;
    }
    return null;
}

// remove a folder; Windows may hold a file of a just-ended process a moment longer
async function removeTree(dir) {
    for (let i = 0; i < 20; i++) {
        try { await fsp.rm(dir, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch { /* retried */ }
        if (!fs.existsSync(dir)) return true;
        await new Promise(r => setTimeout(r, 500));
    }
    return !fs.existsSync(dir);
}

// earlier temporary folders (a crash, a power cut) under the data folder
async function removeStale(dataDir, log) {
    let names = [];
    try { names = fs.readdirSync(dataDir).filter(n => n.startsWith(TMP_PREFIX)); } catch { return; }
    for (const n of names) {
        const ok = await removeTree(path.join(dataDir, n));
        if (log) log(`autodecrypt: earlier temporary folder ${n} ${ok ? 'removed' : 'could not be removed'}`);
    }
}

// The whole flow. src: disc.openGame()'s result (the disc is only read). want: game.json's eboot_elf {size, sha256}.
// out: where a verified EBOOT.elf goes. Returns { path, sha256, rpcs3 }; throws AutoDecryptError with the reason.
// deps (tests): unpack(archive, dir, opts), runDecrypt(exe, input, opts) -> exit code, download(url, file, opts)
async function autoDecrypt({ src, want, dataDir, out, say = () => {}, log = () => {}, signal, deps = {} }) {
    const unpack = deps.unpack || tools.unpack;
    const download = deps.download || tools.download;
    const runDecrypt = deps.runDecrypt || runRpcs3Decrypt;
    if (!src || !src.has('/PS3_GAME/USRDIR/EBOOT.BIN')) throw new AutoDecryptError('Choose your game disc first (step 01): its EBOOT.BIN is what gets decrypted.');
    if (!want || !want.sha256 || !want.size) throw new AutoDecryptError('This release of the game has no known EBOOT.elf hash.');
    fs.mkdirSync(dataDir, { recursive: true });
    await removeStale(dataDir, log);
    const work = await fsp.mkdtemp(path.join(dataDir, TMP_PREFIX));
    log(`autodecrypt: temporary folder ${work}`);
    const aborted = () => { if (signal && signal.aborted) throw new AutoDecryptError('cancelled'); };
    let result = null, failure = null;
    try {
        say('Finding RPCS3', 'the latest official Windows build on GitHub', -1);
        const asset = await resolveRelease({ signal, log });
        log(`autodecrypt: RPCS3 ${asset.tag}: ${asset.name}, ${asset.size} bytes, SHA-256 ${asset.sha256}`);
        aborted();
        const archive = path.join(work, 'download', asset.name);
        try {
            await download(asset.url, archive, { sha256: asset.sha256, size: asset.size, signal,
                onProgress: (d, t) => say('Downloading RPCS3', tools.mb(d, t || asset.size), (t || asset.size) ? d / (t || asset.size) : -1) });
        } catch (e) { throw netError(e, 'download RPCS3'); }
        if (fs.statSync(archive).size !== asset.size) throw new AutoDecryptError(`The RPCS3 download has ${fs.statSync(archive).size} bytes, not ${asset.size}.`);
        aborted();

        say('Unpacking RPCS3', asset.name, -1);
        const prog = path.join(work, 'rpcs3');
        try { await unpack(archive, prog, { log }); }
        catch (e) {
            throw new AutoDecryptError(`Could not unpack RPCS3's .7z archive (${e.message}). Windows' tar.exe reads .7z only in ` +
                                       'recent Windows 11; choose EBOOT.elf... yourself instead.');
        }
        fs.rmSync(path.join(work, 'download'), { recursive: true, force: true });
        const exe = findExe(prog);
        if (!exe) throw new AutoDecryptError('The RPCS3 archive has no rpcs3.exe.');
        // RPCS3 keeps its config, cache, logs and dev_hdd0 in "portable" beside its exe when that folder exists
        // (Utilities/File.cpp fs::get_config_dir): all inside the temporary folder
        fs.mkdirSync(path.join(path.dirname(exe), 'portable'), { recursive: true });
        aborted();

        say('Copying EBOOT.BIN', 'from your disc into the temporary folder (the disc is only read)', -1);
        const input = path.join(work, 'input', 'EBOOT.BIN');
        fs.mkdirSync(path.dirname(input), { recursive: true });
        const outStream = fs.createWriteStream(input);
        for await (const c of src.stream('/PS3_GAME/USRDIR/EBOOT.BIN')) if (!outStream.write(c)) await new Promise(r => outStream.once('drain', r));
        await new Promise((res, rej) => outStream.end(e => e ? rej(e) : res()));
        aborted();

        say('Decrypting EBOOT.BIN', 'RPCS3 --decrypt', -1);
        const tmpDir = path.join(work, 'tmp');
        fs.mkdirSync(tmpDir, { recursive: true });
        const code = await runDecrypt(exe, input, { log, signal, configDir: path.join(path.dirname(exe), 'portable'), tmpDir });
        aborted();
        const elf = path.join(path.dirname(input), 'EBOOT.elf');     // decrypt_binaries.cpp: <path without extension>.elf
        if (!fs.existsSync(elf)) throw new AutoDecryptError(`RPCS3 did not decrypt EBOOT.BIN (exit ${code}). Is the disc a retail one of this game?`);

        say('Checking EBOOT.elf', 'its SHA-256', -1);
        const size = fs.statSync(elf).size;
        const sha = await tools.sha256File(elf);
        log(`autodecrypt: RPCS3 wrote ${size} bytes, SHA-256 ${sha}`);
        if (size !== want.size || sha !== want.sha256)
            throw new AutoDecryptError(`The decrypted EBOOT.elf is not the known 1.00 program (SHA-256 ${sha.slice(0, 12)}..., ${size} bytes): nothing was kept.`);
        fs.mkdirSync(path.dirname(out), { recursive: true });
        const tmpOut = out + '.part';
        fs.copyFileSync(elf, tmpOut);
        if (await tools.sha256File(tmpOut) !== want.sha256) { fs.rmSync(tmpOut, { force: true }); throw new AutoDecryptError('The EBOOT.elf could not be stored intact.'); }
        fs.renameSync(tmpOut, out);
        result = { path: out, sha256: sha, rpcs3: asset.tag };
    } catch (e) {
        failure = e;
    } finally {
        say('Removing RPCS3', 'and everything it made', -1);
        const gone = await removeTree(work);
        log(`autodecrypt: temporary folder ${gone ? 'removed' : 'NOT removed: ' + work}`);
        if (!gone && !failure) failure = new AutoDecryptError(`RPCS3's temporary folder could not be removed: ${work}. Delete it by hand.`);
        else if (!gone) failure.message += ` (RPCS3's temporary folder could not be removed: ${work}. Delete it by hand.)`;
    }
    if (failure) {
        if (result) fs.rmSync(result.path, { force: true });   // keep nothing when the cleanup failed
        throw failure;
    }
    return result;
}

// rpcs3.exe --decrypt <file> (rpcs3/rpcs3.cpp: a headless application; with a wrong key it asks for a KLIC on stdin,
// which here reads end-of-file and so ends). Run from its own folder, with a time limit. TMP/TEMP point into the
// temporary folder too: RPCS3 keeps its guest memory in %TEMP%\rpcs3_vm_sparse.tmp (rpcs3/util/vm_native.cpp), and
// would otherwise create (and replace) the player's own RPCS3's file of that name.
async function runRpcs3Decrypt(exe, input, { log, signal, configDir, tmpDir } = {}) {
    const env = { ...process.env, RPCS3_CONFIG_DIR: configDir.replace(/\\/g, '/') + '/', TMP: tmpDir, TEMP: tmpDir };
    let timer = null, timedOut = false;
    const stop = () => killAll();
    if (signal) signal.addEventListener('abort', stop, { once: true });
    timer = setTimeout(() => { timedOut = true; killAll(); }, DECRYPT_TIMEOUT_MS);
    try {
        // --allow-any-location: RPCS3 otherwise refuses to start from a temporary or OneDrive folder (a launcher on a
        // OneDrive Desktop); it is a check meant for a lasting install, and this copy lives for one decryption
        const code = await run(exe, ['--allow-any-location', '--decrypt', input], { cwd: path.dirname(exe), env, log: l => log && log(`rpcs3: ${l}`) });
        if (timedOut) throw new AutoDecryptError('RPCS3 did not finish decrypting within 5 minutes.');
        return code;
    } finally {
        clearTimeout(timer);
        if (signal) signal.removeEventListener('abort', stop);
    }
}

module.exports = { autoDecrypt, selectAsset, resolveRelease, findExe, removeTree, AutoDecryptError,
                   REPO, API_LATEST, DOWNLOAD_PREFIX, ASSET_RE, TMP_PREFIX };
