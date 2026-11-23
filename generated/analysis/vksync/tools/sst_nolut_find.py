r"""Reads RSX_SHADOW_STABLE_DUMP files (sst_nolut_<fp>.bin, rsx_draw_engine.c eng_sst_dump) and looks in each
draw's vertex constants for vectors that are combinations of a cascade's game rows (the light's world-to-clip
as bound for the shadow pass): those hold the draw's own shadow projection, which the stable atlas no longer
matches. For every 4x4 block (as columns, like c0-c3, or as rows) and every row of it, it solves
row = a*G0 + b*G1 + c*G2 + d*G3 for each tile's game matrix G and prints the fits with a small residual.
usage: py -3 sst_nolut_find.py <dump dir or file> [...]"""
import pathlib, struct, sys
import numpy as np

HDR = struct.Struct('<6I')


def load(path):
    b = pathlib.Path(path).read_bytes()
    magic, fp, frame, vp_start, cb, nt = HDR.unpack_from(b, 0)
    assert magic == 0x44545353, path
    o = HDR.size
    consts = np.frombuffer(b, '<f4', cb // 4, o).reshape(-1, 4).astype(np.float64)
    o += cb
    tiles = []
    for _ in range(nt):
        k = struct.unpack_from('<6f', b, o); o += 24
        used, raw = struct.unpack_from('<2I', b, o); o += 8
        m_in = np.frombuffer(b, '<f4', 16, o).astype(np.float64); o += 64
        m_out = np.frombuffer(b, '<f4', 16, o).astype(np.float64); o += 64
        # columns -> rows
        tiles.append(dict(key=k[:2], kx=k[2], cx=k[3], ky=k[4], cy=k[5], used=used, raw=raw,
                          G=m_in.reshape(4, 4).T, S=m_out.reshape(4, 4).T))
    return dict(fp=fp, frame=frame, vp_start=vp_start, consts=consts, tiles=tiles)


def fits(d, tol=2e-4):
    C = d['consts']
    out = []
    n = len(C)
    for start in range(n - 3):
        blk = C[start:start + 4]
        if not np.isfinite(blk).all() or not np.abs(blk).sum():
            continue
        for lay, M in (('c', blk.T), ('r', blk)):
            for r in range(4):
                v = M[r]
                if not np.abs(v[:3]).sum():
                    continue
                for ti, t in enumerate(d['tiles']):
                    G = t['G']
                    # G is invertible, so every vector is some mix of all four rows: only a mix of one
                    # light axis (x or y) and the w row says "this is that cascade's shadow coordinate"
                    for sub in ((0, 3), (1, 3), (2, 3)):
                        A = G[list(sub)]
                        y, *_ = np.linalg.lstsq(A.T, v, rcond=None)
                        res = np.abs(A.T @ y - v).max() / max(1e-12, np.abs(v).max())
                        if res < tol and abs(y[0]) > 1e-9:
                            x = np.zeros(4)
                            x[list(sub)] = y
                            out.append((start, lay, r, ti, x, res))
    return out


def main():
    paths = []
    for a in sys.argv[1:]:
        p = pathlib.Path(a)
        paths += sorted(p.glob('sst_nolut_*.bin')) if p.is_dir() else [p]
    for p in paths:
        d = load(p)
        print(f"== {p.name}: fp 0x{d['fp']:08X} frame {d['frame']} vp_start {d['vp_start']} tiles {len(d['tiles'])}")
        for ti, t in enumerate(d['tiles']):
            print(f"   tile {ti} key {t['key'][0]:.1f},{t['key'][1]:.1f} used {t['used']} raw {t['raw']} "
                  f"kx {t['kx']:.5f} cx {t['cx']:.5f} ky {t['ky']:.5f} cy {t['cy']:.5f}")
        seen = set()
        for start, lay, r, ti, x, res in fits(d):
            key = (start + (r if lay == 'r' else 0), lay, r, ti)
            if key in seen:
                continue
            seen.add(key)
            print(f"   c{start}{lay} row {r}: tile {ti}  {x[0]:+.5f}*G0 {x[1]:+.5f}*G1 {x[2]:+.5f}*G2 "
                  f"{x[3]:+.5f}*G3  (res {res:.1e})")


main()
