"""usage: py -3 gdis.py <start> [end|fn] [toc: main|gui]   disassemble with trampoline resolution"""
import sys
sys.path.insert(0, __import__('os').path.dirname(__file__))
from common import *
s = int(sys.argv[1], 16)
e = FEND.get(s) if len(sys.argv) < 3 or sys.argv[2] == 'fn' else int(sys.argv[2], 16)
if e is None: e = FEND[fn(s)]
toc = GTOC if len(sys.argv) > 3 and sys.argv[3] == 'gui' else TOC
print('\n'.join(dis(s, e, toc)))
