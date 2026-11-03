"""T123B Phase 7: build tests/test_spurs_event_sched.c once (ps3recomp-t123b) and run the
scheduler arms in balanced order (ABC then CBA per seed), OBSERVER=0, with
PS3_SPURS_SCHED_STATS=1000 so the coordinator prints wakes/passes per window.
  A periodic, B T123 kick wake, C event (default 4 ms fallback); each with the legacy
  admission and with PS3_SPURS_READY_LEVEL=1. D = A/B/C under contention (6 producers,
  20 us jobs, maxContention 1..2 on 5 lanes).
Run under envrun.cmd.   py -3 -I perf_arms.py [seeds] [kicks]"""
import os, re, subprocess, sys
from pathlib import Path
M = Path(__file__).resolve().parents[4]; R = M / 'ps3recomp-t123b'
OUT = M / 'generated/analysis/t123b/logs/perf'; OUT.mkdir(parents=True, exist_ok=True)
EXE = M / 'generated/analysis/t123b/bin/test_spurs_event_sched.exe'; EXE.parent.mkdir(exist_ok=True)
seeds = int(sys.argv[1]) if len(sys.argv) > 1 else 3
kicks = sys.argv[2] if len(sys.argv) > 2 else '400'
units = ['spu_channels', 'spu_drain', 'spu_lockstep', 'spu_coherency', 'spu_workload', 'spurs_policy',
         'spurs_job', 'spu_tsp_weak', 'spu_vm_pagemap', 'spurs_policy_blob_weak', 'spu_interp']
subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu17', '-O2', '-UNDEBUG', '-ffunction-sections', '-fdata-sections',
    '-Wl,/OPT:REF', '-I' + str(R / 'include'), '-I' + str(R / 'runtime/spu'), '-I' + str(R / 'runtime/platform'),
    str(R / 'tests/test_spurs_event_sched.c'), *[str(R / 'runtime/spu' / f'{u}.c') for u in units],
    str(R / 'runtime/platform/win32_compat.c'), '-o', str(EXE)], check=True)
MODES = {'A': {}, 'B': {'PS3_SPURS_KICK_WAKE': '1'}, 'C': {'PS3_SPURS_EVENT_SCHED': '1'}}
LOADS = {'legacy': {}, 'level': {'PS3_SPURS_READY_LEVEL': '1'},
         'D-contention': {'PRODUCERS': '6', 'SPIN_US': '20'}}
for seed in range(1, seeds + 1):
    for load, lenv in LOADS.items():
        for m in ('ABC' if seed % 2 else 'CBA'):
            e = {k: v for k, v in os.environ.items() if not k.startswith('PS3_SPURS_')}
            e.update(MODES[m]); e.update(lenv)
            e.update({'STRESS_SEED': str(seed), 'OBSERVER': '0', 'PS3_SPURS_SCHED_STATS': '1000', 'UNCOVERED': '20'})
            p = subprocess.run([str(EXE), kicks], env=e, capture_output=True, text=True, timeout=900)
            log = OUT / f'{load}_{m}_s{seed}.log'
            log.write_text(p.stdout + '\n--- stderr ---\n' + p.stderr, encoding='utf-8', errors='replace')
            lines = [l for l in p.stdout.splitlines() if l.startswith(('  ', 'PASS', 'FAIL'))]
            print(f'== {load} {m} seed {seed} rc={p.returncode}', *lines, sep='\n', flush=True)
