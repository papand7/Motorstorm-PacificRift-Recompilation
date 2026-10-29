"""T162: list draws whose enabled texture units resolve to null_srv / zeta / zeta_as_color in an RSXI frame,
with the fragment program, unit, format, address and target -- to attribute black or wrong surfaces.
usage: python null_srv_t162.py <frame_dir> [src ...]"""
import collections, json, os, sys


def main(frame, srcs):
    srcs = set(srcs or ['null_srv'])
    per = collections.Counter()
    zeta_addrs = collections.Counter()
    first = {}
    with open(os.path.join(frame, 'events.jsonl'), encoding='utf-8', errors='replace') as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get('e') == 'draw':
                g = e.get('guest', {})
                zeta_addrs[g.get('zeta')] += 1
            if e.get('e') != 'draw':
                continue
            for t in e.get('tex', []):
                r = t.get('req', {})
                if 'control0' in r and not int(r['control0'], 16) >> 31:
                    continue
                if t.get('src') in srcs:
                    k = (t.get('src'), g.get('fp'), t.get('unit'), r.get('fmt'), r.get('addr'), r.get('w'), r.get('h'),
                         g.get('rt'), g.get('zeta'))
                    per[k] += 1
                    first.setdefault(k, (e.get('op'), t.get('native')))
    for k, v in per.most_common(40):
        print(v, k, 'first op', first[k][0], first[k][1])
    print('-- zeta surfaces bound as depth target in this frame:', dict(zeta_addrs.most_common(10)))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
