"""T136: .text of one lifted module built like the race (SSE4.1) and with PORT_SPU_AVX2's -mavx2,
against base (T123) and new (T136) headers.  py -3 -I tu_avx2_size.py <spu_recomp.c>"""
import re, shlex, subprocess, sys
from pathlib import Path
M = Path(__file__).resolve().parents[4]
src = Path(sys.argv[1]).resolve()
t = (M / 'build/motorstorm-t109-aot/build.ninja').read_text(errors='replace')
var = None
for m in re.finditer(r'^build [^\n]*?\.obj: (C|CXX)_COMPILER__(\S+) (\S+)[^\n]*\n((?:  [^\n]*\n)+)', t, re.M):
    if m.group(3).replace('$:', ':').replace('/', '\\').lower() == str(src).lower():
        var = dict(re.findall(r'^  (\w+) = ([^\n]*)', m.group(4), re.M)); break
args = []
for k in ('DEFINES', 'INCLUDES', 'FLAGS'):
    args += shlex.split(var.get(k, '').replace('\\', '/'), posix=True)
L = M / 'build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin'
out = M / 'generated/analysis/t136/logs/tu_lifted'
for tree, extra, tag in (('ps3recomp-t123', ['-mavx2'], 'base_avx2'), ('ps3recomp-t136', ['-mavx2'], 'new_avx2')):
    a = [x.replace('ps3recomp-t109', tree) for x in args] + extra
    o = out / f'{src.parent.name[:12]}_{tag}.obj'
    p = subprocess.run([str(L / 'clang-cl.exe'), *a, '/c', str(src), '/Fo' + str(o)], capture_output=True, text=True)
    h = subprocess.run([str(L / 'llvm-objdump.exe'), '-h', str(o)], capture_output=True, text=True).stdout
    print(tag, 'rc', p.returncode, 'text', sum(int(l.split()[2], 16) for l in h.splitlines() if re.match(r'\s*\d+\s+\.text', l)))
