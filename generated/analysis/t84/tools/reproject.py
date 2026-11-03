#!/usr/bin/env python3
"""T84: where would each draw of an RSXI frame land under another draw's camera? (offline, read-only)

For VS programs of the form world = a0.x*c256 + a0.y*c257 + a0.z*c258 + a0.w*c259,
clip = world.x*c0 + world.y*c1 + world.z*c2 + c3 (CEED7030, 0E74E41D, 2F867C86, 94C50138: checked
from their decompiled HLSL), take each draw's own world rows and its recorded vertex samples plus
the 8 corners of its attribute-0 bounding box, and project them with
  own : the draw's own c0..c3 (sanity check against its own target and occlusion count), and
  cam : c0..c3 of draw <cam_op> (the main-scene camera).
A vertex is inside when w > 0, |x| <= w, |y| <= w and |z| <= w (RSX/GL clip volume; window z is
0.5*z/w + 0.5). Window coordinates use the camera draw's viewport scale/offset.
  py -3 -I reproject.py <rsxi frame dir> <first_op> <last_op> <cam_op>"""
import itertools, json, re, sys
from pathlib import Path

VS_OK = {'0xCEED7030', '0x0E74E41D', '0x2F867C86', '0x94C50138'}


def load(fd):
    return [json.loads(re.sub(r'-?(?:nan|inf)', 'null', l))
            for l in (Path(fd) / 'events.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]


def consts(g):
    return {r[0]: r[1:5] for r in g.get('vp_consts', [])}


def xf(c, p):
    w = [sum(p[k] * c.get(256 + k, [0, 0, 0, 0])[i] for k in range(4)) for i in range(3)]
    return [sum(w[k] * c.get(k, [0, 0, 0, 0])[i] for k in range(3)) + c.get(3, [0, 0, 0, 0])[i] for i in range(4)]


def clipcam(cam, c, p):
    w = [sum(p[k] * c.get(256 + k, [0, 0, 0, 0])[i] for k in range(4)) for i in range(3)]
    return [sum(w[k] * cam[k][i] for k in range(3)) + cam[3][i] for i in range(4)]


def inside(v):
    x, y, z, w = v
    return w > 0 and abs(x) <= w and abs(y) <= w and abs(z) <= w


def win(v, sc, of):
    x, y, z, w = v
    return (x / w * sc[0] + of[0], y / w * sc[1] + of[1], z / w * sc[2] + of[2])


def main(fd, lo, hi, cam_op):
    ev = load(fd)
    D = {e['op']: e for e in ev if e['e'] == 'draw'}
    occ = {e['op']: e['samples_passed'] for e in ev if e['e'] == 'occlusion'}
    cg = D[cam_op]['guest']
    cc = consts(cg)
    cam = [cc[i] for i in range(4)]
    sc, of = cg['raster']['vp_scale'], cg['raster']['vp_offset']
    tot = {'draws': 0, 'cam_any_inside': 0, 'own_any_inside': 0}
    for op in range(lo, hi + 1):
        e = D.get(op)
        if not e or e['guest']['vs_hash'] not in VS_OK:
            continue
        g = e['guest']
        inp = (g.get('geom') or {}).get('input') or {}
        if not inp.get('lo'):
            continue
        c = consts(g)
        lo3, hi3 = inp['lo'], inp['hi']
        pts = [list(p) + [1.0] for p in itertools.product(*[(lo3[i], hi3[i]) for i in range(3)])]
        pts += [s if len(s) == 4 else list(s) + [1.0] for s in inp.get('sample', [])]
        own = [xf(c, p) for p in pts]
        cm = [clipcam(cam, c, p) for p in pts]
        oin, cin = sum(map(inside, own)), sum(map(inside, cm))
        wins = [win(v, sc, of) for v in cm if v[3] > 0]
        ys = [round(w[1]) for w in wins]
        zs = [round(w[2], 4) for w in wins]
        tot['draws'] += 1
        tot['cam_any_inside'] += cin > 0
        tot['own_any_inside'] += oin > 0
        print(f"{op:4d} vs={g['vs_hash'][2:]} fp={g['fp'][2:]} occ={occ.get(op, '-'):>6} own_in={oin:2d}/{len(pts)}"
              f" cam_in={cin:2d}/{len(pts)} cam_wy=[{min(ys, default='-')},{max(ys, default='-')}]"
              f" cam_wz=[{min(zs, default='-')},{max(zs, default='-')}]")
    print('TOTAL', tot)


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], int(a[1]), int(a[2]), int(a[3]))
