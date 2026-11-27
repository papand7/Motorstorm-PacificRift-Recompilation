// node test_texdeps.js: what the HD textures page installs (service/texdeps.js, toolchain.json "textures"): the
// dependency list against the scripts' own imports, the pinned wheels and hashes, the "already installed" skip, and
// the clear failure without a network. Nothing is downloaded: fetch is replaced by a stub.
'use strict';
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const texdeps = require('./service/texdeps');

const REPO = path.resolve(__dirname, '..', '..');
const tc = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'toolchain.json'), 'utf8'));
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ms texdeps '));   // a space on purpose
let failed = 0;
async function test(name, fn) {
    try { await fn(); console.log(`ok   ${name}`); } catch (e) { failed++; console.log(`FAIL ${name}\n     ${e.stack}`); }
}

// the import name of each pinned package (wheel name -> what the scripts import)
const IMPORT_OF = { numpy: 'numpy', pillow: 'PIL' };
// the standard-library modules the texture scripts use; a new import outside this set and the pinned packages fails
// the test, so the dependency list is looked at again
const STDLIB = new Set(['__future__', 'argparse', 'os', 'concurrent', 'shutil', 'struct', 'subprocess', 'sys', 'time', 'pathlib',
                        'hashlib', 'ctypes', 'json', 'zlib', 'psarc']);   // (psarc: texcollect's own module)
function importsOf(file) {
    const found = new Set();
    for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
        const m = /^\s*(?:import\s+([A-Za-z_][\w.]*)|from\s+([A-Za-z_][\w.]*)\s+import\b)/.exec(line);
        if (m) found.add((m[1] || m[2]).split('.')[0]);
    }
    return found;
}
const SCRIPTS = [path.join(REPO, 'generated', 'analysis', 'vksync', 'tools', 'texpack.py'),
                 path.join(REPO, 'tools', 'texcollect', 'texcollect.py'), path.join(REPO, 'tools', 'texcollect', 'psarc.py')];

(async () => {
    const list = texdeps.textureTools(tc);
    const pydeps = list.find(t => t.id === 'pydeps');
    const python = list.find(t => t.id === 'python');

    await test('the dependency list covers every third-party import of the texture scripts', () => {
        const pinned = new Set(pydeps.files.map(f => IMPORT_OF[texdeps.wheelInfo(f.name).name.toLowerCase()]));
        assert.deepStrictEqual([...pinned].sort(), [...pydeps.imports].sort(), 'imports checked after install = the pinned packages');
        for (const s of SCRIPTS.filter(f => fs.existsSync(f))) {
            for (const m of importsOf(s)) {
                assert.ok(STDLIB.has(m) || pinned.has(m), `${path.basename(s)} imports ${m}: pin it in toolchain.json "textures" or add it to STDLIB here`);
            }
        }
        assert.ok(pinned.has('numpy') && pinned.has('PIL'));
    });

    await test('install order: Python, then the wheels, then Real-ESRGAN', () => {
        assert.deepStrictEqual(list.map(t => t.id), ['python', 'pydeps', 'realesrgan', 'realesrgan-license']);
    });

    await test('every download is pinned: https, SHA-256, size; wheels match the launcher Python', () => {
        const pyVer = /python-(\d+)\.(\d+)\.\d+-embed-amd64\.zip$/.exec(python.url);
        assert.ok(pyVer, python.url);
        assert.strictEqual(pydeps.python, `${pyVer[1]}.${pyVer[2]}`);
        for (const t of list.slice(1)) {
            for (const f of t.files || [{ url: t.url, sha256: t.sha256, size: t.size }]) {
                assert.match(f.url, /^https:\/\//);
                assert.match(f.sha256, /^[0-9a-f]{64}$/);
                assert.ok(Number.isInteger(f.size) && f.size > 0, `${f.url}: size`);
            }
        }
        for (const f of pydeps.files) {
            const w = texdeps.wheelInfo(f.name);
            assert.ok(w, f.name);
            assert.strictEqual(w.python, `cp${pyVer[1]}${pyVer[2]}`, `${f.name} is for another Python`);
            assert.strictEqual(w.platform, 'win_amd64');
            assert.match(f.url, /^https:\/\/files\.pythonhosted\.org\/packages\//);
            assert.strictEqual(decodeURIComponent(f.url.split('/').pop()), f.name);
        }
        const v = Object.fromEntries(pydeps.files.map(f => { const w = texdeps.wheelInfo(f.name); return [w.name.toLowerCase(), [w.version, f.sha256]]; }));
        assert.deepStrictEqual(v, {
            numpy: ['2.5.4', '2ca144f15135b6212a5c47b1e2aeca6e412f102f95a2d5d88d8aec77eb255de3'],
            pillow: ['13.0.0', 'f7cbb7a64e7ec664775195e4f81923bc8a93d9451b963f844e59118f63147a7a'] });
        const esr = list.find(t => t.id === 'realesrgan');
        assert.strictEqual(esr.sha256, 'abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d');
        assert.ok(esr.include.includes('realesrgan-ncnn-vulkan.exe') && esr.include.includes('models/*'));
    });

    await test('the scripts run with the pinned packages first and without the user site-packages', () => {
        const env = texdeps.pythonEnv('X:\\t', { PATH: 'p', PYTHONHOME: 'C:\\Python314', PYTHONPATH: 'C:\\elsewhere' });
        assert.strictEqual(env.PYTHONPATH, path.join('X:\\t', 'pydeps'));
        assert.strictEqual(env.PYTHONNOUSERSITE, '1');
        assert.strictEqual(env.PYTHONHOME, undefined);
        assert.strictEqual(env.PATH, 'p');
    });

    // a tools folder as installTool leaves it
    function fakeInstall(dir, tools) {
        for (const t of tools) {
            const d = path.join(dir, t.id);
            fs.mkdirSync(d, { recursive: true });
            fs.writeFileSync(path.join(d, '.launcher-stamp'), texdeps.stampOf(t));
            for (const f of t.files || []) { const w = texdeps.wheelInfo(f.name); if (w) fs.mkdirSync(path.join(d, `${w.name}-${w.version}.dist-info`)); }
            if (t.id === 'python') fs.writeFileSync(path.join(d, 'python.exe'), '');
            if (t.id === 'realesrgan') fs.writeFileSync(path.join(d, 'realesrgan-ncnn-vulkan.exe'), '');
        }
    }
    const realFetch = global.fetch;

    await test('already installed: no download, no import run', async () => {
        const dir = path.join(tmp, 'installed', 'tools');
        fakeInstall(dir, list);
        for (const t of list) assert.ok(texdeps.installed(t, dir), t.id);
        global.fetch = async () => { throw new Error('fetch called for an installed tool'); };
        const said = [];
        try {
            const p = await texdeps.ensure({ toolchain: tc, toolsDir: dir, downloadsDir: path.join(tmp, 'dl'), say: l => said.push(l) });
            assert.strictEqual(p.python, path.join(dir, 'python', 'python.exe'));
            assert.strictEqual(p.esrgan, path.join(dir, 'realesrgan', 'realesrgan-ncnn-vulkan.exe'));
            assert.strictEqual(p.env.PYTHONPATH, path.join(dir, 'pydeps'));
            assert.deepStrictEqual(said, []);
        } finally { global.fetch = realFetch; }
    });

    await test('a removed package or an older stamp means install again', () => {
        const dir = path.join(tmp, 'stale', 'tools');
        fakeInstall(dir, list);
        fs.rmSync(path.join(dir, 'pydeps', 'numpy-2.5.4.dist-info'), { recursive: true });
        assert.ok(!texdeps.installed(pydeps, dir));
        fs.writeFileSync(path.join(dir, 'realesrgan', '.launcher-stamp'), '0'.repeat(64));
        assert.ok(!texdeps.installed(list.find(t => t.id === 'realesrgan'), dir));
        assert.ok(texdeps.installed(python, dir));
    });

    await test('no network: a clear message, nothing left half-installed', async () => {
        const dir = path.join(tmp, 'offline', 'tools');
        fakeInstall(dir, [python]);   // Python there, the packages not
        global.fetch = async () => { const e = new TypeError('fetch failed'); e.cause = Object.assign(new Error('getaddrinfo ENOTFOUND files.pythonhosted.org'), { code: 'ENOTFOUND' }); throw e; };
        try {
            await assert.rejects(texdeps.ensure({ toolchain: tc, toolsDir: dir, downloadsDir: path.join(tmp, 'offline', 'dl') }),
                                 /Could not download Python packages numpy 2\.5\.4 and Pillow 13\.0\.0: no connection to the internet \(ENOTFOUND\)\. It is needed once; connect and try again\./);
            assert.ok(!fs.existsSync(path.join(dir, 'pydeps', '.launcher-stamp')));
        } finally { global.fetch = realFetch; }
    });

    await test('a wheel with the wrong SHA-256 is refused', async () => {
        const dir = path.join(tmp, 'badhash', 'tools');
        fakeInstall(dir, [python]);
        global.fetch = async () => new Response(Buffer.from('not the wheel'), { status: 200 });
        try {
            await assert.rejects(texdeps.ensure({ toolchain: tc, toolsDir: dir, downloadsDir: path.join(tmp, 'badhash', 'dl'), need: 'python' }),
                                 /Could not install Python packages .*SHA-256 [0-9a-f]{64}, expected 2ca144f1/);
            assert.ok(!texdeps.installed(pydeps, dir));
        } finally { global.fetch = realFetch; }
    });

    fs.rmSync(tmp, { recursive: true, force: true });
    console.log(failed ? `${failed} failed` : 'all passed');
    process.exit(failed ? 1 : 0);
})();
