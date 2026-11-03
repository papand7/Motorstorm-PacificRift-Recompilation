# T65: list 2D texture resources in an EVOSBIG .rpk and decode DXT5 ones to PNG (private analysis helper).
# usage: py -3 -I rpk_dxt5.py RPK OUTDIR [name-substring ...]
# Texture resource (type 2): 43-byte header, u16 w at +0x1C, u16 h at +0x1E, then w/4*h/4 DXT5 blocks.
import os, re, struct, sys, zlib
rpk, outdir, want = sys.argv[1], sys.argv[2], sys.argv[3:]
d = open(rpk, 'rb').read()
offs = [m.start() for m in re.finditer(b'EVOSBIG ', d)]
names = [m.group().decode('latin1') for m in re.finditer(rb'[\x20-\x7e]+?\.dds', d[0x5A:offs[2]])]
tex = [o for o in offs if d[o + 0x10:o + 0x12] == b'\x00\x02']
def c565(c): return (((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31)
def dxt5(buf, w, h):
    px = bytearray(w * h * 4); bw = w // 4
    for b in range(bw * (h // 4)):
        blk = buf[b * 16:b * 16 + 16]; a0, a1 = blk[0], blk[1]
        ai = int.from_bytes(blk[2:8], 'little')
        al = [a0, a1] + ([((6 - i) * a0 + (1 + i) * a1) // 7 for i in range(6)] if a0 > a1 else
                         [((4 - i) * a0 + (1 + i) * a1) // 5 for i in range(4)] + [0, 255])
        c0, c1 = struct.unpack('<HH', blk[8:12]); ci = int.from_bytes(blk[12:16], 'little')
        p0, p1 = c565(c0), c565(c1)
        cl = [p0, p1, tuple((2 * x + y) // 3 for x, y in zip(p0, p1)), tuple((x + 2 * y) // 3 for x, y in zip(p0, p1))]
        bx, by = (b % bw) * 4, (b // bw) * 4
        for i in range(16):
            r, g, bb = cl[(ci >> (2 * i)) & 3]; a = al[(ai >> (3 * i)) & 7]
            o = ((by + i // 4) * w + bx + i % 4) * 4; px[o:o + 4] = bytes((r, g, bb, a))
    return px
def png(path, px, w, h):
    raw = b''.join(b'\0' + bytes(px[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    ch = lambda t, x: struct.pack('>I', len(x)) + t + x + struct.pack('>I', zlib.crc32(t + x))
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b''))
os.makedirs(outdir, exist_ok=True)
print('names', len(names), 'texture resources', len(tex))
for i, o in enumerate(tex):
    w, h = struct.unpack('>HH', d[o + 0x1C:o + 0x20])
    end = min([x for x in offs if x > o] + [len(d)]); n = w // 4 * (h // 4) * 16
    nm = names[i - 1] if 0 < i <= len(names) else 'res%d' % i   # resource 0 has no name entry: res i <-> name i-1 (verified: 80x92 res 97 = padlock)
    ok = end - o - 43 == n
    if want and not any(s in nm for s in want): continue
    px = dxt5(d[o + 43:o + 43 + n], w, h)
    a = px[3::4]; rgb = [sum(px[c::4]) / (w * h) for c in range(3)]
    print('%3d %-28s %4dx%-4d size_ok=%d mean_rgb=%5.1f,%5.1f,%5.1f alpha min/mean/max=%d/%.1f/%d opaque_white=%.3f' % (
        i, nm, w, h, ok, *rgb, min(a), sum(a) / len(a), max(a),
        sum(1 for k in range(0, len(px), 4) if px[k] >= 250 and px[k + 1] >= 250 and px[k + 2] >= 250 and px[k + 3] >= 250) / (w * h)))
    png(os.path.join(outdir, nm.replace('.dds', '.png')), px, w, h)
