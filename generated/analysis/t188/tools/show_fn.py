"""print one lifted function: show_fn.py func_XXXXXXXX [file.cpp | staging-dir]"""
import re, sys
from pathlib import Path
name = sys.argv[1]
st = Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).resolve().parents[3] / 'ppu-t173-staging')
pat = re.compile(r'^void ' + name + r'\(ppu_context\* ctx\) \{.*?^\}\n', re.M | re.S)
for f in ([st] if st.is_file() else sorted(st.glob('ppu_recomp_*.cpp'))):
    d = f.read_text(encoding='latin1')
    m = pat.search(d)
    if m:
        print('//', f.name); print(m.group(0)); break
