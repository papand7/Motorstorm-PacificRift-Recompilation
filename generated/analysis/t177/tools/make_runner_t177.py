"""T177 load comparison runner (needs authorization to launch): t170/base169/run_base.py with the T177 exe and five added arms.
Run from the main checkout copy of generated/analysis/t177/tools.
  py -3 generated/analysis/t177/tools/make_runner_t177.py <exe sha256>      write generated/analysis/t177/ab/run_t177.py
  py -3 generated/analysis/t177/ab/run_t177.py prepare r ; launch P|U|W|C|H <tag>
P poll baseline; U wakeups everywhere (T161 D); W wakeups with the heavy-scene gate; C = W + shader cache level 3, cold;
H = C again with the same cache directory, warm. Run C immediately before H and never clear the directory between them."""
import re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
base = ROOT / 'generated' / 'analysis' / 't170' / 'base169' / 'run_base.py'
pin = (sys.argv[1] if len(sys.argv) > 1 else '').lower()
if not re.fullmatch(r'[0-9a-f]{64}', pin):
    raise SystemExit('usage: make_runner_t177.py <exe sha256 of build/motorstorm-t177>')
src = base.read_text(encoding='utf-8')


def sub(old, new):
    global src
    assert src.count(old) == 1, (old[:70], src.count(old))
    src = src.replace(old, new)


sub("'motorstorm-t169'", "'motorstorm-t177'")
sub("PIN = '59019e06b9a39074ea2d47e90dd3c41f0299d73463e610db2ce8fa030011ba08'", f"PIN = '{pin}'")
sub("f't170base-{arm}{tag}'", "f't177-{arm}{tag}'")
sub("FORBIDDEN = (", """_A = ARMS['A'][1]
_WAKE = 'PS3_LWCOND_WAKE'
_STATS = '1:poll_ms=100:stats_ms=1000'
_GATE = _STATS + ':heavy_draws=200'
_CACHE = {'RSX_SHADER_CACHE': '3', 'RSX_SHADER_CACHE_DIR': str(HERE / 'shader_cache')}
ARMS.update({
    'P': ('r', dict(_A)),
    'U': ('r', {**_A, _WAKE: _STATS}),
    'W': ('r', {**_A, _WAKE: _GATE}),
    'C': ('r', {**_A, _WAKE: _GATE, **_CACHE}),
    'H': ('r', {**_A, _WAKE: _GATE, **_CACHE}),
})
FORBIDDEN = (""")
out = HERE.parent / 'ab'
out.mkdir(exist_ok=True)
(out / 'cpath_sites.cfg').write_bytes((ROOT / 'generated' / 'analysis' / 't170' / 'base169' / 'cpath_sites.cfg').read_bytes())
(out / 'run_t177.py').write_text(src, encoding='utf-8')
print('wrote', out / 'run_t177.py', 'pin', pin)
