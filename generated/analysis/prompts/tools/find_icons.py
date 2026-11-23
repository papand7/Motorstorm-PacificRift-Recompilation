# Private analysis: for the GUI prompt textures, the FNV-1a 64 of level 0 (as the engine's patch hook sees it)
# and the bounding boxes of bright icon-like components, with a debug PNG per texture.
# usage: python find_icons.py <gui_all dir> <out dir> [name substrings...]
import sys, os, struct, glob, json
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scratch'))
from pack import parse
from dumptex import dxt5


def fnv64(b):
    h = 0xcbf29ce484222325
    for x in b:
        h ^= x
        h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


def fnv64_fast(b):
    # same as fnv64, vectorised enough for 1 MB in python: plain loop is fine for a few textures
    return fnv64(b)


def components(img, thr=170):
    lum = img[:, :, :3].astype(np.int32).mean(axis=2)
    m = (lum > thr) & (img[:, :, 3] > 100)
    h, w = m.shape
    lab = np.zeros((h, w), np.int32)
    boxes = []
    n = 0
    for y in range(h):
        for x in range(w):
            if m[y, x] and not lab[y, x]:
                n += 1
                st = [(y, x)]; lab[y, x] = n
                x0 = x1 = x; y0 = y1 = y; cnt = 0
                while st:
                    cy, cx = st.pop(); cnt += 1
                    x0 = min(x0, cx); x1 = max(x1, cx); y0 = min(y0, cy); y1 = max(y1, cy)
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not lab[ny, nx]:
                                lab[ny, nx] = n; st.append((ny, nx))
                boxes.append([x0, y0, x1 + 1, y1 + 1, cnt])
    # merge boxes that overlap or touch within 3 px
    changed = True
    while changed:
        changed = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if a[0] - 3 <= b[2] and b[0] - 3 <= a[2] and a[1] - 3 <= b[3] and b[1] - 3 <= a[3]:
                    boxes[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]), a[4] + b[4]]
                    del boxes[j]; changed = True; break
            if changed: break
    return [b for b in boxes if 8 <= b[2] - b[0] <= 90 and 8 <= b[3] - b[1] <= 90 and b[4] >= 20]


if __name__ == '__main__':
    gdir, out = sys.argv[1], sys.argv[2]
    pats = sys.argv[3:]
    os.makedirs(out, exist_ok=True)
    seen = {}
    res = []
    for f in sorted(glob.glob(os.path.join(gdir, '*.gui'))):
        d = open(f, 'rb').read()
        try:
            r = parse(d)
        except Exception:
            continue
        if not r: continue
        for e in r['ents']:
            n = e['names'][0]
            if not n.endswith('.dds') or not any(p == n for p in pats): continue
            o = e['off']
            w, h = struct.unpack_from('>HH', d, o + 0x1C)
            mips = struct.unpack_from('>H', d, o + 0x20)[0]
            fmt = struct.unpack_from('>H', d, o + 0x22)[0]
            size = struct.unpack_from('>I', d, o + 0x27)[0]
            data = d[o + 43:o + 43 + size]
            if fmt != 0x0B: continue
            l0 = ((w + 3) // 4) * ((h + 3) // 4) * 16
            hv = fnv64(data[:l0])
            if hv in seen: continue
            seen[hv] = 1
            img = dxt5(data, w, h)
            boxes = components(img)
            res.append({'name': n, 'w': w, 'h': h, 'mips': mips, 'hash': '0x%016X' % hv, 'boxes': boxes, 'pack': os.path.basename(f)})
            im = Image.fromarray(np.ascontiguousarray(img), 'RGBA')
            bg = Image.new('RGBA', im.size, (40, 90, 40, 255)); bg.alpha_composite(im)
            bg = bg.convert('RGB')
            dr = ImageDraw.Draw(bg)
            for b in boxes: dr.rectangle([b[0], b[1], b[2] - 1, b[3] - 1], outline=(255, 0, 0))
            bg.save(os.path.join(out, n[:-4].replace(' ', '_') + '_%016X.png' % hv))
            print(n, w, h, 'mips', mips, '0x%016X' % hv, boxes)
    json.dump(res, open(os.path.join(out, 'icons.json'), 'w'), indent=1)
