"""T134: PS3_CRITICAL_PATH_TRACE hooks (one-shot patch of a ps3recomp tree).
  py -3 patch_hooks.py <tree>
- D3D12: TEXSNAP spans per draw (>= PS3_FTRACE_MIN_US), RSX_RECORD around render_frame;
- cellGcmSys: the drain's host thread is named (role rsx);
- cellSpurs: lanes / coordinator named, SPURS_PICK at admission, SPURS_PM around a lane's PM run;
- spu_workload: SPU_TASK around each async task run (who = its short-lived host thread id, not registered);
- sys_ppu_thread: PPU host threads named (main at registration, others at their entry)."""
from pathlib import Path
import sys

W = Path(sys.argv[1])


def patch(rel, pairs):
    p = W / rel
    t = p.read_text(encoding='utf-8')
    crlf = '\r\n' in t
    t = t.replace('\r\n', '\n')
    for old, new in pairs:
        assert t.count(old) == 1, (rel, old[:100], t.count(old))
        t = t.replace(old, new)
    if crlf:
        t = t.replace('\n', '\r\n')
    p.write_text(t, encoding='utf-8', newline='')
    print('patched', rel)


patch('libs/video/rsx_d3d12_backend.c', [
    ('''static void vp_record_tex_snap(D3D12DrawRecord* dr)
{
    extern uint8_t* vm_base;
    const int mode = tex_snapshot_mode();
''', '''static void vp_record_tex_snap_units(D3D12DrawRecord* dr);
static void vp_record_tex_snap(D3D12DrawRecord* dr)
{
    /* PS3_FTRACE / PS3_CRITICAL_PATH_TRACE (T134): one span per draw whose
     * captures took at least PS3_FTRACE_MIN_US; a = KB hashed, b = copies. */
    const uint64_t ft_t0 = PS3_FT_ON() ? ps3_ft_now() : 0;
    const uint64_t h0 = s_texsnap.hashed, c0 = s_texsnap.copies;
    vp_record_tex_snap_units(dr);
    if (ft_t0) {
        const uint64_t t1 = ps3_ft_now();
        if (t1 - ft_t0 >= ps3_ft_min_ns())
            ps3_ft_span(PS3_FT_TEXSNAP, 0, (uint32_t)((s_texsnap.hashed - h0) >> 10),
                        (uint32_t)(s_texsnap.copies - c0), ft_t0, t1);
    }
}

static void vp_record_tex_snap_units(D3D12DrawRecord* dr)
{
    extern uint8_t* vm_base;
    const int mode = tex_snapshot_mode();
'''),
    ('''static void render_frame(void)
{
    pp_note(PP_REPLAY);''', '''static void render_frame_body(void);
/* PS3_FTRACE / PS3_CRITICAL_PATH_TRACE (T134): the whole replay, a = 0, b = presented. */
static void render_frame(void)
{
    const uint64_t ft_t0 = PS3_FT_ON() ? ps3_ft_now() : 0;
    render_frame_body();
    if (ft_t0) ps3_ft_span(PS3_FT_RSX_RECORD, 0, 0, (uint32_t)s_present_this_frame, ft_t0, ps3_ft_now());
}

static void render_frame_body(void)
{
    pp_note(PP_REPLAY);'''),
])

patch('libs/video/cellGcmSys.c', [
    ('''    const uint64_t ft_t0 = PS3_FT_ON() ? ps3_ft_now() : 0;
    const unsigned gsw_op0 = cellGcm_stall_op(GSW_OP_FIFO_LOCK);''',
     '''    const uint64_t ft_t0 = PS3_FT_ON() ? ps3_ft_now() : 0;
    if (ft_t0) ps3_ft_host_thread(PS3_FT_ROLE_RSX, 0, "rsx-drain");
    const unsigned gsw_op0 = cellGcm_stall_op(GSW_OP_FIFO_LOCK);'''),
])

patch('libs/spurs/cellSpurs.c', [
    ('''#include "ps3emu/video_stats.h"
''', '''#include "ps3emu/video_stats.h"
#include "ps3emu/ps3_ftrace.h"   /* T134: SPURS_PICK / SPURS_PM spans, lane names */
'''),
    ('''    if (spurs_busy_ms()) {
        slot->host_tid = (unsigned long)GetCurrentThreadId();
        fprintf(stderr, "[thread-role] hosttid=%lu role=spurs-pm spurs=0x%08X sn=%u\\n",
                slot->host_tid, si->ea, slot->spu_num);
    }''', '''    if (spurs_busy_ms()) {
        slot->host_tid = (unsigned long)GetCurrentThreadId();
        fprintf(stderr, "[thread-role] hosttid=%lu role=spurs-pm spurs=0x%08X sn=%u\\n",
                slot->host_tid, si->ea, slot->spu_num);
    }
    if (PS3_FT_ON()) {
        char nm[40]; snprintf(nm, sizeof nm, "spurs-pm 0x%08X sn=%u", si->ea, slot->spu_num);
        ps3_ft_host_thread(PS3_FT_ROLE_SPURS_PM, slot->spu_num, nm);
    }'''),
    ('''        u64 busy_t0 = spurs_busy_ms() ? spurs_busy_now_us() : 0;
        spu_run_policy_module(slot->fn, slot->image_id, slot->pm, slot->pm_size,
                              slot->data, slot->wid, slot->ea, slot->spu_num);
        extern SPU_THREAD_LOCAL volatile unsigned g_spurs_pm_polls;
        unsigned polls = g_spurs_pm_polls;''', '''        u64 busy_t0 = spurs_busy_ms() ? spurs_busy_now_us() : 0;
        const uint64_t ft_t0 = PS3_FT_ON() ? ps3_ft_now() : 0;
        spu_run_policy_module(slot->fn, slot->image_id, slot->pm, slot->pm_size,
                              slot->data, slot->wid, slot->ea, slot->spu_num);
        extern SPU_THREAD_LOCAL volatile unsigned g_spurs_pm_polls;
        unsigned polls = g_spurs_pm_polls;
        if (ft_t0)   /* T134: the lane's policy-module residency */
            ps3_ft_span(PS3_FT_SPURS_PM, slot->spu_num,
                        (slot->wid & 0xFFu) | (slot->spu_num & 0xFFu) << 8 | (polls > 0xFFFFu ? 0xFFFFu : polls) << 16,
                        slot->ea, ft_t0, ps3_ft_now());'''),
    ('''    if (busy_ms)
        fprintf(stderr, "[thread-role] hosttid=%lu role=spurs-kernel spurs=0x%08X\\n",
                (unsigned long)GetCurrentThreadId(), si->ea);''', '''    if (busy_ms)
        fprintf(stderr, "[thread-role] hosttid=%lu role=spurs-kernel spurs=0x%08X\\n",
                (unsigned long)GetCurrentThreadId(), si->ea);
    if (PS3_FT_ON()) {
        char nm[40]; snprintf(nm, sizeof nm, "spurs-kernel 0x%08X", si->ea);
        ps3_ft_host_thread(PS3_FT_ROLE_SPURS_KERNEL, 0, nm);
    }'''),
    ('''                si->active[wid]++;
                spu_lockline_lock();
                vm_base[ea + SPURS_WKL_CURCONT + wid] = si->active[wid];
                ef_line_end(ea);
                slot->busy = 1;''', '''                si->active[wid]++;
                spu_lockline_lock();
                vm_base[ea + SPURS_WKL_CURCONT + wid] = si->active[wid];
                ef_line_end(ea);
                if (PS3_FT_ON()) {   /* T134: admission, instant */
                    const uint64_t t = ps3_ft_now();
                    ps3_ft_span(PS3_FT_SPURS_PICK, sn, wid | (sn & 0xFFu) << 8 | (kicked ? 1u : 0u) << 16, ea, t, t);
                }
                slot->busy = 1;'''),
])

patch('runtime/spu/spu_workload.c', [
    ('''#include "../ps3_log.h"      /* ps3_log_verbose */
''', '''#include "../ps3_log.h"      /* ps3_log_verbose */
#include "ps3emu/ps3_ftrace.h"   /* T134: SPU_TASK spans */
'''),
    ('''    { ULONG g = 256 * 1024; SetThreadStackGuarantee(&g); }
    spu_async_run((spu_async_job*)p);''', '''    { ULONG g = 256 * 1024; SetThreadStackGuarantee(&g); }
    if (PS3_FT_ON()) {   /* T134: one span per task run; who = this (short-lived) host thread's id */
        spu_async_job* j = (spu_async_job*)p;
        const int image = j->image_id;
        const uint64_t t0 = ps3_ft_now();
        spu_async_run(j);   /* frees j */
        ps3_ft_span(PS3_FT_SPU_TASK, (uint32_t)GetCurrentThreadId(), (uint32_t)image, 0, t0, ps3_ft_now());
    } else
    spu_async_run((spu_async_job*)p);'''),
])

patch('runtime/syscalls/sys_ppu_thread.c', [
    ('''    { extern void ppu_resv_register(ppu_context*); ppu_resv_register(&info->ctx); }
''', '''    { extern void ppu_resv_register(ppu_context*); ppu_resv_register(&info->ctx); }
    ps3_ft_host_thread(PS3_FT_ROLE_PPU, (uint32_t)info->ctx.thread_id, info->name);   /* T134 */
'''),
    ('''        ps3_ft_name(1, "main");
''', '''        ps3_ft_name(1, "main");
        ps3_ft_host_thread(PS3_FT_ROLE_PPU, 1, "main");   /* T134: the registering (main) host thread */
'''),
])
