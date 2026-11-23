MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T99 v2: RSX_FRAME_PERF without renaming or restructuring any existing function.

Wrappers are defined right after each original definition and bound with an
object-like macro, so later call sites (unchanged text) reach the wrapper and
the original bodies stay byte-identical for the existing source pins.
"""
import re
import sys
sys.path.insert(0, __import__('tempfile').gettempdir())
from t96rep import R

W = (MS_ROOT + r'\ps3recomp-t99')
r = R(W + r'\libs\video\rsx_d3d12_backend.c')
NL = '\r\n' if r.crlf else '\n'


def after_function(sig, text):
    """Insert `text` right after the function whose definition starts with `sig`."""
    s = r.s
    i = s.find(sig)
    assert i >= 0 and s.find(sig, i + 1) < 0, sig
    j = s.find(NL + '}' + NL, i)
    assert j > 0
    j += len(NL + '}' + NL)
    r.s = s[:j] + text.replace('\n', NL) + s[j:]


r.rep('#include "ps3emu/vp_flush.h"           /* early replay instead of dropping a draw */\n',
      '#include "ps3emu/vp_flush.h"           /* early replay instead of dropping a draw */\n'
      '#include "ps3emu/rsx_frame_perf.h"     /* RSX_FRAME_PERF: per-guest-frame time split */\n')

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
 * Off unless set; when off nothing below runs except one flag test per
 * wrapped call. When on: two QPC reads per draw callback, per render_frame
 * pass, per FIFO drain and per shader/PSO/texture lookup, plain counters
 * (the thread that drains and renders), no lock, no file, nothing per draw
 * on stderr. Wrappers are bound by macros after each original definition. */
static int s_fpf_on = 0;
static rfpf_state s_fpf;
static __declspec(thread) int s_fpf_in_drain = 0;   /* per thread: a guest thread may drain too */
static __declspec(thread) u64 s_fpf_drain_t0 = 0;
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

after_function('static int vp_get_vs(const rsx_state* st)\n{'.replace('\n', NL), '''
/* RSX_FRAME_PERF: a call that added a cache entry, or took 1 ms or more
 * without adding one (an uncached failed compile), counts as a miss. */
static int fpf_vp_get_vs(const rsx_state* st)
{
    if (!s_fpf_on) return vp_get_vs(st);
    const int n0 = s_d3d.vp_vs_n;
    const u64 t0 = fpf_now_us();
    const int r = vp_get_vs(st);
    const u64 dt = fpf_now_us() - t0;
    s_fpf.cur.vs_calls++;
    if (s_d3d.vp_vs_n != n0 || dt >= 1000u) { s_fpf.cur.vs_miss++; s_fpf.cur.vs_miss_us += dt; }
    return r;
}
#define vp_get_vs fpf_vp_get_vs
''')

after_function('static ID3D12PipelineState* vp_get_fp_pso(int vs_idx, u32 fp_addr, u32 blend, int nrt,', '''
static ID3D12PipelineState* fpf_vp_get_fp_pso(int vs_idx, u32 fp_addr, u32 blend, int nrt,
                                              DXGI_FORMAT rtfmt, int exp32, u32 cmask, u32 cull,
                                              u32 cube_mask, const rsx_fp_shadow_desc* shadow,
                                              u32 shadow_key, u32 depth)
{
    if (!s_fpf_on)
        return vp_get_fp_pso(vs_idx, fp_addr, blend, nrt, rtfmt, exp32, cmask, cull, cube_mask, shadow, shadow_key, depth);
    const int m0 = s_perf_pso_miss;   /* counted on every miss, PERF or not */
    const u64 t0 = fpf_now_us();
    ID3D12PipelineState* p = vp_get_fp_pso(vs_idx, fp_addr, blend, nrt, rtfmt, exp32, cmask, cull, cube_mask,
                                           shadow, shadow_key, depth);
    const u64 dt = fpf_now_us() - t0;
    s_fpf.cur.pso_calls++; s_fpf.cur.pso_us += dt;
    if (s_perf_pso_miss != m0) { s_fpf.cur.pso_miss++; s_fpf.cur.pso_miss_us += dt; }
    return p;
}
#define vp_get_fp_pso fpf_vp_get_fp_pso
''')

after_function('static int vp_upload_tex_slot(u32 off, u32 w, u32 h, u32 fmt, int cube, u32 mips)', '''
static int fpf_vp_upload_tex_slot(u32 off, u32 w, u32 h, u32 fmt, int cube, u32 mips)
{
    if (!s_fpf_on) return vp_upload_tex_slot(off, w, h, fmt, cube, mips);
    const u64 t0 = fpf_now_us();
    const int r = vp_upload_tex_slot(off, w, h, fmt, cube, mips);
    s_fpf.cur.tex_calls++; s_fpf.cur.tex_us += fpf_now_us() - t0;
    return r;
}
#define vp_upload_tex_slot fpf_vp_upload_tex_slot
''')

after_function('static void render_frame(void)\n{'.replace('\n', NL), '''
/* RSX_FRAME_PERF: time each pass; a presenting pass that is not an early
 * replay closes the guest frame. The phase split comes from rf_phase.h,
 * which marks only while RF_PHASE_MS > 0: with RSX_FRAME_PERF on and
 * RF_PHASE_MS unset its threshold is set out of reach, so phases are timed
 * and no [rf-phase] line prints. */
static void fpf_render_frame(void)
{
    if (!s_fpf_on) { render_frame(); return; }
    if (s_rfp_ms < 0 && !getenv("RF_PHASE_MS")) s_rfp_ms = 0x7FFFFFFF;
    const int early = s_vpf.in_flush, present = s_present_this_frame, in_drain = s_fpf_in_drain;
    const u32 recs = s_d3d.draw_count;
    const u64 t0 = fpf_now_us();
    render_frame();
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
#define render_frame fpf_render_frame
''')

# early replays started from a draw callback
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

r.rep('''    s_up_want += want; s_up_got += got;''', '''    s_up_want += want; s_up_got += got;
    if (s_fpf_on) s_fpf.cur.verts += got;''')

# draw callbacks: wrappers installed after the (unchanged) registration
r.rep('''static void d3d12_draw_indexed(void* ud, u32 primitive, u32 first, u32 count)
{''', '''static void fpf_draw_arrays(void* ud, u32 primitive, u32 first, u32 count);
static void fpf_draw_indexed(void* ud, u32 primitive, u32 first, u32 count);
static void d3d12_draw_indexed(void* ud, u32 primitive, u32 first, u32 count)
{''')
after_function('static void d3d12_draw_indexed(void* ud, u32 primitive, u32 first, u32 count)\n{'.replace('\n', NL), '''/* RSX_FRAME_PERF: time in the draw callbacks (expansion, upload, record
 * building, VS lookups and early replays started from them). */
static void fpf_draw_arrays(void* ud, u32 primitive, u32 first, u32 count)
{
    const u64 t0 = fpf_now_us();
    d3d12_draw_arrays(ud, primitive, first, count);
    s_fpf.cur.draw_calls++; s_fpf.cur.draw_us += fpf_now_us() - t0;
}
static void fpf_draw_indexed(void* ud, u32 primitive, u32 first, u32 count)
{
    const u64 t0 = fpf_now_us();
    d3d12_draw_indexed(ud, primitive, first, count);
    s_fpf.cur.draw_calls++; s_fpf.cur.draw_us += fpf_now_us() - t0;
}
''')
r.rep('''    s_d3d12_backend.draw_indexed      = d3d12_draw_indexed;
''', '''    s_d3d12_backend.draw_indexed      = d3d12_draw_indexed;
    if (s_fpf_on) {   /* RSX_FRAME_PERF: timing wrappers around the same callbacks */
        s_d3d12_backend.draw_arrays  = fpf_draw_arrays;
        s_d3d12_backend.draw_indexed = fpf_draw_indexed;
    }
''')

r.rep('int rsx_d3d12_backend_init(u32 width, u32 height, const char* title)\n{',
      'int rsx_d3d12_backend_init(u32 width, u32 height, const char* title)\n{\n    fpf_init();   /* RSX_FRAME_PERF, off unless set */')
r.save()
print('ok')
