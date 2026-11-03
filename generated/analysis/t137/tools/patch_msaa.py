"""T137: RSX_MSAA=1 in the D3D12 backend (one-shot; anchored replacements)."""
import sys
p = sys.argv[1] + '/libs/video/rsx_d3d12_backend.c'
s = open(p, newline='', encoding='utf-8').read().replace('\r\n', '\n')


def rep(a, b, cnt=1):
    global s
    n = s.count(a)
    assert n == cnt, (a[:100], n)
    s = s.replace(a, b)


# ---- includes, records, structs ------------------------------------------------
rep('#include "rsx_sampler_xlate.h"', '#include "rsx_sampler_xlate.h"\n#include "rsx_msaa.h"          /* RSX_MSAA: 2-sample antialias-3 surfaces */')
rep('    u16 tex_win;        /* units whose tex_rt is read through its window (RSX_RT_WINDOW) */\n',
    '    u16 tex_win;        /* units whose tex_rt is read through its window (RSX_RT_WINDOW) */\n'
    '    u16 tex_xms;        /* units reading an RSX_MSAA surface\'s sample-expanded image */\n')
rep('''    u64                   rgen;        /* replay writes: bumped on every entry into RENDER_TARGET / COPY_DEST */
} OffRT;''', '''    u64                   rgen;        /* replay writes: bumped on every entry into RENDER_TARGET / COPY_DEST */
    /* RSX_MSAA (rsx_msaa.h): the 2-sample twin antialias-3 passes render to,
     * and its sample-expanded 2W x H image, bound where the guest samples the
     * surface. res stays the copy every single-sample consumer reads.
     * ms_newer: ms holds writes res lacks (resolved on res's next transition);
     * ss_newer: res holds writes ms lacks (broadcast into ms before its use). */
    ID3D12Resource*       ms;
    ID3D12Resource*       xres;
    D3D12_RESOURCE_STATES ms_st, x_st;
    int                   ms_newer, ss_newer;
    u64                   ms_gen, x_gen;   /* x_gen == ms_gen: xres is current */
} OffRT;''')
rep('''    u64                   cgen;        /* bumped on every rebuild of cres (RSX_RT_WINDOW) */
} ZetaSurf;''', '''    u64                   cgen;        /* bumped on every rebuild of cres (RSX_RT_WINDOW) */
    u32                   cw;          /* cres width: w, or 2w for an RSX_MSAA sample image */
    ID3D12Resource*       ms;          /* RSX_MSAA: 2-sample twin, the depth target of antialias-3 passes */
    D3D12_RESOURCE_STATES ms_st;
    int                   ms_newer;    /* ms holds writes res lacks */
    int                   ss_bound;    /* res was bound by a single-sample pass */
} ZetaSurf;''')
rep('#define DRAW_SRV_BASE (ZCOL_SRV_BASE + MAX_ZETA)\n',
    '#define MSRT_SRV_BASE (ZCOL_SRV_BASE + MAX_ZETA)          /* RSX_MSAA: 2-sample SRV per RT slot (+1 spare) */\n'
    '#define MSZ_SRV_BASE  (MSRT_SRV_BASE + MAX_OFF_RTS + 1)  /* RSX_MSAA: 2-sample depth, stencil per zeta slot */\n'
    '#define DRAW_SRV_BASE (MSZ_SRV_BASE + 2 * MAX_ZETA + 1)\n')
rep('    ID3D12DescriptorHeap* rt_rtv_heap;          /* MAX_OFF_RTS RTVs (CPU only)   */\n',
    '    ID3D12DescriptorHeap* rt_rtv_heap;          /* MAX_OFF_RTS RTVs (CPU only)   */\n'
    '    ID3D12DescriptorHeap* ms_rtv_heap;          /* RSX_MSAA: 2-sample RTVs, then sample-image RTVs */\n'
    '    ID3D12DescriptorHeap* ms_dsv_heap;          /* RSX_MSAA: zeta 2-sample DSVs, then the shared one */\n'
    '    ID3D12Resource*       ms_shared_z;          /* RSX_MSAA: 2-sample shared depth buffer */\n'
    '    D3D12_RESOURCE_STATES ms_shared_st;\n'
    '    u32                   ms_shared_w, ms_shared_h;\n')
rep('static D3D12State s_d3d;\n', '''static D3D12State s_d3d;

/* RSX_MSAA=1 (rsx_msaa.h); the functions follow the zeta pool. */
static int  s_msaa = -1;          /* read once; ms_init turns it off if the device cannot */
static UINT s_ms_quality = 0;     /* D3D12_STANDARD_MULTISAMPLE_PATTERN when on */
static int  s_pass_ms = 0;        /* the replay's current targets are 2-sample twins */
static int  s_ms_pass_ok = 1;     /* every twin of the current pass exists */
static int  s_ms_restore = 0;     /* a utility pass replaced the replay's pipeline state */
static u64  s_ms_seq = 0;         /* unique content generations */
static struct { u64 binds, allocs, broadcasts, resolves, expands, xwin_copies, zexpands, zbinds, skipped,
                zeta_ss_after_ms, zeta_ms_from_ss, zdepth_ms, read_other, failed; } s_msc;
static int  msaa_on(void);
static int  ms_fmt_ok(DXGI_FORMAT f);
static void ms_init(void);
static void ms_resolve(int slot);
static void ms_release(int slot);
static D3D12_CPU_DESCRIPTOR_HANDLE ms_rtv(int slot);
static DXGI_FORMAT rsx_surface_dxgi(u32 fmt);
''')
# ---- heaps at device init ----------------------------------------------------------
rep('''            if (FAILED(hr)) printf("[D3D12] zeta RTV heap creation failed (0x%08lX)\\n", hr);
        }
    }
''', '''            if (FAILED(hr)) printf("[D3D12] zeta RTV heap creation failed (0x%08lX)\\n", hr);
        }
        ms_init();   /* RSX_MSAA */
    }
''')
# ---- pipeline key and pipeline --------------------------------------------------------
rep('''static u64 dr_depth_key(const D3D12DrawRecord* dr)
{
    if (ds_state_on()) return dr->g_ds_key;
    return (dr->g_depth >> 16) & 1u;
}''', '''/* RSX_MSAA: this draw's targets are antialias 3 in a format with 2-sample
 * support, so it renders to the 2-sample twins. */
static int dr_ms(const D3D12DrawRecord* dr)
{
    return msaa_on() && dr->rt_off && ((dr->rt_fmt >> 12) & 0xFu) == 3u &&
           ms_fmt_ok(rsx_surface_dxgi(dr->rt_fmt)) && ms_fmt_ok(DXGI_FORMAT_D24_UNORM_S8_UINT);
}

static u64 dr_depth_key(const D3D12DrawRecord* dr)
{
    /* RSX_MSAA: sample count and coverage state in the key's top byte. */
    const u64 ms = dr_ms(dr) ? rsx_msaa_key(2, dr->g_aa_ctl, (int)dr->g_aa_set) : 0;
    if (ds_state_on()) return dr->g_ds_key | ms;
    return ((dr->g_depth >> 16) & 1u) | ms;
}''')
rep('''    pd.SampleDesc.Count = 1;

    /* Bounded diagnostic for one guest FP.''', '''    pd.SampleDesc.Count = 1;
    /* RSX_MSAA: 2 samples, the guest's sample mask and alpha to coverage. */
    { rsx_msaa_pso _mp; rsx_msaa_pso_of(depth, &_mp);
      if (_mp.samples > 1) {
          pd.SampleDesc.Count = _mp.samples; pd.SampleDesc.Quality = s_ms_quality;
          pd.BlendState.AlphaToCoverageEnable = _mp.alpha_to_coverage ? TRUE : FALSE;
          pd.SampleMask = _mp.sample_mask;
      } }

    /* Bounded diagnostic for one guest FP.''')
# ---- off-screen targets -------------------------------------------------------------------
rep('''static D3D12_CPU_DESCRIPTOR_HANDLE off_rt_rtv(int slot)
{
''', '''static D3D12_CPU_DESCRIPTOR_HANDLE off_rt_rtv(int slot)
{
    if (s_pass_ms && s_d3d.off_rt[slot].ms) return ms_rtv(slot);   /* RSX_MSAA */
''')
rep('''static void off_rt_transition(int slot, D3D12_RESOURCE_STATES to)
{
    OffRT* r = &s_d3d.off_rt[slot];
''', '''static void off_rt_transition(int slot, D3D12_RESOURCE_STATES to)
{
    OffRT* r = &s_d3d.off_rt[slot];
    /* RSX_MSAA: res catches up with the 2-sample twin before any use, and a
     * write to res makes the twin stale. */
    if (r->ms && r->ms_newer) ms_resolve(slot);
    if (r->ms && (to == D3D12_RESOURCE_STATE_RENDER_TARGET || to == D3D12_RESOURCE_STATE_COPY_DEST)) r->ss_newer = 1;
''')
rep('        r->res->lpVtbl->Release(r->res); r->res = NULL;   /* dims/format changed */\n',
    '        r->res->lpVtbl->Release(r->res); r->res = NULL;   /* dims/format changed */\n'
    '        ms_release(slot);   /* RSX_MSAA: after the same wait */\n')
rep('            s_d3d.off_rt[slot].res = NULL;\n',
    '            s_d3d.off_rt[slot].res = NULL;\n'
    '            ms_release(slot);   /* RSX_MSAA */\n')
# ---- zeta pool ----------------------------------------------------------------------------
rep('''static void zeta_transition(int z, D3D12_RESOURCE_STATES to)
{
    res_transition(s_d3d.zeta[z].res, &s_d3d.zeta[z].st, to);
}''', '''static void zeta_transition(int z, D3D12_RESOURCE_STATES to)
{
    ZetaSurf* e = &s_d3d.zeta[z];
    if (e->ms && e->ms_newer) { res_transition(e->ms, &e->ms_st, to); return; }   /* RSX_MSAA */
    res_transition(s_d3d.zeta[z].res, &s_d3d.zeta[z].st, to);
}''')
rep('''    e->res = e->cres = NULL;
    e->conv_ok = 0;
}''', '''    if (e->ms) {   /* RSX_MSAA */
        if (s_d3d.zeta_ngrave < (int)(sizeof s_d3d.zeta_grave / sizeof s_d3d.zeta_grave[0]))
            s_d3d.zeta_grave[s_d3d.zeta_ngrave++] = e->ms;
        else { wait_for_gpu(); e->ms->lpVtbl->Release(e->ms); }
        e->ms = NULL;
    }
    e->ms_newer = 0; e->ss_bound = 0;
    e->res = e->cres = NULL; e->cw = 0;
    e->conv_ok = 0;
}''')
rep('''/* The zeta surface's A8R8G8B8 image resource (created on first use). */
static int zeta_color_get(int z)
{
    ZetaSurf* e = &s_d3d.zeta[z];
    if (e->cres) return 1;
    if (!s_d3d.zeta_rtv_heap) return 0;''', '''/* RSX_MSAA: zeta z, bound by antialias-3 passes, is read as its samples. */
static int zeta_ms_read(int z)
{
    return msaa_on() && s_d3d.zeta[z].aa == 3u && ms_fmt_ok(DXGI_FORMAT_D24_UNORM_S8_UINT);
}

/* The zeta surface's A8R8G8B8 image resource (created on first use): w wide,
 * or 2w for an RSX_MSAA sample image. */
static int zeta_color_get(int z)
{
    ZetaSurf* e = &s_d3d.zeta[z];
    const u32 cw = zeta_ms_read(z) ? 2u * e->w : e->w;
    if (e->cres && e->cw == cw) return 1;
    if (e->cres) {   /* RSX_MSAA switched the image's width */
        res_transition(e->cres, &e->cst, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
        if (s_d3d.zeta_ngrave < (int)(sizeof s_d3d.zeta_grave / sizeof s_d3d.zeta_grave[0]))
            s_d3d.zeta_grave[s_d3d.zeta_ngrave++] = e->cres;
        else { wait_for_gpu(); e->cres->lpVtbl->Release(e->cres); }
        e->cres = NULL; e->conv_ok = 0;
    }
    if (!s_d3d.zeta_rtv_heap) return 0;''')
rep('''    td.Width = e->w; td.Height = e->h; td.DepthOrArraySize = 1; td.MipLevels = 1;
    td.Format = DXGI_FORMAT_R8G8B8A8_UNORM; td.SampleDesc.Count = 1;''',
    '''    td.Width = cw; td.Height = e->h; td.DepthOrArraySize = 1; td.MipLevels = 1;
    td.Format = DXGI_FORMAT_R8G8B8A8_UNORM; td.SampleDesc.Count = 1;''')
rep('''    e->cst = D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE;
    e->conv_ok = 0;
    s_d3d.device->lpVtbl->CreateRenderTargetView(s_d3d.device, e->cres, NULL, zeta_crtv(z));''',
    '''    e->cst = D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE;
    e->conv_ok = 0; e->cw = cw;
    s_d3d.device->lpVtbl->CreateRenderTargetView(s_d3d.device, e->cres, NULL, zeta_crtv(z));''')
rep('''        "    uint d = (uint)(saturate(zd.Load(c)) * 16777215.0 + 0.5);\\n"
        "    uint s = zs.Load(c).g;\\n"
        "    /* the target holds R,G,B,A: R=[15:8] G=[7:0] B=stencil A=[23:16] */\\n"
        "    return float4((d >> 8) & 255u, d & 255u, s & 255u, d >> 16) / 255.0;\\n}\\n";
    ID3DBlob *vb = NULL, *pb = NULL, *err = NULL;
    if (FAILED(D3DCompile(vs, sizeof vs - 1, "zconv_vs", NULL, NULL, "main", "vs_5_0", 0, 0, &vb, &err)) ||
        FAILED(D3DCompile(ps, sizeof ps - 1, "zconv_ps", NULL, NULL, "main", "ps_5_0", 0, 0, &pb, &err))) {''',
    '''        "    uint d = (uint)(saturate(zd.Load(c)) * 16777215.0 + 0.5);\\n"
        "    uint s = zs.Load(c).g;\\n"
        "    /* the target holds R,G,B,A: R=[15:8] G=[7:0] B=stencil A=[23:16] */\\n"
        "    return float4((d >> 8) & 255u, d & 255u, s & 255u, d >> 16) / 255.0;\\n}\\n";
    /* RSX_MSAA=1 also clamps d to 0xFFFFFF: in float, 1.0 * 16777215 + 0.5
     * rounds to 2^24, so every far-plane pixel above reads 0xFF0000. */
    static const char ps_clamped[] =
        "Texture2D<float> zd : register(t0);\\n"
        "Texture2D<uint2> zs : register(t1);\\n"
        "float4 main(float4 p : SV_Position) : SV_Target {\\n"
        "    int3 c = int3(p.xy, 0);\\n"
        "    uint d = min((uint)(saturate(zd.Load(c)) * 16777215.0 + 0.5), 16777215u);\\n"
        "    uint s = zs.Load(c).g;\\n"
        "    return float4((d >> 8) & 255u, d & 255u, s & 255u, d >> 16) / 255.0;\\n}\\n";
    const char* psrc = msaa_on() ? ps_clamped : ps;
    ID3DBlob *vb = NULL, *pb = NULL, *err = NULL;
    if (FAILED(D3DCompile(vs, sizeof vs - 1, "zconv_vs", NULL, NULL, "main", "vs_5_0", 0, 0, &vb, &err)) ||
        FAILED(D3DCompile(psrc, strlen(psrc), "zconv_ps", NULL, NULL, "main", "ps_5_0", 0, 0, &pb, &err))) {''')
MSBLOCK = open(sys.argv[2], encoding='utf-8').read().replace('\r\n', '\n')
rep('''/* Rebuild zeta z's A8R8G8B8 image from its current depth/stencil. Leaves the
 * conversion pipeline, root signature and target bound: the caller restores
 * its own state. */
static int zeta_convert(int z)
{
    ZetaSurf* e = &s_d3d.zeta[z];
    if (!zeta_color_get(z) || !zconv_ready()) return 0;''', MSBLOCK + '''
/* Rebuild zeta z's A8R8G8B8 image from its current depth/stencil. Leaves the
 * conversion pipeline, root signature and target bound: the caller restores
 * its own state. */
static int zeta_convert(int z)
{
    ZetaSurf* e = &s_d3d.zeta[z];
    if (zeta_ms_read(z)) return zeta_convert_ms(z);   /* RSX_MSAA: the sample image */
    if (!zeta_color_get(z) || !zconv_ready()) return 0;''')
# ---- frame begin --------------------------------------------------------------------------
rep('    rtwin_frame_begin();\n', '    rtwin_frame_begin();\n    ms_frame_report();   /* RSX_MSAA */\n')
# ---- bind step --------------------------------------------------------------------------
rep('        dr->tex_win = 0;\n', '        dr->tex_win = 0;\n        dr->tex_xms = 0;\n')
rep('''                if (z >= 0 && VP_TEX_IS_DEPTH(bf)) {
                    dr->tex_zeta[_u] = (s8)z;''', '''                if (z >= 0 && VP_TEX_IS_DEPTH(bf)) {
                    if (s_d3d.zeta[z].ms) s_msc.zdepth_ms++;   /* RSX_MSAA: reads the single-sample copy */
                    dr->tex_zeta[_u] = (s8)z;''')
rep('''                        ID3D12Resource* _zr = s_d3d.zeta[z].cres;
                        rsx_rt_window _win;
                        if (rtwin_on() && rsx_rt_window_of(''', '''                        ID3D12Resource* _zr = s_d3d.zeta[z].cres;
                        rsx_rt_window _win;
                        u32 _mw, _mh;
                        if (zeta_ms_read(z)) {   /* RSX_MSAA: cres is the sample image */
                            const int _mr = rsx_msaa_read_window(dr->tex[_u].w, dr->tex[_u].h, 3u, s_d3d.zeta[z].w,
                                                                 s_d3d.zeta[z].h, &_mw, &_mh);
                            if (_mr < 0) s_msc.read_other++;
                            if (_mr == 1) {
                                ID3D12Resource* _wr = zwin_get(z, _mw, _mh);
                                if (_wr) { _zr = _wr; dr->tex_win |= (u16)(1u << _u); }
                            }
                        } else if (rtwin_on() && rsx_rt_window_of(''')
rep('''                    const OffRT* _r = &s_d3d.off_rt[rt];
                    ID3D12Resource* _sr = _r->res;
''', '''                    const OffRT* _r = &s_d3d.off_rt[rt];
                    ID3D12Resource* _sr = _r->res;
                    /* RSX_MSAA: an antialias-3 surface is read as its samples. */
                    if (rt_ms_read(rt)) {
                        u32 _mw, _mh;
                        const int _mr = rsx_msaa_read_window(dr->tex[_u].w, dr->tex[_u].h, 3u, _r->w, _r->h, &_mw, &_mh);
                        ID3D12Resource* _xr = (_mr >= 0 && ms_alloc(rt)) ?
                            (_mr ? xwin_get(rt, _mw, _mh) : s_d3d.off_rt[rt].xres) : NULL;
                        if (_mr < 0) s_msc.read_other++;
                        if (_xr) {
                            dr->tex_xms |= (u16)(1u << _u);
                            srv_write(wslot, _xr, (DXGI_FORMAT)s_d3d.off_rt[rt].dxgi,
                                      D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING);
                            continue;
                        }
                    }
''')
# ---- replay ---------------------------------------------------------------------------------
rep('''            D3D12_CPU_DESCRIPTOR_HANDLE cur_rh[4];
            UINT cur_nrt = 1;
            cur_rh[0] = rtv_handle;
''', '''            D3D12_CPU_DESCRIPTOR_HANDLE cur_rh[4];
            UINT cur_nrt = 1;
            cur_rh[0] = rtv_handle;
            ms_pass_end();   /* RSX_MSAA: the replay starts on the backbuffer */
''')
rep('''                if (want != cur_rt || wantm[0] != cur_m[0] ||
                    wantm[1] != cur_m[1] || wantm[2] != cur_m[2] || want_z != cur_z) {
                    if (s_rsxi.active) rsxi_on_retarget(d, dr, cur_rt, cur_m, want, wantm);
                    D3D12_CPU_DESCRIPTOR_HANDLE rh[4];
                    UINT nrt = 1;
                    rh[0] = rtv_handle;
                    D3D12_VIEWPORT vp = {0, 0, (float)s_d3d.width, (float)s_d3d.height, 0.0f, 1.0f};
                    if (want >= 0) {
                        off_rt_transition(want, D3D12_RESOURCE_STATE_RENDER_TARGET);
                        rh[0] = off_rt_rtv(want);''', '''                const int pass_ms = want >= 0 && dr_ms(dr);   /* RSX_MSAA: 2-sample twins */
                if (want != cur_rt || wantm[0] != cur_m[0] ||
                    wantm[1] != cur_m[1] || wantm[2] != cur_m[2] || want_z != cur_z || pass_ms != s_pass_ms) {
                    if (s_rsxi.active) rsxi_on_retarget(d, dr, cur_rt, cur_m, want, wantm);
                    ms_pass_end();
                    s_pass_ms = pass_ms; s_ms_pass_ok = 1;
                    D3D12_CPU_DESCRIPTOR_HANDLE rh[4];
                    UINT nrt = 1;
                    rh[0] = rtv_handle;
                    D3D12_VIEWPORT vp = {0, 0, (float)s_d3d.width, (float)s_d3d.height, 0.0f, 1.0f};
                    if (want >= 0) {
                        if (pass_ms) s_ms_pass_ok &= ms_bind_rt(want);
                        else off_rt_transition(want, D3D12_RESOURCE_STATE_RENDER_TARGET);
                        rh[0] = off_rt_rtv(want);''')
rep('''                    for (int _m = 0; _m < 3 && wantm[_m] >= 0; _m++) {
                        off_rt_transition(wantm[_m], D3D12_RESOURCE_STATE_RENDER_TARGET);
                        rh[nrt++] = off_rt_rtv(wantm[_m]);
                    }''', '''                    for (int _m = 0; _m < 3 && wantm[_m] >= 0; _m++) {
                        if (pass_ms) s_ms_pass_ok &= ms_bind_rt(wantm[_m]);
                        else off_rt_transition(wantm[_m], D3D12_RESOURCE_STATE_RENDER_TARGET);
                        rh[nrt++] = off_rt_rtv(wantm[_m]);
                    }''')
rep('''                    if (want_z >= 0) {
                        zeta_transition(want_z, D3D12_RESOURCE_STATE_DEPTH_WRITE);
                        s_d3d.zeta[want_z].conv_ok = 0;
                        cur_dsv = zeta_dsv(want_z);
                    } else
                        cur_dsv = dsv_handle;
                    s_d3d.cmd_list->lpVtbl->OMSetRenderTargets(s_d3d.cmd_list, nrt, rh, FALSE, &cur_dsv);
                    s_d3d.cmd_list->lpVtbl->RSSetViewports(s_d3d.cmd_list, 1, &vp);
                    s_d3d.cmd_list->lpVtbl->RSSetScissorRects(s_d3d.cmd_list, 1, &sc);
                    if (want_z < 0)
                        s_d3d.cmd_list->lpVtbl->ClearDepthStencilView(s_d3d.cmd_list, dsv_handle,''',
    '''                    if (want_z >= 0) {
                        if (pass_ms) s_ms_pass_ok &= zeta_ms_bind(want_z);   /* RSX_MSAA */
                        else zeta_ss_bind_note(want_z);
                        zeta_transition(want_z, D3D12_RESOURCE_STATE_DEPTH_WRITE);
                        s_d3d.zeta[want_z].conv_ok = 0;
                        cur_dsv = (pass_ms && s_d3d.zeta[want_z].ms) ? ms_dsv(want_z) : zeta_dsv(want_z);
                    } else
                        cur_dsv = pass_ms ? ms_shared_dsv((u32)vp.Width, (u32)vp.Height) : dsv_handle;
                    s_d3d.cmd_list->lpVtbl->OMSetRenderTargets(s_d3d.cmd_list, nrt, rh, FALSE, &cur_dsv);
                    s_d3d.cmd_list->lpVtbl->RSSetViewports(s_d3d.cmd_list, 1, &vp);
                    s_d3d.cmd_list->lpVtbl->RSSetScissorRects(s_d3d.cmd_list, 1, &sc);
                    if (want_z < 0)
                        s_d3d.cmd_list->lpVtbl->ClearDepthStencilView(s_d3d.cmd_list, cur_dsv,''')
rep('''                    if (conv) {
                        ID3D12GraphicsCommandList* cl = s_d3d.cmd_list;
                        cl->lpVtbl->SetGraphicsRootSignature(cl, s_d3d.vp_root_sig);''', '''                    /* RSX_MSAA: sample-expanded reads follow their surface; a
                     * target bound now is expanded as of the draws so far. */
                    for (int _u = 0; dr->tex_xms && _u < RSX_DSP_NUM_TEXTURES; _u++) {
                        const int rt = dr->tex_rt[_u];
                        if (rt < 0 || !((dr->tex_xms >> _u) & 1u) || !((dr->fp_units >> _u) & 1u)) continue;
                        ms_expand_refresh(rt, s_pass_ms && (rt == cur_rt || rt == cur_m[0] ||
                                                            rt == cur_m[1] || rt == cur_m[2]));
                    }
                    if (s_ms_restore) { conv = 1; s_ms_restore = 0; }
                    if (conv) {
                        ID3D12GraphicsCommandList* cl = s_d3d.cmd_list;
                        cl->lpVtbl->SetGraphicsRootSignature(cl, s_d3d.vp_root_sig);''')
rep('''                s_d3d.cmd_list->lpVtbl->SetPipelineState(s_d3d.cmd_list,
                                                         dpso ? dpso : vpso);''', '''                /* RSX_MSAA: a 2-sample pass has no 1-sample fallback pipeline. */
                if (s_pass_ms && (!dpso || !s_ms_pass_ok)) { s_msc.skipped++; continue; }
                s_d3d.cmd_list->lpVtbl->SetPipelineState(s_d3d.cmd_list,
                                                         dpso ? dpso : vpso);''')
rep('''                    if (rt >= 0 && rt != cur_rt &&
                        rt != cur_m[0] && rt != cur_m[1] && rt != cur_m[2]) {''', '''                    if (rt >= 0 && rt != cur_rt && !((dr->tex_xms >> _u) & 1u) &&
                        rt != cur_m[0] && rt != cur_m[1] && rt != cur_m[2]) {''')
rep('''            if (perf_on()) s_perf_gpu += perf_now() - _rec0;   /* reuse: record time */''',
    '''            ms_pass_end();   /* RSX_MSAA */
            if (perf_on()) s_perf_gpu += perf_now() - _rec0;   /* reuse: record time */''')
open(p, 'w', newline='', encoding='utf-8').write(s.replace('\n', '\r\n'))
print('ok')
