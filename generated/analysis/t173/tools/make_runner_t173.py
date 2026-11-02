"""T173 game-validation runner (NOT run by T173): arm A of the T170 benchmark with the T173 exe, pinned.
Derived from t170/base169/run_base.py (itself ab/run_t170.py arm A with a guest-crash stop 3 s after an `unresolved indirect call` or a
null-page write). Same route, flags and environment as T170 arm A; the only difference from that run is the executable.
  py -3 generated/analysis/t173/tools/make_runner_t173.py <exe sha256>      write generated/analysis/t173/ab/run_t173.py
  py -3 generated/analysis/t173/ab/run_t173.py prepare r ; envcheck ; dryrun A ; launch A V1       (the launch needs authorization)"""
import re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
base = ROOT / 'generated' / 'analysis' / 't170' / 'base169' / 'run_base.py'
pin = (sys.argv[1] if len(sys.argv) > 1 else '').lower()
if not re.fullmatch(r'[0-9a-f]{64}', pin):
    raise SystemExit('usage: make_runner_t173.py <exe sha256 of build/motorstorm-t173>')
src = base.read_text(encoding='utf-8')


def sub(old, new):
    global src
    assert src.count(old) == 1, (old[:70], src.count(old))
    src = src.replace(old, new)


sub("'motorstorm-t169'", "'motorstorm-t173'")
sub("PIN = '59019e06b9a39074ea2d47e90dd3c41f0299d73463e610db2ce8fa030011ba08'", f"PIN = '{pin}'")
sub("f't170base-{arm}{tag}'", "f't173-{arm}{tag}'")
out = HERE.parent / 'ab'
out.mkdir(exist_ok=True)
(out / 'cpath_sites.cfg').write_bytes((ROOT / 'generated' / 'analysis' / 't170' / 'base169' / 'cpath_sites.cfg').read_bytes())
(out / 'run_t173.py').write_text(src, encoding='utf-8')
print('wrote', out / 'run_t173.py', 'pin', pin)
