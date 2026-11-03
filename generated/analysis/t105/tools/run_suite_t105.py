#!/usr/bin/env python3
"""T105 (from t104/tools/run_suite_t104.py): renderer offline regressions for one tree,
plus the header-only C tests that have no runner (T100 race_display_diag, T103 win_dpi)
and T101's model + pins run against this tree's sources. Builds no game exe.
  py -3 -I run_suite_t105.py <tree>"""
import os, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LOGS = HERE.parent / 'logs' / 'suite'
LOGS.mkdir(parents=True, exist_ok=True)
TESTS = '''test_d3d12_blend_state test_d3d12_depth_state test_d3d12_rsxi_hooks test_d3d12_shader_trace
test_d3d12_texture_source_order test_d3d12_zeta_pool test_rf_phase test_geom_expand test_vp_flush test_prim_stream
test_draw_rejection test_present_gate test_rsx_frame_perf test_vp_expand test_race_display_diag
test_race_present_probe test_rsxi_frame_gain test_rsxi_geom'''.split()
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
    # T101 (5cb0181, tests only): its model + pins against this tree's sources.
    ov = HERE.parent / 'scratch' / f't101_on_{tree}'
    if ov.exists(): shutil.rmtree(ov)
    (ov / 'tools').mkdir(parents=True); (ov / 'libs/video/tests').mkdir(parents=True)
    for f in ('tools/test_t101_pins.py', 'libs/video/tests/test_t101_offscreen_replay.c'):
        (ov / f).write_bytes(subprocess.run(['git', '-C', str(T), 'show', f'5cb0181:{f}'], capture_output=True).stdout)
    shutil.copy(T / 'libs/video/rsx_d3d12_backend.c', ov / 'libs/video/rsx_d3d12_backend.c')
    t0 = time.time()
    exe = LOGS / 'bin' / f'{tree}__t101.exe'
    out, rc = run([str(CLANG), '-std=gnu17', '-O2', '-Wall', '-Wextra', '-Wno-unused-parameter', '-UNDEBUG',
                   '-D_CRT_SECURE_NO_WARNINGS', f'-I{T / "include"}', f'-I{T / "libs/video"}', f'-I{T}',
                   str(ov / 'libs/video/tests/test_t101_offscreen_replay.c'),
                   *[str(T / 'libs/video' / s) for s in ('rsx_commands.c', 'rsx_vertex_fetch.c', 'rsx_vertex_compact.c', 'rsx_dispatch.c')],
                   '-o', str(exe)], T)
    if rc == 0:
        o2, rc = run([str(exe)], T, 300); out += o2
    report(tree, 'c_t101_offscreen_replay (T101)', out, rc, t0)
    t0 = time.time()
    out, rc = run([sys.executable, str(ov / 'tools/test_t101_pins.py')], T)
    report(tree, 'test_t101_pins (T101)', out, rc, t0)

print('SUMMARY', {k: results.count(k) for k in ('PASS', 'SKIP', 'FAIL', 'ABSENT')})
