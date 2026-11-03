#!/usr/bin/env python3
"""T87 post-run check (reads logs only).

  py -3 -I t87_check.py <run dir> [--out report.txt]

1. Every "[stall]" line (GCM_STALL_MS snapshot), and the 16 words at get decoded as FIFO words.
2. PT timeline of the push-buffer frames: 50D868 batches (job index [rs+0x44C], done [rs+0x2560]),
   757028 CALL emits (r4 = slot IO, [r3+8] = ctx->current = EA of the CALL word), 50C818 frame-end
   spin enter/exit, 72E1E0 ref throttle (ctrl->ref vs target), bb 7367E4 PUT stores (r3 = new put).
3. Ordering: for each CALL, the first PUT that exposes its word (put > CALL word IO), and whether
   that batch's job is shown complete (done > job) before, or shown incomplete after, the exposure.
   Only an observation of done <= job at or after the exposing PUT demonstrates a violation.
4. Slot reuse: other CALL emits with the stalled target, and when.
The snapshot's time on the PT clock is taken from the nearest PT line before it in stderr.
"""
import re, sys
from pathlib import Path

PT = re.compile(r'^\[PT\] t=(\d+) tid=(\d+) ev=(\w+) pc=([0-9A-F]{8})(.*)$')
KV = re.compile(r'(r\d+|m\[[^ ]*\])=(--|[0-9A-Fa-f]+)')
RING_EA = 0x11200000          # ctx ring EA base <-> IO 0 (GcKernel: Host Ea 0x11210068 = offset 0x00010068)

METH = {0x0050: 'NV406E_SET_REFERENCE', 0x0064: 'NV406E_SEMAPHORE_OFFSET', 0x0068: 'NV406E_SEMAPHORE_ACQUIRE',
        0x006C: 'NV406E_SEMAPHORE_RELEASE', 0x1808: 'BEGIN_END', 0x1814: 'DRAW_ARRAYS', 0x1818: 'INLINE_ARRAY',
        0x181C: 'INDEX_ARRAY_ADDRESS', 0x1820: 'INDEX_ARRAY_DMA', 0x1824: 'DRAW_INDEX_ARRAY', 0x1D6C: 'SET_SEMAPHORE_OFFSET',
        0x1D70: 'BACK_END_WRITE_SEMAPHORE_RELEASE', 0x1D74: 'TEXTURE_READ_SEMAPHORE_RELEASE', 0x0100: 'NOP/NO_OPERATION',
        0x1680: 'VERTEX_DATA_ARRAY_OFFSET', 0x1740: 'VERTEX_DATA_ARRAY_FORMAT', 0x1E94: 'SET_TRANSFORM_PROGRAM_START',
        0x08E4: 'SET_SHADER_PROGRAM', 0x1EFC: 'SET_TRANSFORM_CONSTANT_LOAD', 0x0B00: 'TRANSFORM_PROGRAM'}


def regs(tail):
    return {k: (None if v == '--' else int(v, 16)) for k, v in KV.findall(tail)}


def decode_words(words):
    """FIFO words from get on: headers with their data words consumed."""
    out, i = [], 0
    while i < len(words):
        w = words[i]
        if w is None:
            out.append(f'+{i*4:02X} -------- unreadable'); i += 1; continue
        if w == 0:
            out.append(f'+{i*4:02X} 00000000 NOP'); i += 1; continue
        if w == 0x00020000:
            out.append(f'+{i*4:02X} {w:08X} RET'); i += 1; continue
        if (w & 0xE0000003) == 0x20000000:
            out.append(f'+{i*4:02X} {w:08X} JUMP(old) -> {w & 0x1FFFFFFC:08X}'); i += 1; continue
        if (w & 3) == 1:
            out.append(f'+{i*4:02X} {w:08X} JUMP -> {w & 0xFFFFFFFC:08X}'); i += 1; continue
        if (w & 3) == 2:
            out.append(f'+{i*4:02X} {w:08X} CALL -> {w & 0xFFFFFFFC:08X}'); i += 1; continue
        typ, cnt, sub, meth = w >> 29, (w >> 18) & 0x7FF, (w >> 13) & 7, w & 0x1FFC
        if typ in (0, 2):
            data = words[i + 1:i + 1 + cnt]
            name = METH.get(meth, '?')
            ds = ' '.join('--------' if d is None else f'{d:08X}' for d in data[:6]) + (' ...' if cnt > 6 else '')
            out.append(f'+{i*4:02X} {w:08X} {"NI " if typ == 2 else ""}subch={sub} method=0x{meth:04X} {name} count={cnt}'
                       + (f' data: {ds}' if cnt else '') + (' (data runs past the dump)' if i + 1 + cnt > len(words) else ''))
            i += 1 + cnt; continue
        out.append(f'+{i*4:02X} {w:08X} not a command (type {typ})'); i += 1
    return out


def main(argv):
    run = Path(argv[1])
    lines = (run / 'stderr.log').read_text(encoding='utf-8', errors='replace').splitlines()
    out = []
    p = out.append
    last_pt_t = 0
    stalls, ev = [], []
    for ln in lines:
        m = PT.match(ln)
        if m:
            t, tid, kind, pc, tail = int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4), 16), m.group(5)
            last_pt_t = t
            lr = re.search(r'\blr=([0-9A-F]{8})', tail)
            fn = re.search(r'\bfn=([0-9A-F]{8})', tail)
            ev.append({'t': t, 'tid': tid, 'kind': kind, 'pc': pc, 'lr': int(lr.group(1), 16) if lr else None,
                       'fn': int(fn.group(1), 16) if fn else None, 'r': regs(tail), 'raw': ln})
            continue
        if ln.startswith('[stall]'):
            stalls.append((last_pt_t, ln))

    # 1. snapshot
    p('== [stall] lines (PT clock = last PT line before each)')
    if not stalls:
        p('none: no stall snapshot printed')
    for t, ln in stalls:
        p(f'  pt~{t/1e6:9.3f}s  {ln}')
    snap = {}
    for t, ln in stalls:
        if ln.startswith('[stall] #') and 'n' not in snap:
            snap['t'] = t
            for k, v in re.findall(r'(\w+)=(0x[0-9A-F]+|\d+|[a-z-]+)', ln):
                snap[k] = v
        if ln.startswith('[stall] at-get') and 'words' not in snap:
            m = re.match(r'\[stall\] at-get io=0x([0-9A-F]+):(.*)$', ln)
            snap['get_io'] = int(m.group(1), 16)
            snap['words'] = [None if x == '--------' else int(x, 16) for x in m.group(2).split()]
        if ln.startswith('[stall] last-cmd') and 'lastcmd' not in snap:
            snap['lastcmd'] = ln
    if 'words' in snap:
        p(f"\n== words at get 0x{snap['get_io']:08X} decoded")
        for d in decode_words(snap['words']):
            p('  ' + d)

    # 2. timeline
    calls = [e for e in ev if e['pc'] == 0x00757028 and e['kind'] == 'enter']
    batches = [e for e in ev if e['pc'] == 0x0050D868 and e['kind'] == 'enter']
    puts = [e for e in ev if e['pc'] == 0x007367E4 and e['kind'] == 'bb']
    spins = [e for e in ev if (e['pc'] == 0x0050C818 and e['kind'] == 'enter') or
             (e['kind'] == 'exit' and e['fn'] == 0x0050C818)]
    thr = [e for e in ev if (e['pc'] == 0x0072E1E0 and e['kind'] == 'enter') or (e['kind'] == 'exit' and e['fn'] == 0x0072E1E0)]
    p(f'\n== PT counts: 50D868 {len(batches)}, 757028 {len(calls)}, 50C818 enter/exit {len(spins)}, '
      f'72E1E0 enter/exit {len(thr)}, 7367E4 PUT {len(puts)}')
    if not calls:
        p('no CALL emits traced')
        return out
    t0 = calls[0]['t'] - 2_000_000
    p('\n== timeline from 2 s before the first CALL emit')
    for e in ev:
        if e['t'] < t0:
            continue
        r = e['r']
        if e['pc'] == 0x0050D868 and e['kind'] == 'enter':
            p(f"  {e['t']/1e6:9.3f} tid{e['tid']:<3} batch   view={r.get('m[r4+0x24]')} n={r.get('m[r4+0x10]')} "
              f"slot={r.get('m[r3+0x24E8]')} job={r.get('m[r3+0x44C]')} done={r.get('m[r3+0x2560]')} "
              f"frame={r.get('m[r3+0x450]')} parity={r.get('m[r3+0x454]')}")
        elif e['pc'] == 0x00757028 and e['kind'] == 'enter':
            cur = r.get('m[r3+0x8]')
            p(f"  {e['t']/1e6:9.3f} tid{e['tid']:<3} CALL    target=0x{(r.get('r4') or 0):08X} lr={e['lr']:08X} "
              f"word_io=0x{((cur or RING_EA) - RING_EA) & 0xFFFFFFFF:08X}")
        elif e['pc'] == 0x0050C818 and e['kind'] == 'enter':
            p(f"  {e['t']/1e6:9.3f} tid{e['tid']:<3} spin>   jobs={r.get('m[r3+0x44C]')} done={r.get('m[r3+0x2560]')} "
              f"frame={r.get('m[r3+0x450]')} parity={r.get('m[r3+0x454]')}")
        elif e['kind'] == 'exit' and e['fn'] == 0x0050C818:
            p(f"  {e['t']/1e6:9.3f} tid{e['tid']:<3} spin<   {e['raw'].split('how=')[1][:40] if 'how=' in e['raw'] else ''}")
        elif e['pc'] == 0x0072E1E0 and e['kind'] == 'enter':
            p(f"  {e['t']/1e6:9.3f} tid{e['tid']:<3} thr>    ref={r.get('m[[[r2+0x5AB8]+0x0]+0x8]')} "
              f"target={r.get('m[[r2+0x5AB0]+0x98]')} ctrl={r.get('m[[r2+0x5AB8]+0x0]')}")
        elif e['kind'] == 'exit' and e['fn'] == 0x0072E1E0:
            p(f"  {e['t']/1e6:9.3f} tid{e['tid']:<3} thr<    {e['raw'].split('how=')[1][:40] if 'how=' in e['raw'] else ''}")
        elif e['pc'] == 0x007367E4 and e['kind'] == 'bb':
            p(f"  {e['t']/1e6:9.3f} tid{e['tid']:<3} PUT     r3=0x{(r.get('r3') or 0):08X} r28={r.get('r28')} "
              f"ctrl.put={r.get('m[[[r2+0x5B30]+0x0]+0x0]')} get={r.get('m[[[r2+0x5B30]+0x0]+0x4]')} "
              f"ref={r.get('m[[[r2+0x5B30]+0x0]+0x8]')}")
        elif e['kind'] == 'stall':
            p(f"  {e['t']/1e6:9.3f} tid{e['tid']:<3} PTSTALL {e['raw'][e['raw'].find('fn='):][:150]}")
    if 'n' in snap or stalls:
        p(f"  {snap.get('t', 0)/1e6:9.3f}         [stall] snapshot printed (PT clock, upper bound of the stall start + {snap.get('no_progress_ms')} ms)")

    # 3. ordering per CALL
    p('\n== ordering: CALL word exposure (first PUT past it) vs that batch\'s job completion')
    # pair each CALL with the batch record before it on the same thread
    bi = 0
    rows = []
    for c in calls:
        b = None
        for e in batches:
            if e['tid'] == c['tid'] and e['t'] <= c['t']:
                b = e
        job = b['r'].get('m[r3+0x44C]') if b else None
        cur = c['r'].get('m[r3+0x8]')
        word_io = ((cur or RING_EA) - RING_EA) & 0xFFFFFFFF
        expo = next((u for u in puts if u['t'] >= c['t'] and u['r'].get('r3') is not None
                     and 0 < (u['r']['r3'] - word_io) < 0x100000), None)
        # done observations: any record carrying [r3+0x2560]
        obs = [(e['t'], e['r'].get('m[r3+0x2560]')) for e in ev
               if e['r'].get('m[r3+0x2560]') is not None and e['pc'] in (0x0050D868, 0x0050C818)]
        done_before = [d for t, d in obs if expo and t <= expo['t']]
        done_after = [(t, d) for t, d in obs if expo and t >= expo['t']]
        verdict = 'no exposing PUT traced'
        if expo and job is not None:
            if done_before and done_before[-1] > job:
                verdict = f'complete before exposure (done={done_before[-1]} > job={job})'
            elif any(d <= job for t, d in done_after):
                t_bad, d_bad = next((t, d) for t, d in done_after if d <= job)
                verdict = f'VIOLATION: done={d_bad} <= job={job} at {t_bad/1e6:.3f}s, after the exposing PUT at {expo["t"]/1e6:.3f}s'
            else:
                verdict = f'not shown either way (last done before exposure={done_before[-1] if done_before else None}, job={job})'
        rows.append((c, job, word_io, expo, verdict))
    for c, job, word_io, expo, verdict in rows:
        p(f"  CALL {c['t']/1e6:9.3f}s target=0x{c['r'].get('r4', 0):08X} word_io=0x{word_io:08X} job={job} "
          f"exposed={'%.3fs put=0x%08X' % (expo['t']/1e6, expo['r']['r3']) if expo else '-'}  {verdict}")

    # 4. slot reuse of the stalled target
    tgt = snap.get('call_target')
    if tgt:
        tv = int(tgt, 16)
        uses = [c for c in calls if c['r'].get('r4') == tv]
        p(f'\n== CALL emits with the stalled target 0x{tv:08X}: ' +
          (', '.join(f"{c['t']/1e6:.3f}s" for c in uses) if uses else 'none'))
    return out


if __name__ == '__main__':
    o = main(sys.argv)
    text = '\n'.join(o) + '\n'
    if '--out' in sys.argv:
        Path(sys.argv[sys.argv.index('--out') + 1]).write_text(text, encoding='utf-8')
    sys.stdout.write(text)
