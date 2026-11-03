#!/usr/bin/env python3
"""T99 (copy of t96/tools/run_suite_t96.py; T96 copy of t94/tools/run_suite_t94.py; T94 copy of t91/tools/run_suite_t91.py). T87 (from t84e copy): renderer-related offline tests in several ps3recomp trees, one log per (tree, test)
in t91/logs/suite/<tree>__<test>.log, and a summary table. Run under the build MSVC + LLVM
environment with the T17 cc shim (t84/tools/run_suite.cmd). Builds no game exe.
  py -3 -I run_suite.py <tree> [<tree> ...]"""
import os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LOGS = HERE.parent / 'logs' / 'suite'
LOGS.mkdir(parents=True, exist_ok=True)
TESTS = '''test_spurs_wkl_maxcont test_spurs_wws_concurrency test_spurs_scheduler test_spurs_queue_size test_spurs_task_exit_code_initialize test_spurs_taskset_size test_mfc_resume_elements test_spu_chain_chunks test_spu_context_registries test_spu_interpreter_handoff test_spu_machine_status test_spu_program_pipeline test_spu_taskset_elf_flags test_spu_ls_alias test_ppu_trace test_vp_expand test_rsx_frame_perf test_vp_flush test_rf_phase test_geom_expand test_prim_stream test_draw_rejection test_present_gate'''.split()
if os.environ.get('T84_ONLY'): TESTS = os.environ['T84_ONLY'].split(',')
env = {k: v for k, v in os.environ.items() if not k.startswith(('RSX', 'RSXI', 'GCM_', 'VP_', 'PS3_'))}
for tree in sys.argv[1:]:
    for t in TESTS:
        script = ROOT / tree / 'tools' / f'{t}.py'
        log = LOGS / f'{tree}__{t}.log'
        if not script.exists():
            log.write_text('ABSENT in this tree\n', encoding='utf-8')
            print(f'{tree:16s} {t:34s} ABSENT', flush=True)
            continue
        t0 = time.time()
        try:
            p = subprocess.run([sys.executable, str(script)], cwd=ROOT / tree, env=env,
                               capture_output=True, text=True, timeout=900)
            out, rc = p.stdout + p.stderr, p.returncode
        except subprocess.TimeoutExpired as e:
            out, rc = f'TIMEOUT\n{e.stdout or ""}', 'timeout'
        log.write_text(out, encoding='utf-8', errors='replace')
        lines = [l for l in out.splitlines() if l.strip()]
        skip = any(l.startswith('SKIP') for l in lines)
        verdict = 'SKIP' if skip and rc == 0 else 'PASS' if rc == 0 else 'FAIL'
        print(f'{tree:16s} {t:34s} {verdict:4s} rc={rc!s:7s} {time.time() - t0:6.1f}s  {(lines[-1] if lines else "")[:90]}',
              flush=True)
