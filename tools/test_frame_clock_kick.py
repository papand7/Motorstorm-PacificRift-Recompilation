#!/usr/bin/env python3
"""T151 PS3_FRAME_CLOCK_KICK: the frame clock's idle wait (port/main.cpp), opt-in.

Pins, from the source:
  - off unless exactly "1", read once before the loop; off, the loop sleeps Sleep(4) as before;
  - on, it waits in cellGcm_fifo_kick_wait(4): the same 4 ms ceiling, woken early by a kick;
  - the beat, the present, the drain and the pump keep their order after the wait;
  - with a ps3recomp tree given, the kick is what the guest's reference poll signals when
    the drain has not yet published the fence, and the wait is on that same event.

  python tools/test_frame_clock_kick.py [ps3recomp_tree]
"""
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
fails = 0


def check(ok, what):
    global fails
    print(f"[{'PASS' if ok else 'FAIL'}] {what}")
    fails += not ok


src = (root / 'port/main.cpp').read_text(encoding='utf-8', errors='replace').replace('\r\n', '\n')
fc = re.search(r'static DWORD WINAPI frame_clock\(LPVOID\)\n\{(.*?)\n\}\n', src, re.S)
fc = fc.group(1) if fc else ''
check('void     cellGcm_fifo_kick_wait(unsigned ms); /* idle wait, woken by a kick */' in src,
      'cellGcm_fifo_kick_wait is declared with the framework signature')
check('const char* kick_env = getenv("PS3_FRAME_CLOCK_KICK");' in fc
      and "const int kick = kick_env && kick_env[0] == '1' && !kick_env[1];" in fc
      and fc.index('getenv("PS3_FRAME_CLOCK_KICK")') < fc.index('for (;;) {'),
      'on only for exactly "1", read once before the loop')
loop = fc[fc.index('for (;;) {'):] if 'for (;;) {' in fc else ''
check('fcw_mark(FCW_SLEEP);\n        if (kick) cellGcm_fifo_kick_wait(4);\n        else      Sleep(4);\n' in loop
      and loop.count('Sleep(') == 1 and loop.count('cellGcm_fifo_kick_wait(') == 1,
      'off: Sleep(4); on: cellGcm_fifo_kick_wait(4); nothing else waits in the loop')
order = [loop.find(t) for t in ('cellGcm_fifo_kick_wait(4)', 'ps3_vblank_clock_poll(', 'ps3_frame_beat(&beat);',
                                'cellGcm_take_flip_pending()', 'cellGcm_rsx_process_fifo();', 'rsx_backend_pump()')]
check(all(o >= 0 for o in order) and order == sorted(order),
      'after the wait: vblank poll, beats, flip present, drain, pump -- in the old order')

if len(sys.argv) > 1:
    gcm = (Path(sys.argv[1]) / 'libs/video/cellGcmSys.c').read_text(encoding='utf-8', errors='replace').replace('\r\n', '\n')
    kw = re.search(r'void cellGcm_fifo_kick_wait\(unsigned ms\)\n\{(.*?)\n\}', gcm, re.S)
    rp = re.search(r'void cellGcm_ref_on_poll\(void\)\n\{(.*?)\n\}', gcm, re.S)
    check(kw is not None and 'if (ev) WaitForSingleObject(ev, ms);' in kw.group(1) and 'else    Sleep(ms);' in kw.group(1),
          'cellGcm_fifo_kick_wait: waits on the kick event for at most ms (GCM_FIFO_KICK=0: Sleep)')
    check(rp is not None and 'dry = (s_ref_qhead == s_ref_qtail);' in rp.group(1)
          and 'if (dry && s_gcm_kick_ev)\n        SetEvent(s_gcm_kick_ev);' in rp.group(1),
          'the reference poll kicks only when no published fence is pending ("dry")')
    check('s_gcm_kick_ev = CreateEventA(NULL, FALSE, FALSE, NULL);' in gcm, 'auto-reset event: one kick, one early wake')
else:
    print('SKIP: no ps3recomp tree given for the framework half')

print(f'test_frame_clock_kick: {fails} failure(s)')
raise SystemExit(1 if fails else 0)
