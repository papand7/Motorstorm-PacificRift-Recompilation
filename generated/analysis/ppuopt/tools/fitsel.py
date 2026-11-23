"""Private (ppuopt): evaluate --nv-locals selection policies on measured functions.

Policy outcome per function: not selected -> 1.0 (plain); vr > vrmax -> the X arm
(no vector locals); else the N arm. Fit set = training + held-out 1; validation =
held-out 2 (work/results/wl2_h2.json, measured with B, N and X)."""
import json
import statistics
from pathlib import Path

W = Path(__file__).resolve().parents[1] / 'work'


def ratios(files, arm):
    out = {}
    for f in files:
        p = W / 'results' / f
        if not p.exists():
            continue
        for r in json.loads(p.read_text()):
            if arm in r['min']:
                out.setdefault(r['fn'], []).append(r['min']['B'] / r['min'][arm])
    return {k: statistics.geometric_mean(v) for k, v in out.items()}


def dataset(featfiles, nfiles, xfiles, extraN=None):
    feats = {}
    for f in featfiles:
        for r in json.loads((W / f).read_text()):
            feats[r['fn']] = r
    N = ratios(nfiles, 'N')
    if extraN:
        for k, v in extraN.items():
            N.setdefault(k, v)
    X = ratios(xfiles, 'X')
    rows = []
    for fn, r in feats.items():
        if fn in N:
            rows.append({**r, 'Nm': N[fn], 'Xm': X.get(fn)})
    return rows


def outcome(r, sel, vrmax):
    if not sel(r):
        return 1.0
    if r['vr'] > vrmax:
        return r['Xm'] if r['Xm'] is not None else None
    return r['Nm']


def evaluate(rows, sel, vrmax, name):
    vals, bad, miss = [], [], 0
    for r in rows:
        o = outcome(r, sel, vrmax)
        if o is None:
            miss += 1
            continue
        vals.append(o)
        if o < 0.97:
            bad.append((round(o, 3), r['fn'][5:]))
    g = statistics.geometric_mean(vals)
    print(f"{name:44s} n={len(vals)} (no X: {miss}) geo={g:.4f} min={min(vals):.3f} "
          f"below.97={len(bad)} {sorted(bad)}")
    return g, min(vals), bad


SELECTORS = {
    'all': lambda r: True,
    'no fpr&dense calls': lambda r: not (r['fpr'] > 0 and r['call_per100'] >= 8),
    'calls<=20 or freeloop': lambda r: r['calls'] <= 20 or r['free_loop_frac'] > 0.1,
    'not (fpr>=9 and calls>0 and no freeloop)': lambda r: not (r['fpr'] >= 9 and r['calls'] > 0 and r['free_loop_frac'] < 0.1),
}

if __name__ == '__main__':
    import sys
    p1 = json.loads((W / 'feat_train.json').read_text())
    trainN = {r['fn']: r['N'] for r in p1}
    fit = dataset(['feat_train.json', 'feat_held.json'],
                  ['wl2_held_s1.json', 'wl2_held_s2.json', 'wl2_vr.json'], ['wl2_vr.json'], trainN)
    print('== fit (train + held-out 1)')
    for vm in (99, 8, 4):
        for k, s in SELECTORS.items():
            evaluate(fit, s, vm, f'vrmax={vm} {k}')
    if (W / 'feat_h2.json').exists() and (W / 'results' / 'wl2_h2.json').exists():
        val = dataset(['feat_h2.json'], ['wl2_h2.json'], ['wl2_h2.json'])
        print('== validation (held-out 2)')
        for vm in (99, 8, 4):
            for k, s in SELECTORS.items():
                evaluate(val, s, vm, f'vrmax={vm} {k}')
