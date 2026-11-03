"""T110: RSX_RTPOOL_GF=1 - offscreen RT eviction keeps targets of the current guest
frame across early replays (rsx_rtpool_victim.h, T101 test 9).  py -3 -I edit_rtpool.py <tree>"""
import sys
from pathlib import Path
p = Path(sys.argv[1]) / 'libs/video/rsx_d3d12_backend.c'
s = p.read_text(encoding='utf-8')
def rep(old, new, count=1):
    global s
    n = s.count(old); assert n == count, f'{n} matches for:\n{old[:300]}'
    s = s.replace(old, new)
rep('#include "rsx_attr0_gate.h"    /* draws with attribute 0 off (RSX_ATTR0_CONST) */\n',
    '#include "rsx_attr0_gate.h"    /* draws with attribute 0 off (RSX_ATTR0_CONST) */\n'
    '#include "rsx_rtpool_victim.h" /* offscreen RT eviction across early replays (RSX_RTPOOL_GF) */\n')
rep('''        if (slot < 0) {   /* evict an entry not used this frame */
            for (int i = 0; i < MAX_OFF_RTS; i++)
                if (!s_d3d.off_rt[i].used) { slot = i; break; }
            if (slot < 0) {''', '''        if (slot < 0) {   /* evict an entry not used this frame */
            /* RSX_RTPOOL_GF=1: not one targeted earlier in this guest frame
             * either, so an early replay cannot release a target the rest of
             * the frame still samples (rsx_rtpool_victim.h). */
            static int gf_rule = -1;
            if (gf_rule < 0) { const char* e = getenv("RSX_RTPOOL_GF"); gf_rule = (e && e[0] == '1' && !e[1]) ? 1 : 0; }
            int u_[MAX_OFF_RTS], g_[MAX_OFF_RTS], fb = 0;
            for (int i = 0; i < MAX_OFF_RTS; i++) { u_[i] = s_d3d.off_rt[i].used; g_[i] = s_d3d.off_rt[i].gf_used; }
            slot = rsx_rtpool_victim(MAX_OFF_RTS, u_, g_, gf_rule, &fb);
            if (fb) { static int _n = 0; if (PS3_LOG_FIRST(_n, 8))
                fprintf(stderr, "[d3d12] render-target pool: every slot was targeted this guest frame;"
                                " evicting slot %d (off=0x%08X) for off=0x%08X%c", slot, s_d3d.off_rt[slot].off, off, 10); }
            if (slot < 0) {''')
p.write_text(s, encoding='utf-8'); print('ok')
