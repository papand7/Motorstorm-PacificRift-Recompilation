"""T136: compile <src> with the exact build flags of another lifted TU <like> (race AOT build),
against a given tree's headers.  py -3 -I tu_as.py <like spu_recomp.c> <src.c> <tree> <out.obj>"""
import re, shlex, subprocess, sys, time
from pathlib import Path
M = Path(__file__).resolve().parents[4]
like, src, tree, obj = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3], Path(sys.argv[4]).resolve()
t = (M / 'build/motorstorm-t109-aot/build.ninja').read_text(errors='replace')
var = None
for m in re.finditer(r'^build [^\n]*?\.obj: (C|CXX)_COMPILER__(\S+) (\S+)[^\n]*\n((?:  [^\n]*\n)+)', t, re.M):
    if m.group(3).replace('$:', ':').replace('/', '\\').lower() == str(like).lower():
        var = dict(re.findall(r'^  (\w+) = ([^\n]*)', m.group(4), re.M)); break
args = []
for k in ('DEFINES', 'INCLUDES', 'FLAGS'):
    args += shlex.split(var.get(k, '').replace('\\', '/'), posix=True)
args = [x.replace('ps3recomp-t109', tree) for x in args] + ['-I' + str(like.parent)]
L = M / 'build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin'
t0 = time.time()
p = subprocess.run([str(L / 'clang-cl.exe'), *args, '/c', str(src), '/Fo' + str(obj)], capture_output=True, text=True)
obj.with_suffix('.log').write_text(p.stdout + p.stderr, encoding='utf-8', errors='replace')
h = subprocess.run([str(L / 'llvm-objdump.exe'), '-h', str(obj)], capture_output=True, text=True).stdout if not p.returncode else ''
print(f'{src.parent.name} rc={p.returncode} warnings={len(re.findall("warning:", p.stdout + p.stderr))} '
      f'text={sum(int(l.split()[2], 16) for l in h.splitlines() if re.match(r"\s*\d+\s+[.]text", l))} {time.time() - t0:.0f}s')
if p.returncode: print((p.stdout + p.stderr)[-1500:])
