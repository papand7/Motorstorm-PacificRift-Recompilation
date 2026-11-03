"""T162: who writes and who samples one surface address in an RSXI frame.
usage: python rt_trace_t162.py <frame_dir> <addr hex>"""
import collections, json, os, sys


def main(frame, addr):
    addr = int(addr, 16)
    writes, reads, clears = collections.Counter(), collections.Counter(), []
    detail = []
    with open(os.path.join(frame, 'events.jsonl'), encoding='utf-8', errors='replace') as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            kind = e.get('e')
            if kind != 'draw':
                if any(isinstance(v, str) and v.startswith('0x') and int(v, 16) == addr for v in e.values()) or \
                        json.dumps(e).find('0x%08X' % addr) >= 0:
                    clears.append(json.dumps(e)[:400])
                continue
            g = e.get('guest', {})
            rt = int(g.get('rt', '0x0'), 16)
            zeta = int(g.get('zeta', '0x0'), 16)
            if rt == addr or zeta == addr:
                k = ('W', g.get('fp'), g.get('prim'), g.get('rt_w'), g.get('rt_h'), g.get('rt_fmt'), 'zeta' if zeta == addr else 'color',
                     'depth', json.dumps(g.get('depth')), 'blend', g.get('blend'), 'cmask', g.get('cmask'),
                     'vp', json.dumps(g.get('viewport')), 'scis', json.dumps(g.get('scissor')))
                writes[k] += 1
                if len(detail) < 6:
                    detail.append((e.get('op'), g.get('count'), g.get('indexed'), json.dumps(e.get('native', {}))[:300]))
            for t in e.get('tex', []):
                r = t.get('req', {})
                if int(r.get('addr', '0x0'), 16) == addr:
                    reads[(g.get('fp'), t.get('unit'), r.get('fmt'), t.get('src'), g.get('rt'))] += 1
    for k, v in writes.most_common(20):
        print(v, *k)
    for d in detail:
        print('  op', *d)
    print('-- sampled by')
    for k, v in reads.most_common(20):
        print(v, k)
    print('-- non-draw events mentioning it')
    for c in clears[:12]:
        print(c)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
