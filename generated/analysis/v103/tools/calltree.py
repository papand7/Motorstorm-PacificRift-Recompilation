"""Static call tree of a lifted PPU function in a staging tree: its transitive callees, the HLE imports and
syscalls they reach, indirect calls, and the function's own direct callers.
usage: py -3 calltree.py <staging dir> <func hex, e.g. 00793988> [max depth=12]"""
import collections
import pathlib
import re
import sys

st = pathlib.Path(sys.argv[1])
root = 'func_' + sys.argv[2].upper().zfill(8)
maxd = int(sys.argv[3]) if len(sys.argv) > 3 else 12
FN = re.compile(r'^void (func_[0-9A-F]{8})\(ppu_context\* ctx\) \{')
CALL = re.compile(r'\b(func_[0-9A-F]{8})\(ctx\)')
HLE = re.compile(r'ps3_hle_call\(ctx, *(0x[0-9A-Fa-f]+)')
SYSC = re.compile(r'lv2_syscall\(ctx[^)]*\)|ctx->gpr\[11\] = (\d+);\s*lv2_syscall')

calls = collections.defaultdict(set)
hle = collections.defaultdict(set)
indirect = collections.Counter()
syscalls = collections.defaultdict(set)
for f in sorted(st.glob('ppu_recomp_*.cpp')):
    cur = None
    for line in f.read_text(encoding='latin-1').split('\n'):
        m = FN.match(line)
        if m:
            cur = m.group(1)
            continue
        if not cur:
            continue
        for c in CALL.findall(line):
            if c != cur:
                calls[cur].add(c)
        for h in HLE.findall(line):
            hle[cur].add(h)
        if 'ps3_indirect_call' in line:
            indirect[cur] += 1
        if 'lv2_syscall' in line:
            syscalls[cur].add(line.strip()[:80])

callers = [f for f, cs in calls.items() if root in cs]
seen = {root: 0}
q = collections.deque([root])
while q:
    f = q.popleft()
    if seen[f] >= maxd:
        continue
    for c in calls.get(f, ()):
        if c not in seen:
            seen[c] = seen[f] + 1
            q.append(c)
print(f'{root}: {len(seen)} functions reachable (depth <= {maxd}); direct callers: {sorted(callers)}')
allh = collections.Counter(h for f in seen for h in hle.get(f, ()))
print('HLE imports reached:', dict(allh.most_common(30)))
print('functions with indirect calls:', sum(1 for f in seen if indirect[f]), 'sites:', sum(indirect[f] for f in seen))
sc = sorted({s for f in seen for s in syscalls.get(f, ())})
print('syscall sites:', len(sc))
for s in sc[:15]:
    print('  ', s)
