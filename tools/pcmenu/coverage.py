# Read-only (no game data included): walk the full page structure using the decoded layout and check that
# (a) every pointer field reached is in the reloc table, (b) every reloc entry is reached.
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from page import Page
REC = 0x8C
WSLOTS = [0x34,0x38,0x3C,0x40,0x44,0x48,0x4C,0x54,0x58,0x5C,0x60]
def walk_page(p):
    reached = set(); missing = []; unk = collections.Counter()
    def ptr(o, what):
        v = p.u(o)
        if v == 0: return None
        if o in p.relset: reached.add(o); return v
        missing.append((hex(o), what, hex(v))); return None
    def strs(arr, n, what):
        for i in range(n): ptr(arr+4*i, what)
    def hand(h):
        n = p.u(h+4); ap = ptr(h+12, 'h.actions')
        for i in range(n):
            a = ap + 20*i
            ptr(a, 'a.name'); na = p.u(a+4); ag = ptr(a+8, 'a.args')
            if ag: strs(ag, na, 'a.arg')
            ptr(a+16, 'a.succ')
    def widget(r):
        ptr(r, 'w.geo'); ptr(r+4, 'w.blk2'); ptr(r+0x88, 'w.name')
        for s in WSLOTS:
            h = ptr(r+s, f'w.slot{s:#x}')
            if h: hand(h)
        cls = p.u(r+0x64); b = ptr(r+0x84, 'w.class')
        if b is not None:
            if cls == 0: ptr(b+4, 'text.font')
            elif cls == 1: ptr(b+12, 'img.shader')
            elif cls == 10: ptr(b+0x24, 'table.font')
            elif cls == 6: ptr(b+8, 'cls6.name')
            else: pass
        n = p.u(r+0x2C); ca = ptr(r+0x30, 'w.children')
        if ca and n:
            for i in range(n): widget(ca + REC*i)
    n = p.u(0); wa = ptr(4, 'p.widgets')
    for i in range(n): widget(wa + REC*i)
    la = ptr(0xC, 'p.langs'); strs(la, p.u(8), 'p.lang')
    ptr(0x14, 'p.modes')
    ca = ptr(0x1C, 'p.chans')
    for i in range(p.u(0x18)): ptr(ca+12*i, 'ch.name'); ptr(ca+12*i+8, 'ch.keys')
    fa = ptr(0x24, 'p.fonts'); strs(fa, p.u(0x20), 'p.font')
    for s in range(0x28, 0x70, 4):
        h = ptr(s, f'p.slot{s:#x}')
        if h: hand(h)
    return reached, missing
if __name__ == '__main__':
    G = sys.argv[1]; tot = collections.Counter(); bad = []
    unreached_kinds = collections.Counter()
    for fn in sorted(os.listdir(G)):
        if not fn.startswith('gui_'): continue
        p = Page(os.path.join(G, fn))
        reached, missing = walk_page(p)
        un = p.relset - reached
        tot['files'] += 1; tot['reloc'] += len(p.relset); tot['reached'] += len(reached); tot['missing'] += len(missing)
        if missing or un: bad.append((fn, len(un), missing[:3], sorted(un)[:5]))
    print(tot); print('files with gaps:', len(bad))
    for b in bad[:15]: print(' ', b)
