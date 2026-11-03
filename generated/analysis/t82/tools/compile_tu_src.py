"""T82: compile one TU with the exact build.ninja command of the B1 build (build/motorstorm-t70g-aot),
replacing only its source path and object path, so a patched copy of a generated TU is compiled with
the project's LLVM toolchain and flags without touching the build tree or the shared generated input.
Usage (under vcvars + LLVM PATH): py -3 -I compile_tu_src.py <object source substring> <new source> <out .obj> [tree]
[tree]: also re-point every ps3recomp-t70g path (includes) to that worktree."""
import re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
B = ROOT / 'build' / 'motorstorm-t70g-aot'
BS = '\\'
want, src, dst = sys.argv[1], Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()
tree = sys.argv[4] if len(sys.argv) > 4 else None
txt = (B / 'build.ninja').read_text(encoding='utf-8', errors='replace')
objs = re.findall(r'^build (\S+\.obj): \S+_COMPILER\S* (\S+)', txt, re.M)
w = want.replace('/', BS).lower()
hit = [(o, s) for o, s in objs if w in s.replace('$:', ':').replace('/', BS).lower()]
if len(hit) != 1:
    sys.exit(f'{want}: {len(hit)} matching objects')
obj, osrc = hit[0][0].replace('$:', ':'), hit[0][1].replace('$:', ':')
cmd = subprocess.run(['ninja', '-C', str(B), '-t', 'commands', '-s', obj], capture_output=True, text=True).stdout.strip()
new = cmd.replace(obj, str(dst)).replace(osrc, str(src))
new = re.sub(r'\s-MF\s+\S+', '', re.sub(r'\s-MD\b', '', new))
if tree:
    new = re.sub(r'ps3recomp-t70g(?=[\\/"\s])', tree, new)
if str(dst) not in new or str(src) not in new:
    sys.exit('could not redirect source/object')
dst.parent.mkdir(parents=True, exist_ok=True)
r = subprocess.run(new, cwd=B, shell=True, capture_output=True, text=True)
dst.with_suffix('.log').write_text(new + '\n' + r.stdout + r.stderr, encoding='utf-8')
print(new)
print(r.stdout + r.stderr)
print('exit', r.returncode, 'object', dst, dst.stat().st_size if dst.exists() else 'missing')
sys.exit(r.returncode)
