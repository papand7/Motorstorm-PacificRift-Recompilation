"""T70C (offline, read-only): the bisl sites of one retail module with the 4 preceding
instructions, to see how the call target is formed. Usage: py -3 -I t70c_bisl.py <name>"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'ps3recomp-t70/tools'))
from spu_disasm import spu_decode
MODS = ROOT / 'generated/analysis/t37/modules'
MAN = json.loads((ROOT / 'generated/spu_raw/wws_reloc/wws_reloc_manifest.json').read_text())
m = next(x for x in MAN if x['name'] == sys.argv[1])
b = (MODS / m['file']).read_bytes()
B = 0x4000
w = lambda o: int.from_bytes(b[o:o + 4], 'big')
def d(o):
    i = spu_decode(w(o), B + o)
    return f'{B + o:05X} {i.mnemonic} {getattr(i, "op_str", "")}'
print(m['name'], 'entry', hex(B + m['entry_off']))
for o in range(0x30, len(b) & ~3, 4):
    if spu_decode(w(o), B + o).mnemonic.startswith('bisl'):
        print(' | '.join(d(k) for k in range(max(0x30, o - 16), o + 4, 4)))
