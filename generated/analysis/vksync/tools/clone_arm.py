"""clone_arm.py <src tag> <new tag> <note> [KEY=VALUE ...] [-KEY ...]: copy a K_BY_TAG arm of run_vk.py
under a new tag (paths containing the tag renamed), set or drop env keys, and append it to ORDER.
usage: py -3 clone_arm.py k253 k283 "1.03 dust check" RSX_DUST_FLOOR=6 -MSPR_PATCH"""
import ast
import re
import sys
from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
src, new, note = sys.argv[1], sys.argv[2], sys.argv[3]
s = p.read_text(encoding='utf-8')
L = s.split('\n')
i = next(k for k, l in enumerate(L) if l.startswith(f"K_BY_TAG['{src}']"))
last = max(k for k, l in enumerate(L) if l.startswith("K_BY_TAG['"))
line = L[i].split('   #')[0].replace(src, new)
for a in sys.argv[4:]:
    if a.startswith('-'):
        line = re.sub(r", '" + re.escape(a[1:]) + r"': r?'[^']*'", '', line)
    else:
        k, v = a.split('=', 1)
        line = re.sub(r", '" + re.escape(k) + r"': r?'[^']*'", '', line)
        line = line.replace("'RSX_HDR': '0'", "'RSX_HDR': '0', '" + k + "': r'" + v + "'", 1)
L.insert(last + 1, line + f"   # K{new}: {note}")
s = '\n'.join(L)
if "'Yy1']" in s:
    s = re.sub(r"'Yy1'\]", f"'K{new}', 'Yy1']", s, count=1)
ast.parse(s)
p.write_text(s, encoding='utf-8', newline='\n')
print('ok', new)
