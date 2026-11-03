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
TESTS = '''test_d3d12_depth_state test_d3d12_blend_state test_d3d12_rsxi_hooks test_d3d12_shader_trace
test_d3d12_texture_source_order test_d3d12_zeta_pool test_draw_rejection test_fp_alias test_fp_shadow_compare
test_live_draw_sampler_key test_present_diag test_present_gate test_present_progress test_prim_stream
test_rsx_immediate_vertices test_rsx_inspect test_rsxi_frame_gain test_rsxi_geom test_rt_clip
test_rt_pool_srv_layout test_rt_readback test_rt_vis_trace test_vp_branch_base test_vp_fallback test_xfer_diag
test_gcm_offset_table_live test_gcm_io_alloc test_gcm_map_flags test_gcm_io_mappings test_mmapper_hle_heap
test_gcm_flip_stream test_gcm_get_on_jump test_gcm_get_on_release test_gcm_report_trace test_gcm_sync_trace
test_gcm_stall_watch test_ppu_trace test_rf_phase test_geom_expand test_vp_flush test_rsx_frame_perf'''.split()
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
