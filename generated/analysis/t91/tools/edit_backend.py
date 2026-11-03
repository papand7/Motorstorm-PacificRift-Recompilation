"""T91 instrumentation: RF_PHASE_MS render_frame phases (off by default)."""
from pathlib import Path
import sys
p = Path(sys.argv[1]) / 'libs/video/rsx_d3d12_backend.c'
s = p.read_text(encoding='utf-8')


def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (s.count(a), a[:80])
    s = s.replace(a, b)


# 1. state + helpers, before gsw_backend_info (which reports the phase in progress)
rep("""static void gsw_backend_info(char* b, unsigned n)
{""", """/* RF_PHASE_MS=<ms> (ps3emu/rf_phase.h): time each render_frame() phase; one
 * [rf-phase] line for a frame slower than <ms>, at most RF_PHASE_MAX (8) lines.
 * The phase in progress also goes into the GCM_STALL_MS snapshot. Off: one
 * branch per phase mark. */
#include "ps3emu/rf_phase.h"
static int s_rfp_ms = -1;            /* -1 = not read yet, 0 = off */
static int s_rfp_max = 8, s_rfp_lines = 0;
static rfp_frame s_rfp;
static rfp_atlas_geom s_rfp_atlas;   /* this frame's B8 upload, if any */
static u32 s_rfp_atlas_n = 0;        /* uploads this frame */
static u64 s_rfp_grow_copy = 0;      /* bytes vp_vb_grow copied this frame */
static u32 s_rfp_grow_from = 0, s_rfp_grow_to = 0;
static u64 rfp_now_us(void)
{
    static LARGE_INTEGER f; LARGE_INTEGER t;
    if (!f.QuadPart) QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&t);
    return (u64)(t.QuadPart / f.QuadPart) * 1000000ull + (u64)(t.QuadPart % f.QuadPart) * 1000000ull / (u64)f.QuadPart;
}
static inline void rfp_at(int phase) { if (s_rfp_ms > 0) rfp_mark(&s_rfp, rfp_now_us(), phase); }

static void gsw_backend_info(char* b, unsigned n)
{""")
rep("""             fdone, (unsigned long long)s_d3d.fence_values[s_d3d.frame_index], s_d3d.frame_index,
             (unsigned long long)s_d3d.frame_count);
}""", """             fdone, (unsigned long long)s_d3d.fence_values[s_d3d.frame_index], s_d3d.frame_index,
             (unsigned long long)s_d3d.frame_count);
    if (s_rfp_ms > 0) {   /* read-only: the phase render_frame is in, and for how long */
        const unsigned u = (unsigned)strlen(b);
        const int cur = s_rfp.cur;
        const u64 now = rfp_now_us(), t0 = s_rfp.phase_t0_us;
        if (u < n)
            snprintf(b + u, n - u, " rf_phase=%s rf_phase_ms=%llu rf_last_done=%s rf_frame=%llu",
                     rfp_name(cur), cur ? (unsigned long long)((now >= t0 ? now - t0 : 0) / 1000u) : 0ull,
                     rfp_name(s_rfp.last_done), (unsigned long long)s_rfp.frame);
    }
}""")
# 2. vp_vb_grow: record the copy, and retire (not release) the old buffer when deferred
rep("""    if (ok) {
        if (s_d3d.vp_vb_offset)
            memcpy((u8*)nm + (u64)s_d3d.vp_parity * new_cap * 256u,
                   (const u8*)s_d3d.vp_vb_mapped + (u64)s_d3d.vp_parity * old_cap * 256u,
                   s_d3d.vp_vb_offset);
        s_d3d.vp_vb->lpVtbl->Release(s_d3d.vp_vb);""", """    if (ok) {
        s_rfp_grow_copy = rfp_vb_grow_copy_bytes(s_d3d.vp_vb_offset);
        s_rfp_grow_from = old_cap; s_rfp_grow_to = new_cap;
        if (s_d3d.vp_vb_offset)
            memcpy((u8*)nm + (u64)s_d3d.vp_parity * new_cap * 256u,
                   (const u8*)s_d3d.vp_vb_mapped + (u64)s_d3d.vp_parity * old_cap * 256u,
                   s_d3d.vp_vb_offset);
        s_d3d.vp_vb->lpVtbl->Release(s_d3d.vp_vb);""")
# 3. render_frame entry, drain, grow
rep("""    GSW_OP_SCOPE(GSW_OP_RENDER);
    pdg_replay(s_present_this_frame);
    double _rf0 = perf_on() ? perf_now() : 0.0;
    u32 fi = s_d3d.frame_index;
""", """    GSW_OP_SCOPE(GSW_OP_RENDER);
    if (s_rfp_ms < 0) {
        const char* e = getenv("RF_PHASE_MS"); s_rfp_ms = e ? atoi(e) : 0; if (s_rfp_ms < 0) s_rfp_ms = 0;
        const char* m = getenv("RF_PHASE_MAX"); if (m && atoi(m) > 0) s_rfp_max = atoi(m);
        if (s_rfp_ms > 0) fprintf(stderr, "[rf-phase] on: frames slower than %d ms, at most %d line(s)%c", s_rfp_ms, s_rfp_max, 10);
    }
    if (s_rfp_ms > 0) {
        rfp_begin(&s_rfp, rfp_now_us());
        s_rfp_atlas_n = 0; s_rfp_grow_copy = 0; s_rfp_grow_from = s_rfp_grow_to = 0;
    }
    pdg_replay(s_present_this_frame);
    double _rf0 = perf_on() ? perf_now() : 0.0;
    u32 fi = s_d3d.frame_index;
""")
rep("""     * costs little. */
    wait_for_gpu();

    /* The GPU is idle: if this frame's vertex-program geometry did not fit,
     * grow the buffer before the next frame records into it. */
    if (s_d3d.vp_vb && s_d3d.vp_vb_mapped) {
        const u32 grow_to = vpvb_end_frame(&s_vpvb);
        if (grow_to) vp_vb_grow(grow_to);
    }
""", """     * costs little. */
    rfp_at(RFP_GPU_DRAIN);
    wait_for_gpu();
    rfp_at(RFP_VB_GROW);

    /* The GPU is idle: if this frame's vertex-program geometry did not fit,
     * grow the buffer before the next frame records into it. */
    if (s_d3d.vp_vb && s_d3d.vp_vb_mapped) {
        const u32 grow_to = vpvb_end_frame(&s_vpvb);
        if (grow_to) vp_vb_grow(grow_to);
    }
    rfp_at(RFP_COMPILE_VP);
""")
# 4. atlas upload
rep("""    if (s_d3d.tex_bound && (!s_d3d.tex_ready || s_d3d.tex_dirty) && s_d3d.srv_heap && s_d3d.pipeline_state_tex) {
        extern uint8_t* vm_base;
        u32 w = s_d3d.tex_w, h = s_d3d.tex_h;
        u32 pitch = (w + 255) & ~255u;   /* D3D12 requires 256-byte row pitch */
""", """    rfp_at(RFP_ATLAS);
    if (s_d3d.tex_bound && (!s_d3d.tex_ready || s_d3d.tex_dirty) && s_d3d.srv_heap && s_d3d.pipeline_state_tex) {
        extern uint8_t* vm_base;
        u32 w = s_d3d.tex_w, h = s_d3d.tex_h;
        u32 pitch = (w + 255) & ~255u;   /* D3D12 requires 256-byte row pitch */
        if (s_rfp_ms > 0) { s_rfp_atlas = rfp_atlas_calc(w, h, s_d3d.tex_src_offset, 0x100000000ull); s_rfp_atlas_n++; }
""")
rep("""    /* Frames with no ops (init/boot presents) don't count against the cap --
     * PNG-decode-heavy titles burn hundreds of empty presents before the first
     * real draw. */""", """    rfp_at(RFP_RECORD);

    /* Frames with no ops (init/boot presents) don't count against the cap --
     * PNG-decode-heavy titles burn hundreds of empty presents before the first
     * real draw. */""")
# 5. submit / capture / present / next frame / tail
rep("""    /* Close and execute */
    const HRESULT close_hr""", """    rfp_at(RFP_SUBMIT);
    /* Close and execute */
    const HRESULT close_hr""")
rep("""    rsxi_frame_finish();        /* RSXI: one GPU wait, write the captured frame */
""", """    rfp_at(RFP_CAPTURE);
    rsxi_frame_finish();        /* RSXI: one GPU wait, write the captured frame */
    rfp_at(RFP_TAIL);
""")
rep("""    /* Present */
    const uint64_t vs_t0""", """    /* Present */
    rfp_at(RFP_PRESENT);
    const uint64_t vs_t0""")
rep("""    const u64 present_fence = s_d3d.fence_values[s_d3d.frame_index];
    move_to_next_frame();
""", """    const u64 present_fence = s_d3d.fence_values[s_d3d.frame_index];
    rfp_at(RFP_NEXT_FRAME);
    move_to_next_frame();
    rfp_at(RFP_TAIL);
""")
rep("""    s_d3d.frame_count++;

    /* RSX_HEARTBEAT_MS=<ms>""", """    s_d3d.frame_count++;

    /* RSX_HEARTBEAT_MS=<ms>""")
rep("""            SetWindowTextA(s_d3d.hwnd, tb);
            s_tframes = 0;
            s_tt0 = tnow;
        }
    }
}""", """            SetWindowTextA(s_d3d.hwnd, tb);
            s_tframes = 0;
            s_tt0 = tnow;
        }
    }

    if (s_rfp_ms > 0) {
        const u64 total = rfp_end(&s_rfp, rfp_now_us());
        if (total >= (u64)s_rfp_ms * 1000u && s_rfp_lines < s_rfp_max) {
            char ph[512];
            s_rfp_lines++;
            rfp_format_phases(ph, sizeof ph, &s_rfp);
            fprintf(stderr, "[rf-phase] frame=%llu total_ms=%.1f slowest=%s draws=%u vb_cap=%u vb_grow=%u->%u grow_copy_bytes=%llu"
                            " | %s%c", (unsigned long long)s_d3d.frame_count, (double)total / 1000.0,
                    rfp_name(rfp_slowest(&s_rfp)), s_dbg_last_draws, s_vpvb.cap, s_rfp_grow_from, s_rfp_grow_to,
                    (unsigned long long)s_rfp_grow_copy, ph, 10);
            if (s_rfp_atlas_n)
                fprintf(stderr, "[rf-phase]   atlas uploads=%u %ux%u pitch=%llu upload_bytes=%llu copy_bytes=%llu"
                                " src=[0x%llX,0x%llX) src_in_vm=%d d3d12_ok=%d%c", s_rfp_atlas_n,
                        s_rfp_atlas.w, s_rfp_atlas.h, (unsigned long long)s_rfp_atlas.pitch,
                        (unsigned long long)s_rfp_atlas.upload_bytes, (unsigned long long)s_rfp_atlas.copy_bytes,
                        (unsigned long long)s_rfp_atlas.src_off, (unsigned long long)s_rfp_atlas.src_end,
                        s_rfp_atlas.src_in_vm, s_rfp_atlas.d3d12_ok, 10);
        }
    }
}""")
p.write_text(s, encoding='utf-8')
print('ok')
