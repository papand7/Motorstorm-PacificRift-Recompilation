# Read-only (no game data included): inventory of action names over all pages (via the reloc-verified handler slots).
import sys, os, collections, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from page import Page
from widgets import all_widgets
G = sys.argv[1] if len(sys.argv) > 1 else None
WSLOTS = [0x34,0x38,0x3C,0x40,0x44,0x48,0x4C,0x54,0x58,0x5C,0x60]
def handler(p, h):
    entry, n, x, ap = p.u(h), p.u(h+4), p.u(h+8), p.u(h+12)
    acts = []
    for i in range(n):
        a = ap + 20*i
        nm = p.s(p.u(a)); na = p.u(a+4); ag = p.u(a+8); ns = p.u(a+12); sp = p.u(a+16)
        args = [p.s(p.u(ag+4*k)) for k in range(na)] if na else []
        succ = [p.i(sp+4*k) for k in range(ns)] if ns else []
        acts.append((nm, args, succ))
    return entry, x, acts
def page_handlers(p):
    out = []
    for o in range(0x28, 0x70, 4):
        if o in p.relset: out.append(('page', f'P+{o:#x}', p.u(o)))
    for depth, k, r, parent in all_widgets(p):
        nm = p.s(p.u(r+0x88))
        for s in WSLOTS:
            if (r+s) in p.relset: out.append((nm, f'W+{s:#x}', p.u(r+s)))
    return out
if __name__ == '__main__':
    cnt = collections.Counter(); ex = {}; nargs = collections.defaultdict(set); xs = collections.Counter(); slots = collections.Counter()
    for fn in sorted(os.listdir(G)):
        if not fn.startswith('gui_'): continue
        p = Page(os.path.join(G, fn))
        for owner, slot, h in page_handlers(p):
            slots[slot] += 1
            e, x, acts = handler(p, h); xs[x] += 1
            for nm, args, succ in acts:
                cnt[nm] += 1; nargs[nm].add((len(args), len(succ)))
                ex.setdefault(nm, (fn, owner, slot, args))
    print('slots', sorted(slots.items())); print('handler +8 values', xs)
    for nm, c in sorted(cnt.items()): print(f'{c:5} {nm:34} (nargs,nsucc)={sorted(nargs[nm])} e.g. {ex[nm]}')
