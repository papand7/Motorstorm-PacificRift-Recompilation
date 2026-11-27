// node test_updates.js: Settings > Launcher updates (updates.js) with fakes only: no network, no real token, no
// Electron. A fake fetch answers with made-up GitHub release lists; a fake safeStorage stands in for Windows DPAPI.
'use strict';
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const u = require('./updates');

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ms updates '));
// made-up tokens, put together at run time so no token-shaped literal sits in the repository
const TOKEN = 'gh' + 'p_' + 'Fake0Token1For2Tests3Only4Abcdefghij';
const PAT = 'github' + '_pat_' + '11FAKE0000_' + 'x'.repeat(40);
const PRIV = 'papand7/motorstorm-private-builds', PUB = 'papand7/motorstorm-pacific-rift-native';
const rel = (tag, over = {}) => ({ tag_name: tag, name: `Build ${tag}`, draft: false, prerelease: /-/.test(tag),
    html_url: `https://github.com/${over.repo || PRIV}/releases/tag/${tag}`, published_at: '2026-11-27T00:00:00Z',
    assets: [{ name: 'MotorStormPacificRift.exe' }, { name: 'MotorStormPacificRift.exe.sha256' }], ...over });

// a fake fetch: records each call, answers with { status, body }
function fakeFetch(answer) {
    const calls = [];
    const f = async (url, opts) => {
        calls.push({ url, opts });
        const a = typeof answer === 'function' ? answer(url, opts) : answer;
        if (a instanceof Error) throw a;
        return { status: a.status, ok: a.status >= 200 && a.status < 300,
                 headers: { get: k => (a.headers || {})[k.toLowerCase()] ?? null },
                 json: async () => { if (a.badJson) throw new SyntaxError('bad'); return a.body; } };
    };
    f.calls = calls;
    return f;
}
// a fake safeStorage: reversible, and never the token's own bytes
function fakeSafe({ available = true, failDecrypt = false } = {}) {
    return {
        isEncryptionAvailable: () => available,
        encryptString: s => Buffer.concat([Buffer.from('DPAPI'), Buffer.from(s, 'utf8').map(b => b ^ 0x5a)]),
        decryptString: b => { if (failDecrypt || b.subarray(0, 5).toString() !== 'DPAPI') throw new Error('Error while decrypting'); return Buffer.from(b.subarray(5)).map(x => x ^ 0x5a).toString('utf8'); },
    };
}
const noToken = (r, token = TOKEN) => assert.ok(!JSON.stringify(r).includes(token), 'the token is in a result: ' + JSON.stringify(r));

(async () => {
    // ---- versions
    assert.strictEqual(u.compareVersions('0.3.0-private.1', '0.3.0-private.2'), -1);
    assert.strictEqual(u.compareVersions('0.3.0-private.10', '0.3.0-private.2'), 1, 'numeric pre-release parts compare as numbers');
    assert.strictEqual(u.compareVersions('0.3.0', '0.3.0-private.9'), 1, 'a release is above its pre-releases');
    assert.strictEqual(u.compareVersions('v0.2.4', '0.3.0-private.1'), -1);
    assert.strictEqual(u.compareVersions('1.0.0', '1.0.0'), 0);
    assert.strictEqual(u.compareVersions('1.0.0-alpha', '1.0.0-alpha.1'), -1);
    assert.strictEqual(u.parseVersion('latest'), null);

    // ---- selectUpdate: newest above the current, pre-releases count, drafts / odd tags / foreign pages skipped
    const list = [rel('v0.3.0-private.1'), rel('v0.3.0-private.3', { draft: true }), rel('v0.3.0-private.2'), rel('nightly'),
                  rel('v0.9.0', { html_url: 'https://github.com/evil/motorstorm-private-builds/releases/tag/v0.9.0' })];
    const s1 = u.selectUpdate(list, '0.3.0-private.1', PRIV);
    assert.strictEqual(s1.version, '0.3.0-private.2');
    assert.strictEqual(s1.prerelease, true);
    assert.ok(s1.url.startsWith(`https://github.com/${PRIV}/releases/`));
    assert.deepStrictEqual(s1.assets, ['MotorStormPacificRift.exe', 'MotorStormPacificRift.exe.sha256']);
    assert.strictEqual(u.selectUpdate(list, '0.3.0-private.2', PRIV), null, 'nothing newer');
    assert.strictEqual(u.selectUpdate([], '0.3.0-private.1', PRIV), null);
    assert.throws(() => u.selectUpdate({ message: 'Not Found' }, '0.3.0', PRIV), /could not be read/);

    // ---- Private, no token: no request at all
    let f = fakeFetch({ status: 200, body: list });
    let r = await u.checkForUpdate({ channel: 'private', currentVersion: '0.3.0-private.1', token: null, fetchImpl: f });
    assert.strictEqual(r.status, 'no-token');
    assert.match(r.message, /needs a GitHub access token/);
    assert.strictEqual(f.calls.length, 0, 'no request without a token');

    // ---- Private, a token: the private repository's release list, the token sent as a bearer to api.github.com only
    f = fakeFetch({ status: 200, body: list });
    r = await u.checkForUpdate({ channel: 'private', currentVersion: '0.3.0-private.1', token: TOKEN, fetchImpl: f });
    assert.strictEqual(r.status, 'available');
    assert.strictEqual(r.update.version, '0.3.0-private.2');
    assert.strictEqual(f.calls.length, 1);
    assert.strictEqual(f.calls[0].url, `https://api.github.com/repos/${PRIV}/releases?per_page=30`);
    assert.strictEqual(f.calls[0].opts.headers.Authorization, `Bearer ${TOKEN}`);
    assert.strictEqual(f.calls[0].opts.redirect, 'error', 'the token never follows a redirect');
    noToken(r);
    r = await u.checkForUpdate({ channel: 'private', currentVersion: '0.3.0-private.2', token: TOKEN, fetchImpl: fakeFetch({ status: 200, body: list }) });
    assert.strictEqual(r.status, 'none');

    // ---- an invalid token: a clear message, no update
    for (const [status, headers] of [[401, {}], [403, { 'x-ratelimit-remaining': '4999' }], [404, {}]]) {
        r = await u.checkForUpdate({ channel: 'private', currentVersion: '0.3.0-private.1', token: TOKEN, fetchImpl: fakeFetch({ status, headers, body: { message: 'Bad credentials' } }) });
        assert.strictEqual(r.status, 'bad-token', `HTTP ${status}`);
        assert.ok(!r.update);
        noToken(r);
    }
    r = await u.checkForUpdate({ channel: 'private', currentVersion: '0.3.0-private.1', token: TOKEN, fetchImpl: fakeFetch({ status: 403, headers: { 'x-ratelimit-remaining': '0' } }) });
    assert.strictEqual(r.status, 'error');
    assert.match(r.message, /rate limit/);

    // ---- network failures, a broken answer: an error, never the token (even if an error message carried it)
    const err = new TypeError('fetch failed'); err.cause = { code: 'ENOTFOUND' };
    r = await u.checkForUpdate({ channel: 'private', currentVersion: '0.3.0-private.1', token: TOKEN, fetchImpl: fakeFetch(err) });
    assert.strictEqual(r.status, 'error');
    assert.match(r.message, /Could not reach GitHub/);
    const leaky = new TypeError('fetch failed'); leaky.cause = { message: `header Authorization: Bearer ${TOKEN}` };
    r = await u.checkForUpdate({ channel: 'private', currentVersion: '0.3.0-private.1', token: TOKEN, fetchImpl: fakeFetch(leaky) });
    noToken(r);
    r = await u.checkForUpdate({ channel: 'private', currentVersion: '0.3.0-private.1', token: TOKEN, fetchImpl: fakeFetch({ status: 200, badJson: true }) });
    assert.strictEqual(r.status, 'error');
    r = await u.checkForUpdate({ channel: 'private', currentVersion: '0.3.0-private.1', token: TOKEN, fetchImpl: fakeFetch({ status: 500 }) });
    assert.strictEqual(r.status, 'error');
    assert.strictEqual(u.scrub(`x ${PAT} y`, null), 'x [token] y');

    // ---- Public (and anything unknown): the public repository, never a token
    f = fakeFetch({ status: 200, body: [rel('v0.2.3', { repo: PUB }), rel('v0.2.5', { repo: PUB })] });
    r = await u.checkForUpdate({ channel: 'public', currentVersion: '0.2.4', token: TOKEN, fetchImpl: f });
    assert.strictEqual(r.status, 'available');
    assert.strictEqual(r.update.version, '0.2.5');
    assert.strictEqual(f.calls[0].url, `https://api.github.com/repos/${PUB}/releases?per_page=30`);
    assert.ok(!('Authorization' in f.calls[0].opts.headers), 'no token on the public channel');
    r = await u.checkForUpdate({ channel: 'public', currentVersion: '0.2.4', fetchImpl: fakeFetch({ status: 403, headers: { 'x-ratelimit-remaining': '10' } }) });
    assert.strictEqual(r.status, 'error', 'no token problem on the public channel');
    f = fakeFetch({ status: 200, body: [] });
    r = await u.checkForUpdate({ channel: 'bogus', currentVersion: '0.2.4', token: TOKEN, fetchImpl: f });
    assert.strictEqual(r.channel, 'public');
    assert.ok(!('Authorization' in f.calls[0].opts.headers));
    // a private build on the public channel sees no public release as newer
    r = await u.checkForUpdate({ channel: 'public', currentVersion: '0.3.0-private.1', fetchImpl: fakeFetch({ status: 200, body: [rel('v0.2.4', { repo: PUB })] }) });
    assert.strictEqual(r.status, 'none');

    // ---- the channel choice: update.json, Public by default, nothing else in it
    const prefs = path.join(tmp, 'data', 'update.json');
    assert.deepStrictEqual(u.readPrefs(prefs), { channel: 'public' });
    u.writePrefs(prefs, { channel: 'private', token: TOKEN });
    assert.deepStrictEqual(u.readPrefs(prefs), { channel: 'private' });
    assert.ok(!fs.readFileSync(prefs, 'utf8').includes(TOKEN), 'the token never goes into update.json');
    u.writePrefs(prefs, { channel: 'nonsense' });
    assert.deepStrictEqual(u.readPrefs(prefs), { channel: 'public' });
    fs.writeFileSync(prefs, '{broken');
    assert.deepStrictEqual(u.readPrefs(prefs), { channel: 'public' });

    // ---- the token store: encrypted bytes only, round trip, refusals
    const file = path.join(tmp, 'data', 'update-token.bin');
    const store = u.tokenStore(file, fakeSafe());
    assert.strictEqual(store.has(), false);
    assert.strictEqual(store.load(), null);
    store.save(`  ${TOKEN}\n`);
    assert.strictEqual(store.has(), true);
    const onDisk = fs.readFileSync(file);
    assert.ok(!onDisk.includes(Buffer.from(TOKEN)), 'the token is not on disk in plain text');
    assert.strictEqual(store.load(), TOKEN);
    store.save(PAT);
    assert.strictEqual(store.load(), PAT, 'a fine-grained token replaces it');
    assert.ok(!fs.existsSync(file + '.tmp'));
    assert.throws(() => store.save('hunter2'), /not a GitHub personal access token/);
    assert.throws(() => store.save(''), /not a GitHub personal access token/);
    assert.strictEqual(store.load(), PAT, 'a refused token leaves the stored one');
    // another Windows account (or a damaged file): no token, and the window says so (main.js)
    assert.strictEqual(u.tokenStore(file, fakeSafe({ failDecrypt: true })).load(), null);
    fs.writeFileSync(file, 'garbage');
    assert.strictEqual(store.load(), null);
    store.clear();
    assert.strictEqual(store.has(), false);
    // no encryption here: nothing stored, ever in plain text
    const noEnc = u.tokenStore(path.join(tmp, 'data', 'noenc.bin'), fakeSafe({ available: false }));
    assert.throws(() => noEnc.save(TOKEN), /cannot encrypt/);
    assert.ok(!fs.existsSync(path.join(tmp, 'data', 'noenc.bin')));
    // an "encryption" that returns the plain text is refused
    const plain = u.tokenStore(path.join(tmp, 'data', 'plain.bin'), { isEncryptionAvailable: () => true, encryptString: s => Buffer.from(s), decryptString: b => b.toString() });
    assert.throws(() => plain.save(TOKEN), /could not be encrypted/);
    assert.ok(!fs.existsSync(path.join(tmp, 'data', 'plain.bin')));

    // ---- main.js, preload.js and the page: the token never reaches a log, a send to the window or settings.ini
    const main = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
    for (const line of main.split(/\r?\n/).filter(l => /token/i.test(l)))
        assert.ok(!/console\.|send\(|settings\.|writeCfg|appendFile/.test(line), 'a line with the token logs or sends it: ' + line);
    assert.match(main, /safeStorage/);
    const preload = fs.readFileSync(path.join(__dirname, 'preload.js'), 'utf8');
    for (const c of ['update:info', 'update:channel', 'update:token', 'update:forget', 'update:check', 'update:open']) assert.ok(preload.includes(`'${c}'`), c);

    fs.rmSync(tmp, { recursive: true, force: true });
    console.log('test_updates: all passed');
})().catch(e => { console.error(e); fs.rmSync(tmp, { recursive: true, force: true }); process.exit(1); });
