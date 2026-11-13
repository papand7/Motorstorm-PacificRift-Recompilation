// The build tools: each one downloaded from its pinned URL, checked against its SHA-256 and size, unpacked into the
// launcher's own tools folder. Nothing is installed in Windows. The Microsoft C++ libraries and the Windows SDK come
// from the Visual Studio channel's manifest (which lists their SHA-256s), as in the NightFire launcher.
'use strict';
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { run } = require('./proc');

const WIN = process.platform === 'win32';
const TAR = WIN ? path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'tar.exe') : 'tar';

function sha256File(file, onProgress) {
    return new Promise((resolve, reject) => {
        const h = crypto.createHash('sha256');
        let done = 0;
        const total = fs.statSync(file).size;
        const s = fs.createReadStream(file, { highWaterMark: 4 << 20 });
        s.on('data', c => { h.update(c); done += c.length; if (onProgress) onProgress(done, total); });
        s.on('error', reject);
        s.on('end', () => resolve(h.digest('hex')));
    });
}

// url into file, resumed when a part is there, then checked: the wrong SHA-256 removes it
async function download(url, file, { sha256, size, onProgress, signal } = {}) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    if (fs.existsSync(file) && sha256) {
        if ((!size || fs.statSync(file).size === size) && await sha256File(file) === sha256) return file;
        fs.unlinkSync(file);
    }
    // The SHA-256 decides. The size is for progress (and the check when there is no hash): the Visual Studio manifest's
    // sizes do not always match its files (CRT.Headers 14.44: 2,128,977 listed, 2,116,223 served, SHA-256 as listed).
    const part = file + '.part';
    let have = fs.existsSync(part) ? fs.statSync(part).size : 0;
    if (size && have > size && !sha256) { fs.unlinkSync(part); have = 0; }
    if (have && sha256 && await sha256File(part) === sha256) { fs.renameSync(part, file); return file; }   // complete already
    if (!size || have < size || sha256) {
        const headers = { 'User-Agent': 'MotorStormLauncher' };
        if (have) headers.Range = `bytes=${have}-`;
        const r = await fetch(url, { headers, redirect: 'follow', signal });
        if (r.status === 416) { fs.unlinkSync(part); return download(url, file, { sha256, size, onProgress, signal }); }
        if (!r.ok || !r.body) throw new Error(`HTTP ${r.status} for ${url}`);
        if (have && r.status !== 206) have = 0;   // the server sends it all again
        const total = size || (Number(r.headers.get('content-length')) || 0) + have;
        const out = fs.createWriteStream(part, { flags: have ? 'a' : 'w' });
        let done = have;
        try {
            for await (const chunk of r.body) {
                done += chunk.length;
                if (!out.write(chunk)) await new Promise(res => out.once('drain', res));
                if (onProgress) onProgress(done, total);
            }
        } finally {
            await new Promise(res => out.end(res));
        }
    }
    if (size && !sha256 && fs.statSync(part).size !== size) throw new Error(`${path.basename(file)}: ${fs.statSync(part).size} bytes, expected ${size}`);
    if (sha256) {
        const got = await sha256File(part);
        if (got !== sha256) { fs.unlinkSync(part); throw new Error(`${path.basename(file)}: SHA-256 ${got}, expected ${sha256}`); }
    }
    fs.renameSync(part, file);
    return file;
}

// an archive (zip, tar.gz, tar.xz, vsix) unpacked by the system's bsdtar (Windows 10 1803 and later)
async function unpack(archive, dir, { strip = 0, include = [], log } = {}) {
    fs.mkdirSync(dir, { recursive: true });
    const args = ['-xf', archive, '-C', dir];
    if (strip) args.push('--strip-components', String(strip));
    args.push(...include);
    const code = await run(TAR, args, { log });
    if (code !== 0) throw new Error(`could not unpack ${path.basename(archive)} (tar ${code})`);
}

// "%2B" in a vsix's entry names: the real names
function urlDecodeTree(dir) {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, e.name);
        if (e.isDirectory()) urlDecodeTree(p);
        if (/%[0-9A-Fa-f]{2}/.test(e.name)) {
            const to = path.join(dir, decodeURIComponent(e.name));
            if (!fs.existsSync(to)) fs.renameSync(p, to);
        }
    }
}

// the Windows SDK's cabinets an .msi names: 32 hex digits and ".cab"
function msiCabs(buf) {
    const found = new Set();
    const s = buf.toString('latin1');
    const re = /[0-9a-f]{32}\.cab/g;
    let m;
    while ((m = re.exec(s))) found.add(m[0]);
    return [...found];
}

// the Visual Studio channel -> its manifest -> the MSVC library packages and the Windows SDK's installers (each with
// the SHA-256 the manifest gives it)
async function resolveMicrosoft(tc, { signal } = {}) {
    const get = async url => {
        const r = await fetch(url, { headers: { 'User-Agent': 'MotorStormLauncher' }, redirect: 'follow', signal });
        if (!r.ok) throw new Error(`HTTP ${r.status} for ${url}`);
        return r.json();
    };
    const channel = await get(tc.msvc.channel);
    const item = (channel.channelItems || []).find(i => i.id === 'Microsoft.VisualStudio.Manifests.VisualStudio');
    if (!item || !item.payloads) throw new Error('the Visual Studio channel lists no package manifest');
    const manifest = await get(item.payloads[0].url);
    const packages = new Map();
    for (const p of manifest.packages || []) {
        const chip = (p.chip || '').toLowerCase(), lang = (p.language || '').toLowerCase();
        if (chip && chip !== 'x64' && chip !== 'neutral') continue;
        if (lang && lang !== 'en-us' && lang !== 'neutral') continue;
        const id = String(p.id).toLowerCase();
        if (!packages.has(id)) packages.set(id, p);
    }
    const payloads = p => (p.payloads || []).map(pl => ({ url: pl.url, sha256: String(pl.sha256 || '').toLowerCase(), size: pl.size || 0,
                                                         name: String(pl.fileName || '').split(/[\\/]/).pop() }));
    const vc = { id: 'msvc', kind: 'vsix', title: `Microsoft C++ libraries ${tc.msvc.version}`, files: [], stamp: tc.msvc.version };
    for (const name of tc.msvc.packages) {
        const id = name.replace('{v}', tc.msvc.version);
        const p = packages.get(id.toLowerCase());
        if (!p) throw new Error(`the Visual Studio manifest has no ${id}`);
        for (const f of payloads(p)) vc.files.push({ ...f, name: id + '.vsix' });
    }
    const sdkPkg = packages.get(tc.sdk.package.toLowerCase());
    if (!sdkPkg) throw new Error(`the Visual Studio manifest has no ${tc.sdk.package}`);
    const want = new Set(tc.sdk.msis.map(m => m.toLowerCase()));
    const ws = { id: 'winsdk', kind: 'msi', title: `Windows SDK ${tc.sdk.version}`, files: [], cabs: [], version: tc.sdk.version };
    for (const f of payloads(sdkPkg)) {
        const n = f.name.toLowerCase();
        if (want.has(n)) ws.files.push(f);
        else if (n.endsWith('.cab')) ws.cabs.push(f);
    }
    if (ws.files.length !== want.size) throw new Error(`the Windows SDK package lacks some of its installers (${ws.files.length} of ${want.size})`);
    ws.stamp = tc.sdk.package + ' ' + ws.files.map(f => f.name).join(' ');
    return [vc, ws];
}

// one tool into dir (its own folder under tools\): skipped when its stamp says it is there
async function installTool(tool, toolsDir, downloadsDir, { say, log, signal }) {
    const dir = path.join(toolsDir, tool.id), stampFile = path.join(dir, '.launcher-stamp');
    const stamp = tool.stamp || tool.sha256 || (tool.files && tool.files.map(f => f.sha256).join(' '));
    try { if (fs.readFileSync(stampFile, 'utf8') === stamp) return dir; } catch { /* not there */ }
    fs.rmSync(dir, { recursive: true, force: true });
    const dl = path.join(downloadsDir, tool.id);
    const files = tool.files || [{ url: tool.url, sha256: tool.sha256, size: tool.size, name: decodeURIComponent(tool.url.split('/').pop()) }];
    let total = files.reduce((n, f) => n + (f.size || 0), 0), before = 0;
    const fetchOne = async f => {
        log(`download ${f.url}`);
        await download(f.url, path.join(dl, f.name), { sha256: f.sha256, size: f.size, signal,
            onProgress: d => say(`Downloading ${tool.title}`, mb(before + d, total), total ? (before + d) / total : -1) });
        before += f.size || 0;
    };
    for (const f of files) await fetchOne(f);
    if (tool.kind === 'msi') {
        const byName = new Map((tool.cabs || []).map(c => [c.name.toLowerCase(), c]));
        const needed = new Set();
        for (const f of files) for (const c of msiCabs(fs.readFileSync(path.join(dl, f.name)))) if (byName.has(c)) needed.add(byName.get(c));
        total = before + [...needed].reduce((n, c) => n + c.size, 0);
        for (const c of needed) await fetchOne(c);
        let i = 0;
        for (const f of files) {
            say(`Unpacking ${tool.title}`, f.name, i++ / files.length);
            fs.mkdirSync(dir, { recursive: true });
            // msiexec /a: an administrative image, no rights needed and nothing registered
            // (msiexec reads PROPERTY="value" itself, so the line is put together by hand)
            const code = await run('msiexec.exe', ['/a', `"${path.join(dl, f.name)}"`, '/qn', '/norestart', `TARGETDIR="${dir}"`],
                                   { log, windowsVerbatimArguments: true });
            if (code !== 0) throw new Error(`could not extract ${f.name} (msiexec ${code})`);
        }
    } else {
        say(`Unpacking ${tool.title}`, '', -1);
        for (const f of files) {
            if (tool.kind === 'vsix') {
                await unpack(path.join(dl, f.name), dir, { strip: 1, include: ['Contents/*'], log });
            } else if (tool.kind === 'file') {
                // kept as downloaded (a source archive a later step unpacks)
                fs.mkdirSync(dir, { recursive: true });
                fs.copyFileSync(path.join(dl, f.name), path.join(dir, tool.save_as || f.name));
            } else if (tool.kind === 'tar.zst') {
                // (LLVM's zstd window is past what Windows' tar.exe decodes: the launcher's Python 3.14 does it)
                const py = path.join(toolsDir, 'python', 'python.exe');
                if (!fs.existsSync(py)) throw new Error(`${tool.title} needs the Python tool first (toolchain.json order)`);
                const script = path.join(__dirname, 'untar_zst.py').replace(/app\.asar([\\/])/, 'app.asar.unpacked$1');   // (asarUnpack)
                const code = await run(py, [script, path.join(dl, f.name), dir, String(tool.strip || 0)],
                                       { log, onLine: l => say(`Unpacking ${tool.title}`, l, -1) });
                if (code !== 0) throw new Error(`could not unpack ${f.name} (python ${code})`);
            } else {
                await unpack(path.join(dl, f.name), dir, { strip: tool.strip || 0, include: tool.include || [], log });
            }
        }
        if (tool.kind === 'vsix') urlDecodeTree(dir);
    }
    if (tool.post === 'python-embed') {
        // the embeddable Python's ._pth limits sys.path to its own folder: without it the lifter finds its modules
        for (const n of fs.readdirSync(dir)) if (/\._pth$/i.test(n)) fs.unlinkSync(path.join(dir, n));
    }
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(stampFile, stamp);
    fs.rmSync(dl, { recursive: true, force: true });
    log(`${tool.title} ready in ${dir}`);
    return dir;
}

function mb(done, total) {
    const m = n => (n / 1048576).toFixed(1);
    return total ? `${m(done)} of ${m(total)} MB` : `${m(done)} MB`;
}

function firstDir(dir) {
    try { return path.join(dir, fs.readdirSync(dir).filter(n => fs.statSync(path.join(dir, n)).isDirectory()).sort().pop()); }
    catch { return null; }
}

// the environment Visual Studio's developer prompt would give: clang-cl finds the headers and libraries through it
function buildEnv(toolsDir, sdkVersion) {
    const t = id => path.join(toolsDir, id);
    const msvc = firstDir(path.join(t('msvc'), 'VC', 'Tools', 'MSVC'));
    const kits = path.join(t('winsdk'), 'Windows Kits', '10');
    let ver = sdkVersion;
    if (!ver || !fs.existsSync(path.join(kits, 'Include', ver))) ver = path.basename(firstDir(path.join(kits, 'Include')) || '');
    const env = { ...process.env };
    const llvm = path.join(t('llvm'), 'bin');   // (unpacked with its top folder stripped)
    env.PATH = [llvm, path.join(t('cmake'), 'bin'), t('ninja'), t('python'), path.join(kits, 'bin', ver, 'x64'), process.env.PATH].join(';');
    if (msvc) {
        const inc = path.join(kits, 'Include', ver), lib = path.join(kits, 'Lib', ver);
        env.INCLUDE = [path.join(msvc, 'include'), path.join(inc, 'ucrt'), path.join(inc, 'shared'), path.join(inc, 'um'),
                       path.join(inc, 'winrt'), path.join(inc, 'cppwinrt')].join(';');
        env.LIB = [path.join(msvc, 'lib', 'x64'), path.join(lib, 'ucrt', 'x64'), path.join(lib, 'um', 'x64')].join(';');
        env.VCToolsInstallDir = msvc + '\\';
        env.WindowsSdkDir = kits + '\\';
        env.WindowsSDKVersion = ver + '\\';
    }
    delete env.CC; delete env.CXX;
    return { env, llvmBin: llvm, cmake: path.join(t('cmake'), 'bin', 'cmake.exe'), ninja: path.join(t('ninja'), 'ninja.exe'),
             python: path.join(t('python'), 'python.exe') };
}

module.exports = { sha256File, download, unpack, resolveMicrosoft, installTool, buildEnv, msiCabs, mb };
