"""T162: BMP (24/32-bit, as written by RSXI) -> PNG, optional crop and brightness gain, no PIL.
usage: python bmp2png_t162.py in.bmp out.png [gain] [x0 y0 x1 y1]"""
import struct, sys, zlib


def read_bmp(path):
    b = open(path, 'rb').read()
    off = struct.unpack_from('<I', b, 10)[0]
    w, h = struct.unpack_from('<ii', b, 18)
    bpp = struct.unpack_from('<H', b, 28)[0]
    bypp = bpp // 8
    flip = h > 0
    h = abs(h)
    stride = (w * bypp + 3) & ~3
    rows = []
    for y in range(h):
        sy = h - 1 - y if flip else y
        r = b[off + sy * stride: off + sy * stride + w * bypp]
        px = bytearray()
        for x in range(w):
            p = r[x * bypp: x * bypp + 3]
            px += bytes((p[2], p[1], p[0]))
        rows.append(px)
    return w, h, rows


def write_png(path, w, h, rows):
    raw = b''.join(b'\x00' + bytes(r) for r in rows)
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


if __name__ == '__main__':
    w, h, rows = read_bmp(sys.argv[1])
    gain = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    if len(sys.argv) > 7:
        x0, y0, x1, y1 = map(int, sys.argv[4:8])
        rows = [r[x0 * 3:x1 * 3] for r in rows[y0:y1]]
        w, h = x1 - x0, y1 - y0
    if gain != 1.0:
        rows = [bytearray(min(255, int(v * gain)) for v in r) for r in rows]
    write_png(sys.argv[2], w, h, rows)
    print(sys.argv[2], w, h)
