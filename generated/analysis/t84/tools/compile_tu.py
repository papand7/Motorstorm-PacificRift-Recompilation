"""T84: compile chosen TUs of the T64C build (build/motorstorm-t62-font-c529ab0) with their exact
build.ninja command lines (ninja -t commands builds nothing), every ps3recomp-t62 path re-pointed to
the given tree, objects to a scratch dir. Writes <obj>.log (command + output) and <obj>.w (distinct
warning/error lines with the tree prefix removed, for diffing two trees).
Usage (under compile_tu.cmd): py -3 -I compile_tu.py <tree name> <out dir> <source substring> [...]"""
import re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
B = ROOT / 'build' / 'motorstorm-t62-font-c529ab0'
BS = '\\'
tree, out = sys.argv[1], Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
txt = (B / 'build.ninja').read_text(encoding='utf-8', errors='replace')
objs = re.findall(r'^build (\S+\.obj): \S+_COMPILER\S* (\S+)', txt, re.M)
fails = 0
for want in sys.argv[3:]:
    w = want.replace('/', BS).lower()
    hit = [(o, s) for o, s in objs if s.replace('$:', ':').replace('/', BS).lower().endswith(w)]
    if len(hit) != 1:
        print(f'{want}: {len(hit)} matching objects'); fails += 1; continue
    obj = hit[0][0].replace('$:', ':')
    cmd = subprocess.run(['ninja', '-C', str(B), '-t', 'commands', '-s', obj], capture_output=True, text=True).stdout.strip()
    dst = out / Path(obj).name
    new = cmd.replace(obj, str(dst)).replace(obj.replace(BS, '/'), str(dst))
    new = re.sub(r'ps3recomp-t62(?=[\\/"\s])', tree, new)
    new = re.sub(r'\s-MF\s+\S+', '', re.sub(r'\s-MD\b', '', new))
    if str(dst) not in new or (tree != 'ps3recomp-t62' and tree not in new):
        print(f'{want}: could not redirect'); fails += 1; continue
    r = subprocess.run(new, cwd=B, shell=True, capture_output=True, text=True)
    log = r.stdout + r.stderr
    dst.with_suffix('.log').write_text(new + '\n' + log, encoding='utf-8')
    warn = sorted(set(re.sub(r':\d+:\d+:', ':', re.sub(r'^.*?[\\/]ps3recomp-t\d+[a-z]*[\\/]', '', l))
                      for l in log.splitlines() if 'warning:' in l or 'error' in l.lower()))
    dst.with_suffix('.w').write_text('\n'.join(warn), encoding='utf-8')
    ok = r.returncode == 0 and dst.exists()
    fails += not ok
    print(f'{"OK  " if ok else "FAIL"} {tree} {Path(obj).name}: exit {r.returncode}, {len(warn)} distinct warning/error lines')
print('RESULT', 'PASS' if not fails else f'FAIL {fails}')
sys.exit(1 if fails else 0)
