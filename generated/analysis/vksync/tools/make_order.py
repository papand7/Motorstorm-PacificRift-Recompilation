"""A link order file (lld-link /ORDER:@file) from thread_sampler_incl.py profiles: every function seen
running on the sampled threads (on the stack or as the leaf), hottest first, so the linker packs the
code a frame runs into a few MB instead of leaving it spread over the 400 MB image.

usage: py -3 make_order.py <out.txt> <sample.json> [<sample.json> ...]"""
import json
import sys
from collections import Counter
from pathlib import Path

out = Path(sys.argv[1])
heat = Counter()
for f in sys.argv[2:]:
    d = json.loads(Path(f).read_text())
    for t in d['threads']:
        n = max(1, t['running'])
        for name, c in t.get('incl_all', {}).items():
            heat[name] += c / n
        for name, c in t.get('self_all', {}).items():
            heat[name] += 4.0 * c / n   # where the time is spent counts more than being on the stack
names = [nm for nm, _ in heat.most_common()
         if not nm.startswith(('rva+', 'ntdll', 'KERNEL', 'ucrtbase', 'VCRUNTIME', 'vulkan', 'nvoglv'))
         and '.dll' not in nm and ' ' not in nm]
out.write_text('\n'.join(names) + '\n')
lifted = sum(1 for n in names if 'func_' in n)
print(f'{len(names)} functions ({lifted} lifted) -> {out}')
