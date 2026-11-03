"""T134 (copy of t123b/tools/tu_t123b.py, tree ps3recomp-t134). T123B (copy of t123/tools/tu_t123.py, tree ps3recomp-t134). T123: compile changed runtime TUs with the exact flags build/motorstorm-t109/build.ninja
uses for them (compiler, FLAGS, DEFINES, INCLUDES; ps3recomp-t109 paths retargeted to
ps3recomp-t123), new (working tree) and base (git HEAD copy of the same file, its own
directory first on the include path), and compare warning counts and kinds.
  py -3 -I tu_t123.py runtime/spu/spu_workload.c libs/spurs/cellSpurs.c [...]"""
import re, shlex, subprocess, sys
from pathlib import Path

M = Path(__file__).resolve().parents[4]
W = M / 'ps3recomp-t134'
OUT = M / 'generated/analysis/t134/logs/tu'
NINJA = (M / 'build/motorstorm-t109/build.ninja').read_text(errors='replace')
LLVM = M / 'build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin'


def rule_for(rel):
    """(compiler, flags list) for the first build edge compiling `rel`."""
    name = rel.replace('/', '\\')
    for m in re.finditer(r'^build [^\n]*?\.obj: (C|CXX)_COMPILER__(\S+) (\S+)[^\n]*\n((?:  [^\n]*\n)+)', NINJA, re.M):
        if not m.group(3).replace('/', '\\').endswith(name):
            continue
        var = dict(re.findall(r'^  (\w+) = ([^\n]*)', m.group(4), re.M))
        args = []
        for k in ('DEFINES', 'INCLUDES', 'FLAGS'):
            args += shlex.split(var.get(k, '').replace('\\', '/'), posix=True)
        args = [a.replace('ps3recomp-t109', 'ps3recomp-t134') for a in args]
        return ('clang-cl.exe', args)
    raise SystemExit('no build edge for ' + rel)


rc = 0
for rel in sys.argv[1:]:
    cc, args = rule_for(rel)
    src = W / rel
    for arm in ('new', 'base'):
        d = OUT / arm
        d.mkdir(parents=True, exist_ok=True)
        f, extra = src, []
        if arm == 'base':
            f = d / src.name
            f.write_bytes(subprocess.run(['git', '-C', str(W), 'show', 'HEAD:' + rel],
                                         capture_output=True, check=True).stdout)
            extra = ['-I' + str(src.parent)]
        cmd = [str(LLVM / cc), '/nologo'] + extra + args + ['/Fo' + str(d / (src.name + '.obj')), '-c', '--', str(f)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        log = r.stdout + r.stderr
        (d / (src.name + '.log')).write_text(' '.join(cmd) + '\n' + log)
        kinds = sorted(set(re.findall(r'\[(-W[\w-]+)\]', log)))
        print('%s %s rc=%d warnings=%d kinds=%s' % (arm, rel, r.returncode, log.count('warning:'), ','.join(kinds)))
        rc |= r.returncode
sys.exit(rc)
