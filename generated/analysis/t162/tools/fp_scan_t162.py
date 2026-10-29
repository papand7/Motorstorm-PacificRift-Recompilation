"""T162: scan RSXI fp_*.ucode dumps (NV40 fragment ucode, half-word swapped words) for
source-modifier and opcode use.  Read-only; prints per-program and total counts.
usage: python fp_scan_t162.py <shaders_dir> [...]"""
import collections, glob, os, struct, sys

NAMES = {0x00: 'NOP', 0x01: 'MOV', 0x02: 'MUL', 0x03: 'ADD', 0x04: 'MAD', 0x05: 'DP3', 0x06: 'DP4',
         0x07: 'DST', 0x08: 'MIN', 0x09: 'MAX', 0x0A: 'SLT', 0x0B: 'SGE', 0x0C: 'SLE', 0x0D: 'SGT',
         0x0E: 'SNE', 0x0F: 'SEQ', 0x10: 'FRC', 0x11: 'FLR', 0x12: 'KIL', 0x13: 'PK4B', 0x14: 'UP4B',
         0x15: 'DDX', 0x16: 'DDY', 0x17: 'TEX', 0x18: 'TXP', 0x19: 'TXD', 0x1A: 'RCP', 0x1B: 'RSQ',
         0x1C: 'EX2', 0x1D: 'LG2', 0x1E: 'LIT', 0x1F: 'LRP', 0x20: 'STR', 0x21: 'SFL', 0x22: 'COS',
         0x23: 'SIN', 0x24: 'PK2H', 0x25: 'UP2H', 0x26: 'POW', 0x27: 'PK4UB', 0x28: 'UP4UB',
         0x29: 'PK2US', 0x2A: 'UP2US', 0x2C: 'PKG', 0x2D: 'UPG', 0x2E: 'DP2A', 0x2F: 'TXL', 0x31: 'TXB',
         0x33: 'TEXBEM', 0x34: 'TXPBEM', 0x36: 'RFL', 0x38: 'DP2', 0x39: 'NRM', 0x3A: 'DIV',
         0x3B: 'DIVSQ', 0x3C: 'LIF', 0x3D: 'FENCT', 0x3E: 'FENCB'}
SRC2_OPS = {0x04, 0x1F, 0x2E}          # MAD, LRP, DP2A read src2


def word(b, i):
    be = struct.unpack_from('>I', b, i)[0]
    return ((be << 16) | (be >> 16)) & 0xffffffff


def scan(path):
    b = open(path, 'rb').read()
    off, ins = 0, []
    while off + 16 <= len(b):
        w = [word(b, off + 4 * k) for k in range(4)]
        off += 16
        branch = (w[2] >> 31) & 1
        op = ((w[0] >> 24) & 0x3F) | (branch << 6)
        ins.append((op, w))
        if not branch and any((w[k] & 3) == 2 for k in (1, 2, 3)):
            off += 16
        if w[0] & 1:
            break
    return ins


def main(dirs):
    tot = collections.Counter()
    hits = []
    for d in dirs:
        for p in sorted(glob.glob(os.path.join(d, 'fp_*.ucode'))):
            name = os.path.basename(p)
            for i, (op, w) in enumerate(scan(p)):
                n = NAMES.get(op & 0x3F, '?') if op < 0x40 else 'BR%02X' % op
                tot['op_' + n] += 1
                if op >= 0x40:
                    continue
                if (w[1] >> 29) & 1: tot['src0_abs'] += 1
                if (w[2] >> 18) & 1: tot['src1_abs'] += 1
                if (w[3] >> 18) & 1:
                    tot['src2_abs_any'] += 1
                    if op in SRC2_OPS:
                        tot['src2_abs_used'] += 1
                        hits.append((name, i, n, ['%08X' % x for x in w]))
                if (w[2] >> 28) & 7: tot['dst_scale'] += 1
                if (w[0] >> 31) & 1: tot['dst_sat'] += 1
            tot['programs'] += 1
    for k in sorted(tot):
        print('%-16s %d' % (k, tot[k]))
    for h in hits[:40]:
        print('SRC2.abs', *h)
    print('programs with SRC2.abs on MAD/LRP/DP2A:', len({h[0] for h in hits}))


if __name__ == '__main__':
    main(sys.argv[1:])
