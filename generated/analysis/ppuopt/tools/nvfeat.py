"""Private (ppuopt): static features of lifted functions for the --nv-locals selection
heuristic, joined with the measured N-arm speedups (wl2 results).

  nvfeat.py <out.json> [fn ...]   (no fns: every function with a measurement)"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nvtext  # noqa: E402
import ppu_lifter  # noqa: E402

AN = HERE.parent
RES = AN / 'work' / 'results'

CALL = re.compile(r"\w*func_[0-9A-Fa-f]{8}\(ctx\)|ps3_indirect_call|ps3_hle_call|lv2_syscall")
LABEL = re.compile(r"^\s*(loc_[0-9A-Fa-f]{8}):")
GOTO = re.compile(r"\bgoto (loc_[0-9A-Fa-f]{8});")
G = re.compile(r"ctx->gpr\[(\d+)\]")
F = re.compile(r"ctx->fpr\[(\d+)\]")
V = re.compile(r"ctx->vr\[(\d+)\]")


def features(lines):
    n = sum(1 for l in lines if l.strip() and not LABEL.match(l))
    calls = sum(len(CALL.findall(l)) for l in lines)
    gp, fp, vr = set(), set(), set()
    for l in lines:
        gp.update(G.findall(l)); fp.update(F.findall(l)); vr.update(V.findall(l))
    # loop lines: lines inside a backward-goto region; call-free loop lines
    pos, xc = {}, [0]
    for i, l in enumerate(lines):
        m = LABEL.match(l)
        if m:
            pos[m.group(1)] = i
        xc.append(xc[-1] + (1 if CALL.search(l) else 0))
    inloop = [False] * len(lines)
    infree = [False] * len(lines)
    for j, l in enumerate(lines):
        for m in GOTO.finditer(l):
            i = pos.get(m.group(1))
            if i is not None and i <= j:
                free = xc[j + 1] - xc[i] == 0
                for k in range(i, j + 1):
                    inloop[k] = True
                    if free:
                        infree[k] = True
    return {'stmts': n, 'calls': calls, 'call_per100': round(100.0 * calls / max(n, 1), 2),
            'gpr': len(gp), 'fpr': len(fp), 'vr': len(vr), 'regs': len(gp) + len(fp) + len(vr),
            'loop_frac': round(sum(inloop) / max(len(lines), 1), 3),
            'free_loop_frac': round(sum(infree) / max(len(lines), 1), 3),
            'free_loop_lines': sum(infree),
            'callfree_loop': ppu_lifter.has_callfree_loop(lines)}


def measured():
    sp = {}
    for f in RES.glob('*.json'):
        if f.name.endswith('_names.json'):
            continue
        for r in json.loads(f.read_text()):
            if 'N' in r['min']:
                sp.setdefault(r['fn'], []).append(r['min']['B'] / r['min']['N'])
    log = AN / 'work' / 'wl2_hot_time_part1.log'
    for l in log.read_text().splitlines():
        m = re.match(r'(func_\w+) B=([\d.]+) .*? N=([\d.]+) ', l)
        if m:
            sp.setdefault(m.group(1), []).append(float(m.group(2)) / float(m.group(3)))
    return sp


def main():
    import wl2
    out = Path(sys.argv[1])
    sp = measured()
    names = sys.argv[2:] or sorted(sp)
    _pre, fns = wl2.fetch(names)
    rows = []
    for n in names:
        if n not in fns:
            continue
        r = {'fn': n, **features(fns[n][1])}
        if n in sp:
            r['N'] = round(sum(sp[n]) / len(sp[n]), 3)
            r['N_runs'] = [round(x, 3) for x in sp[n]]
        rows.append(r)
    out.write_text(json.dumps(rows, indent=1))
    keys = ['stmts', 'calls', 'call_per100', 'gpr', 'fpr', 'vr', 'loop_frac', 'free_loop_frac', 'free_loop_lines']
    print('fn            N     ' + ' '.join(f'{k[:9]:>9}' for k in keys))
    for r in sorted(rows, key=lambda r: r.get('N', 0)):
        print(f"{r['fn'][5:]} {r.get('N', 0):5.3f} " + ' '.join(f'{r[k]:>9}' for k in keys))


if __name__ == '__main__':
    main()
