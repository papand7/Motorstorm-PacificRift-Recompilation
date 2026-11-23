r"""roadto60_next: decide a build A/B from race_metrics.py rows (offline, no launch).

usage: py -3 ab_compare.py --a ksr68,ksr71,ksr72,ksr75 --b ksr69,ksr70,ksr73,ksr74 [--a-sha 714690f6] [--b-sha 33253d9d]
       [--json out.json]
Runs race_metrics.one() on each tag. A run is VALID when quality == 'OK' or 'WARN' (WARN only for 4-6 non-game
cores; it is listed), its exe hash starts with the arm's pin, and the race window is >= 45 s.
Decision (both must hold, else "no detectable difference"):
  1. >= 3 valid runs per arm;
  2. exact one-sided permutation test on per-run fps (all splits of the pooled valid runs): p <= 0.05;
  3. |median fps difference| >= the noise floor = max(1.5 fps, 2 x the larger within-arm fps SD).
Frame-time percentiles (median of [frame-hist] block p50/p90/p99) and the wait budget are reported per arm but do
not decide. P95 needs presentmon.csv (optional)."""
import argparse
import itertools
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import race_metrics as rm  # noqa: E402

KEYS = ['fps', 'draw_fps', 'frame_ms_mean', 'fps_1s_sd', 'fps_1s_p5', 'ft_p50_med', 'ft_p90_med', 'ft_p99_med', 'ft_p99_max',
        'over34_pct', 'main_usleep_ms_f', 'main_evq_ms_f', 'main_hle_ms_f', 'present_wait_ms_f', 'handler_polls_s',
        'main_mcyc_flip_med', 'simpace_late_per_min', 'simpace_lost_ms_per_s', 'pm_p50', 'pm_p95', 'pm_p99']


def valid(r, pin):
    why = []
    if 'error' in r:
        return False, [r['error']]
    if r['quality'] == 'REJECT':
        why += r['quality_reasons']
    if pin and not (r.get('exe_sha256') or '').startswith(pin):
        why.append('exe hash %s != pin %s' % ((r.get('exe_sha256') or '')[:8], pin))
    if (r.get('window_s') or 0) < 45:
        why.append('window < 45 s')
    return not why, why


def summary(rows):
    out = {}
    for k in KEYS:
        xs = [r[k] for r in rows if isinstance(r.get(k), (int, float))]
        if xs:
            out[k] = {'median': round(st.median(xs), 2), 'mean': round(st.mean(xs), 2),
                      'sd': round(st.stdev(xs), 2) if len(xs) > 1 else None, 'n': len(xs)}
    h = [r['host'] for r in rows]
    for k in ('non_game_cores', 'game_cores', 'gpu_util_pct', 'sys_busy_pct'):
        xs = [x[k] for x in h if x.get(k) is not None]
        if xs:
            out['host_' + k] = round(st.mean(xs), 2)
    return out


def perm_p(a, b):
    """one-sided exact permutation p for mean(b) - mean(a) >= observed (b = candidate)."""
    pool = a + b
    obs = st.mean(b) - st.mean(a)
    n, k = len(pool), len(b)
    hit = tot = 0
    for idx in itertools.combinations(range(n), k):
        bb = [pool[i] for i in idx]
        aa = [pool[i] for i in range(n) if i not in idx]
        tot += 1
        hit += (st.mean(bb) - st.mean(aa)) >= obs - 1e-12
    return hit / tot, obs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', required=True)
    ap.add_argument('--b', required=True)
    ap.add_argument('--a-sha', default='714690f6')
    ap.add_argument('--b-sha', default='33253d9d')
    ap.add_argument('--json')
    o = ap.parse_args()
    arms = {}
    for name, tags, pin in (('A', o.a, o.a_sha), ('B', o.b, o.b_sha)):
        rows, rej = [], []
        for t in [x for x in tags.split(',') if x]:
            r = rm.one(t)
            ok, why = valid(r, pin)
            (rows if ok else rej).append(r if ok else {'tag': t, 'why': why, 'fps': r.get('fps')})
        arms[name] = {'valid': rows, 'rejected': rej}
    res = {'arms': {}}
    for n in 'AB':
        res['arms'][n] = {'valid_tags': [r['tag'] for r in arms[n]['valid']], 'rejected': arms[n]['rejected'],
                          'summary': summary(arms[n]['valid'])}
    fa = [r['fps'] for r in arms['A']['valid']]
    fb = [r['fps'] for r in arms['B']['valid']]
    verdict = 'INSUFFICIENT (need >= 3 valid runs per arm)'
    if len(fa) >= 3 and len(fb) >= 3:
        p, d = perm_p(fa, fb)
        dmed = st.median(fb) - st.median(fa)
        floor = max(1.5, 2 * max(st.stdev(fa), st.stdev(fb)))
        res.update(perm_p_one_sided=round(p, 4), mean_diff_fps=round(d, 2), median_diff_fps=round(dmed, 2), noise_floor_fps=round(floor, 2))
        if p <= 0.05 and abs(dmed) >= floor:
            verdict = 'B FASTER' if dmed > 0 else 'B SLOWER'
        else:
            p2, _ = perm_p(fb, fa)
            res['perm_p_reverse'] = round(p2, 4)
            if p2 <= 0.05 and abs(dmed) >= floor:
                verdict = 'B SLOWER'
            else:
                verdict = 'NO DETECTABLE DIFFERENCE (below noise or not significant)'
    res['verdict'] = verdict
    print(json.dumps(res, indent=1))
    if o.json:
        Path(o.json).write_text(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
