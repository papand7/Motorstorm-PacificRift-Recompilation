#!/usr/bin/env python3
"""Translate MotorStorm: Pacific Rift 1.03 into the C/C++ the port builds, on the player's PC.

Run by the launcher's install service (the launcher's own Python), from the unpacked source snapshot:

    python pipeline/lift_motorstorm.py --root <src> --elf-disc <disc EBOOT.elf> --elf-103 <1.03 EBOOT.elf> [--jobs N]

<src> holds ps3recomp/ (the runtime and its tools), port-vkgame/ and pipeline/. Everything this writes goes under
<src>/generated/, the layout port-vkgame/CMakeLists.txt reads (../generated/spu_raw/wws_job_pm):

  generated/meta/          EBOOT_103.functions.json, EBOOT_103.imports.json (find_functions.py, gen_imports.py)
  generated/ppu-v103/      the PPU lift (ppu_lifter.py --trace-hooks), then pipeline/mspr_patch_lifted.py
  generated/spu_raw/wws_job_pm/      the Wws_Job policy module, cut from the disc ELF and lifted (spu_lifter.py)
  generated/spu_raw/wws_reloc_v103/  the 31 relocatable Wws job modules of the 1.03 ELF (lift_wws_reloc.py --ctor)

The same commands produced the private reference trees (generated/ppu-v103-staging, generated/spu_raw/...) on the
developer's PC; pipeline/manifest.json carries the SHA-256 of every input and output (hashes, offsets and sizes only,
no game bytes), so a player's result is checked against the verified translation. --no-verify skips the output
checks (a developer changing the lifter).

The game's bytes are read from the player's own decrypted ELFs and the outputs stay on the player's PC.
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', required=True, type=Path)
    ap.add_argument('--elf-disc', required=True, type=Path)
    ap.add_argument('--elf-103', required=True, type=Path)
    ap.add_argument('--jobs', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument('--no-verify', action='store_true')
    ap.add_argument('--write-manifest', action='store_true', help='developer: record this run\'s outputs in manifest.json')
    args = ap.parse_args()
    m = json.loads((HERE / 'manifest.json').read_text())
    root = args.root.resolve()
    tools = root / 'ps3recomp' / 'tools'
    gen = root / 'generated'
    py = sys.executable
    verify = not args.no_verify and not args.write_manifest
    t0 = time.time()

    step('checking the decrypted ELFs')
    for p, want in ((args.elf_disc, m['elf_disc_sha256']), (args.elf_103, m['elf_103_sha256'])):
        got = sha256(p)
        if got != want:
            raise SystemExit(f'{p}: SHA-256 {got}, expected {want}')

    # ---- PPU: functions and imports, then the lift
    meta = gen / 'meta'
    meta.mkdir(parents=True, exist_ok=True)
    fn, im = meta / 'EBOOT_103.functions.json', meta / 'EBOOT_103.imports.json'
    step('finding the PPU functions')
    run([py, tools / 'find_functions.py', args.elf_103, '--json', '-o', fn])
    run([py, tools / 'gen_imports.py', args.elf_103, '-o', im])
    for p, key in ((fn, 'functions_sha256'), (im, 'imports_sha256')):
        if args.write_manifest:
            m[key] = sha256(p)
        elif sha256(p) != m[key]:
            msg = f'{p.name} differs from the verified one'
            if verify:
                raise SystemExit(msg)
            print('warning: ' + msg)

    ppu = gen / 'ppu-v103'   # (the name matters: mspr_patch_lifted.py picks its 1.03 edits by "v103")
    step('translating the PPU code (about 5 minutes)')
    run([py, tools / 'ppu_lifter.py', args.elf_103, '--functions', fn, '--hle-stubs', im, '--output', ppu,
         '--jobs', str(args.jobs), '--trace-hooks'])
    step('applying the PC patches (MSPR_PATCH switches)')
    run([py, HERE / 'mspr_patch_lifted.py', ppu])

    # ---- SPU: the Wws_Job policy module (from the disc ELF, as tools/prepare_wws_pm.py does)
    step('translating the SPU policy module')
    raw_dir = gen / 'spu_raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    pm = m['wws_pm']
    data = args.elf_disc.read_bytes()
    off = elf_offset(data, int(pm['ea'], 16), pm['size'])
    raw = data[off:off + pm['size']]
    if f'{fnv1a(raw):016X}' != pm['fnv64'] or hashlib.sha256(raw).hexdigest() != pm['sha256']:
        raise SystemExit('the Wws_Job policy module is not where the verified ELF has it')
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

    # ---- SPU: the relocatable Wws job modules of the 1.03 ELF
    step('translating the SPU job modules')
    mods = gen / 'wws_modules_v103'
    mods.mkdir(parents=True, exist_ok=True)
    elf = args.elf_103.read_bytes()
    for j in m['wws_modules']:
        b = elf[j['file_off']:j['file_off'] + j['size']]
        if hashlib.sha256(b).hexdigest() != j['sha256']:
            raise SystemExit(f'job module {j["file"]} is not where the verified ELF has it')
        (mods / j['file']).write_bytes(b)
    reloc = raw_dir / 'wws_reloc_v103'
    r = m['wws_reloc']
    run([py, tools / 'lift_wws_reloc.py', '--modules', mods, '--out', reloc, '--pm-image', str(r['pm_image']),
         '--codebase-word', r['codebase_word'], '--job-return', r['job_return'], '--ctor'])

    # ---- the outputs against the verified translation
    step('checking the translation')
    outputs = {'ppu-v103': ppu, 'wws_job_pm': raw_dir / 'wws_job_pm', 'wws_reloc_v103': reloc}
    if args.write_manifest:
        for key, d in outputs.items():
            m['outputs'][key] = {str(p.relative_to(d)).replace('\\', '/'): sha256(p)
                                 for p in sorted(d.rglob('*')) if p.is_file() and not p.name.endswith('.json')}
        (HERE / 'manifest.json').write_text(json.dumps(m, indent=1) + '\n')
        print('manifest.json written')
    else:
        for key, d in outputs.items():
            check_tree(d, m['outputs'][key], key, verify)
    print(f'done in {(time.time() - t0) / 60:.1f} minutes', flush=True)


if __name__ == '__main__':
    main()
