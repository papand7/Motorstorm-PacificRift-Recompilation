"""Per host thread, from a PS3_CRITICAL_PATH_TRACE file: CPU ms per frame (HOST_CPU samples, prorated
to the frames between guest flip requests), with the thread's role and name. Busy fraction = CPU ms /
frame ms. A thread near 1.0 cannot go faster by waiting less; it is a candidate gate.

usage: py -3 cpath_threads.py <cpath.txt> [top=12]"""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'ps3recomp-vkgame' / 'tools'))
import cpath_report as cr  # noqa: E402

header, names, hosts, spans = cr.load(sys.argv[1])
top = int(sys.argv[2]) if len(sys.argv) > 2 else 12
flips = sorted(s[4] for s in spans if s[0] == cr.FLIP_REQ)
if len(flips) < 3:
    sys.exit('fewer than 3 flips')
t0, t1 = flips[0], flips[-1]
nfr = len(flips) - 1
fm = (t1 - t0) / nfr
cpu = collections.Counter()
for s in spans:
    if s[0] == cr.HOST_CPU and s[5] > s[4]:
        ov = cr.total(cr.clip([(s[4], s[5])], t0, t1))
        cpu[s[1]] += s[2] / 1e3 * ov / (s[5] - s[4])
print(header)
print(f'{nfr} frames, {fm:.1f} ms mean')
for idx, ms in cpu.most_common(top):
    h = hosts.get(idx, {})
    print(f"host {idx:3d} {h.get('role', '?'):12s} {h.get('name', '')[:34]:34s} cpu {ms / nfr:5.1f} ms/frame  busy {ms / nfr / fm:4.2f}")
