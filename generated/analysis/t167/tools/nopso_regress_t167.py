"""T167 (from T162; arms now state RSX_GVF_ASYNC, and gvfa compiles fetch programs in the background): forced guest-FP pipeline failure on the real backend (test_gvf_draw, D3D12 debug layer).

A GPU-fetch draw whose pipeline fails must render exactly as the CPU path renders the same draw through its
fallback pipeline. Failures are forced in both arms by a property of the guest stream, so they hit the same draws:
  all = FP_OFF=1 (vp_get_fp_pso returns NULL for every draw)
  mix = RSX_TEST_FP_FAIL_EPOCH=3 (every third BEGIN/END, fallback and guest-FP draws interleaved)
Arms: cpu (reference), gvf, gvf4 (4 MB ring, early replays), spill (RSX_GVF_TEST_SPILL=1: own buffer per fallback).
Checks: every arm's presented frames are identical to cpu; the frames are not blank; mix differs from all (so the
forcing is selective) and all differs from no forcing; [gvf] nopso = cpu_drawn > 0, lost = 0; spill arm spill = nopso
(the other arms spill only when the vertex-buffer half is full); no debug-layer message. Exit 1 on any failure.

  py -3 nopso_regress_t162.py <test_gvf_draw.exe> <out dir>
"""
import hashlib, os, pathlib, re, shutil, struct, subprocess, sys

exe = pathlib.Path(sys.argv[1]).resolve()
root = pathlib.Path(sys.argv[2]).resolve()
ARGS = ['3', '3000', '3']
BASE = dict(PS3_TEX_SNAPSHOT_EPOCH='1', RSX_SRV_REUSE='1', RSX_BIND_DEDUP='1', RSX_SHADER_CACHE='1', RSX_VP_COMPACT='1',
            D3D12_DBG='1', D3D12_IQ='1', CELLMARK_DUMP='64', CELLMARK_DUMP_EVERY='1', CELLMARK_DUMP_PRESENT_ONLY='1',
            CELLMARK_DUMP_DIR='frames', RSX_VTX_STATS='100000')
CASES = {'none': {}, 'all': {'FP_OFF': '1'}, 'mix': {'RSX_TEST_FP_FAIL_EPOCH': '3'}}
ARMS = {'cpu': {}, 'gvf': {'RSX_GPU_VERTEX_FETCH': '1', 'RSX_GVF_ASYNC': '0'},
        'gvfa': {'RSX_GPU_VERTEX_FETCH': '1', 'RSX_GVF_ASYNC': '1'},
        'gvf4': {'RSX_GPU_VERTEX_FETCH': '1', 'RSX_GVF_ASYNC': '0', 'RSX_GPU_VERTEX_FETCH_MB': '4'},
        'spill': {'RSX_GPU_VERTEX_FETCH': '1', 'RSX_GVF_ASYNC': '0', 'RSX_GVF_TEST_SPILL': '1'}}
fails = 0


def check(ok, what):
    global fails
    print(f"[{'PASS' if ok else 'FAIL'}] {what}", flush=True)
    fails += not ok


def run(case, arm):
    d = root / f'{case}_{arm}'
    shutil.rmtree(d, ignore_errors=True)
    (d / 'frames').mkdir(parents=True)
    env = dict(os.environ, **BASE, **CASES[case], **ARMS[arm])
    r = subprocess.run([str(exe)] + ARGS, cwd=d, env=env, capture_output=True, text=True, errors='replace', timeout=900)
    (d / 'err.txt').write_text(r.stderr, encoding='utf-8')
    frames = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((d / 'frames').iterdir())}
    gvf = None
    for m in re.finditer(r'\[gvf\] draws=(\d+).*?replay nopso=(\d+) cpu_drawn=(\d+) cpu_corners=(\d+) spill=(\d+) lost=(\d+)', r.stderr):
        gvf = dict(zip(('draws', 'nopso', 'drawn', 'corners', 'spill', 'lost'), map(int, m.groups())))
    dbg = len(re.findall(r'sev=[012] ', r.stderr))
    print(f'{d.name:12s} rc={r.returncode} frames={len(frames)} debug={dbg} {gvf or ""}', flush=True)
    return r.returncode, frames, gvf, dbg, d


def distinct_pixels(path):
    """Distinct colours in a 24/32-bit BMP (blank-frame guard)."""
    b = path.read_bytes()
    off, bpp = struct.unpack_from('<I', b, 10)[0], struct.unpack_from('<H', b, 28)[0]
    step = bpp // 8
    return len({b[i:i + step] for i in range(off, len(b) - step, step * 97)})


res = {(c, a): run(c, a) for c in CASES for a in ARMS}
for (c, a), (rc, fr, gvf, dbg, d) in res.items():
    check(rc == 0 and fr and dbg == 0, f'{c}_{a}: exit 0, frames written, no debug-layer message')
    ref = res[(c, 'cpu')][1]
    if a != 'cpu':
        diff = [k for k in set(ref) | set(fr) if ref.get(k) != fr.get(k)]
        check(not diff, f'{c}_{a}: {len(fr)}/{len(ref)} frames identical to {c}_cpu' + (f', differ: {sorted(diff)[:6]}' if diff else ''))
        check(gvf is not None and gvf['lost'] == 0 and gvf['nopso'] == gvf['drawn'], f'{c}_{a}: nopso = cpu_drawn, lost = 0 ({gvf})')
        if c == 'none':
            check(gvf and gvf['nopso'] == 0, f'{c}_{a}: no failure forced, nopso = 0')
        else:
            check(a == 'gvfa' or (gvf and gvf['nopso'] > 0 and gvf['corners'] > 0), f'{c}_{a}: the forced failures reached the fallback')
            if a == 'spill':
                check(gvf and gvf['spill'] == gvf['nopso'], f'{c}_{a}: every fallback took its own buffer')
none, al, mix = (res[(c, 'cpu')][1] for c in ('none', 'all', 'mix'))
check(al != none, 'FP_OFF changes the output (the fallback pipeline really drew)')
check(mix != none and mix != al, 'the mixed case differs from both (fallback and guest-FP draws interleaved)')
for c in ('all', 'mix'):
    d = res[(c, 'cpu')][4]
    last = sorted((d / 'frames').iterdir())[-1]
    n = distinct_pixels(last)
    check(n > 1, f'{c}_cpu: last frame is not blank ({n} sampled colours)')
print(f'nopso_regress_t162: {fails} failure(s)')
sys.exit(1 if fails else 0)
