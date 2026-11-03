#!/usr/bin/env python3
"""T188 (private): real lifted MotorStorm functions, baseline vs promoted, in the
ps3recomp-t188 difftest fixture. Lifted code: never committed.

  real_bench.py <TU NNN> [--n 24] [--seed 1] [--reps 7] [--runs 3] [--inline] [--out dir]

Picks --n functions (seeded) from generated/ppu-t173-staging/ppu_recomp_<NNN>.cpp that
contain a loop (a backward goto) and 20..400 statements, builds one TU with the TU's
helper prelude + those bodies (every other func_* a fixture stub that mutates the state
like a callee), compiles it with the staging header twice (baseline, promoted; same
flags as the game build), and for each function:
  - differential: DIFF_PTRS=1 (registers/data are pointers into a data window),
    4 seeds; transcripts must match (or both fault/time out the same way);
  - timing: best of --reps x --runs alternating processes."""
import argparse, json, random, re, statistics, subprocess, sys, time
from pathlib import Path

T = Path(__file__).resolve().parents[1]
M = T.parents[2]
sys.path.insert(0, str(M / 'ps3recomp-t188/tools'))
import ppu_difftest as D      # noqa: E402
import ppu_regpromo as rp     # noqa: E402

STG = M / 'generated/ppu-t173-staging'
FN = re.compile(r'^void (func_[0-9A-F]{8})\(ppu_context\* ctx\) \{.*?^\}\n', re.M | re.S)


def pick(src, n, seed):
    cands = []
    for m in FN.finditer(src):
        body = m.group(0)
        lines = body.count('\n')
        if not 20 <= lines <= 400:
            continue
        labels = {l: i for i, l in enumerate(re.findall(r'^(loc_[0-9A-F]{8}):', body, re.M))}
        pos = {mm.group(1): mm.start() for mm in re.finditer(r'^(loc_[0-9A-F]{8}):', body, re.M)}
        loop = any(g in pos and pos[g] < mm.start() for mm in re.finditer(r'goto (loc_[0-9A-F]{8});', body)
                   for g in [mm.group(1)])
        if loop and 'VM_RAW' not in body and '&ctx->vr' not in body and 'vmx_' not in body:
            cands.append((m.group(1), body))
    rng = random.Random(seed)
    rng.shuffle(cands)
    return cands[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tu')
    ap.add_argument('--n', type=int, default=24)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--reps', type=int, default=7)
    ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--iters', type=int, default=200)
    ap.add_argument('--inline', action='store_true')
    ap.add_argument('--sync', action='store_true', help='store_sync policy (out-of-line stores)')
    ap.add_argument('--cold', action='store_true', help='both builds with PPU_COLD_CALLS')
    ap.add_argument('--out', default=str(T / 'scratch/real'))
    a = ap.parse_args()
    src = (STG / f'ppu_recomp_{a.tu}.cpp').read_text(encoding='latin-1')
    prelude = src[:src.index('\nvoid func_') + 1]
    fns = pick(src, a.n, a.seed)
    names = [f for f, _ in fns]
    body = ''.join(b + '\n' for _, b in fns)
    called = set(re.findall(r'\b(func_[0-9A-F]{8})\b', body)) - set(names)
    hdr = (STG / 'ppu_recomp.h').read_text(encoding='latin-1')
    # the cold-call thunks of the current lifter header, so --cold and the inline-store block work
    import ppu_lifter
    hp = ppu_lifter.HEADER_PREAMBLE
    blk = hp[hp.index('/* T152 page gates: begin */'):hp.index('/* T152 page gates: end */') + 26] + '\n'
    hdr = hdr.replace('\r\n', '\n')
    old = ('#ifdef __cplusplus\n}\n#endif\nstatic inline int vm_inl_ok(uint32_t ea, uint32_t n)\n{\n'
           '    return __builtin_expect(vm_inline_ok, 1) && ea >= 0x10000u && ea < 0xE0000000u &&\n'
           '           ea != ppu_hle_inject_base + 0x2008u &&\n'
           '           (ppu_vm_size == 0 || (uint64_t)ea + n <= ppu_vm_size);\n}\n')
    assert hdr.count(old) == 1
    # the current lifter's T152 block: page gates, cold thunks, inline stores (all macro-selected)
    hdr = hdr.replace(old, blk)   # blk closes the extern "C" block as `old` did
    hdr = hdr.replace('\r\n', '\n')
    for nb in (8, 16, 32, 64):
        old = f'    return vm_read{nb}(a);\n}}'
        assert hdr.count(old) == 1, nb
        hdr = hdr.replace(old, f'    return vm_read{nb}_cold(a);\n}}')
    D.MEM_SIZE = 0x08000000
    prog = D.Program()
    prog.entries = names
    out = Path(a.out) / f'{a.tu}_{a.seed}{"_inl" if a.inline else ""}{"_sync" if a.sync else ""}{"_cold" if a.cold else ""}'
    stubs = ''.join(f'extern "C++" void {c}(ppu_context* c) {{ stub_call(0x{c[5:]}u, c); }}\n' for c in sorted(called))
    fixture_extra = ('static void stub_call(uint32_t a, ppu_context* c) { event("stub", a, c); clobber(c, a); }\n'
                     + stubs
                     + 'void (*const k_entries[])(ppu_context*) = { ' + ', '.join(names) + ' };\n'
                     + f'const int k_entry_count = {len(names)};\n'
                     + 'extern "C" const func_entry function_table[] = { '
                     + ''.join(f'{{ 0x{n[5:]}ULL, {n}, "{n}" }}, ' for n in names) + '{ 0, 0, 0 } };\n'
                     + f'extern "C" const uint64_t function_table_count = {len(names)};\n')
    D.fixture_source = lambda prog: (D.FIXTURE.replace('MEM_SIZE', f'0x{D.MEM_SIZE:X}u')
                                     .replace('DATA_BASE', f'0x{D.DATA_BASE:X}u').replace('DATA_SIZE', f'0x{D.DATA_SIZE:X}u')
                                     .replace('STACK_TOP', f'0x{D.STACK_TOP:X}u')
                                     .replace('extern void (*const k_entries[])(ppu_context*);\nextern const int k_entry_count;\n',
                                              'extern void (*const k_entries[])(ppu_context*);\nextern const int k_entry_count;\n'
                                              + 'static void event(const char*, uint64_t, const ppu_context*);\n')
                                     + fixture_extra)
    base_src = prelude + body
    st = {}
    promo_src = rp.promote_source(base_src, st, invalidate_clean=not a.inline, store_sync=a.sync)
    exes, info = {}, {}
    for v, s in (('base', base_src), ('promo', promo_src)):
        exe, ct, osz = D.build(out, v, hdr, s, prog, inline_stores=a.inline, cold_calls=a.cold)
        exes[v] = exe
        info[v] = (ct, osz)
    rows = []
    for i, nm in enumerate(names):
        env = {'DIFF_PTRS': '1', 'DIFF_ONLY': str(i)}
        tr = {}
        for v in exes:
            try:
                tr[v] = D.run(exes[v], 4, 0, env_extra=env)
            except subprocess.TimeoutExpired:
                tr[v] = ('timeout', '')
        same = tr['base'] == tr['promo']
        ok = tr['base'][0] == 0
        t = {v: [] for v in exes}
        if ok and same:
            for _ in range(a.runs):
                for v in exes:
                    rc, so = D.run(exes[v], a.iters, a.reps, env_extra=env)
                    m = re.search(r'best_ms=([\d.]+)', so)
                    t[v].append(float(m.group(1)) if m else float('nan'))
        r = {'fn': nm, 'same': same, 'ran': ok, 'rc': tr['base'][0]}
        if t['base'] and not any(x != x for v in exes for x in t[v]):
            r.update({v: statistics.median(t[v]) for v in exes})
            r['speedup'] = r['base'] / r['promo'] if r['promo'] else float('nan')
            r['cv'] = max(statistics.pstdev(t[v]) / statistics.mean(t[v]) for v in exes)
        if t['base'] and 'speedup' not in r:
            r['timing'] = 'a timed run failed in a build; not timed'
        rows.append(r)
        print(json.dumps(r), flush=True)
    ran = [r for r in rows if 'speedup' in r]
    g = statistics.geometric_mean([r['speedup'] for r in ran]) if ran else float('nan')
    print(f'functions {len(rows)} ran {len(ran)} mismatches {sum(not r["same"] for r in rows)} '
          f'geomean speedup {g:.3f} (min {min((r["speedup"] for r in ran), default=0):.2f}, '
          f'max {max((r["speedup"] for r in ran), default=0):.2f})')
    print('promotion stats', {k: v for k, v in st.items() if k != 'fallback'}, st.get('fallback'))
    print('compile s / obj bytes', info)
    (out / 'result.json').write_text(json.dumps({'rows': rows, 'info': info, 'geomean': g}, indent=1))


if __name__ == '__main__':
    main()
