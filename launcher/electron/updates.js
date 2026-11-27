// Launcher updates (Settings > Launcher updates): which GitHub releases the launcher looks at, and the look itself.
//
//   Public  (default)  papand7/Motorstorm-PacificRift-Recompilation, no token. Checked only when the player presses
//                      "Check for updates" (the launcher made no update check before this; it still makes none on its own)
//   Private            papand7/motorstorm-private-builds (a private repository): every release, pre-releases included,
//                      read with a GitHub personal access token the player enters once. Checked at start and on request.
//
// The token: kept only as Electron safeStorage output (Windows DPAPI: encrypted for this Windows account) in the
// launcher's own data folder (MotorStorm\launcher-data\update-token.bin). Never in plain text on disk, never in
// settings.ini, launcher.json or any repository file, never logged, never sent to the window (it is told only whether
// one is stored), and sent only to api.github.com, only for the Private channel.
//
// The check only reads the release list: an update found is shown with its release page (opened in the browser,
// where the player is signed in to GitHub). Nothing is downloaded or replaced by the launcher.
'use strict';
const fs = require('fs');
const path = require('path');

const CHANNELS = {
    public: { label: 'Public', repo: 'papand7/Motorstorm-PacificRift-Recompilation', token: false },
    private: { label: 'Private', repo: 'papand7/motorstorm-private-builds', token: true },
};
const DEFAULT_CHANNEL = 'public';
const API = 'https://api.github.com';
// GitHub's token forms: classic (ghp_), OAuth/app (gho_ ghu_ ghs_ ghr_) and fine-grained (github_pat_)
const TOKEN_RE = /^(gh[pousr]_[A-Za-z0-9]{30,251}|github_pat_[A-Za-z0-9_]{30,251})$/;
const TIMEOUT_MS = 15000;

const channelOf = c => (Object.prototype.hasOwnProperty.call(CHANNELS, c) ? c : DEFAULT_CHANNEL);

// ---- versions: semantic versions with pre-release parts (0.3.0-private.1 < 0.3.0-private.2 < 0.3.0)
function parseVersion(s) {
    const m = /^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$/.exec(String(s == null ? '' : s).trim());
    return m ? { nums: [+m[1], +m[2], +m[3]], pre: m[4] ? m[4].split('.') : [] } : null;
}
function compareVersions(a, b) {
    const x = typeof a === 'string' ? parseVersion(a) : a, y = typeof b === 'string' ? parseVersion(b) : b;
    if (!x || !y) throw new Error('not a version');
    for (let i = 0; i < 3; i++) if (x.nums[i] !== y.nums[i]) return x.nums[i] < y.nums[i] ? -1 : 1;
    if (!x.pre.length || !y.pre.length) return x.pre.length === y.pre.length ? 0 : x.pre.length ? -1 : 1;
    for (let i = 0; i < Math.max(x.pre.length, y.pre.length); i++) {
        if (i >= x.pre.length) return -1;
        if (i >= y.pre.length) return 1;
        const p = x.pre[i], q = y.pre[i], pn = /^\d+$/.test(p), qn = /^\d+$/.test(q);
        if (p === q) continue;
        if (pn && qn) return +p < +q ? -1 : 1;
        if (pn !== qn) return pn ? -1 : 1;
        return p < q ? -1 : 1;
    }
    return 0;
}

// the newest release above `current` in a GitHub release list (drafts and odd tags skipped; pre-releases count),
// or null. Its page must be on the channel's own repository.
function selectUpdate(releases, current, repo) {
    if (!Array.isArray(releases)) throw new Error('The release list could not be read.');
    const cur = parseVersion(current);
    if (!cur) throw new Error(`This launcher's version (${current}) is not a version number.`);
    const page = `https://github.com/${repo}/releases/`.toLowerCase();   // GitHub names are case-insensitive
    let best = null;
    for (const r of releases) {
        if (!r || r.draft) continue;
        const v = parseVersion(r.tag_name);
        if (!v || compareVersions(v, cur) <= 0) continue;
        const url = String(r.html_url || '');
        if (!url.toLowerCase().startsWith(page)) continue;
        if (!best || compareVersions(v, best.v) > 0) best = { v, r, url };
    }
    if (!best) return null;
    const r = best.r;
    return { version: String(r.tag_name).replace(/^v/, ''), tag: String(r.tag_name), name: String(r.name || r.tag_name),
             url: best.url, prerelease: !!r.prerelease, published: r.published_at || null,
             assets: (Array.isArray(r.assets) ? r.assets : []).map(a => String(a && a.name || '')).filter(Boolean) };
}

// a message never carries the token, whatever an error has in it
function scrub(text, token) {
    let s = String(text == null ? '' : text);
    if (token) s = s.split(token).join('[token]');
    return s.replace(/\b(gh[pousr]_[A-Za-z0-9]{8,}|github_pat_[A-Za-z0-9_]{8,})/g, '[token]');
}

// { status, message, ... }: status 'available' (with update), 'none', 'no-token', 'bad-token', 'error'
async function checkForUpdate({ channel, currentVersion, token, fetchImpl = globalThis.fetch, timeoutMs = TIMEOUT_MS } = {}) {
    const ch = channelOf(channel), C = CHANNELS[ch];
    const base = { channel: ch, repo: C.repo, current: currentVersion };
    if (C.token && !token)
        return { ...base, status: 'no-token', message: 'The Private channel needs a GitHub access token: enter it under Settings > Launcher updates. No update check was made.' };
    const headers = { 'User-Agent': 'MotorStormLauncher', Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' };
    if (C.token) headers.Authorization = `Bearer ${token}`;   // the private channel only, to api.github.com only
    const url = `${API}/repos/${C.repo}/releases?per_page=30`;
    const ctl = typeof AbortController === 'function' ? new AbortController() : null;
    const timer = ctl ? setTimeout(() => ctl.abort(), timeoutMs) : null;
    try {
        let r;
        // a token never follows a redirect (a renamed repository); the public check, without one, may
        try { r = await fetchImpl(url, { headers, redirect: C.token ? 'error' : 'follow', signal: ctl ? ctl.signal : undefined }); }
        catch (e) {
            const cause = e && e.cause && (e.cause.code || e.cause.message);
            if (e && e.name === 'AbortError') return { ...base, status: 'error', message: 'GitHub did not answer in time. No update check was made.' };
            return { ...base, status: 'error', message: scrub(`Could not reach GitHub (no internet connection?${cause ? ' ' + cause : ''}). No update check was made.`, token) };
        }
        const remaining = r.headers && typeof r.headers.get === 'function' ? r.headers.get('x-ratelimit-remaining') : null;
        if (r.status === 401)
            return { ...base, status: 'bad-token', message: 'GitHub refused the access token (wrong, expired or revoked). Enter a new one under Settings > Launcher updates. No update was found.' };
        if ((r.status === 403 || r.status === 429) && remaining === '0')
            return { ...base, status: 'error', message: 'GitHub refused the request for now (rate limit). Try again later.' };
        if (C.token && (r.status === 403 || r.status === 404))
            return { ...base, status: 'bad-token', message: `The access token cannot read ${C.repo} (no access to it, or the token lacks the Contents: read / repo permission). No update was found.` };
        if (!r.ok) return { ...base, status: 'error', message: `GitHub answered HTTP ${r.status} for ${C.repo}'s releases. No update was found.` };
        let list;
        try { list = await r.json(); } catch { return { ...base, status: 'error', message: 'GitHub sent a release list that could not be read.' }; }
        const update = selectUpdate(list, currentVersion, C.repo);
        if (!update) return { ...base, status: 'none', message: `No update: ${currentVersion} is the newest on the ${C.label} channel.` };
        return { ...base, status: 'available', update, message: `Update available: ${update.name} (${update.version}${update.prerelease ? ', pre-release' : ''}).` };
    } catch (e) {
        return { ...base, status: 'error', message: scrub(`The update check failed: ${e && e.message}`, token) };
    } finally { if (timer) clearTimeout(timer); }
}

// ---- the channel choice: <data>\update.json { "channel": "public" | "private" } (no token in it)
function readPrefs(file) {
    try { const j = JSON.parse(fs.readFileSync(file, 'utf8')); return { channel: channelOf(j && j.channel) }; }
    catch { return { channel: DEFAULT_CHANNEL }; }
}
function writePrefs(file, prefs) {
    const out = { channel: channelOf(prefs && prefs.channel) };
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file + '.tmp', JSON.stringify(out, null, 2) + '\n');
    fs.renameSync(file + '.tmp', file);
    return out;
}

// ---- the token: safeStorage (Electron's; a fake in the tests) output in `file`, nothing else
function tokenStore(file, safeStorage) {
    const available = () => { try { return !!safeStorage.isEncryptionAvailable(); } catch { return false; } };
    return {
        file,
        available,
        has: () => fs.existsSync(file),
        // throws a message for the window; nothing is written unless the token is encrypted
        save(token) {
            const t = String(token == null ? '' : token).trim();
            if (!TOKEN_RE.test(t)) throw new Error('That is not a GitHub personal access token (it starts with github_pat_ or ghp_). Nothing was stored.');
            if (!available()) throw new Error('Windows cannot encrypt the token for this account here, so it was not stored (the launcher never keeps it in plain text).');
            const enc = safeStorage.encryptString(t);
            if (!Buffer.isBuffer(enc) || !enc.length || enc.includes(Buffer.from(t))) throw new Error('The token could not be encrypted. Nothing was stored.');
            fs.mkdirSync(path.dirname(file), { recursive: true });
            fs.writeFileSync(file + '.tmp', enc);
            fs.renameSync(file + '.tmp', file);
        },
        // the token, or null (none stored, or it cannot be decrypted: another Windows account, or the file is damaged)
        load() {
            if (!fs.existsSync(file) || !available()) return null;
            try { const t = safeStorage.decryptString(fs.readFileSync(file)); return TOKEN_RE.test(t) ? t : null; }
            catch { return null; }
        },
        clear() { fs.rmSync(file, { force: true }); fs.rmSync(file + '.tmp', { force: true }); },
    };
}

module.exports = { CHANNELS, DEFAULT_CHANNEL, TOKEN_RE, channelOf, parseVersion, compareVersions, selectUpdate, scrub,
                   checkForUpdate, readPrefs, writePrefs, tokenStore };
