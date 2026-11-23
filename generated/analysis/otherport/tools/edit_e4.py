# spu_channels.c: PS3_SPU_HWFLOAT run bracket and host-call brackets.
rep(r"""void spu_halt(spu_context* ctx)
{
""", r"""/* PS3_SPU_HWFLOAT (spu_hwfloat.h): PS3_SPU_HWFLOAT=1 and FMA3 on this CPU. Read once. */
int spu_hwfloat_enabled(void)
{
    static volatile int s_on = -1;
    int on = s_on;
    if (__builtin_expect(on >= 0, 1)) return on;
    const char* e = getenv("PS3_SPU_HWFLOAT");
    on = e && e[0] == '1' && !e[1];
#if defined(SPU_HWF_X86)
    if (on) {
        int fma = 0;
#  ifdef _WIN32
        int r[4]; __cpuid(r, 1); fma = (r[2] >> 12) & 1;
#  else
        unsigned a, b, c, d; __cpuid(1, a, b, c, d); fma = (int)((c >> 12) & 1); (void)a; (void)b; (void)d;
#  endif
        if (!fma) { on = 0; fprintf(stderr, "[spu-hwfloat] PS3_SPU_HWFLOAT=1 ignored: this CPU has no FMA3\n"); }
    }
    if (on) fprintf(stderr, "[spu-hwfloat] on: lifted SPU single precision under MXCSR toward-zero/FTZ/DAZ "
                            "(0x%04X), host calls at the thread's own MXCSR\n", SPU_HWF_CSR);
#else
    if (on) { on = 0; fprintf(stderr, "[spu-hwfloat] PS3_SPU_HWFLOAT=1 ignored: not an x86-64 clang/gcc build\n"); }
#endif
    s_on = on;
    return on;
}

/* Host-call brackets (PS3_SPU_HWFLOAT): the five SPU-facing entry points below leave the SPU float mode
 * for the host work behind them and re-enter it before returning to lifted code. Off, one TLS load. */
static void spu_halt_host(spu_context* ctx);
void spu_halt(spu_context* ctx)
{
    const int hwf = spu_hwf_suspend();
    spu_halt_host(ctx);                 /* may longjmp: spu_run_with_halt then sets the mode itself */
    spu_hwf_resume(hwf);
}
static void spu_halt_host(spu_context* ctx)
{
""")
rep(r"""void spu_stop(spu_context* ctx)
{
""", r"""static void spu_stop_host(spu_context* ctx);
void spu_stop(spu_context* ctx)
{
    const int hwf = spu_hwf_suspend();
    spu_stop_host(ctx);
    spu_hwf_resume(hwf);
}
static void spu_stop_host(spu_context* ctx)
{
""")
rep(r"""    spu_halt_buf outer_env; const int outer_armed = s_spu_halt_armed;""",
r"""    /* PS3_SPU_HWFLOAT: the caller's float state, restored on the way out; armed on each path into
     * lifted code below (after the landing pad's setjmp, since a longjmp may restore its MXCSR). */
    spu_hwf_outer hwf_outer;
    spu_hwf_run_enter(&hwf_outer);
    spu_halt_buf outer_env; const int outer_armed = s_spu_halt_armed;""")
rep(r"""        ctx->host_depth = 0;
        g_spu_trampoline_fn = 0;
        spu_indirect_branch(ctx);
        SPU_DRAIN(ctx);
        break;""", r"""        ctx->host_depth = 0;
        g_spu_trampoline_fn = 0;
        spu_hwf_run_arm(&hwf_outer);
        spu_indirect_branch(ctx);
        SPU_DRAIN(ctx);
        break;""")
rep(r"""         * calls drain inside their own call brackets (see the lifter). */
        entry(ctx);""", r"""         * calls drain inside their own call brackets (see the lifter). */
        spu_hwf_run_arm(&hwf_outer);
        entry(ctx);""")
rep(r"""        SPU_DRAIN(ctx);
    }
    if (__builtin_expect(ps3_ft_spujob_ret() != 0, 0)) spu_jobspan_run_end(ctx);""",
r"""        SPU_DRAIN(ctx);
    }
    spu_hwf_run_leave(&hwf_outer);
    if (__builtin_expect(ps3_ft_spujob_ret() != 0, 0)) spu_jobspan_run_end(ctx);""")
rep(r"""void spu_wrch(spu_context* ctx, uint32_t channel, u128 value)
{
""", r"""static __attribute__((noinline)) void spu_wrch_host(spu_context* ctx, uint32_t channel, u128 value);
void spu_wrch(spu_context* ctx, uint32_t channel, u128 value)
{
    const int hwf = spu_hwf_suspend();
    spu_wrch_host(ctx, channel, value);
    spu_hwf_resume(hwf);
}
static __attribute__((noinline)) void spu_wrch_host(spu_context* ctx, uint32_t channel, u128 value)
{
""")
rep(r"""u128 spu_rdch(spu_context* ctx, uint32_t channel)
{
""", r"""static __attribute__((noinline)) u128 spu_rdch_host(spu_context* ctx, uint32_t channel);
u128 spu_rdch(spu_context* ctx, uint32_t channel)
{
    const int hwf = spu_hwf_suspend();
    const u128 r = spu_rdch_host(ctx, channel);
    spu_hwf_resume(hwf);
    return r;
}
static __attribute__((noinline)) u128 spu_rdch_host(spu_context* ctx, uint32_t channel)
{
""")
rep(r"""uint32_t spu_rchcnt(spu_context* ctx, uint32_t channel)
{
""", r"""static __attribute__((noinline)) uint32_t spu_rchcnt_host(spu_context* ctx, uint32_t channel);
uint32_t spu_rchcnt(spu_context* ctx, uint32_t channel)
{
    const int hwf = spu_hwf_suspend();
    const uint32_t r = spu_rchcnt_host(ctx, channel);
    spu_hwf_resume(hwf);
    return r;
}
static __attribute__((noinline)) uint32_t spu_rchcnt_host(spu_context* ctx, uint32_t channel)
{
""")
rep(r"""            spu_spurs_taskset_syscall(ctx);
            ctx->pc = ctx->gpr[0]._u32[0] & SPU_LS_MASK;
            return;""", r"""            { const int hwf = spu_hwf_suspend();   /* HLE kernel service: host float state */
              spu_spurs_taskset_syscall(ctx);
              spu_hwf_resume(hwf); }
            ctx->pc = ctx->gpr[0]._u32[0] & SPU_LS_MASK;
            return;""")
rep(r"""#include "spu_helpers.h"   /* spu_splat_u32 / spu_ls_read128 (SMC microstep) */
""", r"""#include "spu_helpers.h"   /* spu_splat_u32 / spu_ls_read128 (SMC microstep) */
#include "spu_hwfloat.h"   /* PS3_SPU_HWFLOAT run and host-call brackets */
#if defined(SPU_HWF_X86)
#  ifdef _WIN32
#    include <intrin.h>    /* __cpuid */
#  else
#    include <cpuid.h>
#  endif
#endif
""")
