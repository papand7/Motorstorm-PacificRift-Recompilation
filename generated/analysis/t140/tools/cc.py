"""T140: compile runtime TUs with the exact project flags (build/motorstorm-t122/build.ninja) and link
offline benchmarks / tests against them. Nothing here builds or launches the game.

  python -I cc.py obj <tree> <rel.cpp|rel.c> <out.obj> [-Dmacro ...]
  python -I cc.py exe <out.exe> <src-or-obj> [...] [-Dmacro ...] [--force]

<tree> is a ps3recomp worktree directory name under the motorstorm root (e.g. ps3recomp-t140).
"""
import subprocess
import sys
from pathlib import Path

M = Path(__file__).resolve().parents[4]
BIN = M / 'build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin'
CL = BIN / 'clang-cl.exe'
CXXFLAGS = ('/DWIN32 /D_WINDOWS /EHsc /O2 /Ob2 /DNDEBUG -std:c++20 -MD -Wall -Wextra -Wno-unused-parameter '
            '-fno-strict-aliasing -fwrapv').split()
CFLAGS = ('/DWIN32 /D_WINDOWS /O2 /Ob2 /DNDEBUG /std:c17 -MD -Wall -Wextra -Wno-unused-parameter '
          '-fno-strict-aliasing -ffp-contract=off -O2 -msse4.1').split()
STAGING = M / 'generated/ppu-hooked-staging'   # only ppu_recomp.h's declarations are used


HDR = []   # --hdr <dir>: a ppu_recomp.h to use instead of the staging one


def incs(tree):
    w = M / tree
    dirs = HDR + [STAGING, w / 'include', w / 'runtime/ppu', w / 'runtime/spu', w / 'runtime/memory',
            w / 'runtime/syscalls', w / 'runtime/platform', w / 'libs/video', M / 'port']
    return ['-I' + str(d) for d in dirs]


def run(cmd, log):
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = r.stdout + r.stderr
    Path(log).write_text(out)
    errs = [l for l in out.splitlines() if ': error' in l or 'error:' in l]
    print('rc=%d warnings=%d errors=%d -> %s' % (r.returncode, out.count('warning:'), len(errs), log))
    for l in errs[:20]:
        print('  ' + l)
    return r.returncode


def main():
    mode = sys.argv[1]
    if '--hdr' in sys.argv:
        i = sys.argv.index('--hdr')
        HDR.append(Path(sys.argv[i + 1]).resolve())
        del sys.argv[i:i + 2]
    defs = [a for a in sys.argv[2:] if a.startswith('-D') or a.startswith('/D')]
    args = [a for a in sys.argv[2:] if a not in defs]
    if mode == 'obj':
        tree, rel, out = args[0], args[1], Path(args[2])
        src = M / tree / rel
        flags = CXXFLAGS if src.suffix == '.cpp' else CFLAGS
        cmd = [str(CL), '/nologo'] + incs(tree) + flags + defs + ['/Fo' + str(out), '-c', '--', str(src)]
        sys.exit(run(cmd, str(out) + '.log'))
    if mode == 'exe':
        force = '--force' in args
        args = [a for a in args if a != '--force']
        out, srcs = Path(args[0]), args[1:]
        tree = 'ps3recomp-t140'
        cmd = [str(CL), '/nologo'] + incs(tree) + CXXFLAGS[:-0 or None] + defs + ['/Fe' + str(out), '/Fo' + str(out.parent) + '\\']
        cmd = [c for c in cmd if c != '-std:c++20'] + srcs + ['/link', 'kernel32.lib', 'user32.lib', 'dbghelp.lib']
        if force:
            cmd.append('/FORCE:UNRESOLVED')
        sys.exit(run(cmd, str(out) + '.log'))
    sys.exit('usage')


if __name__ == '__main__':
    main()
