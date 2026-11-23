MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""print the first N functions of a TU that the promotion pass leaves unchanged for a given reason"""
import sys
sys.path.insert(0, (MS_ROOT + r'\ps3recomp-t188\tools'))
import ppu_regpromo as rp
src = open(sys.argv[1], encoding='latin-1').read()
want, n = sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1
for m in rp._FN_RE.finditer(src):
    new, info = rp.promote_body(m.group(2))
    if new is None and want in info:
        print(m.group(0)[:3000]); print('=====')
        n -= 1
        if not n:
            break
