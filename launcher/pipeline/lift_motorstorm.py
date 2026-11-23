#!/usr/bin/env python3
"""Translate MotorStorm: Pacific Rift into the C/C++ the port builds, on the player's PC.

Run by the launcher's install service (the launcher's own Python), from the unpacked source snapshot:

    python pipeline/lift_motorstorm.py --root <src> --elf-disc <1.00 EBOOT.elf> [--jobs N]

<src> holds ps3recomp/ (the runtime and its tools), port-vkgame/ and pipeline/. Outputs go under <src>/generated/:

  generated/meta/                      EBOOT_100.* (find_functions.py, gen_imports.py)
  generated/ppu-100/                   the 1.00 PPU lift (ppu_lifter.py --trace-hooks), then the port's hook patches
                                       (mspr_patch_lifted.py and the rest of PATCHES_100 below)
  generated/spu_raw/wws_job_pm/        the Wws_Job policy module, cut from the 1.00 ELF at 0x00FFCC80 and lifted
  generated/spu_raw/wws_reloc_v100/    the relocatable Wws job modules of the 1.00 ELF (lift_wws_reloc.py --ctor)

pipeline/manifest.json carries the SHA-256 of every input and of every verified output (hashes, offsets and sizes only,
no game bytes), so a player's result is checked against the verified translation. --no-verify skips the output checks
(a developer changing the lifter). --write-manifest records this run's outputs (developer, on private inputs).
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# the 1.00 lift's hook patches after mspr_patch_lifted.py (launcher copies of the generated/analysis tools the
# developer builds use; the port's main.cpp / pc_menu.cpp define the functions they call):
PATCHES_100 = [
    'slice_patch_lifted.py',          # the main thread's per-frame task slice (MSPR_SLICE_MS)
    'cam_patch_lifted.py',            # camera rate and shake (MSPR_CAM, above 30 FPS)
    'dist_patch_lifted.py',           # draw, LOD and shadow distances (the lod setting)
    'unlockall_lifted.py',            # Cheats: unlockvehicles, unlocktracks
    'pcmenu_lifted.py',               # the in-game PC Settings pages (pcmenu_lookup, pcmenu_page_load)
    'cockpit_tune_patch_ppucc.py',    # cockpit camera live tuning and saved positions (after cam_patch_lifted.py)
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()


def step(text):
    print(f'[step] {text}', flush=True)


def run(args, **kw):
    print('$ ' + ' '.join(str(a) for a in args), flush=True)
    r = subprocess.run([str(a) for a in args], **kw)
    if r.returncode:
        raise SystemExit(f'failed ({r.returncode}): {args[1] if len(args) > 1 else args[0]}')


def fnv1a(data):
    v = 1469598103934665603
    for b in data:
        v = ((v ^ b) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return v


def elf_offset(data, ea, size):
    import struct
    if data[:6] != b'\x7fELF\x02\x02':
        raise SystemExit('not a big-endian ELF64')
    phoff = struct.unpack_from('>Q', data, 32)[0]
    phentsize, phnum = struct.unpack_from('>HH', data, 54)
    for i in range(phnum):
        kind, _, off, vaddr, _, filesz, _, _ = struct.unpack_from('>IIQQQQQQ', data, phoff + i * phentsize)
        if kind == 1 and vaddr <= ea and ea + size <= vaddr + filesz:
            return off + ea - vaddr
    raise SystemExit(f'no PT_LOAD holds {ea:#x}+{size:#x}')


def check_tree(out_dir, want, what, verify):
    """every file the manifest names, with its SHA-256"""
    bad = []
    for rel, digest in sorted(want.items()):
        p = out_dir / rel
        if not p.exists():
            bad.append(f'{rel}: missing')
        elif sha256(p) != digest:
            bad.append(f'{rel}: differs')
    if bad:
        msg = f'{what}: {len(bad)} of {len(want)} files differ from the verified translation: ' + '; '.join(bad[:5])
        if verify:
            raise SystemExit(msg)
        print('warning: ' + msg, flush=True)
    else:
        print(f'{what}: all {len(want)} files match the verified translation', flush=True)


def lift_ppu(tools, py, elf, tag, out, meta, jobs):
    """functions and imports from the ELF, the PPU lift, the MSPR patch sites (the output's name picks the patch set).

    1.00 uses ppu_loader.py's lists: they reproduce the list the verified 1.00 translation (generated/ppu-hooked-staging)
    was lifted from, byte for byte, and the patch anchors need its function boundaries."""
    if tag == '100':
        ld = meta / 'loader100'
        ld.mkdir(parents=True, exist_ok=True)
        step('finding the 1.00 PPU functions (ppu_loader)')
        run([py, tools / 'ppu_loader.py', elf, '-o', ld])
        stem = Path(elf).stem
        fn, im = ld / f'{stem}.functions.json', ld / f'{stem}.imports.json'
    else:
        fn, im = meta / f'EBOOT_{tag}.functions.json', meta / f'EBOOT_{tag}.imports.json'
        step(f'finding the {tag} PPU functions')
        run([py, tools / 'find_functions.py', elf, '--json', '-o', fn])
        run([py, tools / 'gen_imports.py', elf, '-o', im])
    step(f'translating the {tag} PPU code (about 5 minutes)')
    run([py, tools / 'ppu_lifter.py', elf, '--functions', fn, '--hle-stubs', im, '--output', out,
         '--jobs', str(jobs), '--trace-hooks'])
    step(f'applying the {tag} PC patches (MSPR_PATCH switches)')
    run([py, HERE / 'mspr_patch_lifted.py', out])
    if 'v103' not in out.name:   # 1.00: the port's other hooks, in this order (each asserts its own counts)
        step(f'applying the {tag} PC hooks (settings pages, cheats, camera, detail, cockpit)')
        for script in PATCHES_100:
            run([py, HERE / script, out])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', required=True, type=Path)
    ap.add_argument('--elf-disc', required=True, type=Path, help='the decrypted 1.00 EBOOT.elf')
    ap.add_argument('--jobs', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument('--no-verify', action='store_true')
    ap.add_argument('--write-manifest', action='store_true', help="developer: record this run's outputs in manifest.json")
    args = ap.parse_args()
    m = json.loads((HERE / 'manifest.json').read_text())
    root = args.root.resolve()
    tools = root / 'ps3recomp' / 'tools'
    gen = root / 'generated'
    py = sys.executable
    verify = not args.no_verify and not args.write_manifest
    t0 = time.time()

    step('checking the decrypted ELF')
    got = sha256(args.elf_disc)
    if got != m['elf_disc_sha256']:
        raise SystemExit(f'the 1.00 EBOOT.elf: SHA-256 {got}, expected {m["elf_disc_sha256"]}')

    meta = gen / 'meta'
    meta.mkdir(parents=True, exist_ok=True)
    built = {}   # output key -> its folder

    # ---- 1.00 (primary): PPU lift, and the Wws_Job policy module (both builds take that module from 1.00)
    p100 = gen / 'ppu-100'
    lift_ppu(tools, py, args.elf_disc, '100', p100, meta, args.jobs)
    built['ppu-100'] = p100

    step('translating the SPU policy module')
    raw_dir = gen / 'spu_raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    pm = m['wws_pm']
    data = args.elf_disc.read_bytes()
    off = elf_offset(data, int(pm['ea'], 16), pm['size'])
    raw = data[off:off + pm['size']]
    if f'{fnv1a(raw):016X}' != pm['fnv64'] or hashlib.sha256(raw).hexdigest() != pm['sha256']:
        raise SystemExit('the Wws_Job policy module is not where the verified 1.00 ELF has it')
    sys.path.insert(0, str(tools))
    from wrap_spu_elf import wrap
    base = int(pm['spu_base'], 16)
    (raw_dir / 'wws_job_pm.elf').write_bytes(wrap(raw, base=base, entry=base))
    run([py, tools / 'spu_lifter.py', '--auto-functions', raw_dir / 'wws_job_pm.elf', '--output', raw_dir / 'wws_job_pm',
         '--symbol-prefix', 'mspr_wws_pm_', '--return-entries', '--report', raw_dir / 'wws_job_pm_lift.json'])
    rep = json.loads((raw_dir / 'wws_job_pm_lift.json').read_text())
    if rep.get('unsupported'):
        raise SystemExit(f'unsupported Wws_Job SPU instructions: {rep["unsupported"]}')
    for name, old, new in (('spu_recomp.c', '../../runtime/spu/spu_helpers.h', 'spu_helpers.h'),
                           ('spu_recomp.h', '../../runtime/spu/spu_context.h', 'spu_context.h')):
        p = raw_dir / 'wws_job_pm' / name
        b = p.read_bytes()
        if b.count(old.encode()) != 1:
            raise SystemExit(f'unexpected include in {p}')
        p.write_bytes(b.replace(old.encode(), new.encode()))
    built['wws_job_pm'] = raw_dir / 'wws_job_pm'

    # ---- 1.00 relocatable Wws job modules (MSPR_WWS_AOT): cut from the player's 1.00 ELF, lifted as raced
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

    # ---- the outputs against the verified translation
    step('checking the translation')
    if args.write_manifest:
        ld = meta / 'loader100'
        m['functions_100_sha256'] = sha256(ld / f'{args.elf_disc.stem}.functions.json')
        m['imports_100_sha256'] = sha256(ld / f'{args.elf_disc.stem}.imports.json')
        for key, d in built.items():
            m['outputs'][key] = {str(p.relative_to(d)).replace('\\', '/'): sha256(p)
                                 for p in sorted(d.rglob('*')) if p.is_file() and not p.name.endswith('.json')}
        (HERE / 'manifest.json').write_text(json.dumps(m, indent=1) + '\n')
        print('manifest.json written')
    else:
        for key, d in built.items():
            if key in m['outputs']:
                check_tree(d, m['outputs'][key], key, verify)
            else:
                print(f'note: no verified manifest entry for {key} yet (developer: --write-manifest)', flush=True)
    print(f'done in {(time.time() - t0) / 60:.1f} minutes', flush=True)


if __name__ == '__main__':
    main()
