MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""Race frame stats from existing run logs. Race = frames with records >= 1000. No game launch."""
import json, os, re, statistics as st, sys
RUNS = (MS_ROOT + r'\generated\runs')
PERF = re.compile(rb'\[rsx-frame-perf\] gframe=(\d+) .*?wall_ms=([\d.]+).*?records=(\d+).*?upload_mb=([\d.]+).*?drain_ms=([\d.]+).*?expand_ms=([\d.]+).*?flush_ms=([\d.]+)')
KEYS = ('RSXI', 'RSXI_VP_CONSTS', 'RSXI_UNITS', 'RSX_FRAME_DUMP', 'RSX_PERF_DEEP', 'RSX_VP_COMPACT', 'RSX_VP_FAST_FETCH', 'RSX_FP_SCAN_MEMO',
        'RSX_SHADER_CACHE', 'PS3_LWCOND_WAKE', 'PS3_CRITICAL_PATH_TRACE', 'D3D12_DBG', 'RSX_VISUAL_DIAG', 'RSX_VEHICLE_DIAG')
def env_of(d):
    try:
        m = json.load(open(os.path.join(d, 'manifest.json'), encoding='utf-8'))
    except Exception:
        return {}
    e = m.get('env') or m.get('environment') or {}
    if isinstance(e, list):
        e = dict(x.split('=', 1) for x in e if '=' in x)
    return e
print('run\tn\tfps\tp50\tp95\trec\tup_mb\texpand\tflush\tflags')
for name in sys.argv[1:] or sorted(os.listdir(RUNS))[-45:]:
    d = os.path.join(RUNS, name)
    p = os.path.join(d, 'stderr.log')
    if not os.path.exists(p):
        continue
    b = open(p, 'rb').read()
    if b[:2] == b'\xff\xfe':
        b = b.decode('utf-16', 'ignore').encode()
    rows = [(float(m[2]), int(m[3]), float(m[4]), float(m[6]), float(m[7])) for m in PERF.finditer(b) if int(m[3]) >= 1000]
    if len(rows) < 30:
        continue
    w = sorted(r[0] for r in rows)
    e = env_of(d)
    fl = ' '.join(f'{k}={e[k][:12]}' for k in KEYS if k in e)
    print(f"{name}\t{len(rows)}\t{1000 / st.mean(w):.1f}\t{w[len(w)//2]:.0f}\t{w[int(len(w)*.95)]:.0f}\t{st.median(r[1] for r in rows):.0f}\t{st.median(r[2] for r in rows):.0f}\t{st.median(r[3] for r in rows):.1f}\t{st.median(r[4] for r in rows):.1f}\t{fl}")
