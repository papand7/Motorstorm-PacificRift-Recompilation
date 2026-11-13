// The install, step by step, each one kept when done (a stamp file) so Install can run again after a stop or a
// failure and only redo what is missing:
//   game      the player's disc (image or folder: its title, the helper for the files) and the 1.03 update folder
//             (its ms2patch.psarc, checked by SHA-256)
//   elf       the player's own decrypted EBOOT.elf for 1.00 and for 1.03, chosen by the player, checked by SHA-256
//             (game.json). Nothing is decrypted here and the files stay where the player keeps them.
//   files     the game's files copied out of a disc image (a folder is read where it is)
//   tools     clang, CMake, Ninja, Python, the Microsoft C++ libraries and Windows SDK, the Vulkan headers and
//             glslang/SPIRV-Tools sources: each pinned by SHA-256 (toolchain.json)
//   source    the launcher's source snapshot (the port, the ps3recomp runtime and the lifting recipe) unpacked
//   glslang   glslang + SPIRV-Tools built into tools\vulkan-sdk (the shader compiler the Vulkan renderer links)
//   lift      the PPU and SPU code translated from the decrypted ELFs (pipeline\lift_motorstorm.py)
//   build     CMake + Ninja: the game's exe
//   install   the exe into play\, play.json (the player's 1.03 EBOOT.elf it runs), motorstorm.cfg (paths)
'use strict';
const fs = require('fs');
const path = require('path');
const os = require('os');
const tools = require('./tools');
const disc = require('./disc');
const { run, killAll } = require('./proc');

const EXE = 'MotorStormPacificRiftRecomp.exe';

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
        this.updateInfo = null;
        this.elfInfo = { 100: null, 103: null };
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
            ['lift', 'Translate the game code'], ['build', 'Build the game'], ['install', 'Install'], ['pcmenu', 'Make the PC Settings pages'],
        ].map(([id, title]) => ({ id, title, done: this.done(id) }));
    }

    built() { return fs.existsSync(path.join(this.dirs.play, EXE)) && fs.existsSync(path.join(this.dirs.play, 'play.json')); }

    // a player's EBOOT.elf: its path, and whether its SHA-256 is the one game.json names for that release
    elfState(which) {
        const p = this.cfg['elf' + which];
        if (!p) return null;
        if (this.elfInfo[which]) return { path: p, ...this.elfInfo[which] };
        return { path: p, checking: true };
    }

    sendState(extra = {}) {
        this.emit({
            ev: 'state', busy: this.busy, stepId: this.stepId, steps: this.steps(), built: this.built(), agreed: !!this.cfg.agreed,
            disc: this.cfg.disc ? { path: this.cfg.disc, ...(this.discInfo || { checking: true }) } : null,
            update: this.updateInfo ? this.updateInfo : this.cfg.update ? { path: this.cfg.update, checking: true } : null,
            elf100: this.elfState(100), elf103: this.elfState(103),
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
        if (cmd.update !== undefined) { this.cfg.update = cmd.update; this.updateInfo = null; this.unmark('game'); }
        if (cmd.elf100 !== undefined) { this.cfg.elf100 = cmd.elf100; this.elfInfo[100] = null; this.unmark('elf'); }
        if (cmd.elf103 !== undefined) { this.cfg.elf103 = cmd.elf103; this.elfInfo[103] = null; this.unmark('elf', 'lift', 'build', 'install'); }
        if (cmd.agreed !== undefined) this.cfg.agreed = !!cmd.agreed;
        this.save();
        this.message = null;
        return this.scan('set');
    }

    // the 1.03 update folder the player chose (USRDIR\ms2patch.psarc is its data, checked by SHA-256)
    async checkUpdate() {
        const dir = this.cfg.update;
        if (!dir) return null;
        const u = this.game.update;
        const data = path.join(dir, 'USRDIR', u.data_file);
        if (!fs.existsSync(data)) return { path: dir, ok: false, error: `No USRDIR\\${u.data_file} in that folder (the 1.03 update's data).` };
        if (fs.statSync(data).size !== u.data.size) return { path: dir, ok: false, error: `That ${u.data_file} is not the ${u.version} update this launcher builds.` };
        if (await tools.sha256File(data) !== u.data.sha256) return { path: dir, ok: false, error: `That ${u.data_file} is not the ${u.version} update this launcher builds.` };
        return { path: dir, ok: true, version: u.version, data };
    }

    // a player's decrypted EBOOT.elf: its SHA-256 against game.json (the only check; nothing is read but the file)
    async checkElf(which) {
        const p = this.cfg['elf' + which];
        if (!p) return null;
        const want = which === 100 ? this.game.discs[0].eboot_elf : this.game.update.eboot_elf;
        const label = which === 100 ? '1.00 (the disc)' : `${this.game.update.version}`;
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
        try { this.updateInfo = await this.checkUpdate(); } catch (e) { this.updateInfo = { ok: false, error: e.message }; }
        for (const w of [100, 103]) {
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
            for (const s of ['game', 'elf', 'files', 'tools', 'source', 'glslang', 'lift', 'build', 'install', 'pcmenu']) {
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

    // ---- game: the disc (title, the files) and the 1.03 update folder (its data) are known and checked
    async step_game() {
        await this.scan();
        if (!this.discInfo || !this.discInfo.ok) throw new Error(this.discInfo ? this.discInfo.error : 'Choose your game disc first.');
        if (!this.updateInfo || !this.updateInfo.ok)
            throw new Error(this.updateInfo ? this.updateInfo.error : 'Choose the 1.03 update folder (the one with USRDIR\\ms2patch.psarc).');
        this.mark('game', `${this.discInfo.release}\n${this.game.update.version}`);
    }

    // the player's own decrypted EBOOT.elf files: used where they are, never copied, decrypted or stored by the launcher
    elfPath(which) { return this.cfg['elf' + (which === 'disc' ? 100 : 103)]; }

    // ---- elf: both files chosen and checked by SHA-256
    async step_elf() {
        // copies an earlier launcher made with RPCS3 (its work\decrypted and work\self) are removed: nothing decrypted is kept
        for (const d of ['decrypted', 'self']) fs.rmSync(path.join(this.dirs.work, d), { recursive: true, force: true });
        for (const w of [100, 103]) {
            if (!this.cfg['elf' + w]) throw new Error(w === 100
                ? 'Choose your decrypted EBOOT.elf of 1.00 (the disc\'s): it holds the Wws_Job module the build needs.'
                : `Choose your decrypted EBOOT.elf of ${this.game.update.version} (the update's).`);
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
        // the update's data file (the patch archive) beside the game's own, where the 1.03 EBOOT looks for it
        await this.placeUpdateData();
        this.mark('files');
    }

    // the update as the PS3 keeps it, /dev_hdd0/game/<title id>: its PARAM.SFO and its data (ms2patch.psarc). The
    // game reads the patch archive through PS3_VFS_OVERLAY. The update's EBOOT.BIN is not copied (it is not used).
    updateDir() { return path.join(this.root, 'hdd0', 'game', this.discInfo.titleId); }
    async placeUpdateData() {
        const from = this.cfg.update;
        const to = this.updateDir();
        const files = [];
        for (const n of fs.readdirSync(from)) if (fs.statSync(path.join(from, n)).isFile()) files.push(n);
        for (const n of fs.readdirSync(path.join(from, 'USRDIR'))) if (!/^EBOOT\.BIN$/i.test(n)) files.push(path.join('USRDIR', n));
        for (const rel of files) {
            const a = path.join(from, rel), b = path.join(to, rel);
            if (!fs.statSync(a).isFile()) continue;
            fs.mkdirSync(path.dirname(b), { recursive: true });
            if (fs.existsSync(b) && fs.statSync(b).size === fs.statSync(a).size) continue;
            this.say('Copying the update\'s data', rel, -1);
            // a hard link when on the same drive (no second copy of 600 MB), else a copy
            try { fs.rmSync(b, { force: true }); fs.linkSync(a, b); }
            catch { await fs.promises.copyFile(a, b); }
        }
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
        const have = path.join(this.srcDir(), 'SOURCE.json');
        if (fs.existsSync(have) && fs.readFileSync(have, 'utf8') === want) return this.mark('source');
        // a changed source: what was made from the old one is made again
        this.unmark('glslang', 'lift', 'build', 'install');
        fs.rmSync(this.srcDir(), { recursive: true, force: true });
        this.say('Unpacking the source', '', -1);
        await tools.unpack(tar, this.srcDir(), { log: l => this.log(l) });
        fs.writeFileSync(have, want);
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
        code = await run(cmake, ['--build', bld, '--target', 'install', '--parallel', String(this.jobs())], { env, log,
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
        const byMem = Math.max(1, Math.floor(os.totalmem() / (4 * 1024 ** 3)));
        return Math.max(1, Math.min(os.cpus().length - 1, byMem));
    }

    // ---- lift: pipeline\lift_motorstorm.py (in the source snapshot) from the decrypted ELFs into work\src\generated
    async step_lift() {
        if (this.done('lift')) return;
        const { env, python } = this.env();
        if (!this.elfPath('disc') || !this.elfPath('update')) throw new Error('Choose your decrypted EBOOT.elf files first.');
        const script = path.join(this.srcDir(), 'pipeline', 'lift_motorstorm.py');
        const args = [script, '--root', this.srcDir(), '--elf-disc', this.elfPath('disc'), '--elf-103', this.elfPath('update'),
                      '--jobs', String(Math.max(1, Math.min(os.cpus().length - 1, Math.floor(os.totalmem() / (3 * 1024 ** 3)))))];
        this.say('Translating the game code', 'PPU and SPU, about 10 minutes', -1);
        const code = await run(python, args, { env, cwd: this.srcDir(), log: l => this.log('lift: ' + l),
            onLine: l => { const m = /^\[step\] (.*)$/.exec(l); if (m) this.say('Translating the game code', m[1], -1);
                           const p = /lifted (\d+)\/(\d+) functions/.exec(l); if (p) this.say('Translating the game code', `PPU: ${p[1]} of ${p[2]} functions`, p[1] / p[2]); } });
        if (code !== 0) throw new Error('Translating the game code failed, see the log.');
        this.unmark('build');
        this.mark('lift');
    }

    // ---- build: the port with CMake and Ninja (the options of build_vkgame_103.cmd)
    buildDir() { return path.join(this.dirs.work, 'build'); }
    async step_build() {
        const { env, llvmBin, cmake, ninja, python } = this.env();
        const src = this.srcDir(), gen = path.join(src, 'generated'), bld = this.buildDir();
        const cc = path.join(llvmBin, 'clang-cl.exe');
        const fwd = p => p.replace(/\\/g, '/');
        const log = l => this.log(l);
        {   // configured every time (cheap; incremental): the cache must hold the current paths (the player's ELFs, the tools)
            this.say('Preparing the build', 'CMake', -1);
            const b = this.game.build;
            const defs = [
                `-DCMAKE_MAKE_PROGRAM=${ninja}`, '-DCMAKE_BUILD_TYPE=Release', `-DCMAKE_C_COMPILER=${cc}`, `-DCMAKE_CXX_COMPILER=${cc}`,
                '-DCMAKE_LINKER_TYPE=LLD', `-DPython3_EXECUTABLE=${python}`,
                `-DPS3RECOMP_DIR=${path.join(src, 'ps3recomp')}`, `-DRECOMP_DIR=${path.join(gen, 'ppu-v103')}`,
                `-DSPU_DIR=${path.join(gen, 'spu')}`, `-DPORT_SPU_INPUTS=${this.elfPath('update')}`,
                `-DMSPR_WWS_AOT_DIR=${path.join(gen, 'spu_raw', 'wws_reloc_v103')}`,
                `-DPS3RECOMP_VULKAN_INCLUDE_DIR=${path.join(this.dirs.tools, 'vulkan-sdk', 'include')}`,
                `-DPS3RECOMP_VULKAN_SDK=${fwd(path.join(this.dirs.tools, 'vulkan-sdk'))}`,
                `-DPS3RECOMP_SPU_LIFTER_IMAGE_ARGS=${b.spu_lifter_image_args.join(';')}`,
                ...b.options.map(o => `-D${o}`),
            ];
            const code = await run(cmake, ['-S', path.join(src, 'port-vkgame'), '-B', bld, '-G', 'Ninja', ...defs], { env, log });
            if (code !== 0) { fs.rmSync(path.join(bld, 'CMakeCache.txt'), { force: true }); throw new Error('Preparing the build failed, see the log.'); }
        }
        this.say('Building MotorStorm: Pacific Rift', 'the first build takes 30 to 90 minutes', 0);
        const code = await run(cmake, ['--build', bld, '--parallel', String(this.jobs())], { env, log,
            onLine: l => { const m = /^\[(\d+)\/(\d+)\]/.exec(l); if (m) this.say('Building MotorStorm: Pacific Rift', `${m[1]} of ${m[2]} steps`, m[1] / m[2]); } });
        if (code !== 0) throw new Error(this.abort.signal.aborted ? 'cancelled' : 'The build failed, see the log.');
        if (!fs.existsSync(path.join(bld, EXE))) throw new Error(`The build made no ${EXE}.`);
        this.mark('build');
    }

    // ---- install: the exe and its DLLs into play\, the player's 1.03 EBOOT.elf named in play.json
    async step_install() {
        const play = this.dirs.play, bld = this.buildDir();
        fs.mkdirSync(play, { recursive: true });
        for (const n of fs.readdirSync(bld)) {
            if (n === EXE || /\.dll$/i.test(n)) {
                try { fs.copyFileSync(path.join(bld, n), path.join(play, n)); }
                catch (e) { throw new Error(`Cannot copy ${n} (is the game still running?)`); }
            }
        }
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
        const info = { elf: this.elfPath('update'), elf_disc: this.elfPath('disc'), vfs_root: vfs, hdd0: path.join(this.root, 'hdd0'),
                       overlay: path.join(this.updateDir(), 'USRDIR'), release: this.discInfo.release,
                       update: this.game.update.version, built: new Date().toISOString() };
        fs.writeFileSync(path.join(play, 'play.json'), JSON.stringify(info, null, 2));
        // motorstorm.cfg: the game's file root, its hdd0 and the update's data (as the developer's 1.03 runs set
        // them); the player's own settings are kept
        const cfg = path.join(play, 'motorstorm.cfg');
        const ours = { PS3_VFS_ROOT: vfs, PS3_HDD0_ROOT: info.hdd0, PS3_VFS_OVERLAY: info.overlay };
        let lines = [];
        try { lines = fs.readFileSync(cfg, 'utf8').split(/\r?\n/).filter(l => l && !Object.keys(ours).some(k => l.startsWith(k + '='))); } catch { /* new */ }
        if (!lines.length) lines.push('# MotorStorm: Pacific Rift settings (written by the launcher; read by the game at start-up)');
        for (const [k, v] of Object.entries(ours)) lines.push(`${k}=${v}`);
        fs.writeFileSync(cfg, lines.join('\n') + '\n');
        this.log(`installed in ${play}`);
        this.mark('install');
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
        this.say('Making the PC Settings pages', 'from your game\'s Options pages', -1);
        const code = await run(python, [path.join(dir, 'make_pcmenu.py'), '--psarc', psarc, '--out', out,
                                        '--port', path.join(this.srcDir(), 'port-vkgame')], { env, cwd: dir, log: l => this.log('pcmenu: ' + l) });
        if (code !== 0) { this.log(`pcmenu: make_pcmenu.py failed (${code}): the game keeps its retail Options page`); return; }
        this.mark('pcmenu');
    }
}

module.exports = { Builder };
