"""T82: which PM `bi $rN` sites compute_link_returns classifies as link returns, old (t70g) vs patched (t82)."""
import importlib.util, json, struct, sys
def load(tree):
    sys.path.insert(0, f'{tree}/tools')
    spec = importlib.util.spec_from_file_location(f'L_{tree}', f'{tree}/tools/spu_lifter.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); sys.path.pop(0); return m
raw = open('generated/spu_raw/wws_job_pm.bin', 'rb').read(); base = 0xA00
rep = json.load(open('generated/spu_raw/wws_job_pm_lift.json'))
bounds = [tuple(f) for f in rep['functions']]
res = {}
for tree in ('ps3recomp-t70g', 'ps3recomp-t82'):
    L = load(tree)
    import spu_disasm as d
    insns = [d.spu_decode(struct.unpack_from('>I', raw, o)[0], base + o) for o in range(0, len(raw) - 3, 4)]
    res[tree] = L.compute_link_returns(insns, bounds)
a, b = res['ps3recomp-t70g'], res['ps3recomp-t82']
print('old', sorted(hex(x) for x in a)); print('new', sorted(hex(x) for x in b))
print('reclassified (return -> dispatch):', sorted(hex(x) for x in a - b))
