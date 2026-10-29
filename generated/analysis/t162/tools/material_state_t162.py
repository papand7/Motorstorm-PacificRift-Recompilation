"""T162: per-unit sampler requests of the lit-material draws (draws whose enabled units include a cube map)
in RSXI captures: min filter, wrap modes, mips, LOD bias, format -- versus what the default renderer applies
(unit 0 point/clamp, units 1-15 linear/wrap, one level).
usage: python material_state_t162.py <rsxi_dir> [...]"""
import collections, glob, json, os, sys

MIN = {1: 'NEAREST', 2: 'LINEAR', 3: 'N_MIP_N', 4: 'L_MIP_N', 5: 'N_MIP_L', 6: 'L_MIP_L', 7: 'CONV'}
WRAP = {1: 'wrap', 2: 'mirror', 3: 'clamp_edge', 4: 'border', 5: 'clamp', 6: 'mo_edge', 7: 'mo_border', 8: 'mo_clamp'}


def main(dirs):
    per = collections.Counter()
    draws = mat = 0
    fps = collections.Counter()
    for d in dirs:
        for p in glob.glob(os.path.join(d, 'frames', '*', 'events.jsonl')):
            for line in open(p, encoding='utf-8', errors='replace'):
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get('e') != 'draw':
                    continue
                draws += 1
                tex = [t for t in e.get('tex', []) if 'control0' not in t.get('req', {}) or int(t['req']['control0'], 16) >> 31]
                if not any(t['req'].get('cube') for t in tex):
                    continue
                mat += 1
                fps[e['guest'].get('fp')] += 1
                for t in tex:
                    r = t['req']
                    f, a = int(r['filter'], 16), int(r['address'], 16)
                    bias = (f & 0x1FFF) - (0x2000 if f & 0x1000 else 0)
                    key = (t['unit'], r['fmt'], 'cube' if r.get('cube') else '2d', 'mips%d' % r.get('mips', 1),
                           MIN.get((f >> 16) & 7, '?'), WRAP.get(a & 15, '?') + '/' + WRAP.get((a >> 8) & 15, '?'),
                           'bias%+.2f' % (bias / 256.0), 'gamma%X' % ((a >> 20) & 15))
                    per[key] += 1
    print('draws', draws, 'lit-material draws (a cube bound)', mat, 'programs', len(fps))
    for k, v in sorted(per.items()):
        print('%6d' % v, *k)


if __name__ == '__main__':
    main(sys.argv[1:])
