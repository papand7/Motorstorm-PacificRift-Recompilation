"""T37 Phase 4 on the real retail modules (private inputs, offline, no launch).

Builds tests/test_spu_reloc_job.c with all lifted retail modules
(generated/analysis/t37/lift, from tools/lift_wws_reloc.py) and runs its
`fuzz` differential on every lifted function that can run to completion from
a random state (tests/test_spu_reloc_job.fuzzable): interpreted vs relocatable
lift through the real dispatcher, all GPRs and LS compared byte for byte.

  python generated/analysis/t37/fuzz_retail.py [trials] [base ...]
Compiler as for tests/test_spu_reloc_job.py ($CC, $T37_CFLAGS, $T37_LIFTED_CFLAGS).
"""
import collections, json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]  # T70: tools/ is one level deeper
T37 = ROOT / 'ps3recomp-t70'  # T70: runtime under test
sys.path.insert(0, str(T37 / 'tests'))
sys.path.insert(0, str(T37 / 'tools'))
from test_spu_reloc_job import build, fuzzable  # noqa: E402

trials = sys.argv[1] if len(sys.argv) > 1 else '40'
bases = [int(b, 16) for b in sys.argv[2:] if not b.startswith('-')] or [0x15C00]
lift = ROOT / 'generated' / 'spu_raw' / 'wws_reloc'  # T70: regenerated lift
man = json.load(open(lift / 'wws_reloc_manifest.json'))
lines, per = [], collections.Counter()
for m in man:
    if not m.get('registered'):
        continue
    raw = (ROOT / 'generated' / 'analysis' / 't37' / 'modules' / m['file']).read_bytes()
    stem = m['file'][:-4]
    funcs = json.load(open(lift / f'{stem}.report.json'))['functions']
    for off in fuzzable(raw, m['link_base'], funcs):
        lines.append(f"{m['image_id']} {m['size']:X} {off:X} {ROOT / 'generated' / 'analysis' / 't37' / 'modules' / m['file']}")
        per[m['name']] += 1
work = ROOT / 'scratch' / 't37' / 'fuzz_retail'
work.mkdir(parents=True, exist_ok=True)
(work / 'list.txt').write_text('\n'.join(lines) + '\n')
print(f'{len(lines)} qualifying functions in {len(per)} modules:',
      ', '.join(f'{k} {v}' for k, v in sorted(per.items(), key=lambda x: -x[1])))
if '--count' in sys.argv:
    sys.exit(0)
exe = build(work, lift, os.environ.get('T37_LIFTED_CFLAGS', ''))
env = {k: v for k, v in os.environ.items() if not k.startswith(('SPU_', 'SPURS_', 'PS3_', 'YDKJ_', 'LBP_'))}
rc = 0
for b in bases:
    r = subprocess.run([str(exe), 'fuzz', str(work / 'list.txt'), f'{b:X}', trials],
                       capture_output=True, text=True, env=env, timeout=7200)
    for ln in r.stdout.splitlines():
        if ln.startswith('[FAIL]') or ln.startswith('fuzz '):
            print(ln)
    rc |= r.returncode
sys.exit(rc)
