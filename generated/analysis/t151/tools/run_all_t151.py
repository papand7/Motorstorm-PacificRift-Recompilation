#!/usr/bin/env python3
"""T151 (copy of T146 run_all_t146.py): every tools/test_*.py driver of a tree, plus the header-only / WARP C tests of the
T145 renderer suite. Builds no game exe. One log per test in ../logs/suite/<tree>__<test>.log.

  py -3 -I run_all_t146.py [--only a,b,c] [--jobs N] <tree> [<tree> ...]

Tests in SERIAL (timing-sensitive: concurrency, sleeps, spin) run one at a time after the
parallel batch so host contention cannot fail them spuriously."""
import os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LOGS = HERE.parent / 'logs' / 'suite'
LOGS.mkdir(parents=True, exist_ok=True)
CLANG = ROOT / 'build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin/clang.exe'
SERIAL = set('''test_spurs_wws_concurrency test_spurs_wws_stress test_spurs_event_sched test_spurs_kick_wake
test_spurs_scheduler test_spurs_wkl_maxcont test_timer_usleep test_spu_fp_cache test_vm_store_fast test_spu_diag_tls
test_spu_event_lr_race test_sc_wait_acct test_cpath_trace test_d3d12_shader_cache test_bind_dedup test_spu_exec_sse'''.split())
env = {k: v for k, v in os.environ.items() if not k.startswith(('RSX', 'RSXI', 'GCM_', 'VP_', 'PS3_', 'PPU_', 'RACE_', 'CELLMARK', 'D3D12_'))}

args = sys.argv[1:]
only, jobs = None, 6
while args and args[0].startswith('--'):
    if args[0] == '--only': only = set(args[1].split(',')); args = args[2:]
    elif args[0] == '--jobs': jobs = int(args[1]); args = args[2:]
    else: sys.exit('bad arg ' + args[0])


def run(cmd, cwd, timeout=1200):
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout,
                           encoding='utf-8', errors='replace')
        return p.stdout + p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        o = e.stdout.decode('utf-8', 'replace') if isinstance(e.stdout, bytes) else (e.stdout or '')
        return f'TIMEOUT\n{o}', 'timeout'


def verdict(out, rc):
    lines = [l for l in out.splitlines() if l.strip()]
    skip = any(l.startswith('SKIP') for l in lines)
    return ('SKIP' if skip and rc == 0 else 'PASS' if rc == 0 else 'FAIL'), (lines[-1] if lines else '')


def py_test(tree, name):
    t0 = time.time()
    out, rc = run([sys.executable, str(ROOT / tree / 'tools' / f'{name}.py')], ROOT / tree)
    (LOGS / f'{tree}__{name}.log').write_text(out, encoding='utf-8', errors='replace')
    v, last = verdict(out, rc)
    return name, v, rc, time.time() - t0, last


def c_test(tree, name, srcs, incs, extra=()):
    t0 = time.time()
    T = ROOT / tree
    exe = LOGS / 'bin' / f'{tree}__{name.split()[0]}.exe'
    exe.parent.mkdir(exist_ok=True)
    out, rc = run([str(CLANG), '-std=gnu17', '-O2', '-Wall', '-Wextra', '-Wno-unused-parameter', '-UNDEBUG',
                   '-D_CRT_SECURE_NO_WARNINGS', *[f'-I{T / i}' for i in incs], *[str(T / s) for s in srcs], *extra,
                   '-o', str(exe)], T)
    if rc == 0:
        o2, rc = run([str(exe)], T, 600)
        out += o2
    (LOGS / f'{tree}__{name.split()[0]}.log').write_text(out, encoding='utf-8', errors='replace')
    v, last = verdict(out, rc)
    return name, v, rc, time.time() - t0, last


VID = ['libs/video/rsx_commands.c', 'libs/video/rsx_vertex_fetch.c', 'libs/video/rsx_vertex_compact.c', 'libs/video/rsx_dispatch.c']
D3D = ['-ld3d12', '-ldxgi', '-ld3dcompiler', '-ldxguid']
C_TESTS = [
    ('c_race_display_diag (T100)', ['libs/video/tests/test_race_display_diag.c'], ['include'], ()),
    ('c_win_dpi (T103)', ['libs/video/tests/test_win_dpi.c'], ['libs/video'], ['-luser32']),
    ('c_t101_offscreen_replay (T101)', ['libs/video/tests/test_t101_offscreen_replay.c', *VID], ['include', 'libs/video', '.'], ()),
    ('c_sampler_xlate (T110)', ['libs/video/tests/test_sampler_xlate.c'], ['libs/video'], ()),
    ('c_attr0_gate (T110)', ['libs/video/tests/test_attr0_gate.c', *VID], ['include', 'libs/video', '.'], ()),
    ('c_t120_rsx_state_decode (T120)', ['libs/video/tests/test_t120_rsx_state_decode.c', *VID], ['include', 'libs/video', '.'], ()),
    ('c_rtpool_victim (T110)', ['libs/video/tests/test_rtpool_victim.c'], ['libs/video'], ()),
    ('c_t110_warp (T110, WARP)', ['libs/video/tests/test_t110_warp.c', 'libs/video/rsx_fp_decompiler.c'], ['include', 'libs/video'], D3D),
    ('c_tex_mips (T115)', ['libs/video/tests/test_tex_mips.c', 'libs/video/rsx_texture_layout.c'], ['include', 'libs/video'], ()),
    ('c_t115_warp (T115, WARP)', ['libs/video/tests/test_t115_warp.c', 'libs/video/rsx_texture_layout.c'], ['include', 'libs/video'], D3D),
    ('c_tex_cache (T115B)', ['libs/video/tests/test_tex_cache.c', 'libs/video/rsx_texture_layout.c'], ['include', 'libs/video'], ()),
    ('c_t115b_warp (T115B, WARP)', ['libs/video/tests/test_t115b_warp.c', 'libs/video/rsx_texture_layout.c'], ['include', 'libs/video'], D3D),
    ('c_fp_span (T113)', ['libs/video/tests/test_fp_span.c', 'libs/video/rsx_fp_decompiler.c'], ['include', 'libs/video'], D3D),
    ('c_vp_compact (T119)', ['libs/video/tests/test_vp_compact.c'], ['include'], ()),
    ('c_vp_vs_memo (T119)', ['libs/video/tests/test_vp_vs_memo.c'], ['include'], ()),
    ('c_draw_split (T119)', ['libs/video/tests/test_draw_split.c'], ['include'], ()),
    ('c_t133_image_quality (T133)', ['libs/video/tests/test_t133_image_quality.c', 'libs/video/rsx_fp_decompiler.c'], ['include', 'libs/video'], D3D),
    ('c_t137_msaa_logic (T137)', ['libs/video/tests/test_t137_msaa_logic.c'], ['include', 'libs/video'], ()),
    ('c_t137_msaa_warp (T137, WARP)', ['libs/video/tests/test_t137_msaa_warp.c'], ['include', 'libs/video'], D3D),
    ('c_t141_blend_feedback_warp (T141, WARP)', ['libs/video/tests/test_t141_blend_feedback_warp.c'], ['include', 'libs/video'], D3D),
    ('c_t144_stencil_warp (T144, WARP)', ['libs/video/tests/test_t144_stencil_warp.c'], ['include', 'libs/video'], D3D),
    ('c_t145_shader_window_warp (T145, WARP)', ['libs/video/tests/test_t145_shader_window_warp.c', 'libs/video/rsx_fp_decompiler.c'], ['include', 'libs/video'], D3D),
]

summary = {}
for tree in args:
    T = ROOT / tree
    names = sorted(p.stem for p in (T / 'tools').glob('test_*.py'))
    if only: names = [n for n in names if n in only]
    par = [n for n in names if n not in SERIAL]
    ser = [n for n in names if n in SERIAL]
    res = []
    with ThreadPoolExecutor(jobs) as ex:
        res += list(ex.map(lambda n: py_test(tree, n), par))
        cts = [c for c in C_TESTS if (not only or c[0].split()[0] in only) and all((T / s).exists() for s in c[1])]
        res += list(ex.map(lambda c: c_test(tree, *c), cts))
    for n in ser:
        res.append(py_test(tree, n))
    for name, v, rc, dt, last in res:
        print(f'{tree:28s} {name:42s} {v:4s} rc={rc!s:7s} {dt:6.1f}s  {last[:90]}', flush=True)
    summary[tree] = {k: sum(1 for r in res if r[1] == k) for k in ('PASS', 'SKIP', 'FAIL')}
    print('FAILED', tree, [r[0] for r in res if r[1] == 'FAIL'], flush=True)
print('SUMMARY', summary)
