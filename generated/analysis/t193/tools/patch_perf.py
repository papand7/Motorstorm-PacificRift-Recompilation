p='ps3recomp-t193/runtime/spu/spu_channels.c'
s=open(p,encoding='utf-8',newline='').read()
nl='\r\n' if '\r\n' in s else '\n'
s=s.replace('\r\n','\n')
def rep(a,b):
    global s
    assert s.count(a)==1,(s.count(a),a[:80]); s=s.replace(a,b)
rep('typedef struct { unsigned long long n[IBR_N], sent[IBR_N]; unsigned tick; } spu_ibr_shard;',
    'typedef struct { unsigned long long n[IBR_N], sent[IBR_N]; unsigned tick, obs_left; void* raw; } spu_ibr_shard;\n'
    'static unsigned g_ibr_obs_period = 1;           /* overlapping observations every Nth branch (1 exact, 0 off) */')
rep('#  define SPU_IBF_SUB_HIT(o) (t_ibr_sh->n[IBR_S_HIT_RELOC] += (o) == -3, t_ibr_sh->n[IBR_S_HIT_SLOT] += (o) == -2)',
    '#  define SPU_IBF_SUB_HIT(o) ((o) < 0 ? (void)(t_ibr_sh->n[(o) == -3 ? IBR_S_HIT_RELOC : IBR_S_HIT_SLOT]++) : (void)0)')
rep('#  define SPU_IBF_SUB_FILL(o) (t_ibr_sh->n[IBR_S_FILL_RELOC] += (o) == -3)',
    '#  define SPU_IBF_SUB_FILL(o) ((o) == -3 ? (void)(t_ibr_sh->n[IBR_S_FILL_RELOC]++) : (void)0)')
# aligned shard allocation (no two threads' shards share a cache line)
rep('''    free(sh);
}
static int s_ibr_key_state;''','''    free(sh->raw);
}
static int s_ibr_key_state;''')
rep('''    spu_ibr_shard* sh = spu_ibr_key_ready() ? (spu_ibr_shard*)calloc(1, sizeof *sh) : NULL;
    int ok = 0;''','''    /* 64-byte aligned and padded: shards of different threads never share a cache line. */
    const size_t sz = (sizeof(spu_ibr_shard) + 63u) & ~(size_t)63u;
    void* raw = spu_ibr_key_ready() ? calloc(1, sz + 64u) : NULL;
    spu_ibr_shard* sh = raw ? (spu_ibr_shard*)(((uintptr_t)raw + 63u) & ~(uintptr_t)63u) : NULL;
    if (sh) { sh->raw = raw; sh->obs_left = 0; }
    int ok = 0;''')
rep('    if (!ok) { free(sh); t_ibr_sh = &t_ibr_fallback; return; }   /* counted, flushed at ticks only */',
    '    if (!ok) { free(raw); t_ibr_sh = &t_ibr_fallback; return; }   /* counted, flushed at ticks only */')
# observations sampled
i=s.index('/* Overlapping observations of the context (independent of the primary reason) and the policy / irq reasons. */\nstatic inline void spu_ibf_pre(const spu_context* ctx)')
j=s.index('#else\nvoid spu_ib_fast_thread_flush(void) {}')
s=s[:i]+'''/* Overlapping observations of the context (independent of the primary reason). */
static void spu_ibr_observe(unsigned long long* n, const spu_context* ctx)
{
    n[IBR_O_POLICY] += ctx->policy_mode != 0;
    n[IBR_O_IRQ] += ctx->irq_saved != 0;
    n[IBR_O_OVL] += ctx->resident_ovl != 0;
    n[IBR_O_TASKRES] += ctx->resident_task != 0;
    n[IBR_O_TASKREG] += (s_task_elf_count | s_task_entry_count) != 0;
    n[IBR_O_TASKPC] += ctx->pc >= SPU_TASKSET_TASK_LO;
    for (unsigned slot = 0; slot < 4; ++slot) {
        const uint32_t lsa = ctx->resident_code[slot].lsa;
        if (ctx->resident_code[slot].image_id && ctx->pc >= lsa && ctx->pc - lsa < ctx->resident_code[slot].size) {
            n[IBR_O_SLOT]++; n[IBR_O_SLOT_RELOC] += ctx->resident_code[slot].link_base != 0; break;
        }
    }
}
/* Per branch: registration on first use, the flush tick, the sampled observations, the policy / irq reasons. */
static inline void spu_ibf_pre(const spu_context* ctx)
{
    spu_ibr_shard* sh = t_ibr_sh;
    if (__builtin_expect(!sh, 0)) { spu_ibr_register(); sh = t_ibr_sh; }
    if (__builtin_expect((++sh->tick & 0xFFFu) == 0, 0)) spu_ibr_flush_point();
    if (__builtin_expect(sh->obs_left == 0, 0)) {
        const unsigned per = g_ibr_obs_period;
        sh->obs_left = per ? per - 1u : 0xFFFFFFFFu;
        if (per) spu_ibr_observe(sh->n, ctx);
    } else sh->obs_left--;
    if (ctx->policy_mode) sh->n[IBR_D_POLICY]++; else if (ctx->irq_saved) sh->n[IBR_D_IRQ]++;
}
'''+s[j:]
# environment + line field
rep('''        const char* fp = getenv("PS3_SPU_IB_STATS_FILE");''','''        const char* fp = getenv("PS3_SPU_IB_STATS_FILE");
        const char* ob = getenv("PS3_SPU_IB_STATS_OBS");
        if (ob) { extern void spu_ib_fast_set_obs_period(unsigned); spu_ib_fast_set_obs_period((unsigned)strtoul(ob, NULL, 10)); }''')
rep('''                     " thr_live=%u thr_seen=%u thr_exited=%u consistent=%d",''','''                     " thr_live=%u thr_seen=%u thr_exited=%u consistent=%d obs_period=%u",''')
rep('''                     __atomic_load_n(&g_ibr_exited, __ATOMIC_RELAXED), ok);''','''                     __atomic_load_n(&g_ibr_exited, __ATOMIC_RELAXED), ok, g_ibr_obs_period);''')
rep('void spu_ib_fast_threads(unsigned out[3])\n{','/* Overlapping observations every Nth branch of a thread (1 = every branch, exact; 0 = off). Set before dispatch starts. */\nvoid spu_ib_fast_set_obs_period(unsigned n) { g_ibr_obs_period = n; }\nvoid spu_ib_fast_threads(unsigned out[3])\n{')
rep('void spu_ib_fast_register_atexit_for_test(void) {}\n','void spu_ib_fast_register_atexit_for_test(void) {}\nvoid spu_ib_fast_set_obs_period(unsigned n) { (void)n; }\n')
open(p,'w',encoding='utf-8',newline='').write(s.replace('\n',nl))
# telemetry mutant 3 pattern, bench obs arm
p='ps3recomp-t193/tools/test_spu_ib_telemetry.py'
t=open(p,encoding='utf-8').read()
a='("relocatable hits counted as plain-slot hits", "t_ibr_sh->n[IBR_S_HIT_SLOT] += (o) == -2)", "t_ibr_sh->n[IBR_S_HIT_SLOT] += (o) < 0)"),'
assert a in t
t=t.replace(a,'("relocatable hits counted as plain-slot hits", "(o) == -3 ? IBR_S_HIT_RELOC : IBR_S_HIT_SLOT", "(o) == -3 ? IBR_S_HIT_SLOT : IBR_S_HIT_SLOT"),')
open(p,'w',encoding='utf-8').write(t)
print('ok')
