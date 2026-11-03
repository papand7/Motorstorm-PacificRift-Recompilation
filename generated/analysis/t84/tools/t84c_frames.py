#!/usr/bin/env python3
"""T84C: per-frame, per-view breakdown of a vis_trace_t84c.cfg PT log (offline).

Only the window where every visibility site is still below the PT per-site limit (no sampling) is
used, so each frame there is complete. A frame starts at the 0x458558 kick whose (view, list)
pair was already kicked in the current frame. Waits and ExecutePushBuffer calls are attributed by
view: waits through the Vis -> view map built from the kicks, ExecutePushBuffer by ctx+0x24.
  py -3 t84c_frames.py <stderr.log> [limit=3000]"""
import collections, re, sys

LINE = re.compile(r'\[PT\] t=(\d+) tid=(\d+) ev=(\w+) pc=([0-9A-F]{8}) lr=([0-9A-F]{8}).*? n=(\d+)(.*)')
FIELD = re.compile(r' (r\d+|m\[r\d+\+0x[0-9A-F]+\])=([0-9A-F]{8}|--)')
SITES = {0x458558, 0x45CB30, 0x45CAA8, 0x50D868, 0x5F69B8, 0x5F74B0}


def main(path, limit=3000):
    ev = []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = LINE.search(line)
        if not m or m.group(3) != 'enter':
            continue
        pc = int(m.group(4), 16)
        if pc not in SITES:
            continue
        f = {k: (None if v == '--' else int(v, 16)) for k, v in FIELD.findall(m.group(7))}
        ev.append((int(m.group(1)), int(m.group(2)), pc, int(m.group(5), 16), int(m.group(6)), f))
    # end of the unsampled window: first event of any site past the limit
    end = min((e[0] for e in ev if e[4] > limit), default=None)
    win = [e for e in ev if end is None or e[0] < end]
    print(f'{len(ev)} vis events; unsampled window {win[0][0]/1e6:.3f}-{win[-1][0]/1e6:.3f} s, {len(win)} events')
    view_of_vis, view_obj, frames, cur, seen = {}, {}, [], None, set()
    pend = {}
    for t, tid, pc, lr, n, f in win:
        if pc == 0x458558:
            idx, lst = f.get('m[r4+0x430]'), f.get('r3')
            view_obj[idx] = f.get('r4')
            if cur is None or (idx, lst) in seen:
                cur = {'t': t, 'kick': collections.Counter(), 'lists': collections.defaultdict(set),
                       'wait': collections.defaultdict(collections.Counter), 'pb': collections.defaultdict(lambda: [0, 0]),
                       'pblr': collections.defaultdict(collections.Counter), 'order': [], 'start': 0, 'fin': 0}
                frames.append(cur); seen = set()
            seen.add((idx, lst)); cur['kick'][idx] += 1; cur['lists'][idx].add(lst)
            if idx not in cur['order']:
                cur['order'].append(idx)
            pend[tid] = idx
        elif cur is None:
            continue
        elif pc == 0x45CB30:
            view_of_vis[f.get('r3')] = pend.get(tid)
        elif pc == 0x5F69B8:
            cur['start'] += 1
        elif pc == 0x5F74B0:
            cur['fin'] += 1
        elif pc == 0x45CAA8:
            cur['wait'][view_of_vis.get(f.get('r3'))][f'{lr:08X}'] += 1
        elif pc == 0x50D868:
            v = f.get('m[r4+0x24]')
            cur['pb'][v][0] += 1; cur['pb'][v][1] += f.get('m[r4+0x10]') or 0
            cur['pblr'][v][f'{lr:08X}'] += 1
    print('view objects:', {k: f'{v:08X}' for k, v in sorted(view_obj.items())})
    full = frames[1:-1]           # first and last may be partial
    print(f'{len(frames)} frames, {len(full)} complete; view order in frame 1: {frames[1]["order"] if len(frames) > 1 else None}')
    tot = collections.defaultdict(lambda: collections.Counter())
    for fr in full:
        for v in fr['order']:
            tot[v]['kick'] += fr['kick'][v]; tot[v]['wait'] += sum(fr['wait'][v].values())
            tot[v]['pb'] += fr['pb'][v][0]; tot[v]['ent'] += fr['pb'][v][1]
            tot[v]['frames_with_pb'] += fr['pb'][v][0] > 0
        tot['?']['wait'] += sum(fr['wait'][None].values())
        for v in fr['pb']:
            if v not in fr['order']:
                tot[f'pb-view-{v}']['pb'] += fr['pb'][v][0]
    for v, c in tot.items():
        print(f'view {v}: per complete frame kicks {c["kick"]/len(full):.1f} waits {c["wait"]/len(full):.1f} '
              f'PB {c["pb"]/len(full):.1f} entries {c["ent"]/len(full):.1f}; frames with PB {c["frames_with_pb"]}/{len(full)}')
    for i, fr in enumerate(frames[:6] + frames[-3:]):
        print(f'frame t={fr["t"]/1e6:.3f}: order {fr["order"]} kicks {dict(fr["kick"])} start/fin {fr["start"]}/{fr["fin"]}')
        for v in sorted(set(fr['wait']) | set(fr['pb']), key=str):
            print(f'   view {v}: waits {dict(fr["wait"][v])} PB {fr["pb"][v]} PB-lr {dict(fr["pblr"][v])}')


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3000)
