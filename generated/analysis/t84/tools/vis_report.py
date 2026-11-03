#!/usr/bin/env python3
"""T84B: summarize a PT log taken with t84/vis_trace_v1.cfg or vis_trace_v2.cfg (offline).

Per view (index = [view+0x430]) it prints: visibility kicks, scene lists kicked, Vis::Wait calls
by renderer family (lr), ExecutePushBuffer batches and entries, and, for v2, the last and the
maximum of each of the 8 PVS counters and of the visible count pair. A view whose renderers wait
but never call ExecutePushBuffer has an empty visible list; a view never kicked has no visibility.
  py -3 -I vis_report.py <PT log (stderr.log or the PT out= file)>"""
import collections, re, sys

LINE = re.compile(r'\[PT\] .*?ev=(\w+) pc=([0-9A-F]{8}) lr=([0-9A-F]{8})(.*)')
FIELD = re.compile(r' (r\d+|m\[\[?r\d+\+0x[0-9A-F]+\]?(?:\+0x[0-9A-F]+\])?)=([0-9A-F]{8}|--)')
FAMILY = {0x9440: 'simple-blended', 0x9442: 'simple-unblended', 0x9447: 'zpass', 0x944A: 'blended',
          0x944C: 'unblended', 0x944F: 'shadow', 0x4827: 'family481B00', 0x4829: 'family481B00',
          0x482A: 'family481B00', 0x482B: 'family481B00', 0x482D: 'family481B00', 0x4830: 'family481B00'}


def fields(rest):
    return {k: (None if v == '--' else int(v, 16)) for k, v in FIELD.findall(rest)}


def family(lr):
    return FAMILY.get(lr >> 8, f'lr{lr:08X}')


def main(path):
    view_of_vis = {}          # vis -> view index
    idx_of_view = {}          # view object -> index
    kicks = collections.Counter(); lists = collections.defaultdict(set)
    waits = collections.defaultdict(collections.Counter)
    pb = collections.defaultdict(lambda: [0, 0])
    stats = collections.defaultdict(lambda: {'last': None, 'max': [0] * 10})
    bb = collections.Counter(); other = collections.Counter(); n = 0
    pending_view = {}          # tid -> view index from the last 458558 entry
    for line in open(path, encoding='utf-8', errors='replace'):
        m = LINE.search(line)
        if not m:
            continue
        ev, pc, lr, rest = m.group(1), int(m.group(2), 16), int(m.group(3), 16), m.group(4)
        f = fields(rest); n += 1
        tid = re.search(r'tid=(\d+)', line)
        tid = tid.group(1) if tid else '0'
        if ev == 'enter' and pc == 0x458558:
            view = f.get('r4'); idx = f.get('m[r4+0x430]')
            if view is not None and idx is not None:
                idx_of_view[view] = idx
            pending_view[tid] = (idx, f.get('r3'))
        elif ev == 'enter' and pc == 0x45CB30:
            vis = f.get('r3')
            idx = f.get('m[[r3+0x0]+0x430]')
            if idx is None and f.get('m[r3+0x0]') in idx_of_view:
                idx = idx_of_view[f['m[r3+0x0]']]
            if idx is None and tid in pending_view:
                idx = pending_view[tid][0]
            if vis is not None and idx is not None:
                view_of_vis[vis] = idx
            kicks[idx] += 1
            if tid in pending_view:
                lists[idx].add(pending_view[tid][1])
            vals = [f.get(f'm[[r3+0x220]+0x{o:X}]') for o in range(0, 0x20, 4)] + \
                   [f.get('m[[r3+0x278]+0x0]'), f.get('m[[r3+0x278]+0x4]')]
            if any(v is not None for v in vals):
                s = stats[idx]; s['last'] = vals
                s['max'] = [max(a, b or 0) for a, b in zip(s['max'], vals)]
        elif ev == 'enter' and pc == 0x45CAA8:
            vis = f.get('r3')
            idx = f.get('m[[r3+0x0]+0x430]')
            if idx is None:
                idx = view_of_vis.get(vis, idx_of_view.get(f.get('m[r3+0x0]')))
            waits[idx][family(lr)] += 1
        elif ev == 'enter' and pc == 0x50D868:
            idx = f.get('m[r4+0x24]'); cnt = f.get('m[r4+0x10]') or 0
            pb[idx][0] += 1; pb[idx][1] += cnt
        elif ev == 'bb':
            bb[pc] += 1
        elif ev == 'enter':
            other[pc] += 1
    print(f'{n} PT events; views seen {sorted(k for k in set(kicks) | set(waits) | set(pb) if k is not None)}')
    for idx in sorted(set(kicks) | set(waits) | set(pb), key=lambda x: (x is None, x)):
        w = ', '.join(f'{k} {v}' for k, v in sorted(waits[idx].items()))
        print(f'view {idx}: kicks {kicks[idx]} over {len(lists[idx])} scene lists; waits [{w}]; '
              f'ExecutePushBuffer {pb[idx][0]} batches / {pb[idx][1]} entries')
        if stats[idx]['last']:
            print(f'   PVS counters last {stats[idx]["last"][:8]} max {stats[idx]["max"][:8]}; '
                  f'visible pair last {stats[idx]["last"][8:]} max {stats[idx]["max"][8:]}')
    print('bb visits', {f'{k:08X}': v for k, v in bb.items()}, 'other entries', {f'{k:08X}': v for k, v in other.items()})


if __name__ == '__main__':
    main(sys.argv[1])
