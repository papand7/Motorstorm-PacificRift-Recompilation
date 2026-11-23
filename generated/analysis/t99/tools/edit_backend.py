MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T99: RSX_FRAME_PERF instrumentation (off by default) in ps3recomp-t99."""
import sys
sys.path.insert(0, __import__('tempfile').gettempdir())
from t96rep import R

W = (MS_ROOT + r'\ps3recomp-t99')
r = R(W + r'\libs\video\rsx_d3d12_backend.c')

r.rep('#include "ps3emu/vp_flush.h"           /* early replay instead of dropping a draw */\n',
      '#include "ps3emu/vp_flush.h"           /* early replay instead of dropping a draw */\n'
      '#include "ps3emu/rsx_frame_perf.h"     /* RSX_FRAME_PERF: per-guest-frame time split */\n')

# state, clock, env, drain hook: right after perf_on()
r.rep('''static int perf_on(void)
{
    static int v = -1;
    if (v < 0) { const char* e = getenv("PERF"); v = e ? atoi(e) : 0; }
    return v;
}
''', '''static int perf_on(void)
{
    static int v = -1;
    if (v < 0) { const char* e = getenv("PERF"); v = e ? atoi(e) : 0; }
    return v;
}

/* RSX_FRAME_PERF=<first N guest frames>[,<every K-th after>][,<max lines>]
 * (rsx_frame_perf.h): one [rsx-frame-perf] line per selected guest frame.
 * Off unless set. Two QPC reads per draw callback, per render_frame pass and
 * per FIFO drain, plus per shader/PSO/texture lookup; counters are plain
 * fields touched by the thread that drains and renders. */
static int s_fpf_on = 0;
static rfpf_state s_fpf;
static _Thread_local int s_fpf_in_drain = 0;
static _Thread_local u64 s_fpf_drain_t0 = 0;
static u64 fpf_now_us(void)
{
    static LARGE_INTEGER f; LARGE_INTEGER t;
    if (!f.QuadPart) QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&t);
    return (u64)(t.QuadPart / f.QuadPart) * 1000000ull + (u64)(t.QuadPart % f.QuadPart) * 1000000ull / (u64)f.QuadPart;
}
extern void (*volatile cellGcm_drain_hook)(int begin);   /* cellGcmSys.c */
static void fpf_drain_hook(int begin)
{
    if (begin) { s_fpf_in_drain = 1; s_fpf_drain_t0 = fpf_now_us(); return; }
    s_fpf_in_drain = 0;
    s_fpf.cur.drain_us += fpf_now_us() - s_fpf_drain_t0;
}
static void fpf_init(void)
{
    const char* e = getenv("RSX_FRAME_PERF");
    unsigned first = 0, every = 0, maxl = 400;
    if (e) sscanf(e, "%u,%u,%u", &first, &every, &maxl);
    if (!first && !every) return;
    rfpf_init(&s_fpf, first, every, maxl);
    s_fpf_on = 1;
    cellGcm_drain_hook = fpf_drain_hook;
    fprintf(stderr, "[rsx-frame-perf] on: first %u guest frames, then every %u, at most %u lines%c", first, every, maxl, 10);
}
''')

# vp_get_vs wrapper
r.rep('static int vp_get_vs(const rsx_state* st)\n{', 'static int vp_get_vs_impl(const rsx_state* st)\n{')
r.rep('''static ID3D12PipelineState* vp_get_fp_pso(int vs_idx, u32 fp_addr, u32 blend, int nrt,
                                          DXGI_FORMAT rtfmt, int exp32, u32 cmask, u32 cull,
                                          u32 cube_mask, const rsx_fp_shadow_desc* shadow,
                                          u32 shadow_key, u32 depth)
{''', '''/* RSX_FRAME_PERF: a call that added a cache entry, or took over 1 ms
 * without adding one (an uncached failed compile), counts as a miss. */
static int vp_get_vs(const rsx_state* st)
{
    if (!s_fpf_on) return vp_get_vs_impl(st);
    const int n0 = s_d3d.vp_vs_n;
    const u64 t0 = fpf_now_us();
    const int r = vp_get_vs_impl(st);
    const u64 dt = fpf_now_us() - t0;
    s_fpf.cur.vs_calls++;
    if (s_d3d.vp_vs_n != n0 || dt >= 1000u) { s_fpf.cur.vs_miss++; s_fpf.cur.vs_miss_us += dt; }
    return r;
}

static ID3D12PipelineState* vp_get_fp_pso_impl(int vs_idx, u32 fp_addr, u32 blend, int nrt,
                                          DXGI_FORMAT rtfmt, int exp32, u32 cmask, u32 cull,
                                          u32 cube_mask, const rsx_fp_shadow_desc* shadow,
                                          u32 shadow_key, u32 depth)
{''')

# pso + tex wrappers: before vp_upload_tex_slot definition
r.rep('static int vp_upload_tex_slot(u32 off, u32 w, u32 h, u32 fmt, int cube, u32 mips)\n{',
'''static ID3D12PipelineState* vp_get_fp_pso(int vs_idx, u32 fp_addr, u32 blend, int nrt,
                                          DXGI_FORMAT rtfmt, int exp32, u32 cmask, u32 cull,
                                          u32 cube_mask, const rsx_fp_shadow_desc* shadow,
                                          u32 shadow_key, u32 depth)
{
    if (!s_fpf_on)
        return vp_get_fp_pso_impl(vs_idx, fp_addr, blend, nrt, rtfmt, exp32, cmask, cull, cube_mask, shadow, shadow_key, depth);
    const int m0 = s_perf_pso_miss;
    const u64 t0 = fpf_now_us();
    ID3D12PipelineState* p = vp_get_fp_pso_impl(vs_idx, fp_addr, blend, nrt, rtfmt, exp32, cmask, cull, cube_mask,
                                                 shadow, shadow_key, depth);
    const u64 dt = fpf_now_us() - t0;
    s_fpf.cur.pso_calls++; s_fpf.cur.pso_us += dt;
    if (s_perf_pso_miss != m0) { s_fpf.cur.pso_miss++; s_fpf.cur.pso_miss_us += dt; }
    return p;
}

static int vp_upload_tex_slot_impl(u32 off, u32 w, u32 h, u32 fmt, int cube, u32 mips);
static int vp_upload_tex_slot(u32 off, u32 w, u32 h, u32 fmt, int cube, u32 mips)
{
    if (!s_fpf_on) return vp_upload_tex_slot_impl(off, w, h, fmt, cube, mips);
    const u64 t0 = fpf_now_us();
    const int r = vp_upload_tex_slot_impl(off, w, h, fmt, cube, mips);
    s_fpf.cur.tex_calls++; s_fpf.cur.tex_us += fpf_now_us() - t0;
    return r;
}

static int vp_upload_tex_slot_impl(u32 off, u32 w, u32 h, u32 fmt, int cube, u32 mips)
{''')

# rf-phase timing also when RSX_FRAME_PERF is on (printing still needs RF_PHASE_MS)
r.rep('static inline void rfp_at(int phase) { if (s_rfp_ms > 0) rfp_mark(&s_rfp, rfp_now_us(), phase); }',
      'static inline void rfp_at(int phase) { if (s_rfp_ms > 0 || s_fpf_on) rfp_mark(&s_rfp, rfp_now_us(), phase); }')
r.rep('''    if (s_rfp_ms > 0) {
        rfp_begin(&s_rfp, rfp_now_us());''', '''    if (s_rfp_ms > 0 || s_fpf_on) {
        rfp_begin(&s_rfp, rfp_now_us());''')

# render_frame wrapper
r.rep('''static void render_frame(void)
{
    pp_note(PP_REPLAY);''', '''static void render_frame_impl(void);
/* RSX_FRAME_PERF: time each pass; a presenting pass that is not an early
 * replay closes the guest frame. */
static void render_frame(void)
{
    if (!s_fpf_on) { render_frame_impl(); return; }
    const int early = s_vpf.in_flush, present = s_present_this_frame, in_drain = s_fpf_in_drain;
    const u32 recs = s_d3d.draw_count;
    const u64 t0 = fpf_now_us();
    render_frame_impl();
    const u64 t1 = fpf_now_us(), dt = t1 - t0;
    rfpf_counts* c = &s_fpf.cur;
    c->passes++; c->early += early ? 1u : 0u; c->records += recs;
    c->rf_us += dt; if (in_drain) c->rf_in_drain_us += dt;
    c->rf_record_us += s_rfp.us[RFP_RECORD];
    c->rf_wait_us += s_rfp.us[RFP_GPU_DRAIN] + s_rfp.us[RFP_NEXT_FRAME];
    c->rf_present_us += s_rfp.us[RFP_PRESENT];
    c->rf_submit_us += s_rfp.us[RFP_SUBMIT];
    if (early || !present) return;
    u64 wall = 0;
    if (rfpf_close(&s_fpf, t1, &wall)) {
        char b[768];
        rfpf_format(b, sizeof b, s_fpf.guest_frames, s_d3d.frame_count, c, wall);
        fprintf(stderr, "%s%c", b, 10);
    }
    rfpf_reset(&s_fpf);
}

static void render_frame_impl(void)
{
    pp_note(PP_REPLAY);''')

# vp_flush timing
r.rep('''    const int keep = s_present_this_frame;
    s_present_this_frame = 0;
    render_frame();
    s_present_this_frame = keep;
    vpf_flush_end(&s_vpf);''', '''    const int keep = s_present_this_frame;
    s_present_this_frame = 0;
    const u64 ft0 = s_fpf_on ? fpf_now_us() : 0;
    render_frame();
    if (s_fpf_on) s_fpf.cur.flush_us += fpf_now_us() - ft0;
    s_present_this_frame = keep;
    vpf_flush_end(&s_vpf);''')

# vertices written
r.rep('''    s_up_want += want; s_up_got += got;''', '''    s_up_want += want; s_up_got += got;
    if (s_fpf_on) s_fpf.cur.verts += got;''')

# draw callbacks
for kind in ('arrays', 'indexed'):
    r.rep(f'''static void d3d12_draw_{kind}(void* ud, u32 primitive, u32 first, u32 count)
{{
    s_da_reason = DA_R_OTHER; s_up_want = s_up_got = 0;
    if (!da_on()) {{ d3d12_draw_{kind}_body(ud, primitive, first, count); return; }}
    const u32 n0 = s_d3d.draw_count;
    s_da_merged = 0;
    d3d12_draw_{kind}_body(ud, primitive, first, count);
    da_account(n0, primitive, count);
}}''', f'''static void d3d12_draw_{kind}(void* ud, u32 primitive, u32 first, u32 count)
{{
    s_da_reason = DA_R_OTHER; s_up_want = s_up_got = 0;
    const u64 fp0 = s_fpf_on ? fpf_now_us() : 0;
    if (!da_on()) d3d12_draw_{kind}_body(ud, primitive, first, count);
    else {{
        const u32 n0 = s_d3d.draw_count;
        s_da_merged = 0;
        d3d12_draw_{kind}_body(ud, primitive, first, count);
        da_account(n0, primitive, count);
    }}
    if (s_fpf_on) {{ s_fpf.cur.draw_calls++; s_fpf.cur.draw_us += fpf_now_us() - fp0; }}
}}''')

# init
r.rep('int rsx_d3d12_backend_init(u32 width, u32 height, const char* title)\n{',
      'int rsx_d3d12_backend_init(u32 width, u32 height, const char* title)\n{\n    fpf_init();   /* RSX_FRAME_PERF, off unless set */')
r.save()

g = R(W + r'\libs\video\cellGcmSys.c')
g.rep('''void cellGcm_rsx_process_fifo(void)
{
    const uint64_t ft_t0 = PS3_FT_ON() ? ps3_ft_now() : 0;''', '''/* RSX_FRAME_PERF (backend, rsx_frame_perf.h): set by the D3D12 backend when
 * on, so it can split a guest frame's time; NULL otherwise. */
void (*volatile cellGcm_drain_hook)(int begin) = NULL;

void cellGcm_rsx_process_fifo(void)
{
    void (*const dh)(int) = cellGcm_drain_hook;
    if (dh) dh(1);
    const uint64_t ft_t0 = PS3_FT_ON() ? ps3_ft_now() : 0;''')
g.save()
print('ok')

g = R(W + r'\libs\video\cellGcmSys.c')
g.rep('''            ps3_ft_span(PS3_FT_DRAIN, 0, s_ft_sema_t0 ? 1u : 0u, 0, ft_t0, t1);
    }
}
''', '''            ps3_ft_span(PS3_FT_DRAIN, 0, s_ft_sema_t0 ? 1u : 0u, 0, ft_t0, t1);
    }
    if (dh) dh(0);
}
''')
g.save()
print('ok2')
