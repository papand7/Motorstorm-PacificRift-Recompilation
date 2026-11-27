// The install, step by step, each one kept when done (a stamp file) so Install can run again after a stop or a
// failure and only redo what is missing:
//   game      the player's disc (image or folder: its title, the helper for the files)
//   elf       the player's own decrypted EBOOT.elf of 1.00 (required): chosen by
//             the player, checked by SHA-256 (game.json). Nothing is decrypted here; the files stay where they are.
//   files     the game's files copied out of a disc image (a folder is read where it is)
//   tools     clang, CMake, Ninja, Python, the Microsoft C++ libraries and Windows SDK, the Vulkan headers and
//             glslang/SPIRV-Tools sources: each pinned by SHA-256 (toolchain.json), and DXC and FSR 3.1 for run time
//   source    the launcher's source snapshot (the port, the ps3recomp runtime and the lifting recipe) unpacked
//   glslang   glslang + SPIRV-Tools built into tools\vulkan-sdk (the shader compiler the Vulkan renderer links)
//   lift      the PPU and SPU code translated from the player's ELFs (pipeline\lift_motorstorm.py)
//   build     CMake + Ninja: the 1.00 build into work\build-stable
//   install   the exes into play\, play.json (the builds and how each starts), motorstorm.cfg (paths)
//   overlays  the SPU overlay captured from one short game run, lifted (tools\build_spu_overlay.py) and built in
//   pcmenu    the in-game PC Settings pages, from the 1.00 disc's MS2.PSARC
//   cockpit   the cockpit camera lists, from the same MS2.PSARC (cockpit-tool\, with the tuned positions)
'use strict';
const fs = require('fs');
const path = require('path');
const os = require('os');
const tools = require('./tools');
const disc = require('./disc');
const { run, killAll } = require('./proc');

const STABLE_EXE = 'MotorStormPacificRiftRecomp.exe';
// How both builds start (play.json): the Vulkan renderer with guest programs and async shader compile, as raced.
// The exe picks its renderer during static initialisation, before its own defaults (k_defaults) apply, so these
// have to be in the process environment.
// The rest is the full optimisation set of the 40+ fps reference run (vksync/ab2 ksr117, exe_c), minus its
// diagnostics, test-harness switches and per-run paths; most match k_defaults, but an older exe lacks some of them.
// Nothing settings.ini owns (pc_settings.h: frame rate, camera, patches, vsync, RT shadows, FSR, HDR, resolution,
// textures...) may be here: the exe skips a setting whose variable is already in the environment.
const PLAY_ENV = {
    RSX_BACKEND: 'vulkan', PS3RECOMP_VK_WINDOW: '1', PS3RECOMP_VK_GUEST_PROGRAMS: '1', RSX_SHADER_ASYNC: '1',
    PS3_ICALL_FAST: '1', PS3_LWCOND_WAKE: '1:poll_ms=100:heavy_draws=200', PS3_FRAME_CLOCK_KICK: '1', RSX_VK_PRESENT_ASYNC: '1', RSX_VK_ARENA_KEEP: '1', RSX_VK_READBACK_SKIP: '1', RSX_VK_STAGE_VRAM: '1', PS3_MAIN_CORE: '1', PS3_MAIN_CYCLES: '1',
    PS3_SIM_PACE: '1', PS3_SIM_PACE_LAG_MS: '40',   // catch-up bound: a hitch must not play back as a fast burst
    PS3_SPURS_EVENT_FALLBACK_MS: '4', PS3_SPURS_EVENT_SCHED: '1', PS3_SPURS_GUEST_MAXCONT: '1',
    PS3_SPU_DRAIN_RESUME_RELOC: '1', PS3_SPU_FP_CACHE: '1', PS3_SPU_HWFLOAT: '1', PS3_SPU_INTERP_REJOIN_RELOC: '1', PS3_SPU_MFC_FAST: '1',
    PS3_SPU_TASK_POOL: '1', PS3_SPU_TASK_QUIET: '1', PS3_SPU_WWS_AOT: '1', SPU_INTERP_UNLIFTED: '1',
    PS3_TEX_SNAPSHOT: '1', PS3_TEX_SNAPSHOT_EPOCH: '1', PS3_TEX_SNAPSHOT_WWATCH: '1',
    PS3_USLEEP_SPIN: '2', PS3_USLEEP_SPIN_MAIN_ONLY: '1', PS3_USLEEP_TAIL_US: '600',
    PS3_VM_STORE_FAST: '1', PS3_VM_STORE_INLINE: '1',
    RSX_BIND_DEDUP: '1', RSX_FP_SCAN_MEMO: '1', RSX_FP_SPAN: '1', RSX_GPU_REINTERP: '1', RSX_PIPE_MEMO: '1',
    RSX_POLY_OFFSET: '1',
    RSX_RT_NOATLAS: '1', RSX_RT_READBACK: '1', RSX_RT_READBACK_ASYNC: '1',   // =0 fixes exposure spikes (Kbr4/Kbr5) but costs ~5 fps in races; a fenced async ring is being built RSX_RT_READBACK_EAGER: '1',
    RSX_RT_TMIN: '0.5',
    RSX_SHADER_CACHE: '3', RSX_SHADER_GLSLANG_PARALLEL: '1', RSX_SHADER_REPLAY_PARALLEL: '1', RSX_SHADER_WINDOW: '1',
    RSX_TEX_BORDER: '1',   // the guest's texture border colour (vehicle blob shadows drew dark boxes with transparent black)
    RSX_SRV_REUSE: '1', RSX_TEX_BUDGET_MB: '1024', RSX_TEX_CACHE: '1', RSX_TEX_SLOTS: '1024', RSX_TEX_WWATCH: '1',
    RSX_VK_LAZY_SYNC: '1', RSX_VK_MEM_RECYCLE: '1',
    RSX_VP_COMPACT: '1', RSX_VP_FAST_FETCH: '1', RSX_VP_INDEXED: '1', RSX_VP_PARALLEL: '0', RSX_VS_MEMO: '1',
    RSX_VTX_DENSE: '1', RSX_VTX_GPU: '1', RSX_ZSNAP_ON_WRITE: '1',
    RSX_SHADOW_TILES: '1',   // world-fixed sun shadows, Original and Enhanced (as k_defaults; =0 only for testing, no row)
};
// RSX_RT_DXC is added dynamically in step_install (path beside the exe)

// ThinLTO link flags: lld-link's LTO jobs and a cache folder. The cache path is quoted: the flags reach lld-link as one
// command line, and an install folder with a space ("D:\EMU D\MotorStorm", issue #6) otherwise splits into separate
// arguments (lld-link: could not open 'D/MotorStorm/work/build-stable/lto-cache'), which fails CMake's compiler check.
function ltoLinkerFlags(jobs, cacheDir) {
    return `/opt:lldltojobs=${jobs} "/lldltocache:${cacheDir.replace(/\\/g, '/')}"`;
}

class Builder {
    constructor({ root, meta, source, emit, log }) {
        Object.assign(this, { root, meta, source, emit, log });
        this.game = JSON.parse(fs.readFileSync(path.join(meta, 'game.json'), 'utf8'));
        this.toolchain = JSON.parse(fs.readFileSync(path.join(meta, 'toolchain.json'), 'utf8'));
        this.cfgFile = path.join(root, 'launcher.json');
        this.cfg = {};
        try { this.cfg = JSON.parse(fs.readFileSync(this.cfgFile, 'utf8')); } catch { /* first start */ }
        // an earlier launcher stored the player's rpcs3.exe path here: this launcher does not use it, so it goes
        if ('rpcs3' in this.cfg) { delete this.cfg.rpcs3; try { fs.writeFileSync(this.cfgFile, JSON.stringify(this.cfg, null, 2)); } catch { /* best effort */ } }
        this.discInfo = null;
        this.elfInfo = { 100: null };
        this.busy = false;
        this.abort = null;
        this.stepId = null;
        this.message = null;
        this.ok = null;
        this.dirs = {
            tools: path.join(root, 'tools'), downloads: path.join(root, 'downloads'), work: path.join(root, 'work'),
            files: path.join(root, 'game'), play: path.join(root, 'play'),
        };
    }

    // A compile's output for the log: every line goes to launcher.log, but only ninja's progress and failures go to
    // the window. The lifted sources raise ~100k compiler warnings; sending each to the window backed up the
    // service's stdout (synchronous on Windows), which stalled ninja and made a 20 s compile take minutes.
    buildLog(prefix = '') {
        const show = /^\[\d+\/\d+\]|error|FAILED|^ninja:|^CMake|^--/i;
        return l => this.log(prefix + l, { fileOnly: !show.test(l) });
    }

    save() { fs.writeFileSync(this.cfgFile, JSON.stringify(this.cfg, null, 2)); }
    say(step, detail = '', fraction = -1) { this.emit({ ev: 'step', step, detail, fraction }); }
    stamp(id) { return path.join(this.root, 'work', `.done-${id}`); }
    done(id) { return fs.existsSync(this.stamp(id)); }
    mark(id, text = '') { fs.mkdirSync(path.dirname(this.stamp(id)), { recursive: true }); fs.writeFileSync(this.stamp(id), text || new Date().toISOString()); }
    unmark(...ids) { for (const id of ids) fs.rmSync(this.stamp(id), { force: true }); }

    steps() {
        return [
            ['game', 'Check your game'], ['elf', 'Check your decrypted EBOOT.elf files'], ['files', 'Copy the game files'],
            ['tools', 'Download the build tools'], ['source', 'Unpack the source'], ['glslang', 'Build the shader compiler'],
            ['lift', 'Translate the game code'], ['build', 'Build the game'], ['install', 'Install'],
            ['overlays', 'Build the SPU overlay code'], ['pcmenu', 'Make the PC Settings pages'],
            ['cockpit', 'Make the camera files'],
        ].map(([id, title]) => ({ id, title, done: this.done(id) }));
    }

    // the stable build is installed (its exe and play.json)
    installedBuilds() {
        const p = this.playInfo();
        if (!p || !p.builds) return {};
        const out = {};
        for (const [k, b] of Object.entries(p.builds)) if (fs.existsSync(path.join(this.dirs.play, b.exe))) out[k] = b.label;
        return out;
    }
    playInfo() { try { return JSON.parse(fs.readFileSync(path.join(this.dirs.play, 'play.json'), 'utf8')); } catch { return null; } }
    built() { return !!this.installedBuilds().stable; }

    // an EBOOT.elf the player chose: its path, and whether its SHA-256 is the one game.json names for that release
    elfState(which) {
        const p = this.cfg['elf' + which];
        if (!p) return null;
        if (this.elfInfo[which]) return { path: p, ...this.elfInfo[which] };
        return { path: p, checking: true };
    }

    sendState(extra = {}) {
        this.emit({
            ev: 'state', busy: this.busy, stepId: this.stepId, steps: this.steps(), built: this.built(), agreed: !!this.cfg.agreed,
            builds: this.installedBuilds(),
            disc: this.cfg.disc ? { path: this.cfg.disc, ...(this.discInfo || { checking: true }) } : null,
            elf100: this.elfState(100),
            plan: this.planText(), message: this.message, ok: this.ok, ...extra,
        });
    }

    planText() {
        const t = this.toolchain.tools.filter(x => !x.optional);
        const mb = Math.round(t.reduce((n, x) => n + (x.size || 0), 0) / 1048576);
        return `Downloads about ${mb + 600} MB of build tools (${t.map(x => x.title).join(', ')}, Microsoft's C++ libraries and ` +
               'Windows SDK) into the MotorStorm folder, and needs about 40 GB free while it builds.';
    }

    async set(cmd) {
        if (this.busy) return this.sendState();
        if (cmd.disc !== undefined) { this.cfg.disc = cmd.disc; this.discInfo = null; this.unmark('game', 'files'); }
        if (cmd.elf100 !== undefined) { this.cfg.elf100 = cmd.elf100; this.elfInfo[100] = null; this.unmark('elf', 'lift', 'build', 'install'); }
        if (cmd.agreed !== undefined) this.cfg.agreed = !!cmd.agreed;
        this.save();
        this.message = null;
        return this.scan('set');
    }

    // a player's decrypted EBOOT.elf: its SHA-256 against game.json (the only check; nothing is read but the file)
    async checkElf(which) {
        const p = this.cfg['elf' + which];
        if (!p) return null;
        const want = ((this.discInfo && this.discInfo.disc) || this.game.discs[0]).eboot_elf;   // the chosen disc's program
        const label = '1.00 (the disc)';
        if (!fs.existsSync(p)) return { ok: false, error: 'Not found (moved?).' };
        if (fs.statSync(p).size !== want.size)
            return { ok: false, error: `Not the ${label} EBOOT.elf: its size is ${fs.statSync(p).size}, not ${want.size}. Choose the decrypted EBOOT.elf of ${label} from your own console.` };
        const got = await tools.sha256File(p);
        if (got !== want.sha256)
            return { ok: false, error: `Not the ${label} EBOOT.elf (SHA-256 ${got.slice(0, 12)}...). Choose the decrypted EBOOT.elf of ${label} from your own console.` };
        return { ok: true, sha256: got };
    }

    async scan(after) {
        if (this.cfg.disc) {
            try {
                if (!fs.existsSync(this.cfg.disc)) this.discInfo = { ok: false, error: 'Not found (moved, or its drive is not connected).' };
                else {
                    this.say('Checking your game', 'reading its PARAM.SFO', -1);
                    const src = await disc.openGame(this.cfg.disc);
                    this.discInfo = await disc.checkGame(src, this.game);
                }
            } catch (e) { this.discInfo = { ok: false, error: e.message }; }
        }
        for (const w of [100]) {
            try { if (this.cfg['elf' + w]) this.elfInfo[w] = await this.checkElf(w); }
            catch (e) { this.elfInfo[w] = { ok: false, error: e.message }; }
        }
        this.sendState(after ? { after } : {});
    }

    cancel() {
        if (this.abort) this.abort.abort();
        killAll();
    }

    async clean(what) {
        if (this.busy) return;
        fs.rmSync(path.join(this.dirs.work), { recursive: true, force: true });
        if (what === 'all') fs.rmSync(this.dirs.tools, { recursive: true, force: true });
        this.message = 'The build was removed. Install builds it again.';
        this.ok = true;
        this.sendState();
    }

    // ---------------------------------------------------------------- install
    async install(cmd) {
        if (this.busy) return;
        if (cmd.agreed) { this.cfg.agreed = true; this.save(); }
        this.busy = true; this.message = null; this.ok = null;
        this.abort = new AbortController();
        this.sendState();
        const started = Date.now();
        try {
            for (const s of ['game', 'elf', 'files', 'tools', 'source', 'glslang', 'lift', 'build', 'install', 'overlays', 'pcmenu', 'cockpit']) {
                if (this.abort.signal.aborted) throw new Error('cancelled');
                this.stepId = s;
                this.sendState();
                this.log(`== ${s}`);
                await this['step_' + s]();
                if (this.abort.signal.aborted) throw new Error('cancelled');
                if (cmd.until === s) { this.log(`stopped after ${s} (until)`); break; }   // tests: cli.js --until
            }
            this.ok = true;
            this.message = cmd.until ? `Stopped after the ${cmd.until} step, as asked.` : `Installed in ${Math.round((Date.now() - started) / 60000)} minutes. Press Play.`;
            this.emit({ ev: 'done', ok: true, message: this.message });
        } catch (e) {
            this.ok = false;
            this.message = e.message === 'cancelled' || (this.abort && this.abort.signal.aborted)
                ? 'Stopped. Install continues from here.' : `${e.message}`;
            this.log(`failed: ${e.stack || e.message}`);
            this.emit({ ev: 'done', ok: false, message: this.message });
        } finally {
            this.busy = false; this.stepId = null; this.abort = null;
            this.sendState();
        }
    }

    // ---- game: the disc (title, the files) is known
    async step_game() {
        await this.scan();
        if (!this.discInfo || !this.discInfo.ok) throw new Error(this.discInfo ? this.discInfo.error : 'Choose your game disc first.');
        this.mark('game', this.discInfo.release);
    }

    // the player's own decrypted EBOOT.elf files: used where they are, never copied, decrypted or stored by the launcher
    elfPath() { return this.cfg.elf100; }

    // ---- elf: the 1.00 file (required), checked by SHA-256
    async step_elf() {
        // copies an earlier launcher made with RPCS3 (its work\decrypted and work\self) are removed: nothing decrypted is kept
        for (const d of ['decrypted', 'self']) fs.rmSync(path.join(this.dirs.work, d), { recursive: true, force: true });
        const want = [100];
        for (const w of want) {
            if (!this.cfg['elf' + w]) throw new Error("Choose your decrypted EBOOT.elf of 1.00 (the disc's): the stable build needs it.");
            const r = await this.checkElf(w);
            this.elfInfo[w] = r;
            if (!r.ok) throw new Error(r.error);
        }
        this.mark('elf');
    }

    // ---- files: a disc image's files copied out (the game reads loose files); a folder is used where it is
    vfsRoot() { return this.cfg.discKind === 'folder' ? disc.gameRoot(this.cfg.disc) : this.dirs.files; }
    async step_files() {
        const src = await disc.openGame(this.cfg.disc);
        this.cfg.discKind = src.kind;
        this.save();
        if (src.kind === 'iso') {
            const skip = this.game.skip_files || [];
            const need = src.files.filter(f => !skip.includes(f.path.toUpperCase())).reduce((n, f) => n + f.size, 0);
            this.log(`copying ${src.files.length} files (${tools.mb(need, 0)}) out of the disc image into ${this.dirs.files}`);
            await disc.copyGame(src, this.dirs.files, { skip, signal: this.abort.signal,
                say: (p, f, d, t) => this.say('Copying the game files', `${p}  (${tools.mb(d, t)})`, f) });
        }
        this.mark('files');
    }

    // ---- tools
    async step_tools() {
        if (!this.cfg.agreed) throw new Error("Accept the license terms of Microsoft's C++ libraries and Windows SDK first.");
        const opt = { say: (s, d, f) => this.say(s, d, f), log: l => this.log(l), signal: this.abort.signal };
        // the build tools, then what the game uses at run time (DXC for the ray-traced shadows, AMD's FSR 3.1 DLLs)
        for (const t of [...this.toolchain.tools, ...(this.toolchain.runtime || [])]) {
            if (t.optional) continue;
            await tools.installTool(t, this.dirs.tools, this.dirs.downloads, opt);
        }
        const msvcOk = fs.existsSync(path.join(this.dirs.tools, 'msvc', '.launcher-stamp')) && fs.existsSync(path.join(this.dirs.tools, 'winsdk', '.launcher-stamp'));
        if (!msvcOk || !this.done('tools')) {
            this.say('Looking up Microsoft\'s C++ libraries', 'Visual Studio channel', -1);
            const ms = await tools.resolveMicrosoft(this.toolchain, { signal: this.abort.signal });
            for (const t of ms) await tools.installTool(t, this.dirs.tools, this.dirs.downloads, opt);
        }
        this.mark('tools');
    }

    env() { return tools.buildEnv(this.dirs.tools, this.toolchain.sdk.version); }

    // ---- source: the launcher's own snapshot (a tar made by source_bundles.js) into work\src
    srcDir() { return path.join(this.dirs.work, 'src'); }
    async step_source() {
        const tar = path.join(this.source, 'motorstorm-source.tar');
        const info = path.join(this.source, 'SOURCE.json');
        if (!fs.existsSync(tar)) throw new Error(`This launcher carries no game source (${tar}). Developers: npm run bundles.`);
        const want = fs.readFileSync(info, 'utf8');
        // the tar's own SHA-256 decides (not SOURCE.json's text): a snapshot whose SOURCE.json does not describe its tar,
        // or a staging-only SOURCE.json, is refused; a different tar than the one unpacked is unpacked again
        let meta = {};
        try { meta = JSON.parse(want); } catch { throw new Error('SOURCE.json is not readable.'); }
        if (meta.stage_only) throw new Error('This source folder was staged only (no tar was packed): run source_bundles.js again.');
        const actual = await tools.sha256File(tar);
        if (!meta.tar_sha256 || meta.tar_sha256 !== actual)
            throw new Error(`SOURCE.json does not describe motorstorm-source.tar (SHA-256 ${actual.slice(0, 12)}..., it says ${String(meta.tar_sha256).slice(0, 12)}...): run source_bundles.js again.`);
        const have = path.join(this.srcDir(), 'SOURCE.sha256');
        let unpacked = '';
        try { unpacked = fs.readFileSync(have, 'utf8').trim(); } catch { /* nothing unpacked yet */ }
        if (unpacked === actual) return this.mark('source');
        // a different (or no) source: the old tree goes first, and what was made from it is made again
        // (overlays too: its lift lives in work\src\generated and goes with the old tree)
        this.unmark('glslang', 'lift', 'build', 'install', 'overlays');
        fs.rmSync(this.srcDir(), { recursive: true, force: true });
        this.say('Unpacking the source', '', -1);
        await tools.unpack(tar, this.srcDir(), { log: l => this.log(l) });
        fs.writeFileSync(path.join(this.srcDir(), 'SOURCE.json'), want);
        fs.writeFileSync(have, actual + '\n');
        this.mark('source');
    }

    // ---- glslang + SPIRV-Tools from their pinned sources into tools\vulkan-sdk (Include\, Lib\ as the runtime's
    // CMake expects of a LunarG SDK), with the Vulkan headers
    async step_glslang() {
        const sdk = path.join(this.dirs.tools, 'vulkan-sdk');
        const v = this.toolchain.vulkan;
        const stampFile = path.join(sdk, '.launcher-stamp');
        try { if (fs.readFileSync(stampFile, 'utf8') === v.stamp) return this.mark('glslang'); } catch { /* build it */ }
        const t = id => path.join(this.dirs.tools, id);
        const src = path.join(this.dirs.work, 'glslang-src'), bld = path.join(this.dirs.work, 'glslang-build');
        fs.rmSync(src, { recursive: true, force: true });
        fs.rmSync(bld, { recursive: true, force: true });
        fs.rmSync(sdk, { recursive: true, force: true });
        // glslang's External\spirv-tools and its external\spirv-headers, as glslang's update script lays them out
        const unpackTo = async (id, dir) => tools.unpack(path.join(t(id), 'src.tar.gz'), dir, { strip: 1, log: l => this.log(l) });
        await unpackTo('glslang-src', src);
        await unpackTo('spirv-tools-src', path.join(src, 'External', 'spirv-tools'));
        await unpackTo('spirv-headers-src', path.join(src, 'External', 'spirv-tools', 'external', 'spirv-headers'));
        const { env, llvmBin, cmake, ninja } = this.env();
        const cc = path.join(llvmBin, 'clang-cl.exe');
        const log = l => this.log('glslang: ' + l);
        this.say('Building the shader compiler (glslang)', 'a few minutes', -1);
        let code = await run(cmake, ['-S', src, '-B', bld, '-G', 'Ninja', `-DCMAKE_MAKE_PROGRAM=${ninja}`, '-DCMAKE_BUILD_TYPE=Release',
            `-DCMAKE_C_COMPILER=${cc}`, `-DCMAKE_CXX_COMPILER=${cc}`, '-DCMAKE_LINKER_TYPE=LLD', `-DCMAKE_INSTALL_PREFIX=${sdk}`,
            '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL', '-DENABLE_OPT=ON', '-DENABLE_GLSLANG_BINARIES=OFF', '-DGLSLANG_TESTS=OFF',
            '-DSPIRV_SKIP_TESTS=ON', '-DSPIRV_SKIP_EXECUTABLES=ON', '-DSPIRV_WERROR=OFF', '-DBUILD_SHARED_LIBS=OFF',
            '-DENABLE_HLSL=ON', '-DCMAKE_POLICY_VERSION_MINIMUM=3.5'], { env, log });
        if (code !== 0) throw new Error('Preparing the glslang build failed, see the log.');
        code = await run(cmake, ['--build', bld, '--target', 'install', '--parallel', String(this.jobs())], { env, log: this.buildLog('glslang: '),
            onLine: l => { const m = /^\[(\d+)\/(\d+)\]/.exec(l); if (m) this.say('Building the shader compiler (glslang)', `${m[1]} of ${m[2]}`, m[1] / m[2]); } });
        if (code !== 0) throw new Error('Building glslang failed, see the log.');
        // the LunarG layout the runtime's CMake reads: Include\ and Lib\ (CMake installs include\ and lib\; Windows
        // paths ignore case). SPIRV.lib: glslang 16 folded it into glslang.lib, so an empty stand-in library
        const lib = path.join(sdk, 'lib');
        if (!fs.existsSync(path.join(lib, 'SPIRV.lib'))) await this.emptyLib(path.join(lib, 'SPIRV.lib'), env, llvmBin);
        // the Vulkan headers beside them (vulkan\vulkan.h)
        await tools.unpack(path.join(t('vulkan-headers-src'), 'src.tar.gz'), path.join(this.dirs.work, 'vkheaders'), { strip: 1, log: l => this.log(l) });
        fs.cpSync(path.join(this.dirs.work, 'vkheaders', 'include'), path.join(sdk, 'include'), { recursive: true });
        fs.rmSync(path.join(this.dirs.work, 'vkheaders'), { recursive: true, force: true });
        fs.rmSync(bld, { recursive: true, force: true });
        fs.rmSync(src, { recursive: true, force: true });
        fs.writeFileSync(stampFile, v.stamp);
        this.mark('glslang');
    }

    async emptyLib(out, env, llvmBin) {
        const c = path.join(os.tmpdir(), 'ms_empty_spirv.c'), o = c.replace(/\.c$/, '.obj');
        fs.writeFileSync(c, 'int ms_launcher_spirv_placeholder;\n');
        await run(path.join(llvmBin, 'clang-cl.exe'), ['/c', c, `/Fo${o}`], { env, log: l => this.log(l) });
        const code = await run(path.join(llvmBin, 'llvm-lib.exe'), [`/out:${out}`, o], { env, log: l => this.log(l) });
        if (code !== 0) throw new Error('could not make SPIRV.lib');
    }

    jobs() {
        if (Number(process.env.MS_BUILD_JOBS) > 0) return Number(process.env.MS_BUILD_JOBS);   // developers, tests
        // leave the PC usable: the lifted sources take 2-4 GB of memory each to compile
        // (a lifted PPU chunk peaked at 2.7 GB, an SPU image at 0.4 GB: measured 2026-11-27 on the HX 370)
        const byMem = Math.max(1, Math.floor(os.totalmem() / (3 * 1024 ** 3)));
        return Math.max(1, Math.min(os.cpus().length - 1, byMem));
    }

    // the ThinLTO link's backend jobs: about 1.3 GB each (7 jobs peaked at 9.9 GB), so more fit than compiles; the link
    // is the longest single step of an install (15 min at 7 jobs on the HX 370)
    ltoJobs() {
        if (Number(process.env.MS_BUILD_JOBS) > 0) return Number(process.env.MS_BUILD_JOBS);
        return Math.max(1, Math.min(os.cpus().length, Math.floor(os.totalmem() / (2 * 1024 ** 3))));
    }

    // ---- lift: pipeline\lift_motorstorm.py (in the source snapshot) from the player's ELFs into work\src\generated
    async step_lift() {
        const key = '100';
        try { if (this.done('lift') && fs.readFileSync(this.stamp('lift'), 'utf8') === key) return; } catch { /* not there */ }
        const { env, python } = this.env();
        if (!this.elfPath(100)) throw new Error('Choose your decrypted EBOOT.elf (1.00) first.');
        const script = path.join(this.srcDir(), 'pipeline', 'lift_motorstorm.py');
        const args = [script, '--root', this.srcDir(), '--elf-disc', this.elfPath(100),
                      '--jobs', String(Math.max(1, Math.min(os.cpus().length - 1, Math.floor(os.totalmem() / (3 * 1024 ** 3)))))];
        this.say('Translating the game code', 'about 4 minutes', -1);
        const code = await run(python, args, { env, cwd: this.srcDir(), log: l => this.log('lift: ' + l),
            onLine: l => { const m = /^\[step\] (.*)$/.exec(l); if (m) this.say('Translating the game code', m[1], -1);
                           const p = /lifted (\d+)\/(\d+) functions/.exec(l); if (p) this.say('Translating the game code', `PPU: ${p[1]} of ${p[2]} functions`, p[1] / p[2]); } });
        if (code !== 0) throw new Error('Translating the game code failed, see the log.');
        this.unmark('build', 'install');
        this.mark('lift', key);
    }

    // ---- build: each wanted build with CMake and Ninja, its own folder (the options in game.json "builds")
    buildDir(variant) { return path.join(this.dirs.work, `build-${variant}`); }
    variants() { return ['stable']; }
    async step_build() {
        const { env, llvmBin, cmake, ninja, python } = this.env();
        const src = this.srcDir(), gen = path.join(src, 'generated');
        const cc = path.join(llvmBin, 'clang-cl.exe');
        const fwd = p => p.replace(/\\/g, '/');
        const log = l => this.log(l);
        for (const variant of this.variants()) {
            const b = this.game.builds[variant];
            const bld = this.buildDir(variant);
            // configured every time (cheap; incremental): the cache must hold the current paths (the player's ELFs, the tools)
            this.say(`Preparing the ${b.label} build`, `${b.version} with CMake`, -1);
            const defs = [
                `-DCMAKE_MAKE_PROGRAM=${ninja}`, '-DCMAKE_BUILD_TYPE=Release', `-DCMAKE_C_COMPILER=${cc}`, `-DCMAKE_CXX_COMPILER=${cc}`,
                '-DCMAKE_LINKER_TYPE=LLD', `-DPython3_EXECUTABLE=${python}`,
                `-DPS3RECOMP_DIR=${path.join(src, 'ps3recomp')}`, `-DRECOMP_DIR=${path.join(gen, 'ppu-100')}`,
                `-DSPU_DIR=${path.join(gen, 'spu')}`, `-DPORT_SPU_INPUTS=${this.elfPath()}`,
                `-DPS3RECOMP_VULKAN_INCLUDE_DIR=${path.join(this.dirs.tools, 'vulkan-sdk', 'include')}`,
                `-DPS3RECOMP_VULKAN_SDK=${fwd(path.join(this.dirs.tools, 'vulkan-sdk'))}`,
                `-DPS3RECOMP_SPU_LIFTER_IMAGE_ARGS=${b.spu_lifter_image_args.join(';')}`,
                ...(b.options.includes('MSPR_WWS_AOT=ON')
                    ? [`-DMSPR_WWS_AOT_DIR=${path.join(gen, 'spu_raw', 'wws_reloc_v100')}`] : []),
                // ThinLTO (PORT_PPU_LTO) links with lld-link's LTO jobs and a cache beside the build (quoted: ltoLinkerFlags)
                ...(b.options.includes('PORT_PPU_LTO=ON')
                    ? [`-DCMAKE_EXE_LINKER_FLAGS=${ltoLinkerFlags(this.ltoJobs(), path.join(bld, 'lto-cache'))}`] : []),
                ...b.options.map(o => `-D${o}`),
            ];
            const code = await run(cmake, ['-S', path.join(src, 'port-vkgame'), '-B', bld, '-G', 'Ninja', ...defs], { env, log });
            if (code !== 0) { fs.rmSync(path.join(bld, 'CMakeCache.txt'), { force: true }); throw new Error(`Preparing the ${b.label} build failed, see the log.`); }
            this.say(`Building MotorStorm ${b.version} (${b.label})`, 'the first build takes 30 to 90 minutes', 0);
            const built = await run(cmake, ['--build', bld, '--parallel', String(this.jobs())], { env, log: this.buildLog(),
                onLine: l => { const m = /^\[(\d+)\/(\d+)\]/.exec(l); if (m) this.say(`Building MotorStorm ${b.version} (${b.label})`, `${m[1]} of ${m[2]} steps`, m[1] / m[2]); } });
            if (built !== 0) throw new Error(this.abort.signal.aborted ? 'cancelled' : `The ${b.label} build failed, see the log.`);
            if (!fs.existsSync(path.join(bld, STABLE_EXE))) throw new Error(`The ${b.label} build made no ${STABLE_EXE}.`);
        }
        this.mark('build', this.variants().join('+'));
    }

    // ---- install: each build's exe (under its own name) and the DLLs into play\; play.json says how each starts
    async step_install() {
        const play = this.dirs.play;
        fs.mkdirSync(play, { recursive: true });
        const variants = this.variants();
        for (const variant of variants) {
            const bld = this.buildDir(variant);
            const b = this.game.builds[variant];
            for (const n of fs.readdirSync(bld)) {
                if (/\.dll$/i.test(n)) {
                    try { fs.copyFileSync(path.join(bld, n), path.join(play, n)); }
                    catch (e) { throw new Error(`Cannot copy ${n} (is the game still running?)`); }
                }
            }
            try { fs.copyFileSync(path.join(bld, STABLE_EXE), path.join(play, b.exe)); }
            catch (e) { throw new Error(`Cannot copy ${b.exe} (is the game still running?)`); }
        }
        // an earlier launcher's 1.03 exe is removed
        fs.rmSync(path.join(play, 'MotorStormPacificRiftRecomp-103.exe'), { force: true });
        // the run-time pieces from tools\ (toolchain.json "runtime": each tool's files into play\<to>)
        for (const t of this.toolchain.runtime || []) {
            const to = path.join(play, t.install.to);
            fs.mkdirSync(to, { recursive: true });
            for (const pat of t.install.files) {
                const dir = path.join(this.dirs.tools, t.id, path.dirname(pat));
                const re = new RegExp('^' + path.basename(pat).replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$', 'i');
                let any = false;
                for (const n of fs.existsSync(dir) ? fs.readdirSync(dir) : []) {
                    if (!re.test(n)) continue;
                    try { fs.copyFileSync(path.join(dir, n), path.join(to, n)); any = true; }
                    catch (e) { throw new Error(`Cannot copy ${n} (is the game still running?)`); }
                }
                if (!any) this.log(`warning: ${t.title}: nothing matches ${pat}`);
            }
        }
        const vfs = this.vfsRoot();
        const dxcExe = path.join(play, 'dxc', 'dxc.exe');
        const env = { ...PLAY_ENV };
        if (fs.existsSync(dxcExe)) env.RSX_RT_DXC = dxcExe;
        const builds = {
            stable: { label: this.game.builds.stable.label, version: this.game.builds.stable.version, exe: this.game.builds.stable.exe,
                      elf: this.elfPath(100), env },
        };
        const info = { default: 'stable', builds, vfs_root: vfs, release: this.discInfo.release, built: new Date().toISOString() };
        fs.writeFileSync(path.join(play, 'play.json'), JSON.stringify(info, null, 2));
        // motorstorm.cfg: the paths the game reads
        const cfg = path.join(play, 'motorstorm.cfg');
        let lines = [];
        try { lines = fs.readFileSync(cfg, 'utf8').split(/\r?\n/).filter(l => l && !/^(PS3_HDD0_ROOT|PS3_VFS_OVERLAY|PS3_VFS_ROOT)=/.test(l)); } catch { /* new */ }
        if (!lines.length) lines.push('# MotorStorm: Pacific Rift paths (written by the launcher; the settings are in settings.ini)');
        lines.push(`PS3_VFS_ROOT=${vfs}`);
        fs.writeFileSync(cfg, lines.join('\n') + '\n');
        this.log(`installed in ${play}: ${Object.values(builds).map(x => x.label + ' ' + x.version).join(', ')}`);
        this.mark('install');
    }

    // ---- overlays: run the installed game once briefly to capture the SPU DMA overlay, lift it with --chain-chunks,
    //                rebuild the stable exe with MSPR_OVL_CHAIN=ON. Soft failure: if the capture times out the game
    //                runs fine without overlay AOT; re-running Install will retry.
    async step_overlays() {
        const PLAN = [
            { name: 'spu38790', base: 220928, entry: 224880, size: 12288,
              sha256: '7ddb23d4b7882d7bff7771eca8e59167c1e9eb014a2ca1fc52ca6b1876a3a75f' },
        ];
        if (this.done('overlays')) return;

        const playJson = this.playInfo();
        if (!playJson || !playJson.builds || !playJson.builds.stable) {
            this.log('overlays: no play.json or stable build — skipping'); return;
        }
        const sb = playJson.builds.stable;
        const exe = path.join(this.dirs.play, sb.exe);
        if (!fs.existsSync(exe)) { this.log('overlays: stable exe not found — skipping'); return; }

        const dumpDir = path.join(this.dirs.work, 'ovl-capture');
        fs.mkdirSync(dumpDir, { recursive: true });

        const captureEnv = { ...process.env, ...(sb.env || {}), PS3_VFS_ROOT: playJson.vfs_root,
                             // <dir>,<LS base>: the dumper watches LS 0x5000 unless told; the overlay loads at its base
                             // (0x35F00 for spu38790, docs/BUILD.md), so without it nothing was ever written
                             SPU_DUMP_OVL: `${dumpDir},0x${PLAN[0].base.toString(16)}`, SPU_DUMP_OVL_LATEST: '1' };
        this.say('Capturing the SPU overlay', 'running the game briefly (up to 2 minutes)', -1);
        this.log(`overlays: starting ${sb.exe} with SPU_DUMP_OVL=${dumpDir}`);
        const cp = require('child_process');
        // the player's EBOOT.elf is the game's argument, as Play passes it (main.js): without it the exe exits at once
        // and nothing is ever captured. The game's output goes to the log, so a failed capture says why.
        const proc = cp.spawn(exe, [sb.elf], { env: captureEnv, cwd: this.dirs.play, detached: false, stdio: ['ignore', 'pipe', 'pipe'] });
        let exited = null;
        proc.on('exit', code => { exited = code; });
        const tail = [];
        for (const s of [proc.stdout, proc.stderr]) require('readline').createInterface({ input: s })
            .on('line', l => { tail.push(l); if (tail.length > 40) tail.shift(); this.log('overlays: game: ' + l, { fileOnly: true }); });

        const foundBins = [];
        const deadline = Date.now() + 120000;
        let gameGone = false;
        while (Date.now() < deadline && foundBins.length < PLAN.length && !gameGone) {
            await new Promise(r => setTimeout(r, 3000));
            if (this.abort && this.abort.signal.aborted) break;
            // the game has gone: this pass still reads what it wrote, then the loop ends (no 2-minute wait for nothing)
            if (exited !== null && !gameGone) { gameGone = true; this.log(`overlays: the game exited (code ${exited}); its last lines:\n${tail.join('\n')}`); }
            for (const f of fs.readdirSync(dumpDir)) {
                if (!f.endsWith('.bin')) continue;
                const fp = path.join(dumpDir, f);
                const sha = await tools.sha256File(fp);
                const ov = PLAN.find(o => o.sha256 === sha);
                if (ov && !foundBins.find(x => x.name === ov.name)) {
                    foundBins.push({ ...ov, file: fp });
                    this.log(`overlays: captured ${ov.name} sha256=${sha.slice(0, 12)}`);
                    this.say('Capturing the SPU overlay', `captured ${ov.name}`, -1);
                }
            }
        }
        try { proc.kill(); } catch {}

        if (foundBins.length < PLAN.length) {
            const miss = PLAN.filter(o => !foundBins.find(x => x.name === o.name)).map(o => o.name).join(', ');
            this.log(`overlays: ${miss} not captured within 120 s — no overlay AOT this install (re-run Install to retry)`);
            return;
        }

        const src = this.srcDir();
        const { env, python, cmake } = this.env();
        const liftTool = path.join(src, 'tools', 'build_spu_overlay.py');
        for (const ov of foundBins) {
            const outDir = path.join(src, 'generated', 'overlays-chain', ov.name, 'lift');
            this.say('Lifting the SPU overlay', ov.name, -1);
            const code = await run(python, [liftTool,
                '--input-dir', dumpDir, '--sha256', ov.sha256,
                '--out', outDir,
                '--base', String(ov.base), '--entry', String(ov.entry), '--size', String(ov.size),
                '--lifter-arg=--chain-chunks',
            ], { env, log: l => this.log('ovl-lift: ' + l) });
            if (code !== 0) { this.log(`overlays: lifting ${ov.name} failed — no overlay AOT`); return; }
        }

        // incremental rebuild of the stable exe with MSPR_OVL_CHAIN=ON (only the new overlay sources + link)
        const bld = this.buildDir('stable');
        const b = this.game.builds.stable;
        this.say('Rebuilding with SPU overlay AOT', 'incremental, a few minutes', -1);
        let code = await run(cmake, ['-S', path.join(src, 'port-vkgame'), '-B', bld, '-G', 'Ninja',
            '-DMSPR_OVL_CHAIN=ON'], { env, log: l => this.log(l) });
        if (code !== 0) { this.log('overlays: CMake reconfigure failed — no overlay AOT'); return; }
        code = await run(cmake, ['--build', bld, '--parallel', String(this.jobs())], { env, log: this.buildLog(),
            onLine: l => { const m = /^\[(\d+)\/(\d+)\]/.exec(l); if (m) this.say('Rebuilding with SPU overlay AOT', `${m[1]} of ${m[2]} steps`, m[1] / m[2]); } });
        if (code !== 0) { this.log('overlays: rebuild failed — no overlay AOT'); return; }
        try { fs.copyFileSync(path.join(bld, STABLE_EXE), path.join(this.dirs.play, b.exe)); }
        catch (e) { this.log(`overlays: cannot copy updated exe — ${e.message}`); return; }
        this.log('overlays: SPU overlay AOT built and installed');
        this.mark('overlays');
    }

    // ---- pcmenu: the in-game PC Settings pages, made on this PC from the player's MS2.PSARC (the retail Options
    // pages) by make_pcmenu.py (docs/SETTINGS.md). Run after every install, since the pages must match the exe.
    // Never shipped: the output derives from the game's data. Where the tool lives is configurable (it is private
    // analysis code until the project owner decides): MS_PCMENU_DIR, launcher.json "pcmenuDir", or pcmenu-tool\ in the
    // source snapshot (source_bundles.js --with-pcmenu). Without it, or if it fails, the game shows its retail
    // Options page and settings.ini still applies, so this step only warns.
    pcmenuDir() {
        for (const d of [process.env.MS_PCMENU_DIR, this.cfg.pcmenuDir, path.join(this.srcDir(), 'pcmenu-tool')])
            if (d && fs.existsSync(path.join(d, 'make_pcmenu.py'))) return d;
        return null;
    }
    async step_pcmenu() {
        const dir = this.pcmenuDir();
        if (!dir) { this.log('pcmenu: no make_pcmenu.py (see docs/LAUNCHER.md): the game keeps its retail Options page'); return; }
        const psarc = path.join(this.vfsRoot(), 'PS3_GAME', 'USRDIR', 'MS2.PSARC');
        if (!fs.existsSync(psarc)) { this.log(`pcmenu: ${psarc} not found: skipped`); return; }
        const { env, python } = this.env();
        const out = path.join(this.dirs.play, 'pcmenu');
        this.say('Making the PC Settings pages', 'from your game\'s Options pages (1.00)', -1);
        const code = await run(python, [path.join(dir, 'make_pcmenu.py'), '--psarc', psarc, '--out', out,
                                        '--port', path.join(this.srcDir(), 'port-vkgame')], { env, cwd: dir, log: l => this.log('pcmenu: ' + l) });
        if (code !== 0) { this.log(`pcmenu: make_pcmenu.py failed (${code}): the game keeps its retail Options page`); return; }
        this.mark('pcmenu');
    }

    // ---- cockpit: the camera files for Camera: Cockpit view (MSPR_CAM_COCKPIT), made on this PC from the player's own
    // MS2.PSARC by make_cockpit_overlay.py, into the same overlay folder as the PC Settings pages (PS3_VFS_OVERLAY).
    // Never shipped: the output derives from the game's data. The tool is found like make_pcmenu.py: MS_COCKPIT_DIR,
    // launcher.json "cockpitDir", or cockpit-tool\ in the source snapshot (tools/cockpit). Without it the row does nothing
    // (the game logs "[cam-cockpit] no ... not applied"); this step only warns. Runs after pcmenu, which rebuilds the folder.
    // The positions baked in: the shipped cockpit_positions.default.json (camera offsets only), with the player's own
    // play\cockpit_positions.json (the in-game F2 file) on top, vehicle by vehicle. The player's file is only read.
    cockpitDir() {
        for (const d of [process.env.MS_COCKPIT_DIR, this.cfg.cockpitDir, path.join(this.srcDir(), 'cockpit-tool')])
            if (d && fs.existsSync(path.join(d, 'make_cockpit_overlay.py'))) return d;
        return null;
    }
    async step_cockpit() {
        const dir = this.cockpitDir();
        if (!dir) { this.log('cockpit: no make_cockpit_overlay.py: the Camera setting has no camera files'); return; }
        const psarc = path.join(this.vfsRoot(), 'PS3_GAME', 'USRDIR', 'MS2.PSARC');
        if (!fs.existsSync(psarc)) { this.log(`cockpit: ${psarc} not found: skipped`); return; }
        const { env, python } = this.env();
        const out = path.join(this.dirs.play, 'pcmenu');
        const positions = this.cockpitPositions(dir);
        this.say('Making the camera files', `from your game's own camera lists (1.00)`, -1);
        const code = await run(python, ['-I', path.join(dir, 'make_cockpit_overlay.py'), '--psarc', psarc, '--out', out,
                                        ...(positions ? ['--positions', positions] : [])],
                               { env, cwd: dir, log: l => this.log('cockpit: ' + l) });
        if (code !== 0) { this.log(`cockpit: make_cockpit_overlay.py failed (${code}): the Camera setting has no camera files`); return; }
        this.mark('cockpit');
    }

    // the shipped defaults with the player's F2 file on top, written to work\cockpit_positions.json (the player's file
    // in play\ is never written here); null when neither is readable
    cockpitPositions(dir) {
        const FIELDS = ['x', 'dy', 'dz', 'pitch', 'yaw', 'focal'];
        const read = (file, what) => {
            if (!fs.existsSync(file)) return {};
            try {
                const j = JSON.parse(fs.readFileSync(file, 'utf8'));
                if (!j || typeof j !== 'object' || Array.isArray(j)) throw new Error('not an object');
                const outv = {};
                for (const [veh, v] of Object.entries(j)) {
                    if (!v || typeof v !== 'object') continue;
                    const e = {};
                    for (const k of FIELDS) if (typeof v[k] === 'number' && Number.isFinite(v[k])) e[k] = v[k];
                    if (Object.keys(e).length) outv[String(veh).toLowerCase()] = e;
                }
                return outv;
            } catch (e) { this.log(`cockpit: ${what} ${file} not read (${e.message})`); return {}; }
        };
        const merged = read(path.join(dir, 'cockpit_positions.default.json'), 'shipped positions');
        const mine = read(path.join(this.dirs.play, 'cockpit_positions.json'), 'your positions');
        for (const [veh, e] of Object.entries(mine)) merged[veh] = { ...(merged[veh] || {}), ...e };
        if (!Object.keys(merged).length) return null;
        const file = path.join(this.dirs.work, 'cockpit_positions.json');
        fs.mkdirSync(this.dirs.work, { recursive: true });
        fs.writeFileSync(file, JSON.stringify(merged, null, 1) + '\n');
        this.log(`cockpit: positions for ${Object.keys(merged).length} vehicle(s) (${Object.keys(mine).length} from your cockpit_positions.json)`);
        return file;
    }

}

module.exports = { Builder, ltoLinkerFlags, PLAY_ENV };
