"""Frame-time spikes in a race run vs render-thread work (overlap60 / fps stability).
usage: py -3 spikes.py <run dir> <race entry s>
Clock: the last [rsx-hb] ms= before each line. Uses [frame-hist] (per ~5 s window), [drain-prof] worst frames,
[vk-waits] present/readback waits, [sim-pace-late]."""
import re
import sys

run, entry = sys.argv[1], float(sys.argv[2]) * 1000.0
clk = 0.0
fh, dp, vw, late = [], [], [], 0
for l in open(run + '/stderr.log', encoding='latin-1'):
    m = re.match(r'\[rsx-hb\] ms=(\d+)', l)
    if m:
        clk = float(m.group(1)); continue
    if clk < entry:
        continue
    m = re.match(r'\[frame-hist\] p50=([\d.]+) p90=([\d.]+) p99=([\d.]+) max=([\d.]+) ms over34=([\d.]+)%', l)
    if m:
        fh.append((clk, *map(float, m.groups()))); continue
    m = re.match(r'\[drain-prof\] frame (\d+): present gap ([\d.]+) ms, draws ([\d.]+) ms.*?tex uploads (\d+) \((\d+) KB\), new pipelines (\d+) \(([\d.]+) ms\), texture time ([\d.]+) ms \(create ([\d.]+), decode ([\d.]+), copy ([\d.]+)', l)
    if m:
        dp.append((clk, *map(float, m.groups()))); continue
    m = re.match(r'\[vk-waits\].*readback=(\d+)/([\d.]+)ms present=(\d+)/([\d.]+)ms', l)
    if m:
        vw.append((clk, *map(float, m.groups()))); continue
    if l.startswith('[sim-pace-late]'):
        late += 1
print('race windows (frame-hist):', len(fh))
for r in fh:
    print('  t=%6.1fs p50 %5.1f p90 %5.1f p99 %5.1f max %5.1f over34 %4.1f%%' % (r[0] / 1000, *r[1:]))
print('drain-prof worst frames in race: %d' % len(dp))
for r in sorted(dp, key=lambda r: -r[3])[:15]:
    print('  t=%6.1fs frame %5d gap %5.1f draws %5.1f ms | tex %2d (%6d KB) tex_ms %5.1f (decode %5.1f copy %4.1f create %4.1f) | new pipes %d (%4.1f ms)' % (
        r[0] / 1000, r[1], r[2], r[3], r[4], r[5], r[8], r[10], r[11], r[9], r[6], r[7]))
if dp:
    tx = [r for r in dp if r[4] > 0]
    print('worst frames with texture uploads: %d of %d; mean tex_ms on those %.1f; mean draws %.1f vs %.1f without' % (
        len(tx), len(dp), sum(r[8] for r in tx) / max(1, len(tx)), sum(r[3] for r in tx) / max(1, len(tx)),
        sum(r[3] for r in dp if r[4] == 0) / max(1, len(dp) - len(tx))))
print('sim-pace-late lines in race: %d' % late)
if vw:
    print('vk-waits per window (mean): present %.1f ms, readback %.1f ms' % (
        sum(r[4] for r in vw) / len(vw), sum(r[2] for r in vw) / len(vw)))
