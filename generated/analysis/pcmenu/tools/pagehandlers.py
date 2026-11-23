# Private read-only: page-level handler slots (P+0x28..0x6C) of a .gui page as action graphs.
# usage: py -3 tools/pagehandlers.py <page.gui>   (from generated/analysis/pcmenu)
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from page import Page
from actions import handler


def graph(p, h):
    e, x, acts = handler(p, h); out = []; seen = set()
    def walk(i, ind, lab=''):
        if i == -1: return
        if i in seen: out.append('  ' * ind + lab + f'goto[{i}]'); return
        seen.add(i); nm, args, succ = acts[i]
        out.append('  ' * ind + lab + f'{nm}({", ".join(map(str, args))})')
        if len(succ) == 1: walk(succ[0], ind)
        else:
            labs = {2: ['F:', 'T:'], 3: ['<=a:', 'mid:', '>=b:']}.get(len(succ), [f'o{k}:' for k in range(len(succ))])
            for k, s in enumerate(succ): walk(s, ind + 1, labs[k] + ' ')
    walk(e, 0); return out


if __name__ == '__main__':
    p = Page(sys.argv[1])
    print('nWidgets', p.u(0))
    for o in range(0x28, 0x70, 4):
        if o in p.relset:
            g = [l for l in graph(p, p.u(o)) if 'AnimationChannel' not in l]
            print(f'P+{o:#x}: ' + ' | '.join(g)[:500])
