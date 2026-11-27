// What the HD textures page needs, fetched the first time it is used: the launcher's own Python (toolchain.json
// "tools", id python), the Python packages texpack.py and texcollect.py import (numpy, Pillow: toolchain.json
// "textures", wheels pinned by SHA-256 and size and unpacked into tools\pydeps) and Real-ESRGAN (the upscaler
// texpack.py runs). Each one goes through tools.installTool, as the build tools do: downloaded from its pinned URL,
// checked, unpacked into the launcher's tools folder and stamped, so a second run is offline and nothing is installed
// in Windows or in a system Python. The scripts then run with tools\pydeps first on PYTHONPATH and without the user's
// own site-packages (PYTHONNOUSERSITE), so the pinned packages are the ones imported on every PC.
'use strict';
const fs = require('fs');
const path = require('path');
const tools = require('./tools');
const { run } = require('./proc');

// the textures' tools in toolchain.json, in install order
function textureTools(tc) {
    const python = (tc.tools || []).find(t => t.id === 'python');
    if (!python) throw new Error('toolchain.json has no python tool');
    return [python, ...((tc.textures && tc.textures.tools) || [])];
}

// the stamp installTool writes for a tool (its SHA-256, or its files' SHA-256s)
function stampOf(tool) {
    return tool.stamp || tool.sha256 || (tool.files && tool.files.map(f => f.sha256).join(' '));
}

// "pkg-1.2.3-cp314-cp314-win_amd64.whl" -> { name: 'pkg', version: '1.2.3', python: 'cp314' }
function wheelInfo(fileName) {
    const m = /^([A-Za-z0-9_.]+)-([^-]+)-(cp\d+)-[^-]+-([^-]+)\.whl$/.exec(fileName);
    return m ? { name: m[1], version: m[2], python: m[3], platform: m[4] } : null;
}

// a tool already there: its stamp matches, and for the wheels each package's .dist-info folder is in place too
// (a stamp alone would hide a package someone deleted)
function installed(tool, toolsDir) {
    const dir = path.join(toolsDir, tool.id);
    try { if (fs.readFileSync(path.join(dir, '.launcher-stamp'), 'utf8') !== stampOf(tool)) return false; } catch { return false; }
    for (const f of tool.files || []) {
        const w = wheelInfo(f.name);
        if (w && !fs.existsSync(path.join(dir, `${w.name}-${w.version}.dist-info`))) return false;
    }
    if (tool.id === 'python' && !fs.existsSync(path.join(dir, 'python.exe'))) return false;
    if (tool.id === 'realesrgan' && !fs.existsSync(path.join(dir, 'realesrgan-ncnn-vulkan.exe'))) return false;
    return true;
}

// the environment a texture script runs in: the pinned packages first, nothing from the user's own site-packages
function pythonEnv(toolsDir, base = process.env) {
    const env = { ...base, PYTHONUTF8: '1', PYTHONUNBUFFERED: '1', PYTHONNOUSERSITE: '1' };
    env.PYTHONPATH = path.join(toolsDir, 'pydeps');
    delete env.PYTHONHOME;
    return env;
}

function paths(toolsDir) {
    return { python: path.join(toolsDir, 'python', 'python.exe'),
             esrgan: path.join(toolsDir, 'realesrgan', 'realesrgan-ncnn-vulkan.exe'),
             env: pythonEnv(toolsDir) };
}

const offline = e => /fetch failed|ENOTFOUND|EAI_AGAIN|ECONNREFUSED|ECONNRESET|ETIMEDOUT|ENETUNREACH|getaddrinfo|socket/i.test(
    `${e && e.message} ${e && e.cause && (e.cause.code || e.cause.message)}`);

// Every textures tool in place (downloaded once), then the packages imported by the launcher's Python as a check.
// say(line) gets short progress lines. Returns { python, esrgan, env }.
async function ensure({ toolchain, toolsDir, downloadsDir, say = () => {}, log = () => {}, signal, need = 'all' }) {
    const list = textureTools(toolchain).filter(t => need === 'all' || t.id !== 'realesrgan' && t.id !== 'realesrgan-license');
    const missing = list.filter(t => !installed(t, toolsDir));
    if (missing.length) say(`Getting what the textures need (once): ${missing.map(t => t.title).join(', ')}.`);
    for (const t of missing) {
        let shown = -1;
        const opt = { signal, log,
            say: (s, d, f) => { const p = f >= 0 ? Math.floor(f * 4) : -1; if (p !== shown) { shown = p; say(`${s}${d ? ': ' + d : ''}`); } } };
        try {
            await tools.installTool(t, toolsDir, downloadsDir, opt);
        } catch (e) {
            if (signal && signal.aborted) throw new Error('Stopped.');
            if (offline(e)) throw new Error(`Could not download ${t.title}: no connection to the internet (${e.cause && e.cause.code || e.message}). ` +
                                            'It is needed once; connect and try again.');
            throw new Error(`Could not install ${t.title}: ${e.message}`);
        }
    }
    const p = paths(toolsDir);
    const pydeps = list.find(t => t.id === 'pydeps');
    if (pydeps && missing.length) {
        // the packages must import in the launcher's own Python (a wheel for the wrong Python would fail here)
        const imports = pydeps.imports || [];
        const lines = [];
        const code = await run(p.python, ['-c', `import ${imports.join(', ')}; print('imports ok')`], { env: p.env, log: l => { lines.push(l); log(l); } });
        if (code !== 0) throw new Error(`The Python packages do not load (${lines.slice(-2).join(' ') || 'exit ' + code}).`);
    }
    return p;
}

module.exports = { textureTools, stampOf, wheelInfo, installed, pythonEnv, paths, ensure, offline };
