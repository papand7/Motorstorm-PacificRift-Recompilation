"""T82 private (from t79/tools/run_posix_fixture.py): build and run a POSIX-only SPURS fixture on Windows (same units as
tools/test_spurs_scheduler.py, plus win_link_stubs.c). Usage: py -3 -I run_posix_fixture.py tests/x.c"""
import os, subprocess, sys, tempfile
from pathlib import Path
here = Path(__file__).resolve().parent
t79 = here.parents[1] / "t79" / "tools"
r = here.parents[3] / os.environ.get("T82_TREE", "ps3recomp-t82")
units = ['spu_channels', 'spu_drain', 'spu_lockstep', 'spu_coherency', 'spu_workload', 'spurs_policy',
         'spurs_job', 'spu_tsp_weak', 'spu_vm_pagemap', 'spurs_policy_blob_weak', 'spu_interp']
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / 't.exe'
    subprocess.run([os.environ['CC'], '-std=gnu17', '-O1', '-UNDEBUG', '-include', str(t79 / "pthread_min.h"), '-I' + str(r / 'include'),
                    '-I' + str(r / 'runtime/spu'), '-I' + str(r / 'runtime/platform'), str(r / sys.argv[1]),
                    *[str(r / 'runtime/spu' / f'{u}.c') for u in units], str(r / 'runtime/platform/win32_compat.c'),
                    str(t79 / "win_link_stubs.c"), '-o', str(out)], check=True)
    p = subprocess.run([str(out)], timeout=60, capture_output=True, text=True)
    print('\n'.join(l for l in p.stdout.splitlines() if 'PASS' in l or 'FAIL' in l)); print(p.stderr[-1500:])
    print('exit', p.returncode); sys.exit(p.returncode)
