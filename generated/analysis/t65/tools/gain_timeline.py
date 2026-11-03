# T65: per-frame gain of the T63 loading screen relative to a reference dump (private analysis helper).
# usage: py -3 -I gain_timeline.py FRAMES_DIR RUN_WALL0 REF_INDEX FIRST LAST
# Inputs are the raw 24-bit BMP backbuffer dumps (CELLMARK_DUMP). The loading screen draws straight into the
# 8-bit display target (RSXI f6287: rt 0, fmt 328, no offscreen/FP16 target), so these bytes are what was presented.
# Gain: for each reference byte value v, mean of the frame byte over pixels whose reference byte is v;
# g = sum(mean_f(v)) / sum(v) over the v range whose frame bytes stay unsaturated (< 250 for 99 %).
import os, struct, sys
fd, wall0, ref, a, b = sys.argv[1], float(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
def load(i):
    p = os.path.join(fd, 'frame_%03d.bmp' % i)
    d = open(p, 'rb').read()
    return d[struct.unpack_from('<I', d, 10)[0]:], os.stat(p).st_mtime - wall0
R, tr = load(ref)
print('ref %03d at %.2f s' % (ref, tr))
print('frame host_s mean white_frac gain v_range')
for i in range(a, b + 1):
    F, t = load(i)
    acc = [[0, 0, 0] for _ in range(256)]          # count, sum f, count f>=250
    for r, f in zip(R, F):
        c = acc[r]; c[0] += 1; c[1] += f; c[2] += f >= 250
    num = den = 0; vs = []
    for v in range(3, 256):
        n, s, hi = acc[v]
        if n < 200: continue
        if hi > 0.01 * n: break
        num += s; den += n * v; vs.append(v)
    g = num / den if den else float('nan')
    white = sum(1 for k in range(0, len(F) - 2, 3) if F[k] >= 250 and F[k + 1] >= 250 and F[k + 2] >= 250) / (len(F) // 3)
    print('%03d %7.2f %6.1f %5.3f %7.3f %s' % (i, t, sum(F) / len(F), white, g, '%d-%d' % (vs[0], vs[-1]) if vs else '-'))
