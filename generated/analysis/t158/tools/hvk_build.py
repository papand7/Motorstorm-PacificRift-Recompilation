"""T158: build the function-level harness for one Havok image (run under tools/env.cmd).

  py -3 hvk_build.py <ps3recomp tree> <hvk lift dir> <img> <out dir> [extra cflags...]
Lifted TUs get the production flags of the race build (clang, -O2 -msse4.1 -fno-strict-aliasing
-fwrapv, SPU_USE_DISPATCH_MT); the runtime is the real SPU runtime (as tests/test_spu_task_stats.py)
with the interpreter compiled into hvk_ref.c."""
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TREE, LIFT, IMG, OUT = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3], Path(sys.argv[4]).resolve()
EXTRA = sys.argv[5:]
HERE = Path(__file__).resolve().parent / 'hvkdiff'
RUNTIME = ["runtime/spu/spu_channels.c", "runtime/spu/spu_drain.c", "runtime/spu/spu_lockstep.c",
           "runtime/spu/spu_coherency.c", "runtime/spu/spu_workload.c", "runtime/spu/spurs_policy.c",
           "runtime/spu/spurs_job.c", "runtime/spu/spu_tsp_weak.c", "runtime/spu/spu_vm_pagemap.c",
           "runtime/spu/spurs_policy_blob_weak.c", "runtime/spu/spu_dispatch_mt.c",
           "runtime/platform/win32_compat.c"]
SHIM = Path(__file__).resolve().parents[4] / 'scratch' / 't17' / 'posix_shim.h'
base = ['clang', '-std=gnu17', '-O2', '-msse4.1', '-fno-strict-aliasing', '-fwrapv', '-w',
        '-DSPU_USE_DISPATCH_MT', '-D_CRT_SECURE_NO_WARNINGS', '-include', str(SHIM),
        '-I' + str(HERE), '-I' + str(TREE / 'include'), '-I' + str(TREE / 'runtime/spu'),
        '-I' + str(TREE / 'runtime/platform')] + EXTRA
OUT.mkdir(parents=True, exist_ok=True)
srcs = [(HERE / 'hvkdiff.c', 'hvkdiff'), (HERE / 'hvk_ref.c', 'hvk_ref'), (LIFT / IMG / 'table.c', 'table'),
        (LIFT / IMG / 'c0' / 'spu_recomp.c', 'c0'), (LIFT / IMG / 'c1' / 'spu_recomp.c', 'c1')]
srcs += [(TREE / s, 'rt_' + Path(s).stem) for s in RUNTIME]


def cc(item):
    src, stem = item
    o = OUT / (stem + '.o')
    r = subprocess.run(base + ['-c', str(src), '-o', str(o)], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f'compile failed: {src}\n{r.stderr[-3000:]}')
    return str(o)


with ThreadPoolExecutor(6) as ex:
    objs = list(ex.map(cc, srcs))
exe = OUT / f'hvkdiff_{IMG}.exe'
link = ['-fuse-ld=lld', '-g', '-Wl,/debug'] if '-g' in EXTRA else []
r = subprocess.run(['clang'] + objs + link + ['-o', str(exe)], capture_output=True, text=True)
if r.returncode:
    sys.exit('link failed\n' + r.stderr[-4000:])
print('built', exe)
