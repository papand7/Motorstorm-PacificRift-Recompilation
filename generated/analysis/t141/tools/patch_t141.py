"""T141: RSX_MRT_STATE, RSX_RT_FEEDBACK, RSX_ZETA_EXACT and D3D12_GBV in rsx_d3d12_backend.c (one-shot).
usage: python patch_t141.py <worktree>"""
import sys
W = sys.argv[1]
p = W + '/libs/video/rsx_d3d12_backend.c'
s = open(p, newline='', encoding='utf-8').read().replace('\r\n', '\n')


def rep(a, b, cnt=1):
    global s
    n = s.count(a)
    assert n == cnt, (a[:120], n)
    s = s.replace(a, b)


# ---- include and switches ----------------------------------------------------------------------
rep('#include "rsx_msaa.h"          /* RSX_MSAA: 2-sample antialias-3 surfaces */',
    '#include "rsx_msaa.h"          /* RSX_MSAA: 2-sample antialias-3 surfaces */\n'
    '#include "rsx_blend_feedback.h" /* RSX_MRT_STATE, RSX_RT_FEEDBACK, RSX_ZETA_EXACT (T141) */')
rep('static int  s_msaa = -1;',
    '''/* T141 switches (rsx_blend_feedback.h), each "1" to enable, read once. */
static int mrt_state_on(void)
{
    static int on = -1;
    if (on < 0) on = rsx_bf_switch_parse(getenv("RSX_MRT_STATE"));
    return on;
}
static int rt_feedback_on(void)
{
    static int on = -1;
    if (on < 0) on = rsx_bf_switch_parse(getenv("RSX_RT_FEEDBACK"));
    return on;
}
static int zeta_exact_on(void)
{
    static int on = -1;
    if (on < 0) on = rsx_bf_switch_parse(getenv("RSX_ZETA_EXACT"));
    return on;
}
static int  s_msaa = -1;''')

# ---- D3D12_GBV=1: GPU-based validation with the debug layer (diagnostic) -------------------------
rep('''            debug_controller->lpVtbl->EnableDebugLayer(debug_controller);
            debug_controller->lpVtbl->Release(debug_controller);''',
    '''            debug_controller->lpVtbl->EnableDebugLayer(debug_controller);
            /* D3D12_GBV=1: GPU-based validation too (resource states seen by
             * each draw's descriptors; slow, diagnostic only). */
            if (getenv("D3D12_GBV") && getenv("D3D12_GBV")[0] == '1') {
                ID3D12Debug1* d1 = NULL;
                if (SUCCEEDED(debug_controller->lpVtbl->QueryInterface(debug_controller, &IID_ID3D12Debug1, (void**)&d1)) && d1) {
                    d1->lpVtbl->SetEnableGPUBasedValidation(d1, TRUE);
                    d1->lpVtbl->Release(d1);
                    printf("[D3D12] GPU-based validation enabled\\n");
                }
            }
            debug_controller->lpVtbl->Release(debug_controller);''')

# ---- MRT key ------------------------------------------------------------------------------------
rep('''static u64 dr_depth_key(const D3D12DrawRecord* dr)
{''', '''/* RSX_MRT_STATE=1: targets B..D's COLOR_MASK_MRT / BLEND_ENABLE_MRT, OR-ed
 * onto the colour mask argument of the guest-FP pipeline (rsx_mrt_key: 0
 * while the guest never wrote them, so the key is the old one). */
static u32 dr_mrt_key(const D3D12DrawRecord* dr)
{
    if (!mrt_state_on()) return 0;
    if (rsx_mrt_blend_unkeyed(dr->g_mrt_blend, dr->g_mrt_set, dr->blend, dr_num_rts(dr))) {
        static int _n = 0;
        if (PS3_LOG_FIRST(_n, 4))
            fprintf(stderr, "[mrt] fp 0x%08X: BLEND_ENABLE_MRT 0x%X with target A unblended; B..D drawn unblended%c",
                    dr->fp_addr, dr->g_mrt_blend, 10);
    }
    return rsx_mrt_key(dr->g_mrt_cmask, dr->g_mrt_blend, dr->g_mrt_set);
}

static u64 dr_depth_key(const D3D12DrawRecord* dr)
{''')
rep('                          dr->fp_exp32, dr->cmask, dr->cull, dr_cube_mask(dr), _sd, _sk,\n',
    '                          dr->fp_exp32, dr->cmask | dr_mrt_key(dr), dr->cull, dr_cube_mask(dr), _sd, _sk,\n')
rep('                                                dr->fp_exp32, dr->cmask, dr->cull,\n'
    '                                                dr_cube_mask(dr), _sd, _sk,\n',
    '                                                dr->fp_exp32, dr->cmask | dr_mrt_key(dr), dr->cull,\n'
    '                                                dr_cube_mask(dr), _sd, _sk,\n')
rep('''    for (int _r = 0; _r < nrt; _r++)
        pd.BlendState.RenderTarget[_r].RenderTargetWriteMask = (UINT8)(cmask & 0xF);''',
    '''    for (int _r = 0; _r < nrt; _r++)
        pd.BlendState.RenderTarget[_r].RenderTargetWriteMask = (UINT8)rsx_mrt_target_mask(cmask, _r);
    /* RSX_MRT_STATE: targets B..D with their own masks and blend enables
     * (bits above [3:0], rsx_mrt_key). D3D12 reads RenderTarget[1..] only with
     * IndependentBlendEnable; without MRT bits every target mirrors A. */
    if (cmask & (RSX_MRT_KEY_MASKS | RSX_MRT_KEY_BLEND)) {
        pd.BlendState.IndependentBlendEnable = TRUE;
        for (int _r = 1; _r < nrt; _r++)
            if (!rsx_mrt_target_blend(cmask, _r, (blend & 1) != 0))
                pd.BlendState.RenderTarget[_r].BlendEnable = FALSE;
    }''')

# ---- RSX_ZETA_EXACT -----------------------------------------------------------------------------
rep('    const char* psrc = msaa_on() ? ps_clamped : ps;\n',
    '    const char* psrc = msaa_on() ? ps_clamped : ps;\n'
    '    /* RSX_ZETA_EXACT=1: depth24 exactly, far plane 0xFFFFFF (rsx_blend_feedback.h). */\n'
    '    if (zeta_exact_on()) psrc = RSX_ZCOLOR_EXACT_PS;\n')

# ---- RSX_RT_FEEDBACK ----------------------------------------------------------------------------
rep('    u16 tex_xms;        /* units reading an RSX_MSAA surface\'s sample-expanded image */\n',
    '    u16 tex_xms;        /* units reading an RSX_MSAA surface\'s sample-expanded image */\n'
    '    u16 tex_fb;         /* units reading a copy of a target this draw writes (RSX_RT_FEEDBACK) */\n')
rep('typedef struct { ID3D12Resource* res; u32 w, h, dxgi, src_id; u64 gen, frame; D3D12_RESOURCE_STATES st; } RtWin;\n'
    'static RtWin s_rtwin[MAX_OFF_RTS];\n',
    'typedef struct { ID3D12Resource* res; u32 w, h, dxgi, src_id; u64 gen, frame; D3D12_RESOURCE_STATES st; u64 wd; } RtWin;\n'
    'static RtWin s_rtwin[MAX_OFF_RTS];\n'
    'static RtWin s_fbwin[MAX_OFF_RTS];   /* RSX_RT_FEEDBACK: whole-target copies (no RSX_RT_WINDOW window) */\n'
    'static u64 s_fb_wd[MAX_OFF_RTS];     /* draws replayed into each target (RSX_RT_FEEDBACK) */\n'
    'static struct { u64 reads, copies, skipped, bytes, ms_left; } s_fbc;\n')
rep('v->src_id = 0; v->gen = 0;', 'v->src_id = 0; v->gen = 0; v->wd = ~0ull;', 2)
rep('''/* Replay: bring target `slot`'s window up to date before a draw samples it. */''',
    '''/* RSX_RT_FEEDBACK=1: a draw that samples a colour target it writes (RT A or
 * an MRT) reads a copy of that target taken just before the draw: the RSX
 * texture unit sees memory as the draws before it left it, while D3D12 leaves
 * a resource read through an SRV while it is a bound render target undefined
 * (and RSX_RT_WINDOW's window was never refreshed for a bound target: black).
 * The copy is the target's RSX_RT_WINDOW window when the read has one, else a
 * whole-target copy; it is refreshed when a draw was replayed into the target
 * since, so draws that read and write the same target in a row each see the
 * one before. Record time: the copy resource for target slot, or NULL. */
static ID3D12Resource* fbwin_get(int slot)
{
    const OffRT* r = &s_d3d.off_rt[slot];
    return win_get(&s_fbwin[slot], r->dxgi, r->w, r->h, r->off, r->w, r->h, r->aa, r->gpitch);
}
/* Replay: refresh the copy (the window when `windowed`) from target slot;
 * `bound` = slot is one of the bound colour targets, returned to
 * RENDER_TARGET after the copy. No wait: copy and barriers only. */
static void fb_refresh(int slot, int windowed, int bound)
{
    OffRT* r = &s_d3d.off_rt[slot];
    RtWin* v = windowed ? &s_rtwin[slot] : &s_fbwin[slot];
    s_fbc.reads++;
    if (!v->res) return;
    if (v->src_id == r->res_id && v->gen == r->rgen && v->wd == s_fb_wd[slot]) { s_fbc.skipped++; return; }
    off_rt_transition(slot, D3D12_RESOURCE_STATE_COPY_SOURCE);
    win_copy(v, r->res);
    if (bound) off_rt_transition(slot, D3D12_RESOURCE_STATE_RENDER_TARGET);
    v->src_id = r->res_id; v->gen = r->rgen; v->wd = s_fb_wd[slot];
    s_fbc.copies++;
    s_fbc.bytes += (u64)v->w * v->h * 4u;
}
static void fb_frame_report(void)
{
    static u64 frames = 0, next = 1;
    if (!rt_feedback_on() || ++frames < next) return;
    next *= 2;
    fprintf(stderr, "[fb] frame %llu: feedback reads %llu copies %llu (%llu MiB) unchanged %llu msaa_left %llu%c",
            (unsigned long long)frames, (unsigned long long)s_fbc.reads, (unsigned long long)s_fbc.copies,
            (unsigned long long)(s_fbc.bytes >> 20), (unsigned long long)s_fbc.skipped,
            (unsigned long long)s_fbc.ms_left, 10);
}

/* Replay: bring target `slot`'s window up to date before a draw samples it. */''')
rep('    ms_frame_report();   /* RSX_MSAA */\n',
    '    ms_frame_report();   /* RSX_MSAA */\n    fb_frame_report();   /* RSX_RT_FEEDBACK */\n')
rep('        dr->tex_xms = 0;\n', '        dr->tex_xms = 0;\n        dr->tex_fb = 0;\n')
rep('''                    rsx_rt_window _win;
                    if (rtwin_on() && rsx_rt_window_of(dr->tex[_u].w, dr->tex[_u].h, dr->tex[_u].pitch,
                                                       _r->aa, _r->gpitch, _r->w, _r->h, &_win)) {
                        ID3D12Resource* _wr = rtwin_get(rt, _win.w, _win.h);
                        if (_wr) { _sr = _wr; dr->tex_win |= (u16)(1u << _u); }
                    }''',
    '''                    rsx_rt_window _win;
                    if (rtwin_on() && rsx_rt_window_of(dr->tex[_u].w, dr->tex[_u].h, dr->tex[_u].pitch,
                                                       _r->aa, _r->gpitch, _r->w, _r->h, &_win)) {
                        ID3D12Resource* _wr = rtwin_get(rt, _win.w, _win.h);
                        if (_wr) { _sr = _wr; dr->tex_win |= (u16)(1u << _u); }
                    }
                    /* RSX_RT_FEEDBACK: a fetched unit over a target this draw writes. */
                    if (rt_feedback_on() && ((dr->fp_units >> _u) & 1u) &&
                        ((dr->rt_off && off_rt_find(dr->rt_off) == rt) ||
                         (dr->rt_mrt[0] && off_rt_find(dr->rt_mrt[0]) == rt) ||
                         (dr->rt_mrt[1] && off_rt_find(dr->rt_mrt[1]) == rt) ||
                         (dr->rt_mrt[2] && off_rt_find(dr->rt_mrt[2]) == rt))) {
                        if (_r->ms) s_fbc.ms_left++;   /* a 2-sample twin: not this path */
                        else if ((dr->tex_win >> _u) & 1u) dr->tex_fb |= (u16)(1u << _u);
                        else {
                            ID3D12Resource* _fr = fbwin_get(rt);
                            if (_fr) { _sr = _fr; dr->tex_fb |= (u16)(1u << _u); }
                        }
                    }''')
rep('''                for (int _u = 0; _u < RSX_DSP_NUM_TEXTURES; _u++) {
                    int rt = dr->tex_rt[_u];
                    if (rt >= 0 && rt != cur_rt && !((dr->tex_xms >> _u) & 1u) &&''',
    '''                for (int _u = 0; _u < RSX_DSP_NUM_TEXTURES; _u++) {
                    int rt = dr->tex_rt[_u];
                    if (rt >= 0 && ((dr->tex_fb >> _u) & 1u)) {   /* RSX_RT_FEEDBACK */
                        fb_refresh(rt, (dr->tex_win >> _u) & 1u,
                                   rt == cur_rt || rt == cur_m[0] || rt == cur_m[1] || rt == cur_m[2]);
                        continue;
                    }
                    if (rt >= 0 && rt != cur_rt && !((dr->tex_xms >> _u) & 1u) &&''')
# the draw is replayed into its targets: later feedback reads need a new copy
rep('''                D3D12_GPU_DESCRIPTOR_HANDLE gh = gh_base;
                gh.ptr += (u64)(DRAW_SRV_BASE + d * RSX_DSP_NUM_TEXTURES) * s_d3d.srv_inc;''',
    '''                if (cur_rt >= 0) s_fb_wd[cur_rt]++;
                for (int _m = 0; _m < 3; _m++) if (cur_m[_m] >= 0) s_fb_wd[cur_m[_m]]++;
                D3D12_GPU_DESCRIPTOR_HANDLE gh = gh_base;
                gh.ptr += (u64)(DRAW_SRV_BASE + d * RSX_DSP_NUM_TEXTURES) * s_d3d.srv_inc;''')
open(p, 'w', newline='', encoding='utf-8').write(s.replace('\n', '\r\n'))

# T137's sample-layout depth conversion takes the same exact expression.
m = W + '/libs/video/rsx_msaa.h'
t = open(m, newline='', encoding='utf-8').read()
crlf = '\r\n' in t
t = t.replace('\r\n', '\n')
a = '''/* d is clamped to 0xFFFFFF: in float, 1.0 * 16777215 + 0.5 rounds to 2^24,
 * which the unclamped form (the backend's single-sample zconv_ps) writes as
 * 0xFF0000 for every pixel at the far plane. */
#define RSX_MSAA_ZCONV_BODY \\
    "    uint d = min((uint)(saturate(dv) * 16777215.0 + 0.5), 16777215u);\\n" \\'''
b = '''/* d is depth24 exactly (RSX_ZCOLOR_D24, rsx_blend_feedback.h): the old
 * (uint)(d * 16777215.0 + 0.5) rounds to 2^24 at the far plane (0xFF0000) and
 * to k + 1 for every odd k >= 2^23. */
#define RSX_MSAA_ZCONV_BODY \\
    "    uint d = " RSX_ZCOLOR_D24("dv") ";\\n" \\'''
assert t.count(a) == 1
t = t.replace(a, b)
a2 = '#define PS3RECOMP_RSX_MSAA_H\n'
assert t.count(a2) == 1
t = t.replace(a2, a2 + '\n#include "rsx_blend_feedback.h"   /* RSX_ZCOLOR_D24 */\n')
open(m, 'w', newline='', encoding='utf-8').write(t.replace('\n', '\r\n') if crlf else t)
print('ok')
