"""T169: the WARP and backend C fixtures that have no tools/ runner, on the T169 tree. usage: py -3 warp_t169.py <tree>"""
import subprocess, sys
from pathlib import Path
T = Path(sys.argv[1]).resolve(); V = T / 'libs/video'
SUF = ['rsx_fp_decompiler.c']
L = ['-ld3d12', '-ldxgi', '-ld3dcompiler', '-ldxguid']
TESTS = {'test_t110_warp': (SUF, L), 'test_t133_image_quality': (SUF, L), 'test_t137_msaa_warp': (SUF, L), 'test_t137_msaa_logic': ([], []),
         'test_t141_blend_feedback_warp': (SUF, L), 'test_t144_stencil_warp': (SUF, L), 'test_t145_shader_window_warp': (SUF, L),
         'test_t115_warp': (SUF + ['rsx_texture_layout.c'], L), 'test_sampler_xlate': ([], []), 'test_tex_mips': (['rsx_texture_layout.c'], [])}
bad = 0
for n, (src, lib) in TESTS.items():
    exe = Path(sys.argv[2]) / (n + '.exe')
    r = subprocess.run(['clang', '-std=gnu17', '-O2', '-w', '-UNDEBUG', '-D_CRT_SECURE_NO_WARNINGS', f'-I{T / "include"}', f'-I{V}', f'-I{V / "tests"}', str(V / 'tests' / (n + '.c')),
                        *[str(V / s) for s in src], *lib, '-o', str(exe)], capture_output=True, text=True)
    if r.returncode:
        print(n, 'BUILD FAIL', r.stderr[-300:].replace('\n', ' ')); bad += 1; continue
    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300, cwd=T)
    print(n, 'rc', r.returncode, (r.stdout.strip().splitlines() or [''])[-1][:110])
    bad += r.returncode != 0
print('failed', bad)
