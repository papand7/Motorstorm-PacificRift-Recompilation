"""T169: host work one captured frame implies for each correction: distinct textures and bytes (level 0 against the
guest chain), PSO variants the transfers add, distinct guest samplers, per-draw sampler-table changes against the
fixed path, guest packets against host records, render-target binds.
usage: py -3 work_census_t169.py <events.jsonl>"""
import collections, sys
from rsxi_parse_t169 import read_events

BPP = {0x05: 4, 0x01: 1, 0x06: 8, 0x07: 16, 0x08: 16, 0x09: 2, 0x1A: 8, 0x1E: 4}   # DXT: bytes per 4x4 block


def size(w, h, fmt, levels):
    f = fmt & 0x1F
    tot0 = tot = 0
    for l in range(levels):
        a, b = max(w >> l, 1), max(h >> l, 1)
        n = ((a + 3) // 4) * ((b + 3) // 4) * BPP[f] if f in (6, 7, 8) else a * b * BPP.get(f, 4)
        tot += n
        if l == 0:
            tot0 = n
    return tot0, tot


ev = list(read_events(sys.argv[1]))
draws = [e for e in ev if e['e'] == 'draw']
tex = {}
samplers = set()
cur = [None] * 16
changes = 0
variants_base, variants_xfer = set(), set()
off = collections.Counter()
for e in draws:
    g = e['guest']
    off[g['cmd_offset']] += 1
    mask = []
    for t in e.get('tex', []):
        q = t.get('req', {})
        if not q.get('set'):
            continue
        k = (q['filter'], q['address'], q['control0'])
        samplers.add(k)
        if cur[t['unit']] != k:
            changes += 1
            cur[t['unit']] = k
        mask.append((t['unit'], q.get('gamma_mask'), q.get('expand_mask')))
        if t.get('src') == 'upload':
            tex[q['addr']] = (q['w'], q['h'], int(q['fmt'], 16), q.get('mips', 1))
    base = (g['fp'], g['vs_hash'], g['blend_key'], g['cmask'], g['cull'], g['rt_fmt'])
    variants_base.add(base)
    variants_xfer.add(base + (g.get('srgb_output'), tuple(mask)))
b0 = bn = 0
for w, h, f, m in tex.values():
    a, b = size(w, h, f, m)
    b0 += a
    bn += b
rb = [e for e in ev if e['e'] == 'bind_rt']
print(f'draw records {len(draws)}, distinct FIFO offsets {len(off)}, largest packet {off.most_common(1)[0][1]} records')
print(f'textures {len(tex)}, level 0 {b0 / 1048576:.1f} MiB, chains {bn / 1048576:.1f} MiB, +{100 * (bn - b0) / max(b0, 1):.1f} %')
print(f'distinct guest samplers {len(samplers)} of 2032 descriptors; table changes with guest samplers {changes} ({changes / len(draws):.2f} per draw)')
print(f'pipeline identities (fp, vs, blend, cmask, cull, fmt) {len(variants_base)}; with transfer state {len(variants_xfer)} (upper bound: unsampled units count)')
print(f'render-target binds {len(rb)}, frame_end {[e for e in ev if e["e"] == "frame_end"]}')
