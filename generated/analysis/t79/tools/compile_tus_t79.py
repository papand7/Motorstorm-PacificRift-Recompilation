"""T79 (from T70C compile_tus.py): sources and include dirs redirected from ps3recomp-t70 to ps3recomp-t79.
T70C: compile chosen translation units of build/motorstorm-t70-aot with their exact build.ninja
command lines (ninja -t commands, which builds nothing), objects redirected to a scratch directory.
The build tree and its objects are not touched. Run under compile_tus.cmd (MSVC + LLVM env).
Usage: py -3 -I compile_tus.py <out dir> <source substring> [...]"""
import re, shlex, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
B = ROOT / 'build' / 'motorstorm-t70-aot'
out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=True)
txt = (B / 'build.ninja').read_text(encoding='utf-8', errors='replace')
objs = re.findall(r'^build (\S+\.obj): \S+_COMPILER\S* (\S+)', txt, re.M)
fails = 0
for want in sys.argv[2:]:
    hit = [(o, s) for o, s in objs if want.replace('/', '\\').lower() in s.replace('$:', ':').replace('/', '\\').lower()]
    if len(hit) != 1:
        print(f'{want}: {len(hit)} matching objects'); fails += 1; continue
    obj, src = hit[0]
    obj = obj.replace('$:', ':')
    cmd = subprocess.run(['ninja', '-C', str(B), '-t', 'commands', '-s', obj], capture_output=True, text=True).stdout.strip()
    if not cmd:
        print(f'{want}: no command'); fails += 1; continue
    dst = out / (Path(obj).name)
    # /Fo<obj> (clang-cl) or -o <obj>; the dependency file (/showIncludes or -MF) is left as is
    new = cmd.replace(obj, str(dst)).replace(obj.replace('\\', '/'), str(dst))
    if str(dst) not in new:
        print(f'{want}: could not redirect the object'); fails += 1; continue
    new = re.sub(r'\s-MF\s+\S+', '', re.sub(r'\s-MD\b', '', new))
    new = new.replace('ps3recomp-t70', 'ps3recomp-t79')
    if 'ps3recomp-t79' not in new:
        print(f'{want}: no ps3recomp-t79 path after redirect'); fails += 1; continue
    r = subprocess.run(new, cwd=B, shell=True, capture_output=True, text=True)
    dst.with_suffix('.log').write_text(r.stdout + r.stderr, encoding='utf-8')
    warn = [l for l in (r.stdout + r.stderr).splitlines() if 'warning' in l.lower() or 'error' in l.lower()]
    ok = r.returncode == 0 and dst.exists()
    fails += not ok
    print(f'{"OK  " if ok else "FAIL"} {Path(src.replace("$:", ":")).name}: exit {r.returncode}, {len(warn)} warning/error lines')
    for l in warn[:8]:
        print('     ', l[:220])
print('RESULT', 'PASS' if not fails else f'FAIL {fails}')
sys.exit(1 if fails else 0)
