"""T70C (offline, read-only): in the retail Wws job modules, the instructions before the
mid-job re-entry PCs seen in A1, and every call (brsl/brasl/bisl/bisled) whose target can
leave the module (absolute brasl, any bisl). Usage: py -3 -I t70c_callsites.py"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'ps3recomp-t70/tools'))
from spu_disasm import spu_decode
MODS = ROOT / 'generated/analysis/t37/modules'
MAN = json.loads((ROOT / 'generated/spu_raw/wws_reloc/wws_reloc_manifest.json').read_text())
BASE = 0x4000
def word(b, o): return int.from_bytes(b[o:o + 4], 'big')
def dis(b, o, ls):
    i = spu_decode(word(b, o), ls)
    return f'{ls:05X}: {word(b, o):08X} {i.mnemonic} {i.op_str if hasattr(i, "op_str") else getattr(i, "operands", "")}'
reentry = {0x051A8: 'octreequery', 0x15D20: None, 0x16060: None}
for m in MAN:
    b = (MODS / m['file']).read_bytes()
    lo, hi = BASE, BASE + len(b)
    for pc in reentry:
        if lo + 0x30 <= pc < hi and (reentry[pc] is None or reentry[pc] in m['name']):
            print(f'{m["name"]}: around re-entry 0x{pc:05X}')
            for a in range(pc - 12, pc + 4, 4):
                print('   ', dis(b, a - BASE, a))
    calls = []
    for o in range(0x30, len(b) & ~3, 4):
        i = spu_decode(word(b, o), BASE + o)
        if i.mnemonic in ('brasl', 'bisl', 'bisled', 'bisle', 'bisld'):
            calls.append(i.mnemonic)
    print(f'  {m["name"]:44s} size 0x{len(b):05X} brasl/bisl* calls: {len(calls)} {sorted(set(calls))}')
