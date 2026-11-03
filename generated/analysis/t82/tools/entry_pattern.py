import json, struct, sys
sys.path.insert(0, 'ps3recomp-t82/tools')
import spu_disasm as d
mods = json.load(open('generated/analysis/t37/retail_jobs.json'))
for m in mods:
    raw = open('generated/analysis/t37/modules/' + m['file'], 'rb').read()
    e = m['entry_off']; base = 0x4000
    seq = []
    for a in range(e, min(e + 0x100, len(raw) - 4), 4):
        w = struct.unpack_from('>I', raw, a)[0]; i = d.spu_decode(w, base + a)
        seq.append((base + a, i.mnemonic, i.operands))
    ml = None
    for k, (a, mn, op) in enumerate(seq):
        if mn == 'ila' and op.startswith('$r0,'):
            nxt = [x for x in seq[k + 1:k + 4] if x[1] in ('br', 'brz', 'brnz', 'bra')]
            if nxt: ml = (hex(a), op, nxt[0][1], nxt[0][2]); break
    print(f"{m.get('name') or m['sha256'][:12]:28s} entry {base+e:05X} manual-link-body: {ml}")
