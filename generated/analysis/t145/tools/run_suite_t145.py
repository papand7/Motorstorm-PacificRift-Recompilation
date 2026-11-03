#!/usr/bin/env python3
"""T145 (= t141/tools/run_suite_t141.py + test_shader_window; T141 = t137/tools/run_suite_t137.py + test_blend_feedback; T137 = t133/tools/run_suite_t133.py + test_msaa; T133 = t120/tools/run_suite_t120.py + T115 mip tests (cherry-picked) + test_image_quality; T120 = t113/tools/run_suite_t113.py + test_rt_window, test_depth_state; T113 from t110/tools/run_suite_t110.py; T110 from t108/tools/run_suite_t108.py; T108 from t105, T105 from t104): renderer offline regressions for one tree,
plus the header-only C tests that have no runner (T100 race_display_diag, T103 win_dpi)
and T101's model + pins run against this tree's sources. Builds no game exe.
  py -3 -I run_suite_t105.py <tree>"""
import os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LOGS = HERE.parent / 'logs' / 'suite'
LOGS.mkdir(parents=True, exist_ok=True)
TESTS = '''test_d3d12_blend_state test_d3d12_depth_state test_d3d12_rsxi_hooks test_d3d12_shader_trace
test_d3d12_texture_source_order test_d3d12_zeta_pool test_rf_phase test_geom_expand test_vp_flush test_prim_stream
test_draw_rejection test_present_gate test_rsx_frame_perf test_vp_expand test_race_display_diag
test_race_present_probe test_rsxi_frame_gain test_rsxi_geom test_d3d12_color_xfer test_t101_pins
test_t110_pins
test_rt_readback test_exposure_writeback test_fp_span test_rt_window test_depth_state
test_t115_pins test_image_quality test_msaa test_blend_feedback test_shader_window'''.split()
env = {k: v for k, v in os.environ.items() if not k.startswith(('RSX', 'RSXI', 'GCM_', 'VP_', 'PS3_', 'RACE_', 'CELLMARK'))}
CLANG = ROOT / 'build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin/clang.exe'
results = []


def report(tree, name, out, rc, t0):
    (LOGS / f'{tree}__{name}.log').write_text(out, encoding='utf-8', errors='replace')
    lines = [l for l in out.splitlines() if l.strip()]
    skip = any(l.startswith('SKIP') for l in lines)
    verdict = 'SKIP' if skip and rc == 0 else 'PASS' if rc == 0 else 'FAIL'
    results.append(verdict)
    print(f'{tree:16s} {name:34s} {verdict:4s} rc={rc!s:7s} {time.time() - t0:6.1f}s  {(lines[-1] if lines else "")[:90]}',
          flush=True)


def run(cmd, cwd, timeout=900):
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        return p.stdout + p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        return f'TIMEOUT\n{e.stdout or ""}', 'timeout'


def c_test(tree, name, srcs, incs, extra=()):
    t0 = time.time()
    T = ROOT / tree
    exe = LOGS / 'bin' / f'{tree}__{name}.exe'
    exe.parent.mkdir(exist_ok=True)
    out, rc = run([str(CLANG), '-std=gnu17', '-O2', '-Wall', '-Wextra', '-Wno-unused-parameter', '-UNDEBUG',
                   '-D_CRT_SECURE_NO_WARNINGS', *[f'-I{T / i}' for i in incs], *[str(T / s) for s in srcs], *extra,
                   '-o', str(exe)], T)
    if rc == 0:
        o2, rc = run([str(exe)], T, 300)
        out += o2
    report(tree, name, out, rc, t0)


for tree in sys.argv[1:]:
    T = ROOT / tree
    for t in TESTS:
        script = T / 'tools' / f'{t}.py'
        t0 = time.time()
        if not script.exists():
            (LOGS / f'{tree}__{t}.log').write_text('ABSENT in this tree\n', encoding='utf-8')
            results.append('ABSENT'); print(f'{tree:16s} {t:34s} ABSENT', flush=True)
            continue
        out, rc = run([sys.executable, str(script)], T)
        report(tree, t, out, rc, t0)
    c_test(tree, 'c_race_display_diag (T100)', ['libs/video/tests/test_race_display_diag.c'], ['include'])
    c_test(tree, 'c_win_dpi (T103)', ['libs/video/tests/test_win_dpi.c'], ['libs/video'], ['-luser32'])
    # T101 model, now in-tree (T108)
    c_test(tree, 'c_t101_offscreen_replay (T101)',
           ['libs/video/tests/test_t101_offscreen_replay.c', 'libs/video/rsx_commands.c', 'libs/video/rsx_vertex_fetch.c',
            'libs/video/rsx_vertex_compact.c', 'libs/video/rsx_dispatch.c'], ['include', 'libs/video', '.'])

    # T110
    c_test(tree, 'c_sampler_xlate (T110)', ['libs/video/tests/test_sampler_xlate.c'], ['libs/video'])
    c_test(tree, 'c_attr0_gate (T110)',
           ['libs/video/tests/test_attr0_gate.c', 'libs/video/rsx_commands.c', 'libs/video/rsx_vertex_fetch.c',
            'libs/video/rsx_vertex_compact.c', 'libs/video/rsx_dispatch.c'], ['include', 'libs/video', '.'])
    c_test(tree, 'c_t120_rsx_state_decode (T120)',
           ['libs/video/tests/test_t120_rsx_state_decode.c', 'libs/video/rsx_commands.c', 'libs/video/rsx_vertex_fetch.c',
            'libs/video/rsx_vertex_compact.c', 'libs/video/rsx_dispatch.c'], ['include', 'libs/video', '.'])
    c_test(tree, 'c_rtpool_victim (T110)', ['libs/video/tests/test_rtpool_victim.c'], ['libs/video'])
    c_test(tree, 'c_t110_warp (T110, WARP D3D12)',
           ['libs/video/tests/test_t110_warp.c', 'libs/video/rsx_fp_decompiler.c'], ['include', 'libs/video'],
           ['-ld3d12', '-ldxgi', '-ld3dcompiler', '-ldxguid'])

    # T115 (cherry-picked into T133)
    c_test(tree, 'c_tex_mips (T115)', ['libs/video/tests/test_tex_mips.c', 'libs/video/rsx_texture_layout.c'],
           ['include', 'libs/video'])
    c_test(tree, 'c_t115_warp (T115, WARP D3D12)',
           ['libs/video/tests/test_t115_warp.c', 'libs/video/rsx_texture_layout.c'], ['include', 'libs/video'],
           ['-ld3d12', '-ldxgi', '-ld3dcompiler', '-ldxguid'])

    # (test_fp_decompiler.c is not run: it calls POSIX setenv/unsetenv and builds in neither tree on Windows)

print('SUMMARY', {k: results.count(k) for k in ('PASS', 'SKIP', 'FAIL', 'ABSENT')})
