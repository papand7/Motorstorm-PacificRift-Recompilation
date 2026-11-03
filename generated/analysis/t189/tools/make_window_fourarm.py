"""Derive window_fourarm.py from real_fourarm.py: named functions (any TUs), DIFF_WINDOW inputs."""
from pathlib import Path
d = Path(__file__).resolve().parent
s = (d / 'real_fourarm.py').read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)


rep("    ap.add_argument('tu')", "    ap.add_argument('fns', help='comma-separated func_XXXXXXXX names')")
rep("""    src = (STG / f'ppu_recomp_{a.tu}.cpp').read_text(encoding='latin-1')
    prelude = src[:src.index('\\nvoid func_') + 1]
    fns = pick(src, a.n, a.seed)""", """    want = a.fns.split(',')
    fns, prelude = [], None
    for f in sorted(STG.glob('ppu_recomp_*.cpp')):
        t = f.read_text(encoding='latin-1')
        if prelude is None:
            prelude = t[:t.index('\\nvoid func_') + 1]
        for m in FN.finditer(t):
            if m.group(1) in want and m.group(1) not in [x for x, _ in fns]:
                fns.append((m.group(1), m.group(0)))
        if len(fns) == len(want):
            break
    fns.sort(key=lambda x: want.index(x[0]))
    a.tu = 'window'""")
rep("    D.MEM_SIZE = 0x08000000", "    D.MEM_SIZE = 0x11000000")
rep("        env = {'DIFF_PTRS': '1', 'DIFF_ONLY': str(i)}", "        env = {'DIFF_WINDOW': '1', 'DIFF_ONLY': str(i)}")
(d / 'window_fourarm.py').write_text(s, encoding='utf-8')
print('ok')
