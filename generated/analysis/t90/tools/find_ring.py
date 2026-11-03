"""T90: find every mulli rD,rA,0x644 (pad ring entry size) in the retail ELF text."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 't84' / 'tools'))
import elf
for seg in elf.TEXT:
    va, ws = elf.words(seg)
    for i, w in enumerate(ws):
        if (w & 0xFC00FFFF) == 0x1C000644:
            a = va + 4 * i
            print(f'{a:08X} func~{elf.func_start(a) or 0:08X}')
