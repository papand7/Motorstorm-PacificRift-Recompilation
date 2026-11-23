// The game's source the launcher carries (resources\source): one tar of
//   port-vkgame\   the MotorStorm port (copied from the working tree; it is not in git)
//   ps3recomp\     the runtime and its lifter tools: ps3recomp-vkgame's working tree (tracked files and untracked files
//                  git does not ignore, as on disk: `git ls-files -co --exclude-standard`); --runtime-head takes the
//                  committed tree (`git archive HEAD`) instead
//   pipeline\      launcher\pipeline: the lifting recipe and its manifest (hashes, offsets and sizes only)
//   tools\         tools\build_spu_overlay.py (the install's overlays step; it finds ps3recomp\tools beside it)
//   cockpit-tool\  tools\cockpit: make_cockpit_overlay.py, cockpit_positions.py and cockpit_positions.default.json
//                  (the shipped cockpit camera offsets; no game data)
//   pcmenu-tool\   tools\pcmenu (--with-pcmenu; `npm run dist` passes it)
//   texcollect-tool\ tools\texcollect
// staged in build\launcher-source\staging, audited with tools\audit_public.py --tree (the release bar: no game
// input, no lifted code, no binaries), scanned for key material, then packed as build\launcher-source\
// motorstorm-source.tar with SOURCE.json (the commits and the tar's SHA-256).
//
// Key material: the launcher adds none. Two upstream tools that embed PS3 package/EDAT keys and that the build does
// not use (tools/pkg_extract.py, tools/extract_jobmods.py, and test_pkg_extract.py which imports the first) are left
// out. The runtime itself still compiles libs/filesystem/edat.c and runtime/ppu/sdata_decrypt.h, which hold EDAT/SDAT
// keys from the upstream ps3recomp; the scan reports them and the snapshot is refused unless
// --allow-runtime-keys is given (a decision for the project owner: docs/LAUNCHER.md).
//
//   node source_bundles.js [--allow-runtime-keys] [--with-pcmenu] [--runtime-head] [--dev] [--stage-only]
'use strict';
const { execFileSync } = require('child_process');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
// --dev: the developer's snapshot for `npm start` (the unpackaged launcher reads build\launcher-source): packed even
// though the runtime carries key tables (it never leaves this PC and its SOURCE.json says dev_only). Never a release.
const dev = process.argv.includes('--dev');
const OUT = path.join(ROOT, 'build', 'launcher-source');
const STAGE = path.join(OUT, 'staging');
const TAR = process.platform === 'win32' ? path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'tar.exe') : 'tar';
const allowRuntimeKeys = process.argv.includes('--allow-runtime-keys');
const withPcmenu = process.argv.includes('--with-pcmenu');
// the runtime as on disk (the default; --runtime-worktree is the old spelling of it), or its HEAD with --runtime-head
const runtimeWorktree = !process.argv.includes('--runtime-head');
// --stage-only: stage and audit, pack nothing (a developer's test tree in build\, never a release)
const stageOnly = process.argv.includes('--stage-only');

const RUNTIME = path.join(ROOT, 'ps3recomp-vkgame');
const PORT = path.join(ROOT, 'port-vkgame');
const PIPELINE = path.join(ROOT, 'launcher', 'pipeline');
const PCMENU = path.join(ROOT, 'tools', 'pcmenu');
const COCKPIT = path.join(ROOT, 'tools', 'cockpit');
// single files from the project's tools\ the install runs from <src>\tools (each checked to exist)
const PROJECT_TOOLS = ['build_spu_overlay.py'];
// working-tree paths of the runtime never staged (build output, lifts, scratch: the audit's private folders)
const RUNTIME_SKIP_DIRS = new Set(['.git', '__pycache__', 'build', 'out', 'generated', 'recompiled', 'generated_spu',
                                   'spu_lifted', 'original', 'private', 'firmware', 'release', 'dist']);
const LEAVE_OUT = new Set(['tools/pkg_extract.py', 'tools/extract_jobmods.py', 'tools/test_pkg_extract.py']);
// what the runtime's build never reads and the release audit refuses (upstream's lifted test fixtures, packaging
// media, scratch, PDFs): removed from the staged runtime. (tests\ folders otherwise stay: CMake names
// libs/video/tests/test_shader_spirv.c when glslang is found.)
const LEAVE_OUT_DIRS = ['scratch', 'packaging', 'runtime/spu/tests'];
const LEAVE_OUT_EXT = /\.(pdf|png|icns|jpg)$/i;
const SKIP_DIRS = new Set(['__pycache__', '.git', 'build', 'out', 'generated', 'recompiled', 'spu']);
// files the runtime needs that carry upstream key tables (reported, see above)
const RUNTIME_KEY_FILES = ['libs/filesystem/edat.c', 'runtime/ppu/sdata_decrypt.h'];

const git = (dir, ...args) => execFileSync('git', ['-C', dir, ...args], { maxBuffer: 1 << 30 });

function copyTree(from, to) {
    fs.mkdirSync(to, { recursive: true });
    for (const e of fs.readdirSync(from, { withFileTypes: true })) {
        const a = path.join(from, e.name), b = path.join(to, e.name);
        if (e.isSymbolicLink()) throw new Error(`symbolic link in ${a}`);
        if (e.isDirectory()) { if (!SKIP_DIRS.has(e.name)) copyTree(a, b); }
        else if (e.isFile()) fs.copyFileSync(a, b);
    }
}

// a 16-byte table spelt as hex bytes, or a 32-hex-digit literal, near a key-like name
const KEYISH = /(key|klic|erk|riv)[^\n]{0,60}(\{\s*(0x[0-9a-f]{2}\s*,\s*){15}0x[0-9a-f]{2}|["'][0-9a-f]{32}["']|\[(\s*0x[0-9a-f]{2}\s*,){15})/i;
function keyScan(dir) {
    const hits = [];
    const walk = (d, rel) => {
        for (const e of fs.readdirSync(d, { withFileTypes: true })) {
            const p = path.join(d, e.name), r = rel ? `${rel}/${e.name}` : e.name;
            if (e.isDirectory()) walk(p, r);
            else if (/\.(c|h|cc|cpp|hpp|py|js|json|cmake|txt)$/i.test(e.name) && fs.statSync(p).size < 8 << 20) {
                if (KEYISH.test(fs.readFileSync(p, 'latin1'))) hits.push(r);
            }
        }
    };
    walk(dir, '');
    return hits;
}

function main() {
    fs.rmSync(STAGE, { recursive: true, force: true });
    fs.mkdirSync(STAGE, { recursive: true });
    // the runtime: the working tree as on disk (default), or its committed tree (HEAD) with --runtime-head
    const head = git(RUNTIME, "rev-parse", "HEAD").toString().trim();
    const dirty = git(RUNTIME, "status", "--porcelain").toString().trim();
    if (dirty && !runtimeWorktree) console.warn(`warning: ps3recomp-vkgame has uncommitted changes; --runtime-head takes HEAD ${head} without them`);
    const rt = path.join(STAGE, "ps3recomp");
    fs.mkdirSync(rt);
    if (runtimeWorktree) {
        // tracked files and new files git does not ignore (uncommitted headers the sources already include);
        // a tracked file deleted on disk is left out, as the build on disk would not see it either
        let copied = 0, skipped = 0;
        for (const f of git(RUNTIME, "ls-files", "-z", "--cached", "--others", "--exclude-standard").toString().split("\0").filter(Boolean)) {
            if (f.split("/").slice(0, -1).some(p => RUNTIME_SKIP_DIRS.has(p.toLowerCase()))) { skipped++; continue; }
            const a = path.join(RUNTIME, f);
            let st;
            try { st = fs.lstatSync(a); } catch { continue; }
            if (st.isSymbolicLink()) throw new Error(`symbolic link in ${a}`);
            if (!st.isFile()) continue;   // a submodule or a folder
            fs.mkdirSync(path.dirname(path.join(rt, f)), { recursive: true });
            fs.copyFileSync(a, path.join(rt, f));
            copied++;
        }
        console.log(`ps3recomp-vkgame working tree: ${copied} files${skipped ? `, ${skipped} under build/generated folders left out` : ""}` +
                    (dirty ? ` (HEAD ${head.slice(0, 12)} + uncommitted changes)` : ""));
    } else {
        const archive = path.join(OUT, "ps3recomp-head.tar");
        fs.writeFileSync(archive, git(RUNTIME, "archive", "--format=tar", "HEAD"));
        execFileSync(TAR, ["-xf", archive, "-C", rt]);
        fs.rmSync(archive);
    }
    for (const f of LEAVE_OUT) fs.rmSync(path.join(rt, f), { force: true });
    for (const d of LEAVE_OUT_DIRS) fs.rmSync(path.join(rt, d), { recursive: true, force: true });
    const prune = d => { for (const e of fs.readdirSync(d, { withFileTypes: true })) {
        const p = path.join(d, e.name);
        if (e.isDirectory()) prune(p); else if (LEAVE_OUT_EXT.test(e.name)) fs.rmSync(p);
    } };
    prune(rt);
    // the port and the pipeline
    copyTree(PORT, path.join(STAGE, "port-vkgame"));
    copyTree(PIPELINE, path.join(STAGE, "pipeline"));
    // --with-pcmenu: the page generator and its five reader modules as tools/pcmenu holds them (never a generated folder)
    const parts = ["port-vkgame", "ps3recomp", "pipeline"];
    // tools\: what the install runs from <src>\tools (build_spu_overlay.py: ROOT = parents[1] = <src>, so its lifter is
    // <src>\ps3recomp\tools\spu_lifter.py and wrap_spu_elf.py; it imports nothing else)
    {
        const to = path.join(STAGE, "tools");
        fs.mkdirSync(to, { recursive: true });
        for (const n of PROJECT_TOOLS) fs.copyFileSync(path.join(ROOT, "tools", n), path.join(to, n));
        for (const n of ["spu_lifter.py", "wrap_spu_elf.py"])
            if (!fs.existsSync(path.join(rt, "tools", n))) throw new Error(`build_spu_overlay.py needs ps3recomp/tools/${n}: not in the snapshot`);
        parts.push("tools");
    }
    // cockpit-tool\: the cockpit camera lists (code) and the shipped positions (camera offsets only, checked here)
    {
        const to = path.join(STAGE, "cockpit-tool");
        fs.mkdirSync(to, { recursive: true });
        for (const n of fs.readdirSync(COCKPIT)) if (/\.(py|json)$/.test(n)) fs.copyFileSync(path.join(COCKPIT, n), path.join(to, n));
        const pos = JSON.parse(fs.readFileSync(path.join(to, "cockpit_positions.default.json"), "utf8"));
        for (const [veh, v] of Object.entries(pos)) {
            if (!/^[a-z0-9_]+$/.test(veh)) throw new Error(`cockpit_positions.default.json: odd vehicle name ${veh}`);
            for (const [k, x] of Object.entries(v))
                if (!["x", "dy", "dz", "pitch", "yaw", "focal"].includes(k) || typeof x !== "number")
                    throw new Error(`cockpit_positions.default.json: ${veh}.${k} is not a camera offset`);
        }
        parts.push("cockpit-tool");
    }
    if (withPcmenu) {
        const to = path.join(STAGE, "pcmenu-tool");
        fs.mkdirSync(to, { recursive: true });
        for (const n of fs.readdirSync(PCMENU)) if (n.endsWith(".py")) fs.copyFileSync(path.join(PCMENU, n), path.join(to, n));
        parts.push("pcmenu-tool");
    }
    // tools/texcollect: "Collect all textures" (code only: it reads the player's archive; the dump it writes is theirs)
    const texcollect = path.join(ROOT, "tools", "texcollect");
    if (fs.existsSync(texcollect)) {
        const to = path.join(STAGE, "texcollect-tool");
        fs.mkdirSync(to, { recursive: true });
        for (const n of fs.readdirSync(texcollect)) if (n.endsWith(".py")) fs.copyFileSync(path.join(texcollect, n), path.join(to, n));
        parts.push("texcollect-tool");
    }
    // the release audit over everything staged, then the key scan
    let auditOk = true;
    try {
        execFileSync("python", [path.join(ROOT, "tools", "audit_public.py"), "--tree", STAGE], { stdio: "inherit" });
    } catch { auditOk = false; }
    // every quoted #include of the staged port and runtime resolves inside the bundle (before anything long is run)
    const inc = require("./check_includes").check(STAGE);
    console.log(`include check: ${inc.seen} quoted includes, ${inc.unresolved.length} unresolved, ${inc.generated.length} generated by the build`);
    for (const u of inc.unresolved.slice(0, 60)) console.error("  UNRESOLVED " + u);
    if (inc.unresolved.length) { console.error("the bundle misses files the sources include: not packed"); process.exit(1); }
    const keys = keyScan(STAGE);
    const unexpected = keys.filter(k => !RUNTIME_KEY_FILES.includes(k.replace(/^ps3recomp\//, "")));
    console.log(`key scan: ${keys.length} file(s) with key-like tables: ${keys.join(", ") || "none"}`);
    if (!auditOk) { console.error("audit_public.py --tree found private or binary files: not packed"); process.exit(1); }
    if (unexpected.length) { console.error(`unexpected key-like tables: ${unexpected.join(", ")}: not packed`); process.exit(1); }
    if (stageOnly) {
        // no tar: an earlier one is removed and SOURCE.json says so, so no old tar is ever paired with this staging
        fs.rmSync(path.join(OUT, "motorstorm-source.tar"), { force: true });
        let project = "";
        try { project = git(ROOT, "rev-parse", "HEAD").toString().trim(); } catch { /* not a checkout */ }
        fs.writeFileSync(path.join(OUT, "SOURCE.json"), JSON.stringify({ stage_only: true, ps3recomp: head + (runtimeWorktree && dirty ? " + uncommitted changes" : ""),
            project, tar_sha256: null, made: new Date().toISOString(), runtime_key_files: keys }, null, 2) + "\n");
        console.log(`staged and audited (not packed): ${STAGE}`);
        return;
    }
    if (keys.length && !allowRuntimeKeys && !dev) {
        console.error("The runtime carries upstream EDAT/SDAT key tables (above). Packing them into a launcher redistributes " +
                      "them: decide first (docs/LAUNCHER.md), then run with --allow-runtime-keys. Not packed.");
        process.exit(2);
    }
    const tar = path.join(OUT, "motorstorm-source.tar");
    fs.rmSync(tar, { force: true });
    execFileSync(TAR, ["-cf", tar, "-C", STAGE, ...parts]);
    const sha = crypto.createHash("sha256").update(fs.readFileSync(tar)).digest("hex");
    let project = "";
    try { project = git(ROOT, "rev-parse", "HEAD").toString().trim(); } catch { /* not a checkout */ }
    const info = { ps3recomp: head + (runtimeWorktree && dirty ? " + uncommitted changes" : ""), project, tar_sha256: sha,
                   made: new Date().toISOString(), runtime_key_files: keys, pcmenu_tool: withPcmenu, dev_only: dev };
    fs.writeFileSync(path.join(OUT, "SOURCE.json"), JSON.stringify(info, null, 2) + "\n");
    console.log(`${tar}: ${(fs.statSync(tar).size / 1048576).toFixed(1)} MB, SHA-256 ${sha}`);
}

main();
