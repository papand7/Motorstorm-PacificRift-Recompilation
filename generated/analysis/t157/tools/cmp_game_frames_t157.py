"""T157: compare the game runs' CELLMARK_DUMP frames (runtime-*/frames/*.bmp) by relative path: sha256 equality and,
when they differ, the number of differing pixels (BMP pixel data compared byte-wise per 3/4-byte pixel).
  py -3 cmp_game_frames_t157.py <runtime_dir_ref> <runtime_dir> ...     prints one line per pair and frame"""
import hashlib, struct, sys
from pathlib import Path
def load(p):
    b = p.read_bytes(); off = struct.unpack_from('<I', b, 10)[0]; bpp = struct.unpack_from('<H', b, 28)[0]
    return b, b[off:], max(1, bpp // 8)
ref = Path(sys.argv[1])
for other in map(Path, sys.argv[2:]):
    same = 0; lines = []
    for f in sorted((ref / 'frames').glob('*.bmp')):
        g = other / 'frames' / f.name
        if not g.exists(): lines.append(f'  {f.name}: missing'); continue
        a, pa, n = load(f); b, pb, _ = load(g)
        if hashlib.sha256(a).digest() == hashlib.sha256(b).digest(): same += 1; continue
        d = sum(1 for i in range(0, min(len(pa), len(pb)) - n + 1, n) if pa[i:i + n] != pb[i:i + n])
        lines.append(f'  {f.name}: differ, {d} of {len(pa) // n} pixels')
    print(f'{ref.name} vs {other.name}: {same} identical'); print('\n'.join(lines)) if lines else None
