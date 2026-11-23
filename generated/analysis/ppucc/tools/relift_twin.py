#!/usr/bin/env python3
"""Private (ppucc): a NEW lifted tree from generated/ppu-v100-twin with the lifter's --fast-mem / --vmx-locals
passes applied to every emitted function (the same functions the lifter calls: ps3recomp-opt
tools/ppu_fastmem.py, ppu_vmx_locals.py; they rewrite emitted function text, so applying them to the twin's
emitted, already patched (mspr/slice) functions is what a relift with the flags followed by the same patch
scripts gives). The twin is read only; other files are copied unchanged.
  relift_twin.py <out dir> --fast-mem frame --vmx-locals auto
"""
import argparse, json, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tu_compile  # noqa: E402

STG = tu_compile.STG


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--fast-mem', choices=tu_compile.PFM.MODES)
    ap.add_argument('--vmx-locals', choices=('all', 'auto'))
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        sys.exit(f'{out} exists: never overwrite a lift')
    out.mkdir(parents=True)
    st = {}
    for f in sorted(STG.iterdir()):
        if f.is_file() and f.name.startswith('ppu_recomp_') and f.suffix == '.cpp':
            t = f.read_text(encoding='latin-1')
            if '\nvoid func_' in t:
                t = tu_compile.rewrite(t, a.fast_mem, a.vmx_locals, st)
            (out / f.name).write_text(t, encoding='latin-1', newline='')
        elif f.is_file():
            shutil.copy2(f, out / f.name)
        else:
            shutil.copytree(f, out / f.name)
    (out / 'PPUCC_RELIFT.json').write_text(json.dumps({'from': str(STG), 'fast_mem': a.fast_mem,
                                                        'vmx_locals': a.vmx_locals, 'stats': st}, indent=1))
    print(st)


if __name__ == '__main__':
    main()
