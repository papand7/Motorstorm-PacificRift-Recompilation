#!/usr/bin/env python3
"""Map logged archive reads to PSARC members (offline, read-only; private).

  py -3 tools/psarc_read_map.py RUN_DIR [--fd N] [--archive PATH] [--match garage,mainmenu] [--all]

Reads the "[fsread] fd=N want=W got=G pos=P" lines that PS3_FSLOG_READS=N
makes the runtime log, and the archive's own header/TOC/manifest, and reports
which members' compressed bytes each read touched. A touched member means its
bytes were read from the file; it does not show that they were decompressed,
parsed or used. Never prints archive contents.
"""
import argparse
import bisect
import re
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'original' / 'game' / 'PS3_GAME' / 'USRDIR' / 'MS2.PSARC'
READ_RE = re.compile(r'\[fsread\] fd=(\d+) want=(\d+) got=(\d+) pos=(-?\d+)')


def load_index(path: Path):
    """[(start, end, name)] sorted by start: each member's compressed byte span."""
    with open(path, 'rb') as f:
        h = f.read(32)
        if h[:4] != b'PSAR' or h[8:12] != b'zlib':
            raise ValueError('not a zlib PSARC')
        toc_len, entry_len, count, block, _flags = struct.unpack('>5I', h[12:32])
        toc = f.read(entry_len * count)
        nblocks = (toc_len - 32 - entry_len * count) // 2
        lens = struct.unpack(f'>{nblocks}H', f.read(nblocks * 2))
        ents = []
        for i in range(count):
            e = toc[i * entry_len:(i + 1) * entry_len]
            z = int.from_bytes(e[16:20], 'big')
            size = int.from_bytes(e[20:25], 'big')
            off = int.from_bytes(e[25:30], 'big')
            n = (size + block - 1) // block
            span = sum(L or block for L in lens[z:z + n])
            ents.append((off, size, span, z, n))
        off, size, span, z, n = ents[0]           # entry 0 is the manifest
        f.seek(off)
        man = bytearray()
        for L in lens[z:z + n]:
            chunk = f.read(L or block)
            try:
                chunk = zlib.decompress(chunk)
            except zlib.error:
                pass                               # a full-size block is stored raw
            man += chunk
    names = ['<manifest>'] + bytes(man[:size]).decode('utf-8', 'replace').splitlines()
    spans = [(o, o + s, names[i] if i < len(names) else f'<entry {i}>')
             for i, (o, _sz, s, _z, _n) in enumerate(ents)]
    return sorted(spans)


def prefix_end(spans):
    """Running maximum of span ends (monotonic; members may share or overlap bytes)."""
    out, m = [], 0
    for _, e, _ in spans:
        m = max(m, e)
        out.append(m)
    return out


def touched(spans, starts, pos, got, ends=None):
    """Members whose compressed span overlaps [pos, pos+got)."""
    out = []
    ends = ends if ends is not None else prefix_end(spans)
    i = bisect.bisect_right(ends, pos)          # first member whose running end passes pos
    while i < len(spans) and spans[i][0] < pos + got:
        s, e, name = spans[i]
        if e > pos:
            out.append(name)
        i += 1
    return out


def reads(run: Path, fd: int | None):
    text = (run / 'stderr.log').read_text(encoding='utf-8', errors='replace')
    for n, line in enumerate(text.splitlines(), 1):
        m = READ_RE.search(line)
        if m and (fd is None or int(m.group(1)) == fd):
            yield n, int(m.group(1)), int(m.group(3)), int(m.group(4))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('run', type=Path)
    ap.add_argument('--fd', type=int)
    ap.add_argument('--archive', type=Path, default=ARCHIVE)
    ap.add_argument('--match', default='garage,mainmenu', help='comma-separated name substrings to report first hits for')
    ap.add_argument('--all', action='store_true', help='print every read and its members')
    a = ap.parse_args(argv)
    spans = load_index(a.archive)
    starts = [s for s, _, _ in spans]
    ends = prefix_end(spans)
    keys = [k.lower() for k in a.match.split(',') if k]
    first, members, nread, nbytes = {}, set(), 0, 0
    for line, fd, got, pos in reads(a.run, a.fd):
        nread += 1
        nbytes += got
        names = touched(spans, starts, pos, got, ends)
        members.update(names)
        if a.all:
            print(f'stderr:{line} fd={fd} pos={pos} got={got} -> {names[:4]}{" ..." if len(names) > 4 else ""}')
        for k in keys:
            if k not in first:
                hit = next((nm for nm in names if k in nm.lower()), None)
                if hit:
                    first[k] = (line, pos, hit)
    print(f'{nread} reads, {nbytes} bytes, {len(members)} distinct members touched')
    for k in keys:
        print(f'first "{k}" member: ' + (f'stderr:{first[k][0]} pos={first[k][1]} {first[k][2]}' if k in first
                                         else 'none read'))
    print('note: a touched member was read from the archive file; decompression, parsing and use are not shown.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
