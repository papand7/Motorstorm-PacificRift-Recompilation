"""RSX_RT_READBACK_EAGER=1 (opt-in): copy a render target the GPU has not sampled from its first
generation, synchronously while it is young, instead of after min_orphan (2) unsampled generations
and one present of async lag. MotorStorm moves its 16x16 FP16 exposure target to a new address at
race entry (Kk67: off 0x02903600 -> 0x07EBA600); until the target qualified the CPU read memory the
GPU never wrote, and a bad sample drives exposure to Emax (white frames for seconds).
Files are CRLF.

usage: py -3 edit_rtrb_eager.py"""
import pathlib

R = pathlib.Path(__file__).resolve().parents[4] / 'ps3recomp-vkgame'


def edit(rel, subs):
    p = R / rel
    raw = p.read_bytes().decode('utf-8')
    crlf = '\r\n' in raw
    s = raw.replace('\r\n', '\n')
    for a, b in subs:
        assert s.count(a) == 1, (rel, a[:80], s.count(a))
        s = s.replace(a, b)
    if crlf:
        s = s.replace('\n', '\r\n')
    p.write_bytes(s.encode('utf-8'))
    print('edited', rel)


edit('include/ps3emu/rt_readback.h', [
("""    uint32_t min_orphan;
    uint64_t order_seq, lru_seq;""",
"""    uint32_t min_orphan;
    int      eager;             /* ps3_rtrb_set_eager: young, never-sampled surfaces are copied too */
    uint64_t order_seq, lru_seq;"""),

("""/* Release the shadows (shutdown, tests). */""",
"""/* RSX_RT_READBACK_EAGER: "1" selects a surface the GPU has not sampled
 * since its identity began from its first generation, instead of after
 * min_orphan unsampled generations. A target that moves to a new address is
 * otherwise invisible to a CPU reader for those generations: MotorStorm moves
 * its 16x16 exposure target at race entry, and a read of memory the GPU never
 * wrote drives exposure to Emax (white frames until it adapts back). A
 * surface the GPU samples returns to the min_orphan rule. Off unless "1". */
static inline void ps3_rtrb_set_eager(ps3_rtrb* t, const char* env)
{
    t->eager = (env && env[0] == '1' && !env[1]) ? 1 : 0;
}

/* Release the shadows (shutdown, tests). */"""),

("""    if (s->orphan_streak < t->min_orphan)
        return s->sample_reset ? PS3_RTRB_WHY_SAMPLED : PS3_RTRB_WHY_YOUNG;
    return PS3_RTRB_WHY_SELECTED;
}
""",
"""    if (s->orphan_streak < t->min_orphan)
        return s->sample_reset ? PS3_RTRB_WHY_SAMPLED
             : t->eager       ? PS3_RTRB_WHY_SELECTED : PS3_RTRB_WHY_YOUNG;
    return PS3_RTRB_WHY_SELECTED;
}

/* Surface i is selected only because it is young (ps3_rtrb_set_eager): its
 * copy should reach guest memory before the next frame reads it, so the
 * caller copies it synchronously. */
static inline int ps3_rtrb_young(const ps3_rtrb* t, int i)
{
    const ps3_rtrb_surf* s = &t->s[i];
    return t->eager && s->orphan_streak < t->min_orphan && !s->sample_reset &&
           ps3_rtrb_why(t, i) == PS3_RTRB_WHY_SELECTED;
}
"""),
])

edit('libs/video/rsx_draw_engine.c', [
("""        if (s_rtrb_on)
            fprintf(stderr, "[rtrb] engine: on, max_bytes=%u min_orphan=%u\\n",
                    s_rtrb.max_bytes, s_rtrb.min_orphan);""",
"""        if (s_rtrb_on) {
            ps3_rtrb_set_eager(&s_rtrb, getenv("RSX_RT_READBACK_EAGER"));
            fprintf(stderr, "[rtrb] engine: on, max_bytes=%u min_orphan=%u eager=%d\\n",
                    s_rtrb.max_bytes, s_rtrb.min_orphan, s_rtrb.eager);
        }"""),

("""        if (why != PS3_RTRB_WHY_SELECTED) continue;
        if (async) {""",
"""        if (why != PS3_RTRB_WHY_SELECTED) continue;
        /* RSX_RT_READBACK_EAGER: a young surface's copy is synchronous, so the
         * game's next read sees it; the async copies queued before it finish
         * first, keeping the GPU's write order. */
        const int young = ps3_rtrb_young(&s_rtrb, i);
        if (young && async && !waited) eng_rtrb_collect(1);
        if (async && !young) {"""),
])
