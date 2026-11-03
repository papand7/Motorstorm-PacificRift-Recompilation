"""T121: compile changed runtime TUs with the exact project flags (from
build/motorstorm-t113/build.ninja), new (ps3recomp-t121) and base (git HEAD
copy of the same file), and compare warning kinds.
  python -I tu_t121.py runtime/syscalls/sys_timer.c [...]"""
import re, subprocess, sys
from pathlib import Path

M = Path(__file__).resolve().parents[4]
W = M / 'ps3recomp-t121'
OUT = M / 'generated/analysis/t121/logs/tu'
CL = M / 'build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin/clang-cl.exe'
FLAGS = '/DWIN32 /D_WINDOWS /O2 /Ob2 /DNDEBUG /std:c17 -MD -Wall -Wextra -Wno-unused-parameter -fno-strict-aliasing -ffp-contract=off -O2 -msse4.1'.split()
INC = ['include', 'libs/system', 'libs/filesystem', 'libs/input', 'libs/audio', 'libs/video', 'libs/network',
       'libs/spurs', 'libs/sync', 'libs/codec', 'libs/font', 'libs/misc', 'runtime/spu']

rc = 0
for rel in sys.argv[1:]:
    src = W / rel
    for arm in ('new', 'base'):
        d = OUT / arm
        d.mkdir(parents=True, exist_ok=True)
        f = src
        extra = []
        if arm == 'base':
            f = d / src.name
            f.write_bytes(subprocess.run(['git', '-C', str(W), 'show', 'HEAD:' + rel], capture_output=True, check=True).stdout)
            extra = ['-I' + str(src.parent)]
        cmd = [str(CL), '/nologo'] + extra + ['-I' + str(W / i) for i in INC] + FLAGS + \
              ['/Fo' + str(d / (src.name + '.obj')), '-c', '--', str(f)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        log = r.stdout + r.stderr
        (d / (src.name + '.log')).write_text(log)
        kinds = sorted(set(re.findall(r'\[(-W[\w-]+)\]', log)))
        print('%s %s rc=%d warnings=%d kinds=%s' % (arm, rel, r.returncode, log.count('warning:'), ','.join(kinds)))
        rc |= r.returncode
sys.exit(rc)
