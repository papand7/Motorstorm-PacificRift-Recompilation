r"""Reads an RSX_SHADOW_CAP file (ps3recomp-vkgame/libs/video/rsx_shadow_cap.h) and checks whether each
shadow section's light projection moves by whole texels from frame to frame (stable edges) or by fractions
(edges crawl as the camera moves).

For every kind-0 record (first depth-only draw of a (zeta, scissor) section), it looks in the bound vertex
constants for orthographic 4x4 blocks: four consecutive vec4s whose last row (or last column) is
(0, 0, 0, 1) and whose first three rows (columns) are mutually perpendicular. For each such block and
section it prints, frame by frame, the axis lengths (cascade extent) and the translation in texels:
    tx = row0.w * W / 2,  ty = row1.w * H / 2   (W x H = the section's viewport in pixels)
and summarises the fractional part of the frame-to-frame change. A snapped projection changes by whole
texels (fraction 0); an unsnapped one by anything.
usage: py -3 shadow_cap.py <capture.bin> [--rows N] [--key i]"""
import struct, sys, math, collections

HEAD = struct.Struct('<24I')
UNIT = struct.Struct('<8I')


def records(path):
    b = open(path, 'rb').read()
    o = 0
    while o + HEAD.size <= len(b):
        h = HEAD.unpack_from(b, o)
        if h[0] != 0x50414353:
            raise SystemExit(f'bad magic at {o}')
        (magic, ver, kind, frame, draw, zloc, zoff, cw, ch, sh, sv, cm, cmm, dw, vps,
         vcb, vpb, fpc, ms) = h[:19]
        o += HEAD.size
        vp_cb = b[o:o + vcb]; o += vcb
        vp = b[o:o + vpb]; o += vpb
        fp = b[o:o + fpc * 16]; o += fpc * 16
        if o + 16 * UNIT.size > len(b):
            break                          # cut short: the process ended mid-record
        units = [UNIT.unpack_from(b, o + i * UNIT.size) for i in range(16)]; o += 16 * UNIT.size
        small = {}
        for i, u in enumerate(units):
            if u[6]:
                small[i] = b[o:o + 64]; o += 64
        yield dict(kind=kind, frame=frame, draw=draw, zoff=zoff, cw=cw, ch=ch, sh=sh, sv=sv,
                   vp_start=vps, ms=ms, consts=vp_cb, vp=vp, fp=fp, units=units, small=small)


def vec4s(cb):
    n = len(cb) // 16
    return [struct.unpack_from('<4f', cb, 16 * i) for i in range(n)]


def dot3(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def ortho_blocks(c, lo=0, hi=512):
    """Constant slots k where c[k..k+3] is an orthographic matrix: rows (r) or columns (c)."""
    out = []
    for k in range(lo, hi - 3):
        R = c[k:k + 4]
        for form in ('r', 'c'):
            M = R if form == 'r' else [tuple(R[j][i] for j in range(4)) for i in range(4)]
            last = M[3]
            if not (abs(last[0]) < 1e-6 and abs(last[1]) < 1e-6 and abs(last[2]) < 1e-6 and abs(last[3] - 1) < 1e-6):
                continue
            ax = [M[i][:3] for i in range(3)]
            ln = [math.sqrt(dot3(a, a)) for a in ax]
            if min(ln) < 1e-9 or not all(math.isfinite(x) for x in ln):
                continue
            ok = all(abs(dot3(ax[i], ax[j])) / (ln[i] * ln[j]) < 1e-3 for i, j in ((0, 1), (0, 2), (1, 2)))
            if ok:
                out.append((k, form, M))
    return out


def viewport(c):
    """vp_posscale / vp_posoffset after the 512 constants: the section's pixels are 2 * |scale|."""
    s, t = c[512], c[513]
    return abs(s[0]) * 2, abs(s[1]) * 2, s, t


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return
    recs = list(records(a[0]))
    k0 = [r for r in recs if r['kind'] == 0]
    k1 = [r for r in recs if r['kind'] == 1]
    frames = sorted({r['frame'] for r in recs})
    print(f'{len(recs)} records, {len(k0)} depth-only sections, {len(k1)} shadow-reading draws, '
          f'frames {frames[0]}..{frames[-1]} ({len(frames)})' if frames else 'no records')
    by = collections.defaultdict(list)
    for r in k0:
        by[(r['zoff'], r['sh'], r['sv'])].append(r)
    keys = sorted(by, key=lambda k: -len(by[k]))
    for i, key in enumerate(keys):
        rs = by[key]
        sx, sw = key[1] & 0xFFFF, key[1] >> 16
        sy, shh = key[2] & 0xFFFF, key[2] >> 16
        c0 = vec4s(rs[0]['consts'])
        W, H, s, t = viewport(c0)
        blocks = ortho_blocks(c0)
        print(f'\n[{i}] zeta 0x{key[0]:08X} scissor x{sx} y{sy} {sw}x{shh}  frames {len(rs)}  '
              f'viewport {W:.0f}x{H:.0f} at ({t[0]:.1f},{t[1]:.1f})  vp_start {rs[0]["vp_start"]}  '
              f'ortho blocks at {[(k, f) for k, f, _ in blocks]}')
        for k, form, _ in blocks:
            series = []
            for r in rs:
                c = vec4s(r['consts'])
                Wr, Hr, _, _ = viewport(c)
                R = c[k:k + 4]
                M = R if form == 'r' else [tuple(R[j][q] for j in range(4)) for q in range(4)]
                ln = [math.sqrt(dot3(M[q][:3], M[q][:3])) for q in range(3)]
                series.append((r['frame'], r['ms'], ln, M[0][3] * Wr / 2, M[1][3] * Hr / 2, M[0][:3], M[1][:3]))
            ext_changes = sum(1 for p, q in zip(series, series[1:])
                              if abs(p[2][0] - q[2][0]) > 1e-6 * abs(p[2][0]) or abs(p[2][1] - q[2][1]) > 1e-6 * abs(p[2][1]))
            axis_changes = sum(1 for p, q in zip(series, series[1:])
                               if max(abs(x - y) for x, y in zip(p[5] + p[6], q[5] + q[6])) > 1e-6 * p[2][0])
            fr = []
            for p, q in zip(series, series[1:]):
                if p[5] == q[5] and p[6] == q[6]:
                    for d in (q[3] - p[3], q[4] - p[4]):
                        if abs(d) > 1e-4:
                            fr.append(abs(d - round(d)))
            moved = len(fr)
            frac = (sorted(fr)[len(fr) // 2] if fr else float('nan'))
            print(f'  block c{k} ({form}): extent changes {ext_changes}/{len(series) - 1} frames, axis changes '
                  f'{axis_changes}, translation moves with fixed axes {moved}, median sub-texel part {frac:.3f} '
                  f'(0 = whole texels; about 0.25 = uniform)')
            rows = int(a[a.index('--rows') + 1]) if '--rows' in a else 6
            for f, ms, ln, tx, ty, _, _ in series[:rows]:
                print(f'    frame {f} t={ms} ms  axis lengths {ln[0]:.6g} {ln[1]:.6g} {ln[2]:.6g}  '
                      f'translation {tx:.3f} {ty:.3f} texels')


if __name__ == '__main__':
    main()
