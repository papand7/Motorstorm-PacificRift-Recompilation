"""T106: apply the four verified five-lane race fixes to ps3recomp-t106 (run from that tree's root)."""
from pathlib import Path


def sub(path, old, new, count=1):
    p = Path(path)
    t = p.read_text(encoding="utf-8")
    assert t.count(old) == count, (path, old[:70], t.count(old))
    p.write_text(t.replace(old, new), encoding="utf-8")


# 1. event_status read-modify-writes are atomic on every side.
sub("runtime/spu/spu_channels.c", "            ctx->event_status |= 0x1u;\n",
    "            __atomic_fetch_or(&ctx->event_status, 0x1u, __ATOMIC_SEQ_CST);   /* peers raise LR concurrently */\n")
sub("runtime/spu/spu_channels.c", "        ctx->event_status &= ~v;\n",
    "        __atomic_fetch_and(&ctx->event_status, ~v, __ATOMIC_SEQ_CST);\n")
sub("runtime/spu/spu_channels.c", "        ctx->event_status |= 0x400u;\n",
    "        __atomic_fetch_or(&ctx->event_status, 0x400u, __ATOMIC_SEQ_CST);\n")
sub("runtime/spu/spu_dma.h",
    "            spu->event_status    |= 0x2u;       /* SPU_EVENT_SN stall-and-notify */\n",
    "            __atomic_fetch_or(&spu->event_status, 0x2u, __ATOMIC_SEQ_CST);  /* SPU_EVENT_SN stall-and-notify */\n")
sub("runtime/spu/spu_coherency.c", "            c->event_status |= SPU_EVENT_LR;\n",
    "            /* Atomic: the owning lane ORs its own tag/SN/LR bits without this lock. */\n"
    "            __atomic_fetch_or(&c->event_status, SPU_EVENT_LR, __ATOMIC_SEQ_CST);\n", 2)

# 3. Cross-image dedupe table: bounded under concurrent lanes.
sub("runtime/spu/spu_channels.c", """    static unsigned n_seen = 0;
    for (unsigned i = 0; i < n_seen; i++)
        if (seen[i].addr == addr && seen[i].want == want && seen[i].got == got)
            return;
    if (n_seen < SEEN_MAX) {
        seen[n_seen].addr = addr; seen[n_seen].want = want; seen[n_seen].got = got;
        n_seen++;
    }
""", """    static unsigned n_seen = 0;
    static SRWLOCK s_seen_lock = SRWLOCK_INIT;   /* lanes of one image report together */
    AcquireSRWLockExclusive(&s_seen_lock);
    for (unsigned i = 0; i < n_seen; i++)
        if (seen[i].addr == addr && seen[i].want == want && seen[i].got == got) {
            ReleaseSRWLockExclusive(&s_seen_lock);
            return;
        }
    if (n_seen < SEEN_MAX) {
        seen[n_seen].addr = addr; seen[n_seen].want = want; seen[n_seen].got = got;
        n_seen++;
    }
    ReleaseSRWLockExclusive(&s_seen_lock);
""")

# 4. SPU pushbuffer block ring, written from every SPU PUT hook.
G = "libs/video/cellGcmSys.c"
sub(G, "static int s_spu_blk_w = 0;\n",
    "static int s_spu_blk_w = 0;\nstatic SRWLOCK s_spu_blk_lock = SRWLOCK_INIT;   /* several SPU lanes PUT at once */\n")
sub(G, """    memset(s_spu_blk, 0, sizeof s_spu_blk);
    s_spu_blk_w = 0;
}""", """    AcquireSRWLockExclusive(&s_spu_blk_lock);
    memset(s_spu_blk, 0, sizeof s_spu_blk);
    s_spu_blk_w = 0;
    ReleaseSRWLockExclusive(&s_spu_blk_lock);
}""")
sub(G, """    int prev = (s_spu_blk_w + GCM_SPU_BLK_N - 1) % GCM_SPU_BLK_N;
    if (s_spu_blk[prev].io_end == io) { s_spu_blk[prev].io_end = io + size; return; }

    s_spu_blk[s_spu_blk_w].io_start = io;
    s_spu_blk[s_spu_blk_w].io_end   = io + size;
    s_spu_blk_w = (s_spu_blk_w + 1) % GCM_SPU_BLK_N;
}""", """    AcquireSRWLockExclusive(&s_spu_blk_lock);
    int prev = (s_spu_blk_w + GCM_SPU_BLK_N - 1) % GCM_SPU_BLK_N;
    if (s_spu_blk[prev].io_end == io) s_spu_blk[prev].io_end = io + size;
    else {
        s_spu_blk[s_spu_blk_w].io_start = io;
        s_spu_blk[s_spu_blk_w].io_end   = io + size;
        s_spu_blk_w = (s_spu_blk_w + 1) % GCM_SPU_BLK_N;
    }
    ReleaseSRWLockExclusive(&s_spu_blk_lock);
}""")
sub(G, """    u32 best = 0xFFFFFFFFu, best_end = 0;
    for (int i = 0; i < GCM_SPU_BLK_N; i++) {""", """    u32 best = 0xFFFFFFFFu, best_end = 0;
    AcquireSRWLockShared(&s_spu_blk_lock);
    for (int i = 0; i < GCM_SPU_BLK_N; i++) {""")
sub(G, """        if (e >= best_end) { best_end = e; best = s; }
    }
    return best;""", """        if (e >= best_end) { best_end = e; best = s; }
    }
    ReleaseSRWLockShared(&s_spu_blk_lock);
    return best;""")

# 5. Event-flag sync slot directory.
S = "libs/spurs/cellSpurs.c"
sub(S, "static EventFlagSync s_ef_sync[MAX_EVENT_FLAGS];\n", """static EventFlagSync s_ef_sync[MAX_EVENT_FLAGS];
/* Slot allocation, recycling and the commit hook's walk. SPU lanes reach
 * ef_sync_get (spurs_ef_set_from_spu) concurrently. Never taken while holding
 * a slot's own lock. */
static SRWLOCK s_ef_dir = SRWLOCK_INIT;
""")
sub(S, """    if (!s_ef_ppu_waiters) return;
    for (int i = 0; i < MAX_EVENT_FLAGS; i++) {""", """    if (!s_ef_ppu_waiters) return;
    AcquireSRWLockShared(&s_ef_dir);
    for (int i = 0; i < MAX_EVENT_FLAGS; i++) {""")
sub(S, """        pthread_mutex_lock(&s->mtx); pthread_cond_broadcast(&s->cond); pthread_mutex_unlock(&s->mtx);
#endif
    }
}""", """        pthread_mutex_lock(&s->mtx); pthread_cond_broadcast(&s->cond); pthread_mutex_unlock(&s->mtx);
#endif
    }
    ReleaseSRWLockShared(&s_ef_dir);
}""")
sub(S, """static EventFlagSync* ef_sync_find(uint32_t ea)
{
    for (int i = 0; i < MAX_EVENT_FLAGS; i++) {""", """static EventFlagSync* ef_sync_find_unlocked(uint32_t ea)
{
    for (int i = 0; i < MAX_EVENT_FLAGS; i++) {""")
sub(S, """static EventFlagSync* ef_sync_alloc(uint32_t ea)
{
    for (int i = 0; i < MAX_EVENT_FLAGS; i++) {""", """static EventFlagSync* ef_sync_find(uint32_t ea)
{
    AcquireSRWLockShared(&s_ef_dir);
    EventFlagSync* s = ef_sync_find_unlocked(ea);
    ReleaseSRWLockShared(&s_ef_dir);
    return s;
}

static EventFlagSync* ef_sync_alloc_unlocked(uint32_t ea)
{
    for (int i = 0; i < MAX_EVENT_FLAGS; i++) {""")
sub(S, """/* Lenient lookup: a flag touched before we saw its Initialize (alternate init
 * paths, e.g. taskset2) still gets a sync slot instead of an error. */
static EventFlagSync* ef_sync_get(uint32_t ea)
{
    EventFlagSync* s = ef_sync_find(ea);
    if (!s) {
        s = ef_sync_alloc(ea);
        if (s)
            fprintf(stderr, "[cellSpurs] event flag 0x%08X used before Initialize "
                            "-- sync slot auto-allocated\\n", ea);
    }
    return s;
}

static void ef_sync_free(EventFlagSync* sync)
{
    if (!sync) return;
""", """static EventFlagSync* ef_sync_alloc(uint32_t ea)
{
    AcquireSRWLockExclusive(&s_ef_dir);
    EventFlagSync* s = ef_sync_alloc_unlocked(ea);
    ReleaseSRWLockExclusive(&s_ef_dir);
    return s;
}

/* Lenient lookup: a flag touched before we saw its Initialize (alternate init
 * paths, e.g. taskset2) still gets a sync slot instead of an error. Find and
 * allocate under one exclusive hold, so two lanes cannot both allocate it. */
static EventFlagSync* ef_sync_get(uint32_t ea)
{
    EventFlagSync* s = ef_sync_find(ea);
    if (s) return s;
    AcquireSRWLockExclusive(&s_ef_dir);
    s = ef_sync_find_unlocked(ea);
    int fresh = 0;
    if (!s) { s = ef_sync_alloc_unlocked(ea); fresh = s != NULL; }
    ReleaseSRWLockExclusive(&s_ef_dir);
    if (fresh)
        fprintf(stderr, "[cellSpurs] event flag 0x%08X used before Initialize "
                        "-- sync slot auto-allocated\\n", ea);
    return s;
}

static void ef_sync_free(EventFlagSync* sync)
{
    if (!sync) return;
    AcquireSRWLockExclusive(&s_ef_dir);
""")
sub(S, """    sync->ea = 0;
    sync->initialized = 0;
}""", """    sync->ea = 0;
    sync->initialized = 0;
    ReleaseSRWLockExclusive(&s_ef_dir);
}""")
print("ok")
