#!/usr/bin/env python3
"""T84C: ExecutePushBuffer entries per (view, scene-list slot, renderer family) in the unsampled window.
A batch is attributed to the last Vis::Wait on the same PPU thread (its renderer); the Vis gives
(view, list slot) through the kicks (slot = position of the list in the view's 24 kicks).
  py -3 t84c_lists.py <stderr.log> [limit=3000]"""
import collections, re, sys
LINE = re.compile(r'\[PT\] t=(\d+) tid=(\d+) ev=enter pc=([0-9A-F]{8}) lr=([0-9A-F]{8}).*? n=(\d+)(.*)')
FIELD = re.compile(r' (r\d+|m\[r\d+\+0x[0-9A-F]+\])=([0-9A-F]{8}|--)')
ev = []
for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
    m = LINE.search(line)
    if m and int(m.group(3), 16) in (0x458558, 0x45CB30, 0x45CAA8, 0x50D868):
        ev.append((int(m.group(1)), m.group(2), int(m.group(3), 16), int(m.group(4), 16), int(m.group(5)),
                   {k: (None if v == '--' else int(v, 16)) for k, v in FIELD.findall(m.group(6))}))
lim = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
end = min((e[0] for e in ev if e[4] > lim), default=1 << 62)
slot_of_list, vis_of, pend, last_wait = {}, {}, {}, {}
ent = collections.Counter(); bat = collections.Counter(); waits = collections.Counter()
nonempty_wait = collections.Counter(); frames = 0
for t, tid, pc, lr, n, f in ev:
    if t >= end:
        break
    if pc == 0x458558:
        v, lst = f['m[r4+0x430]'], f['r3']
        slot_of_list.setdefault(lst, len(slot_of_list))
        pend[tid] = (v, slot_of_list[lst])
        frames += v == 1 and slot_of_list[lst] == 0
    elif pc == 0x45CB30:
        vis_of[f['r3']] = pend[tid]
    elif pc == 0x45CAA8:
        k = vis_of.get(f['r3'], (None, None)) + (lr,)
        last_wait[tid] = k; waits[k] += 1
    elif pc == 0x50D868 and tid in last_wait:
        k = last_wait[tid]
        if f['m[r4+0x24]'] != k[0]:
            k = (f"ctx{f['m[r4+0x24]']}/wait{k[0]}",) + k[1:]
        ent[k] += f['m[r4+0x10]'] or 0; bat[k] += 1
print(f'{frames} frames (view-1 slot-0 kicks) in the unsampled window; {len(slot_of_list)} scene lists')
for k in sorted(set(ent) | set(waits), key=lambda k: (str(k[0]), k[1] if k[1] is not None else -1, k[2])):
    if ent[k]:
        print(f'view {k[0]} slot {k[1]:>2} family {k[2]:08X}: waits {waits[k]:4} batches {bat[k]:4} entries {ent[k]:5}')
print('per view: slots with entries ->', {v: sorted({k[1] for k in ent if k[0] == v}) for v in sorted({k[0] for k in ent}, key=str)})
