"""Launcher: build and start the 1.00 game as it was raced (2026-11-21).
  game.json        stable options: MSPR_WWS_AOT=ON, PORT_SPU_AVX2, MSPR_PPU_INLINE_STORES, PORT_PPU_VMX_INLINE,
                   PORT_PPU_GATELESS_LOADS, PORT_PPU_LTO; the cbf1b1a1/0e193327 SPU images chained like the 1.03 build.
  manifest.json    wws_modules_100: where the 31 Wws job modules sit in the verified 1.00 ELF (offset, size, SHA-256
                   only), wws_names_100 (their names), and the verified output hashes of their lift (wws_reloc_v100,
                   byte-identical to the raced generated/spu_raw/wws_reloc_t81c).
  lift_motorstorm  cuts the modules from the player's 1.00 ELF and lifts them (lift_wws_reloc.py --ctor, the raced command).
  builder.js       MSPR_WWS_AOT_DIR for the stable build too; ThinLTO link flags when PORT_PPU_LTO is on; play.json
                   starts both builds on the Vulkan renderer with guest programs and async shader compile (the
                   backend is chosen during static initialisation, before the exe's own defaults apply, so these must
                   be in the process environment).
usage: py -3 patch_launcher_perf.py   (from anywhere; edits launcher/ in place, asserts each anchor once)"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
L = ROOT / 'launcher'


def rep(s, a, b, what):
    assert s.count(a) == 1, f'{what}: anchor not found once: {a[:70]!r}'
    return s.replace(a, b)


# ---- game.json
gp = L / 'game.json'
g = json.loads(gp.read_text(encoding='utf-8'))
st = g['builds']['stable']
opts = [o for o in st['options'] if not o.startswith('MSPR_WWS_AOT=')]
for o in ('MSPR_WWS_AOT=ON', 'PORT_SPU_AVX2=ON', 'MSPR_PPU_INLINE_STORES=ON', 'PORT_PPU_VMX_INLINE=ON',
          'PORT_PPU_GATELESS_LOADS=ON', 'PORT_PPU_LTO=ON'):
    if o not in opts:
        opts.insert(len(opts) - 1, o)   # before PORT_EXPECT_ENTRY_OPD
st['options'] = opts
extra = ['spu_cbf1b1a19a3f3eb95183a55e5b65c2de6eef9e025fed16eed2a0a8f1c563dd6f=--chain-chunks',
         'spu_0e193327f9cedb5cf569b211535978c6145d5f0d2d2e845d0f1e116f668d2dcd=--chain-chunks',
         'spu_cbf1b1a19a3f3eb95183a55e5b65c2de6eef9e025fed16eed2a0a8f1c563dd6f=--chain-indirect',
         'spu_0e193327f9cedb5cf569b211535978c6145d5f0d2d2e845d0f1e116f668d2dcd=--chain-indirect']
st['spu_lifter_image_args'] = extra + [a for a in st['spu_lifter_image_args'] if a not in extra]
gp.write_text(json.dumps(g, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

# ---- manifest.json
mp = L / 'pipeline' / 'manifest.json'
m = json.loads(mp.read_text(encoding='utf-8'))
offs = json.loads((ROOT / 'generated/analysis/ppu_spu_overlap60/wws_modules_v100_offsets.json').read_text())
m['wws_modules_100'] = offs
m['wws_names_100'] = json.loads((ROOT / 'generated/analysis/t37/modules/modules.json').read_text())
ref = ROOT / 'generated/spu_raw/wws_reloc_t81c'
m['outputs']['wws_reloc_v100'] = {str(p.relative_to(ref)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sorted(ref.rglob('*')) if p.is_file() and not p.name.endswith('.json')}
mp.write_text(json.dumps(m, indent=1) + '\n', encoding='utf-8')

# ---- lift_motorstorm.py
lp = L / 'pipeline' / 'lift_motorstorm.py'
s = lp.read_text(encoding='utf-8')
s = rep(s, "    # ---- 1.03 (unstable), only when its ELF is given: its PPU lift and its relocatable job modules\n",
        """    # ---- 1.00 relocatable Wws job modules (MSPR_WWS_AOT): cut from the player's 1.00 ELF, lifted as raced
    step('translating the SPU job modules of 1.00')
    mods100 = gen / 'wws_modules_v100'
    mods100.mkdir(parents=True, exist_ok=True)
    elf100 = args.elf_disc.read_bytes()
    for j in m['wws_modules_100']:
        b = elf100[j['file_off']:j['file_off'] + j['size']]
        if hashlib.sha256(b).hexdigest() != j['sha256']:
            raise SystemExit(f'job module {j["file"]} is not where the verified 1.00 ELF has it')
        (mods100 / j['file']).write_bytes(b)
    (mods100 / 'modules.json').write_text(json.dumps(m['wws_names_100'], indent=1))
    reloc100 = raw_dir / 'wws_reloc_v100'
    r = m['wws_reloc']
    run([py, tools / 'lift_wws_reloc.py', '--modules', mods100, '--out', reloc100, '--pm-image', str(r['pm_image']),
         '--codebase-word', r['codebase_word'], '--job-return', r['job_return'], '--names', mods100 / 'modules.json', '--ctor'])
    built['wws_reloc_v100'] = reloc100

    # ---- 1.03 (unstable), only when its ELF is given: its PPU lift and its relocatable job modules
""", 'lift')
lp.write_text(s, encoding='utf-8')

# ---- builder.js
bp = L / 'electron' / 'service' / 'builder.js'
s = bp.read_text(encoding='utf-8')
s = rep(s, "                ...(is103 ? [`-DMSPR_WWS_AOT_DIR=${path.join(gen, 'spu_raw', 'wws_reloc_v103')}`] : []),\n",
        "                ...(b.options.includes('MSPR_WWS_AOT=ON')\n"
        "                    ? [`-DMSPR_WWS_AOT_DIR=${path.join(gen, 'spu_raw', is103 ? 'wws_reloc_v103' : 'wws_reloc_v100')}`] : []),\n"
        "                // ThinLTO (PORT_PPU_LTO) links with lld-link's LTO jobs and a cache beside the build\n"
        "                ...(b.options.includes('PORT_PPU_LTO=ON')\n"
        "                    ? [`-DCMAKE_EXE_LINKER_FLAGS=/opt:lldltojobs=${this.jobs()} /lldltocache:${fwd(path.join(bld, 'lto-cache'))}`] : []),\n",
        'build defs')
s = rep(s, "                      elf: this.elfPath(100), env: {} },",
        "                      elf: this.elfPath(100), env: { ...PLAY_ENV } },", 'play stable')
s = rep(s, "env: { PS3_HDD0_ROOT: hdd0, PS3_VFS_OVERLAY: overlay } };",
        "env: { ...PLAY_ENV, PS3_HDD0_ROOT: hdd0, PS3_VFS_OVERLAY: overlay } };", 'play unstable')
s = rep(s, "const UNSTABLE_EXE = 'MotorStormPacificRiftRecomp-103.exe';\n",
        "const UNSTABLE_EXE = 'MotorStormPacificRiftRecomp-103.exe';\n"
        "// How both builds start (play.json): the Vulkan renderer with guest programs and async shader compile, as raced.\n"
        "// The exe picks its renderer during static initialisation, before its own defaults (k_defaults) apply, so these\n"
        "// have to be in the process environment.\n"
        "const PLAY_ENV = { RSX_BACKEND: 'vulkan', PS3RECOMP_VK_WINDOW: '1', PS3RECOMP_VK_GUEST_PROGRAMS: '1', RSX_SHADER_ASYNC: '1' };\n",
        'PLAY_ENV')
bp.write_text(s, encoding='utf-8')
print('launcher patched: game.json, manifest.json (%d modules, %d verified files), lift_motorstorm.py, builder.js'
      % (len(offs), len(m['outputs']['wws_reloc_v100'])))
