"""T144 (from T141): build test_t141_backend.exe from a worktree with the project's exact compile flags
(taken from tu_t141.cmd, i.e. build.ninja's rsx_d3d12_backend.c line).

  py -3 build_bench.py <worktree> <outdir> [extra cflags...]   (run under tools/env.cmd)
"""
import os, pathlib, re, subprocess, sys

T = pathlib.Path(__file__).resolve().parent
wt = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()
extra = sys.argv[3:]
out.mkdir(parents=True, exist_ok=True)
line = next(x for x in (T / 'tu_t141.cmd').read_text().splitlines() if 'clang-cl' in x)
toks = line.split()
flags = []
for t in toks[1:]:
    if t.startswith(('-clang:-MD', '-clang:-MT', '-clang:-MF', '/Fo', '/Fd')) or t in ('-c', '--', '>', '2>&1'):
        continue
    if t.endswith('.c') or t.endswith('.log"') or t.startswith('"'):
        break
    flags.append(t.replace('ps3recomp-t137', wt.name))
assert '/O2' in flags and '-ffp-contract=off' in flags, flags
srcs = ['libs/video/rsx_d3d12_backend.c', 'libs/video/rsx_commands.c', 'libs/video/rsx_vertex_fetch.c', 'libs/video/rsx_vertex_compact.c',
        'libs/video/rsx_fp_decompiler.c', 'libs/video/rsx_vp_decompiler.c', 'libs/video/rsx_texture_layout.c',
        'libs/video/tests/' + os.environ.get('T144_TEST', 'test_t141_backend') + '.c']
objs = []
if any('T119_GETENV_COUNT' in e for e in extra):
    srcs.append(str(T / 'diag/getenv_count.c'))
for s in srcs:
    o = out / (pathlib.Path(s).stem + '.obj')
    src = str(wt / s) if not pathlib.Path(s).is_absolute() else s
    import os
    if s.endswith('rsx_d3d12_backend.c') and os.environ.get('T119_BACKEND_SRC'):
        src = os.environ['T119_BACKEND_SRC']   # a scratch variant of the same tree's backend (diagnostics only)
    cmd = ['clang-cl'] + flags + extra + ['-I' + str(wt / 'libs/video'), '/Fo' + str(o), '-c', '--', src]
    r = subprocess.run(cmd, capture_output=True, text=True)
    (out / (pathlib.Path(s).stem + '.log')).write_text(r.stdout + r.stderr)
    print(f'{s}: rc={r.returncode} warnings={(r.stdout + r.stderr).count("warning:")}')
    if r.returncode:
        print((r.stdout + r.stderr)[-3000:]); sys.exit(1)
    objs.append(str(o))
exe = out / (os.environ.get('T144_TEST', 'test_t141_backend') + '.exe')
r = subprocess.run(['clang-cl', '/nologo', '/MD'] + objs + ['/Fe' + str(exe), '/link', '/errorlimit:0',
                    'd3d12.lib', 'dxgi.lib', 'd3dcompiler.lib', 'dxguid.lib', 'user32.lib', 'gdi32.lib', 'ole32.lib',
                    'winmm.lib', 'shlwapi.lib', 'advapi32.lib'], capture_output=True, text=True)
(out / 'link.log').write_text(r.stdout + r.stderr)
print(f'link rc={r.returncode}')
if r.returncode:
    print(sorted(set(re.findall(r'undefined symbol: (\S+)', r.stdout + r.stderr))) or (r.stdout + r.stderr)[-3000:])
    sys.exit(1)
