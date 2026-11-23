"""Like find_sites_103.py, but compare instruction words with relocation-sensitive fields masked:
b/bl (opcode 18) displacement, bc (16) displacement, and the immediate of lis/addis (15), addi (14),
ori (24) and D-form loads/stores off r2 (TOC). Window: the first N words of the function at the 1.02
address. usage: py -3 find_sites_masked.py <hex addr> ... [--n 24]"""
import pathlib, struct, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import importlib.util
spec = importlib.util.spec_from_file_location('f', pathlib.Path(__file__).parent / 'find_sites_103.py')
src = open(spec.origin).read().split('a, b = segs')[0]
ns = {'__file__': spec.origin}; exec(src, ns)
segs, read, E102, E103 = ns['segs'], ns['read'], ns['E102'], ns['E103']

def mask(w):
    op = w >> 26
    if op == 18: return w & 0xFC000003
    if op == 16: return w & 0xFFFF0003
    if op in (14, 15, 24, 25): return w & 0xFFFF0000
    if op in (32, 34, 36, 38, 40, 48, 50, 52, 54) and ((w >> 16) & 31) == 2: return w & 0xFFFF0000
    return w

args = [a for a in sys.argv[1:] if not a.startswith('--')]
n = int(sys.argv[sys.argv.index('--n') + 1]) if '--n' in sys.argv else 24
args = [a for a in args if a != str(n)]
A, B = segs(E102), segs(E103)
words_b = [(base, struct.unpack(f'>{len(d)//4}I', d[:len(d)//4*4])) for base, d in B]
for arg in args:
    va = int(arg, 16)
    raw = read(A, va, 4 * n)
    pat = [mask(w) for w in struct.unpack(f'>{n}I', raw)]
    hits = []
    for base, ws in words_b:
        mw = None
        first = pat[0]
        for i in range(len(ws) - n):
            if mask(ws[i]) != first: continue
            if all(mask(ws[i + k]) == pat[k] for k in range(1, n)): hits.append(base + 4 * i)
    print(f'{va:08X} -> ' + (f'{hits[0]:08X}' if len(hits) == 1 else f'{len(hits)} hits {[hex(h) for h in hits[:4]]}'))
