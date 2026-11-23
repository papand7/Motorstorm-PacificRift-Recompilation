# Read-only (no game data included): recursive widget dump for a MotorStorm PR .gui page segment.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from page import Page
REC = 0x8C
def walk(p, arr, cnt, depth, out, parent=None):
    for k in range(cnt):
        r = arr + REC*k
        out.append((depth, k, r, parent))
        typ, nc, ca = p.u(r+8), p.u(r+0x2C), p.u(r+0x30)
        if nc and nc < 256 and ca and (r+0x30) in p.relset:
            walk(p, ca, nc, depth+1, out, r)
    return out
def all_widgets(p): return walk(p, p.u(4), p.u(0), 0, [])
if __name__ == '__main__':
    p = Page(sys.argv[1]); full = len(sys.argv) > 2 and sys.argv[2] == 'full'
    for depth, k, r, parent in all_widgets(p):
        nm = p.s(p.u(r+0x88))
        g = p.u(r)
        geo = ' '.join(f'{p.f(g+4*j):.4g}' for j in range(7)) if g else '-'
        print(f"{'  '*depth}[{k}] @{r:#x} {nm!r} type={p.u(r+8)} sel={[p.i(r+o) for o in (0xc,0x10,0x14)]} nchild={p.u(r+0x2C)} geo=({geo})")
        if full:
            for o in range(0, REC, 4): print(f"{'  '*depth}      +{o:#04x} {p.word(r+o)}")
