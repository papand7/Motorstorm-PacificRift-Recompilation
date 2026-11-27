// node test_autodecrypt.js: "Decrypt automatically" (service/autodecrypt.js) with fakes only: no network, no RPCS3, no
// game data. A made-up release list, a made-up archive and a fake "rpcs3 --decrypt" that writes made-up ELF bytes.
'use strict';
const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const ad = require('./service/autodecrypt');
const { Builder } = require('./service/builder');
const disc = require('./service/disc');

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ms autodecrypt '));   // a space on purpose
const sha = b => crypto.createHash('sha256').update(b).digest('hex');

const TAG = 'build-0123456789abcdef0123456789abcdef01234567';
const NAME = 'rpcs3-v0.0.43-20663-0123456_win64_msvc.7z';
const ARCHIVE = Buffer.from('a made-up RPCS3 archive');
const URL_OF = n => `${ad.DOWNLOAD_PREFIX}${TAG}/${n}`;
function release(over = {}) {
    return {
        tag_name: TAG, body: `${sha(ARCHIVE)};${ARCHIVE.length}B`,
        assets: [
            { name: NAME, size: ARCHIVE.length, browser_download_url: URL_OF(NAME), digest: `sha256:${sha(ARCHIVE)}` },
            { name: NAME + '.sha256', size: 65, browser_download_url: URL_OF(NAME + '.sha256') },
            { name: 'rpcs3-v0.0.43-20663-0123456_win64_arm64.7z', size: 5, browser_download_url: URL_OF('rpcs3-v0.0.43-20663-0123456_win64_arm64.7z') },
        ], ...over,
    };
}

// a fake fetch for the GitHub API, the .sha256 file and the archive; every URL it is asked for is recorded
let calls = [];
function fakeFetch({ rel = release(), archive = ARCHIVE, offline = false, shaText = sha(ARCHIVE) + ' *' + NAME } = {}) {
    calls = [];
    globalThis.fetch = async url => {
        calls.push(url);
        if (offline) { const e = new TypeError('fetch failed'); e.cause = { code: 'ENOTFOUND' }; throw e; }
        const body = data => ({ ok: true, status: 200, headers: new Map([['content-length', String(data.length)]]),
                                body: (async function* () { yield data; })(), json: async () => JSON.parse(data), text: async () => String(data) });
        if (url === ad.API_LATEST) return body(Buffer.from(JSON.stringify(rel)));
        if (url === URL_OF(NAME + '.sha256')) return body(Buffer.from(shaText));
        if (url === URL_OF(NAME)) return body(archive);
        return { ok: false, status: 404 };
    };
}

// the program the fake RPCS3 "decrypts" to, and the disc (a folder: PS3_GAME/PARAM.SFO and an EBOOT.BIN)
const PROG = Buffer.from('a made-up decrypted program');
const WANT = { size: PROG.length, sha256: sha(PROG) };
const discRoot = path.join(tmp, 'disc');
fs.mkdirSync(path.join(discRoot, 'PS3_GAME', 'USRDIR'), { recursive: true });
fs.writeFileSync(path.join(discRoot, 'PS3_GAME', 'PARAM.SFO'), Buffer.from([0, 0x50, 0x53, 0x46]));
const EBOOT_BIN = Buffer.from('SCE\0 a made-up retail SELF');
fs.writeFileSync(path.join(discRoot, 'PS3_GAME', 'USRDIR', 'EBOOT.BIN'), EBOOT_BIN);
const discHash = () => sha(fs.readFileSync(path.join(discRoot, 'PS3_GAME', 'USRDIR', 'EBOOT.BIN')));

const unpackOk = async (archive, dir) => { fs.mkdirSync(path.join(dir, 'rpcs3-x'), { recursive: true }); fs.writeFileSync(path.join(dir, 'rpcs3-x', 'rpcs3.exe'), 'MZ'); };
const unpackFails = async () => { throw new Error('could not unpack (tar 1)'); };
let ran = null;
const decryptTo = bytes => async (exe, input, opts) => {
    ran = { exe, input, configDir: opts.configDir, tmpDir: opts.tmpDir };
    // as RPCS3 does: config into its portable folder, the ELF beside the input with ".elf"
    fs.writeFileSync(path.join(opts.configDir, 'config.yml'), 'x');
    fs.mkdirSync(path.join(opts.configDir, 'dev_hdd0'), { recursive: true });
    if (bytes) fs.writeFileSync(input.replace(/\.BIN$/, '.elf'), bytes);
    return bytes ? 0 : 1;
};

const leftovers = dataDir => fs.readdirSync(dataDir).filter(n => n.startsWith(ad.TMP_PREFIX));

(async () => {
    // ---- asset selection: the one win64 .7z of the pinned repo, its size and SHA-256 from every source agreeing
    const a = ad.selectAsset(release());
    assert.strictEqual(a.name, NAME);
    assert.strictEqual(a.url, URL_OF(NAME));
    assert.strictEqual(a.size, ARCHIVE.length);
    assert.deepStrictEqual([...new Set(a.sha256s)], [sha(ARCHIVE)]);
    assert.ok(a.url.startsWith('https://github.com/RPCS3/rpcs3-binaries-win/releases/download/'));
    const bad = (rel, re, why) => assert.throws(() => ad.selectAsset(rel), re, why);
    const r0 = release();
    bad({ ...r0, assets: r0.assets.map(x => x.name === NAME ? { ...x, browser_download_url: `https://example.com/${TAG}/${NAME}` } : x) }, /not on/, 'another host');
    bad({ ...r0, assets: r0.assets.map(x => x.name === NAME ? { ...x, browser_download_url: `https://github.com/evil/rpcs3-binaries-win/releases/download/${TAG}/${NAME}` } : x) }, /not on/, 'another repo');
    bad({ ...r0, assets: r0.assets.filter(x => x.name !== NAME) }, /0 Windows x64/, 'no win64 archive');
    bad({ ...r0, assets: [...r0.assets, { ...r0.assets[0], name: 'rpcs3-v0.0.44-1-abcdef0_win64_msvc.7z' }] }, /2 Windows x64/, 'two archives');
    bad({ ...r0, body: `${sha(ARCHIVE)};${ARCHIVE.length + 1}B` }, /bytes/, 'release text size differs');
    bad({ ...r0, body: `${'0'.repeat(64)};${ARCHIVE.length}B` }, /two different/, 'release text hash differs from the digest');
    assert.ok(ad.ASSET_RE.test('rpcs3-v0.0.43-20663-0ca5eb0e_win64_msvc.7z'), 'the real name pattern');
    assert.ok(!ad.ASSET_RE.test('rpcs3-v0.0.43-20663-0ca5eb0e_win64_arm64.7z'), 'never arm64');
    assert.ok(!ad.ASSET_RE.test('rpcs3-v0.0.43-20663-0ca5eb0e_win64_msvc.zip.exe'));

    // a release with no checksum at all: refused before any download
    fakeFetch({ rel: { ...r0, body: '', assets: [{ ...r0.assets[0], digest: undefined }] } });
    await assert.rejects(ad.resolveRelease(), /no SHA-256/);
    assert.deepStrictEqual(calls, [ad.API_LATEST]);
    // a .sha256 file that disagrees: refused
    fakeFetch({ shaText: '1'.repeat(64) });
    await assert.rejects(ad.resolveRelease(), /two different/);

    const src = await disc.openGame(discRoot);
    const before = discHash();
    const run = async (name, opts) => {
        const dataDir = path.join(tmp, name), out = path.join(dataDir, 'decrypted', 'EBOOT.elf');
        let err = null, res = null;
        try { res = await ad.autoDecrypt({ src, want: WANT, dataDir, out, ...opts }); } catch (e) { err = e; }
        return { dataDir, out, err, res };
    };

    // ---- success: the ELF is kept, RPCS3's temporary folder (exe, portable config, dev_hdd0, archive, the copy) is gone
    fakeFetch();
    ran = null;
    let r = await run('ok', { deps: { unpack: unpackOk, runDecrypt: decryptTo(PROG) } });
    assert.ifError(r.err);
    assert.strictEqual(sha(fs.readFileSync(r.out)), WANT.sha256);
    assert.deepStrictEqual(leftovers(r.dataDir), [], 'temporary folder removed after success');
    assert.deepStrictEqual(fs.readdirSync(r.dataDir), ['decrypted']);
    assert.ok(ran.input.startsWith(r.dataDir) && !ran.input.startsWith(discRoot), 'RPCS3 is given a copy, never the disc file');
    assert.ok(ran.exe.startsWith(r.dataDir), 'RPCS3 runs from the temporary folder');
    assert.strictEqual(path.dirname(ran.configDir), path.dirname(ran.exe), 'its portable folder is beside its exe');
    assert.ok(ran.tmpDir.startsWith(r.dataDir), 'its TMP/TEMP is in the temporary folder');
    assert.deepStrictEqual(calls, [ad.API_LATEST, URL_OF(NAME + '.sha256'), URL_OF(NAME)]);

    // ---- failures: a clear message, nothing kept, the temporary folder removed every time
    const fails = [
        ['offline', { fetch: { offline: true }, deps: { unpack: unpackOk, runDecrypt: decryptTo(PROG) } }, /Could not reach GitHub.*no internet/],
        ['corrupt', { fetch: { archive: Buffer.from('a made-up RPCS3 archiv!') }, deps: { unpack: unpackOk, runDecrypt: decryptTo(PROG) } }, /Could not download RPCS3.*SHA-256/],
        ['unpack', { deps: { unpack: unpackFails, runDecrypt: decryptTo(PROG) } }, /Could not unpack RPCS3/],
        ['noexe', { deps: { unpack: async () => {}, runDecrypt: decryptTo(PROG) } }, /no rpcs3\.exe/],
        ['nodecrypt', { deps: { unpack: unpackOk, runDecrypt: decryptTo(null) } }, /did not decrypt EBOOT\.BIN \(exit 1\)/],
        ['wronghash', { deps: { unpack: unpackOk, runDecrypt: decryptTo(Buffer.from('another program')) } }, /not the known 1\.00 program.*nothing was kept/],
        ['throws', { deps: { unpack: unpackOk, runDecrypt: async () => { throw new Error('boom'); } } }, /boom/],
    ];
    for (const [name, o, re] of fails) {
        fakeFetch(o.fetch);
        r = await run(name, { deps: o.deps });
        assert.ok(r.err, `${name}: fails`);
        assert.match(r.err.message, re, name);
        assert.ok(!fs.existsSync(r.out), `${name}: no EBOOT.elf kept`);
        assert.deepStrictEqual(leftovers(r.dataDir), [], `${name}: temporary folder removed`);
    }
    // cancelled before the download: removed too
    fakeFetch();
    const ac = new AbortController(); ac.abort();
    r = await run('cancel', { signal: ac.signal, deps: { unpack: unpackOk, runDecrypt: decryptTo(PROG) } });
    assert.match(r.err.message, /cancelled/);
    assert.deepStrictEqual(leftovers(r.dataDir), []);
    // a temporary folder an earlier (crashed) run left is removed at the next start
    fs.mkdirSync(path.join(tmp, 'stale', ad.TMP_PREFIX + 'old', 'rpcs3'), { recursive: true });
    fakeFetch();
    r = await run('stale', { deps: { unpack: unpackOk, runDecrypt: decryptTo(PROG) } });
    assert.ifError(r.err);
    assert.deepStrictEqual(leftovers(r.dataDir), []);
    assert.strictEqual(discHash(), before, 'the disc EBOOT.BIN is never changed');

    // ---- the service: nothing is fetched without the player's confirmation; with it the ELF becomes elf100
    const meta = path.join(tmp, 'meta'), root = path.join(tmp, 'root');
    fs.mkdirSync(meta); fs.mkdirSync(root);
    fs.writeFileSync(path.join(meta, 'game.json'), JSON.stringify({ title: 't', discs: [{ name: 'A', title_id: 'AAAA00001', eboot_elf: WANT }], builds: {} }));
    fs.writeFileSync(path.join(meta, 'toolchain.json'), JSON.stringify({ tools: [] }));
    const events = [];
    const b = new Builder({ root, meta, source: tmp, emit: e => events.push(e), log: () => {} });
    b.cfg.disc = discRoot;
    b.scan = async () => { b.discInfo = { ok: true, disc: b.game.discs[0] }; if (b.cfg.elf100) b.elfInfo[100] = await b.checkElf(100); };
    b.autoDecryptDeps = { unpack: unpackOk, runDecrypt: decryptTo(PROG) };
    fakeFetch();
    await b.autoDecrypt({ cmd: 'autodecrypt' });
    assert.deepStrictEqual(calls, [], 'no confirmation: nothing fetched');
    assert.match(b.message, /confirmation/);
    assert.ok(!b.cfg.elf100);
    await b.autoDecrypt({ cmd: 'autodecrypt', confirmed: true });
    assert.strictEqual(calls[0], ad.API_LATEST);
    assert.strictEqual(b.ok, true, b.message);
    assert.strictEqual(b.cfg.elf100, path.join(root, 'decrypted', 'EBOOT.elf'));
    assert.strictEqual(b.elfInfo[100].ok, true, 'checked as if the player had chosen it');
    assert.ok(events.some(e => e.ev === 'done' && e.ok), 'done event');
    assert.deepStrictEqual(leftovers(root), []);
    // a failure in the service: a clear message, elf100 unchanged, nothing left
    const prevElf = b.cfg.elf100;
    b.autoDecryptDeps = { unpack: unpackOk, runDecrypt: decryptTo(Buffer.from('another program')) };
    fakeFetch();
    await b.autoDecrypt({ cmd: 'autodecrypt', confirmed: true });
    assert.strictEqual(b.ok, false);
    assert.match(b.message, /not the known 1\.00 program/);
    assert.strictEqual(b.cfg.elf100, prevElf);
    assert.deepStrictEqual(leftovers(root), []);

    fs.rmSync(tmp, { recursive: true, force: true });
    console.log('test_autodecrypt: all passed');
})().catch(e => { console.error(e); process.exit(1); });
