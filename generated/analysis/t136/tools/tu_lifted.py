"""T136: compile real lifted SPU TUs (private) with the exact flags build/motorstorm-t109-aot uses
for them, against the T136 runtime headers (new) and the unchanged T123 headers (base, the same
base commit e48f279), and compare rc, warnings, .text size and helper call sites in the object.
  py -3 -I tu_lifted.py <lifted spu_recomp.c> [...]"""
import re, shlex, subprocess, sys, time
from pathlib import Path

M = Path(__file__).resolve().parents[4]
OUT = M / 'generated/analysis/t136/logs/tu_lifted'
OUT.mkdir(parents=True, exist_ok=True)
NINJA = (M / 'build/motorstorm-t109-aot/build.ninja').read_text(errors='replace')
LLVM = M / 'build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin'
TREES = {'new': 'ps3recomp-t136', 'base': 'ps3recomp-t123'}


def flags_for(src):
    name = str(src).replace('/', '\\').lower()
    for m in re.finditer(r'^build [^\n]*?\.obj: (C|CXX)_COMPILER__(\S+) (\S+)[^\n]*\n((?:  [^\n]*\n)+)', NINJA, re.M):
        if m.group(3).replace('$:', ':').replace('/', '\\').lower() != name:
            continue
        var = dict(re.findall(r'^  (\w+) = ([^\n]*)', m.group(4), re.M))
        args = []
        for k in ('DEFINES', 'INCLUDES', 'FLAGS'):
            args += shlex.split(var.get(k, '').replace('\\', '/'), posix=True)
        return args
    raise SystemExit('no build edge for ' + str(src))


def section_size(obj):
    p = subprocess.run([str(LLVM / 'llvm-objdump.exe'), '-h', str(obj)], capture_output=True, text=True)
    return sum(int(l.split()[2], 16) for l in p.stdout.splitlines() if re.match(r'\s*\d+\s+\.text', l))


def calls(obj, sym):
    p = subprocess.run([str(LLVM / 'llvm-objdump.exe'), '-dr', '--no-show-raw-insn', str(obj)],
                       capture_output=True, text=True)
    return len(re.findall(r'IMAGE_REL_AMD64_REL32\s+' + re.escape(sym) + r'\b', p.stdout))


for src in sys.argv[1:]:
    src = Path(src).resolve()
    args = flags_for(src)
    tag = src.parent.name[:16]
    for arm, tree in TREES.items():
        a = [x.replace('ps3recomp-t109', tree) for x in args]
        obj = OUT / f'{tag}_{arm}.obj'
        t0 = time.time()
        p = subprocess.run([str(LLVM / 'clang-cl.exe'), *a, '/c', str(src), '/Fo' + str(obj)],
                           capture_output=True, text=True, cwd=M)
        dt = time.time() - t0
        (OUT / f'{tag}_{arm}.log').write_text(p.stdout + p.stderr, encoding='utf-8', errors='replace')
        w = len(re.findall(r'warning:', p.stdout + p.stderr))
        if p.returncode:
            print(f'{tag} {arm:4s} rc={p.returncode} warnings={w}'); continue
        print(f'{tag} {arm:4s} rc=0 warnings={w} text={section_size(obj)} fma_calls={calls(obj, "fma")} '
              f'fa_fix={calls(obj, "spu__x4_fa_fix")} {dt:.0f}s', flush=True)
