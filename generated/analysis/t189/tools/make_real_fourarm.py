MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""Derive t189/tools/real_fourarm.py from t188/tools/real_bench.py (private)."""
from pathlib import Path
src = Path((MS_ROOT + r'\generated\analysis\t188\tools\real_bench.py')).read_text(encoding='utf-8')
src = src.replace("ps3recomp-t188/tools", "ps3recomp-t189/tools")
src = src.replace('"""T188 (private)', '"""T189 four-arm version of T188 (private)')
a = src.index("    base_src = prelude + body")
b = src.index("    ran = [r for r in rows if 'speedup' in r]")
new = '''    base_src = prelude + body
    import bench_ppu_fourarm as F
    arms = ('A', 'B', 'C', 'C2', 'D')
    exes, info = F.build_arms(out, hdr, base_src, prog, arms)
    st = F.static_for(info, names)
    rows = []
    for i, nm in enumerate(names):
        env = {'DIFF_PTRS': '1', 'DIFF_ONLY': str(i)}
        tr = {}
        for v in exes:
            try:
                tr[v] = D.run(exes[v], 4, 0, env_extra=env)
            except subprocess.TimeoutExpired:
                tr[v] = ('timeout', '')
        same = all(tr[v] == tr['A'] for v in exes)
        r = {'fn': nm, 'same': same, 'rc': tr['A'][0]}
        if same and tr['A'][0] == 0:
            tm = F.time_arms(exes, (a.iters, a.reps), a.runs, env)
            if all(tm[v] for v in exes):
                for v in exes:
                    r[v] = tm[v]['median_ms']
                    r['cv_' + v] = tm[v]['cv']
        rows.append(r)
        print(json.dumps(r), flush=True)
    timed = [r for r in rows if 'A' in r]
    for v in arms[1:]:
        g = statistics.geometric_mean([r['A'] / r[v] for r in timed]) if timed else float('nan')
        lo = min((r['A'] / r[v] for r in timed), default=0)
        hi = max((r['A'] / r[v] for r in timed), default=0)
        print(f'{v} vs A: geomean speedup {g:.3f} (min {lo:.2f}, max {hi:.2f}) over {len(timed)} functions')
    if timed:
        g = statistics.geometric_mean([r['B'] / r['D'] for r in timed])
        print(f'D vs B (promotion on top of inline stores): geomean {g:.3f}')
    print(f'functions {len(rows)} timed {len(timed)} mismatches {sum(not r["same"] for r in rows)}')
    print('static (x64, ctx, stk, call, push):', {v: st[v] for v in arms})
    print('object bytes / compile s:', {v: (info[v]['obj_bytes'], round(info[v]['compile_s'], 2)) for v in arms})
    (out / 'result.json').write_text(json.dumps({'rows': rows}, indent=1))


if __name__ == '__main__':
    main()
'''
src = src[:a] + new
Path((MS_ROOT + r'\generated\analysis\t189\tools\real_fourarm.py')).write_text(src, encoding='utf-8')
print('ok')
