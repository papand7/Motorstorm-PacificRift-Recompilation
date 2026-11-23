"""Static call/transfer graph of a lifted relocatable Wws module (private analysis).
usage: py -3 callgraph.py <module dir> <prefix> <from-hex>[,..] <to-hex>[,..]
Edges: calls (func_X(ctx); spu_drain_call(ctx, RET)), direct tail transfers (g_spu_trampoline_fn = func_X),
SPU_RET_REG (indirect return, marked 'retreg')."""
import re, sys
from pathlib import Path
d = Path(sys.argv[1]); pre = sys.argv[2]
src = (d / 'spu_recomp.c').read_text(errors='replace')
FN = re.compile(r'^void ' + re.escape(pre) + r'spu_func_([0-9A-F]{8})\(spu_context\* ctx\) \{(.*?)^\}', re.S | re.M)
CALL = re.compile(re.escape(pre) + r'spu_func_([0-9A-F]{8})\(ctx\); spu_drain_call\(ctx, SPU_RA\(0x([0-9A-F]+)u\)\)')
TAIL = re.compile(r'g_spu_trampoline_fn = ' + re.escape(pre) + r'spu_func_([0-9A-F]{8})')
G = {}; RR = {}; CALLS = {}
for m in FN.finditer(src):
    a = int(m.group(1), 16); body = m.group(2)
    calls = [(int(c, 16), int(r, 16)) for c, r in CALL.findall(body)]
    tails = [int(t, 16) for t in TAIL.findall(body)]
    G[a] = set([c for c, _ in calls] + tails); CALLS[a] = calls
    RR[a] = len(re.findall(r'SPU_RET_REG\(ctx, (\d+)\)', body))
def reach(s):
    seen = {s}; st = [s]
    while st:
        x = st.pop()
        for y in G.get(x, ()):
            if y not in seen: seen.add(y); st.append(y)
    return seen
if __name__ == '__main__':
    srcs = [int(x, 16) for x in sys.argv[3].split(',')]
    dsts = [int(x, 16) for x in sys.argv[4].split(',')]
    print('functions', len(G), 'with SPU_RET_REG', sum(1 for v in RR.values() if v))
    for s in srcs:
        r = reach(s)
        print('%05X reaches %d fns;' % (s, len(r)), ' '.join('%05X:%s' % (t, 'Y' if t in r else '-') for t in dsts))
