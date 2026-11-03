"""T140: compile one private lifted TU (generated/ppu-hooked-staging/<name>) with the build's exact flags,
once with the staging ppu_recomp.h and once with the T140 raw-store section swapped in, and compare the
object's .text size. Output stays under t140/bench/obj (private, not committed). Not a game build.

  python -I lifted_tu_size.py ppu_recomp_010.cpp
"""
import re
import subprocess
import sys
from pathlib import Path

M = Path(__file__).resolve().parents[4]
T = M / 'generated/analysis/t140'
CL = M / 'build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin/clang-cl.exe'
OBJDUMP = M / 'build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin/llvm-objdump.exe'
FLAGS = ('/DWIN32 /D_WINDOWS /EHsc /O2 /Ob2 /DNDEBUG -std:c++20 -MD -Wall -Wextra -Wno-unused-parameter '
         '-fno-strict-aliasing -fwrapv /w /bigobj').split()
name = sys.argv[1]
src = M / 'generated/ppu-hooked-staging' / name
import shutil
# A quoted #include searches the source's own directory first, so the new arm compiles a copy of the TU
# placed next to the new header.
shutil.copyfile(src, T / 'bench/hdr_staging_new' / name)
for arm, hdr in (('base', M / 'generated/ppu-hooked-staging'), ('new', T / 'bench/hdr_staging_new')):
    src = hdr / name
    obj = T / 'bench/obj' / f'{Path(name).stem}_{arm}.obj'
    inc = ['-I' + str(hdr), '-I' + str(M / 'ps3recomp-t140/runtime/ppu'), '-I' + str(M / 'ps3recomp-t140/include')]
    r = subprocess.run([str(CL), '/nologo'] + inc + FLAGS + ['/Fo' + str(obj), '-c', '--', str(src)],
                       capture_output=True, text=True)
    if r.returncode:
        print(arm, 'compile failed', (r.stdout + r.stderr)[-1500:])
        continue
    h = subprocess.run([str(OBJDUMP), '-h', str(obj)], capture_output=True, text=True).stdout
    text = sum(int(m.group(1), 16) for m in re.finditer(r'\.text\S*\s+([0-9a-f]+)', h))
    print(f'{arm}: .text {text} bytes, obj {obj.stat().st_size} bytes')
