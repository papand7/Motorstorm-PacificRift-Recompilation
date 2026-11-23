#!/usr/bin/env python3
"""Collect every texture of MotorStorm: Pacific Rift from the player's own MS2.PSARC, with no game running.

Public-tree code: it contains no game data and no keys. It reads the archive the player owns, finds every
texture resource in its 'EVOSBIG ' packs (resource type 5), and writes each one in the form the in-game dump
(RSX_TEX_DUMP) writes: <w>x<h>_<rsx format>_<hash>.dds, level 0 only, BC1/BC2/BC3 blocks as they are or
R8G8B8A8 for A8R8G8B8. The key is the one the engine computes in guest memory: a 64-bit word-wise FNV-1a over
every byte of the texture's mip chain as the game stores it (the archive stores exactly those bytes), so a
file written here is found by the existing texture-pack code (RSX_TEX_PACK) and upscaled by "Make the HD pack".

Usage:  py -3 texcollect.py --play <play folder> [--game <folder with MS2.PSARC>] [--out <dump folder>]
Output defaults to <play>/textures/dump.  The dump is derived from the game's data: keep it on this PC.
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from psarc import Psarc, evosbig_sections  # noqa: E402

try:
    import numpy as np
except ImportError:          # the A8R8G8B8 path needs it; block formats do not
    np = None

M64 = (1 << 64) - 1
FNV_OFFSET = 1469598103934665603
FNV_PRIME = 1099511628211

# Archive pixel format byte -> RSX format (swizzled), block bytes (0 = 4 bytes per texel).
ARCHIVE_FORMATS = {0x01: (0x85, 0), 0x09: (0x86, 8), 0x0A: (0x87, 16), 0x0B: (0x88, 16)}
LINEAR = 0x20          # RSX 'LN' bit: the format byte of a texture that is not power-of-two sized


def fnv_words(d):
    """The engine's texture content hash: 64-bit FNV-1a over native-order 8-byte words, then single bytes."""
    h = FNV_OFFSET
    n = len(d) & ~7
    if n:
        for w in memoryview(d)[:n].cast('Q'):
            h = ((h ^ w) * FNV_PRIME) & M64
    for b in d[n:]:
        h = ((h ^ b) * FNV_PRIME) & M64
    return h


def level_bytes(fmt, block, w, h):
    if block:
        return ((w + 3) // 4) * ((h + 3) // 4) * block
    return w * h * 4


def chain_bytes(fmt, block, w, h, levels):
    """Bytes a mip chain spans (the engine's rsx_texture_mip_chain: levels packed one after another)."""
    total, lw, lh = 0, w, h
    for _ in range(max(levels, 1)):
        total += level_bytes(fmt, block, lw, lh)
        if lw == 1 and lh == 1:
            break
        lw, lh = max(lw >> 1, 1), max(lh >> 1, 1)
    return total


def pow2(v):
    return v > 0 and (v & (v - 1)) == 0


def morton_index(w, h):
    """Swizzle offsets of a w x h image (RSX Morton order; the longer side's extra bits are on top)."""
    x = np.arange(w, dtype=np.uint32)[None, :]
    y = np.arange(h, dtype=np.uint32)[:, None]
    lw, lh = w.bit_length() - 1, h.bit_length() - 1
    off = np.zeros((h, w), dtype=np.uint32)
    shift = 0
    xs, ys = x, y
    while lw and lh:
        off |= (xs & 1) << shift
        xs = xs >> 1
        shift += 1
        off |= (ys & 1) << shift
        ys = ys >> 1
        shift += 1
        lw -= 1
        lh -= 1
    off |= (xs | ys) << shift
    return off


def dds_header(fmt, w, h):
    hd = bytearray(128)
    hd[0:4] = b'DDS '
    struct.pack_into('<I', hd, 4, 124)
    bc = fmt != 0x85 and fmt != 0xA5
    struct.pack_into('<I', hd, 8, 0x1007 | (0x80000 if bc else 0x8))
    struct.pack_into('<II', hd, 12, h, w)
    block = 8 if fmt & 0x9F == 0x86 else 16
    struct.pack_into('<I', hd, 20, ((w + 3) // 4) * ((h + 3) // 4) * block if bc else w * 4)
    struct.pack_into('<I', hd, 28, 1)
    struct.pack_into('<I', hd, 76, 32)
    if bc:
        struct.pack_into('<I', hd, 80, 4)
        hd[84:88] = {0x86: b'DXT1', 0x87: b'DXT3', 0x88: b'DXT5'}[fmt & 0x9F]
    else:
        struct.pack_into('<I', hd, 80, 0x41)
        struct.pack_into('<I', hd, 88, 32)
        struct.pack_into('<IIII', hd, 92, 0x000000FF, 0x0000FF00, 0x00FF0000, 0xFF000000)
    struct.pack_into('<I', hd, 108, 0x1000)
    return bytes(hd)


def level0_dds(fmt, block, w, h, data):
    """The dump file for level 0: BC blocks as stored, or A,R,G,B texels (swizzled when the size allows) as R,G,B,A."""
    if block:
        return dds_header(fmt, w, h) + bytes(data[:level_bytes(fmt, block, w, h)])
    if np is None:
        return None
    raw = np.frombuffer(data, dtype=np.uint8, count=w * h * 4).reshape(-1, 4)
    if not (fmt & LINEAR):
        raw = raw[morton_index(w, h).reshape(-1)]
    rgba = raw[:, [1, 2, 3, 0]]
    return dds_header(fmt, w, h) + rgba.tobytes()


def find_psarc(game):
    if os.path.isfile(game):
        return game
    for root, _dirs, files in os.walk(game):
        for f in files:
            if f.lower() == 'ms2.psarc':
                return os.path.join(root, f)
    raise SystemExit('MS2.PSARC not found under ' + game)


def parse_texture(body):
    """Fields of a type-5 section: (width, height, depth, archive format, mips, flags, data) or None."""
    if len(body) < 27 or struct.unpack_from('>H', body, 0)[0] != 2:
        return None
    w, h, depth, fmt = struct.unpack_from('>HHHH', body, 12)
    mips, cube, _one, n = body[20], body[21], body[22], struct.unpack_from('>I', body, 23)[0]
    return w, h, depth, fmt, mips, cube, body[27:27 + n]


def collect(psarc_path, out_dir, min_side=16, progress=print, write=True):
    a = Psarc(psarc_path)
    os.makedirs(out_dir, exist_ok=True)
    stat = {'sections': 0, 'members_with_textures': 0, 'duplicates': 0, 'unique': 0, 'written': 0,
            'existing': 0, 'small': 0, 'cube': 0, 'volume': 0, 'unsupported_format': {}, 'size_mismatch': 0}
    keys = {}                       # key -> first (member, name)
    seen = {}                       # digest of what defines a key -> key
    t0 = time.time()
    for n, (name, idx) in enumerate(a.members()):
        d = a.read(idx)
        secs = evosbig_sections(d)
        had = False
        for ty, names, body in secs:
            if ty != 5:
                continue
            t = parse_texture(body)
            stat['sections'] += 1
            had = True
            if t is None:
                stat['size_mismatch'] += 1
                continue
            w, h, depth, fmt, mips, cube, data = t
            if cube == 2 or cube == 3:
                stat['cube'] += 1
                continue
            if depth > 1 or cube == 1:
                stat['volume'] += 1
                continue
            if fmt not in ARCHIVE_FORMATS:
                stat['unsupported_format'][fmt] = stat['unsupported_format'].get(fmt, 0) + 1
                continue
            if w < min_side or h < min_side:
                stat['small'] += 1
                continue
            rsx, block = ARCHIVE_FORMATS[fmt]
            if not (pow2(w) and pow2(h)):
                rsx |= LINEAR
            span = chain_bytes(rsx, block, w, h, mips)
            if len(data) < span:
                stat['size_mismatch'] += 1
                continue
            data = data[:span]
            dig = hashlib.md5(struct.pack('<IIII', w, h, rsx, mips) + data).digest()
            if dig in seen:
                stat['duplicates'] += 1
                continue
            key = '%dx%d_%02x_%016x' % (w, h, rsx, fnv_words(data))
            seen[dig] = key
            if key in keys:
                stat['duplicates'] += 1
                continue
            keys[key] = (name, names[0] if names else '')
            stat['unique'] += 1
            path = os.path.join(out_dir, key + '.dds')
            if os.path.exists(path):
                stat['existing'] += 1
                continue
            if write:
                blob = level0_dds(rsx, block, w, h, data)
                if blob is None:
                    raise SystemExit('numpy is needed for A8R8G8B8 textures: py -3 -m pip install numpy')
                with open(path, 'wb') as f:
                    f.write(blob)
                stat['written'] += 1
        if had:
            stat['members_with_textures'] += 1
        if progress and n % 500 == 0:
            progress('[texcollect] %d members, %d textures (%.0fs)' % (n, stat['unique'], time.time() - t0))
    stat['unsupported_format'] = {'0x%02x' % k: v for k, v in sorted(stat['unsupported_format'].items())}
    return stat, keys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--play', help='the play folder (output goes to <play>/textures/dump)')
    ap.add_argument('--game', help='folder holding MS2.PSARC, or the archive itself (default: <play>/../original/game)')
    ap.add_argument('--out', help='dump folder (default <play>/textures/dump)')
    ap.add_argument('--min', type=int, default=16, help='smallest side to keep (RSX_TEX_DUMP_MIN, default 16)')
    ap.add_argument('--report', help='write the totals as JSON here')
    ap.add_argument('--dry-run', action='store_true', help='count and key only; write nothing')
    a = ap.parse_args()
    if not a.out and not a.play:
        ap.error('give --play or --out')
    out = a.out or os.path.join(a.play, 'textures', 'dump')
    game = a.game or (os.path.join(a.play, '..', 'original', 'game') if a.play else None)
    if not game:
        ap.error('give --game')
    stat, keys = collect(find_psarc(game), out, a.min, write=not a.dry_run)
    print('[texcollect] %d textures (unique keys) from %d texture sections; wrote %d, %d already there'
          % (len(keys), stat['sections'], stat['written'], stat['existing']))
    print('[texcollect] not collected: %d cube, %d volume, %d small, %s unsupported format, %d size mismatch'
          % (stat['cube'], stat['volume'], stat['small'], stat['unsupported_format'], stat['size_mismatch']))
    if a.report:
        with open(a.report, 'w') as f:
            json.dump(dict(stat, keys=sorted(keys)), f, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
