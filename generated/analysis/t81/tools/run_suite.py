#!/usr/bin/env python3
"""T81 phase 5: every applicable offline test on ps3recomp-t81, one log each in t81/logs/suite_<name>.log.
Run under run_t81.cmd (MSVC + LLVM env, T17 cc shim, cwd = ps3recomp-t81).
  py -3 -I run_suite.py"""
import os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[3] / 'ps3recomp-t81'
LOGS = HERE.parent / 'logs'
LOGS.mkdir(exist_ok=True)
PY = sys.executable
POSIX = [PY, str(HERE / 'run_posix_fixture.py')]

TESTS = [  # (name, argv relative to TREE, timeout s)
    ('spu_jobspan', [PY, 'tools/test_spu_jobspan.py'], 600),
    ('spu_jobspan_path', [PY, 'tests/test_spu_jobspan_path.py'], 900),
    ('spu_reloc_job', [PY, 'tests/test_spu_reloc_job.py'], 1800),
    ('spu_lifter_reloc', [PY, 'tools/test_spu_lifter_reloc.py'], 900),
    ('spurs_wkl_maxcont', [PY, 'tools/test_spurs_wkl_maxcont.py'], 600),
    ('spurs_wws_concurrency_1', [PY, 'tools/test_spurs_wws_concurrency.py'], 900),
    ('spurs_wws_concurrency_2', [PY, 'tools/test_spurs_wws_concurrency.py'], 900),
    ('spurs_wws_concurrency_3', [PY, 'tools/test_spurs_wws_concurrency.py'], 900),
    ('spurs_scheduler', POSIX + ['tests/test_spurs_scheduler.c'], 600),
    ('ppu_trace', [PY, 'tools/test_ppu_trace.py'], 900),
    ('spu_chain_chunks', [PY, 'tools/test_spu_chain_chunks.py'], 900),
    ('spu_interpreter_handoff', [PY, 'tools/test_spu_interpreter_handoff.py'], 900),
    ('spu_lift_selftest', [PY, 'tools/spu_lift_selftest.py'], 900),
    ('lifter_dedupe', [PY, 'tools/test_lifter_dedupe.py'], 600),
    ('lifter_header_name', [PY, 'tools/test_lifter_header_name.py'], 600),
    ('spu_fnms_zero_extended', [PY, 'tests/test_spu_fnms_zero_extended.py'], 600),
    # POSIX-only on this host (T79 §12.2): attempted, expected to SKIP/fail to link
    ('spurs_queue_size', [PY, 'tools/test_spurs_queue_size.py'], 300),
    ('spurs_taskset_size', [PY, 'tools/test_spurs_taskset_size.py'], 300),
    ('spurs_task_exit_code_initialize', [PY, 'tools/test_spurs_task_exit_code_initialize.py'], 300),
    ('spu_context_registries', [PY, 'tools/test_spu_context_registries.py'], 300),
    ('spu_machine_status', [PY, 'tools/test_spu_machine_status.py'], 300),
]
only = set(sys.argv[1:])
env = {k: v for k, v in os.environ.items() if not k.startswith(('SPU_', 'SPURS_', 'PS3_', 'YDKJ_', 'LBP_', 'RSX_'))}
for name, argv, to in TESTS:
    if only and name not in only:
        continue
    t0 = time.time()
    try:
        p = subprocess.run(argv, cwd=TREE, env=env, capture_output=True, text=True, timeout=to)
        out, rc = p.stdout + p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        out, rc = f'TIMEOUT after {to} s\n{e.stdout or ""}', 'timeout'
    (LOGS / f'suite_{name}.log').write_text(out, encoding='utf-8', errors='replace')
    tail = [l for l in out.splitlines() if l.strip()][-1:] or ['']
    print(f'{name:34s} rc={rc!s:7s} {time.time() - t0:6.1f}s  {tail[0][:110]}', flush=True)
