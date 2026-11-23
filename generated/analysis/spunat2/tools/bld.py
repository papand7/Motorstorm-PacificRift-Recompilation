"""spunat2: build the fnx harness for one mkpair output directory.

  python bld.py <pair dir> <exe> [--pgo-gen] [--pgo-use <profdata>] [--cflag X ...]

Flags as the port compiles the lifted SPU sources (PORT_SPU_AVX2): clang -O2 -msse4.1 -mavx2
-fno-strict-aliasing -fwrapv -DSPU_USE_DISPATCH_MT. The lifted baseline and the natives are in the
same executable, built with the same flags and (with --pgo-use) the same profile."""
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TREE = ROOT / 'ps3recomp-spunat2'
CLANG = ROOT / 'build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin/clang.exe'
HAR = HERE.parent / 'harness'
RUNTIME = ["runtime/spu/spu_channels.c", "runtime/spu/spu_drain.c", "runtime/spu/spu_lockstep.c",
           "runtime/spu/spu_coherency.c", "runtime/spu/spu_workload.c", "runtime/spu/spurs_policy.c",
           "runtime/spu/spurs_job.c", "runtime/spu/spu_tsp_weak.c", "runtime/spu/spu_vm_pagemap.c",
           "runtime/spu/spurs_policy_blob_weak.c", "runtime/spu/spu_dispatch_mt.c",
           "runtime/platform/win32_compat.c"]

pair, exe = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
a = sys.argv[3:]
extra, pgo = [], []
i = 0
while i < len(a):
    if a[i] == '--pgo-gen':
        pgo = ['-fprofile-instr-generate']
    elif a[i] == '--pgo-use':
        pgo = ['-fprofile-instr-use=' + str(Path(a[i + 1]).resolve()), '-Wno-profile-instr-unprofiled',
               '-Wno-profile-instr-out-of-date']
        i += 1
    elif a[i] == '--cflag':
        extra.append(a[i + 1]); i += 1
    i += 1
shim = HAR / 'shim.h'
if not shim.exists():
    shim.write_text('#include <stdlib.h>\n#include <string.h>\n#ifndef strdup\n#define strdup _strdup\n#endif\n')
base = [str(CLANG), '-std=gnu17', '-O2', '-msse4.1', '-mavx2', '-fno-strict-aliasing', '-fwrapv', '-w', '-g',
        '-gcodeview', '-DSPU_USE_DISPATCH_MT', '-D_CRT_SECURE_NO_WARNINGS', '-include', str(shim),
        '-I' + str(HAR), '-I' + str(TREE / 'include'), '-I' + str(TREE / 'runtime/spu'),
        '-I' + str(TREE / 'runtime/platform'), '-I' + str(TREE / 'runtime')] + extra
od = exe.parent / (exe.stem + '_obj')
od.mkdir(parents=True, exist_ok=True)
srcs = [(HAR / 'fnx.c', 'fnx', []), (HAR / 'fnx_ref.c', 'fnx_ref', []), (pair / 'table.c', 'table', []),
        (pair / 'c0' / 'spu_recomp.c', 'c0', pgo), (pair / 'c1' / 'spu_recomp.c', 'c1', pgo)]
srcs += [(TREE / s, 'rt_' + Path(s).stem, pgo) for s in RUNTIME]


def cc(item):
    src, stem, fl = item
    o = od / (stem + '.o')
    r = subprocess.run(base + fl + ['-c', str(src), '-o', str(o)], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f'compile failed: {src}\n{r.stderr[-4000:]}')
    return str(o)


with ThreadPoolExecutor(6) as ex:
    objs = list(ex.map(cc, srcs))
link = [str(CLANG)] + objs + ['-fuse-ld=lld', '-g', '-Wl,/debug'] + (['-fprofile-instr-generate'] if pgo[:1] == ['-fprofile-instr-generate'] else []) + ['-o', str(exe)]
r = subprocess.run(link, capture_output=True, text=True)
if r.returncode:
    sys.exit('link failed\n' + r.stderr[-4000:])
print('built', exe)
