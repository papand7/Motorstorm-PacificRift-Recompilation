#!/usr/bin/env python3
"""T167: offline validation on the real D3D12 backend (bench_draw_path, test_gvf_draw). No game code runs.

  py -3 validate_t167.py <t167/gpuvtx dir> <t162/gpuvtx dir> correct|interval|compile|perf [repeats]

correct:  presented frames of fetch async, sync, 4 MB ring and a rerun against the CPU path (SHA-256), D3D12 debug layer on;
          the fetch-off arm also against T162's fetch-off frames.
interval: RSX_PRESENT_INTERVAL unset against 0, interleaved, few and many draws: frame time, CPU fence wait, Present, slow frames.
compile:  [shader-compile] per arm: calls, unique sources, duplicates, total, worst, and the worst frame.
perf:     GPU and CPU frame costs, T162 binaries against T167 binaries, interleaved (output for perf_summary_t162.py).
"""
import hashlib, os, re, statistics as S, subprocess, sys
from pathlib import Path

G = Path(sys.argv[1]).resolve()
OLD = Path(sys.argv[2]).resolve()
MODE = sys.argv[3]
REP = int(sys.argv[4]) if len(sys.argv) > 4 else 3
DRAW, BENCH = G / 'bin/draw/test_gvf_draw.exe', G / 'bin/bench/bench_draw_path.exe'
PRESET = dict(PS3_TEX_SNAPSHOT_EPOCH='1', RSX_SRV_REUSE='1', RSX_BIND_DEDUP='1', RSX_SHADER_CACHE='1')
ON = dict(RSX_VP_COMPACT='1', RSX_GPU_VERTEX_FETCH='1')
fails = 0


def check(ok, what):
    global fails
    print(f"[{'PASS' if ok else 'FAIL'}] {what}", flush=True)
    fails += not ok


def run(exe, args, d, env, timeout=1200):
    d.mkdir(parents=True, exist_ok=True)
    e = dict(os.environ, **PRESET, **env)
    with open(d / 'out.txt', 'wb') as o, open(d / 'err.txt', 'wb') as er:
        rc = subprocess.run([str(exe)] + [str(a) for a in args], cwd=d, env=e, stdout=o, stderr=er, timeout=timeout).returncode
    return rc, (d / 'err.txt').read_text(encoding='utf-8', errors='replace')


def hashes(p):
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(p.iterdir())} if p.exists() else {}


def correct():
    dbg = dict(D3D12_DBG='1', D3D12_IQ='1', CELLMARK_DUMP='64', CELLMARK_DUMP_EVERY='1', CELLMARK_DUMP_PRESENT_ONLY='1',
               CELLMARK_DUMP_DIR='frames', RSX_VTX_STATS='100000')
    arms = {'cpu': dict(RSX_VP_COMPACT='1'), 'async': ON, 'sync': dict(ON, RSX_GVF_ASYNC='0'),
            'ring4': dict(ON, RSX_GPU_VERTEX_FETCH_MB='4'), 'async_r': ON}
    for case, a in (('heavy', (6, 6900, 3)), ('light', (6, 2000, 3)), ('seam', (4, 3000, 12))):
        ref = None
        for arm, env in arms.items():
            d = G / 'runs/d' / f'{case}_{arm}'
            (d / 'frames').mkdir(parents=True, exist_ok=True)
            for f in (d / 'frames').iterdir():
                f.unlink()
            rc, err = run(DRAW, a, d, dict(dbg, **env))
            h = hashes(d / 'frames')
            gvf = re.findall(r'\[gvf\] draws=.*', err)
            print(f'{case}_{arm} rc={rc} frames={len(h)} {gvf[-1][:150] if gvf else ""}', flush=True)
            check(rc == 0 and h, f'{case}_{arm}: exit 0 and frames')
            check(not re.search(r'sev=[012] ', err), f'{case}_{arm}: no debug-layer message')
            check(' lost=0' in (gvf[-1] if gvf else ' lost=0'), f'{case}_{arm}: nothing lost')
            if arm == 'cpu':
                ref = h
                old = hashes(OLD / 'runs/d' / f'{case}_cpu' / 'frames')
                if old:
                    check(old == h, f'{case}_cpu: identical to T162 fetch-off ({len(old)} frames)')
                else:
                    print(f'{case}_cpu: no T162 frames to compare')
            else:
                check(h == ref, f'{case}_{arm}: {len(h)}/{len(ref)} frames identical to {case}_cpu')


def frames(err):
    out = []
    for l in err.splitlines():
        if l.startswith('[rsx-frame-perf] gframe=') and ' wait_ms=' in l:
            g = lambda n: float(re.search(r'\b' + n + r'=([\d.]+)', l).group(1))
            out.append((g('wall_ms'), g('wait_ms'), g('present_ms')))
    return out[5:]


def interval():
    print('case rep interval frames fps | wall p50 p99 | wait p50 p99 | present p50 max | slow(wait>50) | line')
    agg = {}
    for rep in range(1, REP + 1):
        for case, a in (('few', (600, 10, 8, 64, 24, 0)), ('many', (400, 2000, 8, 64, 24, 0))):
            for iv, env in (('1', {}), ('0', dict(RSX_PRESENT_INTERVAL='0'))):
                d = G / 'runs/i' / f'{case}_{iv}_{rep}'
                rc, err = run(BENCH, a, d, dict(env, RSX_VP_COMPACT='1', RSX_FRAME_PERF='100000,1,100000', RSX_WAIT_DIAG='1'))
                f = frames(err)
                if not f:
                    check(False, f'{d.name}: no frames, rc={rc}')
                    continue
                q = lambda v, p: sorted(v)[min(len(v) - 1, int(len(v) * p))]
                w, t, p = [x[0] for x in f], [x[1] for x in f], [x[2] for x in f]
                slow = sum(x > 50 for x in t)
                line = re.findall(r'\[present\] interval=.*', err)
                print(f'{case} {rep} {iv} {len(f)} {1000 / S.mean(w):.1f} | {q(w, .5):.1f} {q(w, .99):.1f} | {q(t, .5):.1f} {q(t, .99):.1f} | '
                      f'{q(p, .5):.2f} {max(p):.2f} | {slow} | {line[0][:60] if line else ""} rc={rc}', flush=True)
                agg.setdefault((case, iv), []).append((1000 / S.mean(w), q(t, .5), slow, len(f)))
    print('summary')
    for k, v in sorted(agg.items()):
        print(k, 'fps', [round(x[0], 1) for x in v], 'wait p50', [round(x[1], 1) for x in v], 'slow', [f'{x[2]}/{x[3]}' for x in v])


def compile_():
    arms = {'off': dict(RSX_VP_COMPACT='1'), 'sync': dict(ON, RSX_GVF_ASYNC='0'), 'async': ON}
    print('case arm rep rc calls unique dup failed total_ms max_ms | worst frame wall ms | draws fallback')
    for rep in range(1, REP + 1):
        for case, exe, a in (('bench', BENCH, (40, 2000, 8, 64, 24, 0)), ('mixed', DRAW, (10, 6900, 3))):
            for arm, env in arms.items():
                d = G / 'runs/c' / f'{case}_{arm}_{rep}'
                rc, err = run(exe, a, d, dict(env, RSX_SHADER_COMPILE_DIAG='1', RSX_FRAME_PERF='100000,1,100000'))
                ls = re.findall(r'\[shader-compile\] .*', err)
                ms = [float(re.search(r' ms=([\d.]+)', l).group(1)) for l in ls]
                src = [re.search(r' src=(\S+)', l).group(1) for l in ls]
                bad = [l for l in ls if ' hr=0x00000000' not in l]
                wall = [float(re.search(r'wall_ms=([\d.]+)', l).group(1)) for l in err.splitlines() if l.startswith('[rsx-frame-perf] gframe=')]
                gvf = re.findall(r'\[gvf\] draws=(\d+).*?fb_vs=(\d+)', err) or re.findall(r'\[gvf\] draws=(\d+)', err)
                print(f'{case} {arm} {rep} rc={rc} {len(ls)} {len(set(src))} {len(src) - len(set(src))} {len(bad)} {sum(ms):.0f} '
                      f'{max(ms, default=0):.1f} | {max(wall, default=0):.0f} | {gvf[-1] if gvf else ""}', flush=True)
                check(rc == 0 and not bad, f'{d.name}: exit 0, no failed compile')


def perf():
    for rep in range(1, REP + 1):
        for n, kind, a in (('race2k', 'bench', (40, 2000, 8, 64, 24, 0)), ('race6k9', 'bench', (24, 6900, 8, 64, 24, 0)), ('mixed', 'draw', (10, 6900, 3))):
            rel = 'bin/bench/bench_draw_path.exe' if kind == 'bench' else 'bin/draw/test_gvf_draw.exe'
            for arm, root, env in (('cpc', G, dict(RSX_VP_COMPACT='1')), ('g162', OLD, ON), ('g167', G, dict(ON, RSX_GVF_ASYNC='0'))):
                d = G / 'runs/p' / f'{n}_{arm}_{rep}'
                rc, _ = run(root / rel, a, d, dict(env, RSX_FRAME_PERF='100,1,1000', RSX_GPU_PROF='5'))
                print(d.name, 'rc=%d' % rc, flush=True)
                check(rc == 0, f'{d.name}: exit 0')


{'correct': correct, 'interval': interval, 'compile': compile_, 'perf': perf}[MODE]()
print(f'validate_t167 {MODE}: {fails} failure(s)')
sys.exit(1 if fails else 0)
