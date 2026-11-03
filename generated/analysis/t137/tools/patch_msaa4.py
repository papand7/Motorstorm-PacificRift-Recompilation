"""T137: expand straight into the guest's window (no copy); the full sample image only on demand (one-shot)."""
import sys
p = sys.argv[1] + '/libs/video/rsx_d3d12_backend.c'
s = open(p, newline='', encoding='utf-8').read().replace('\r\n', '\n')


def rep(a, b, cnt=1):
    global s
    n = s.count(a)
    assert n == cnt, (a[:100], n)
    s = s.replace(a, b)


rep('''    hd.Type = D3D12_DESCRIPTOR_HEAP_TYPE_RTV;
    hd.NumDescriptors = 2 * MAX_OFF_RTS;''', '''    hd.Type = D3D12_DESCRIPTOR_HEAP_TYPE_RTV;
    hd.NumDescriptors = 3 * MAX_OFF_RTS;   /* 2-sample twins, sample images, sample windows */''')
rep('''static D3D12_CPU_DESCRIPTOR_HANDLE xs_rtv(int slot) { return ms_heap_cpu(s_d3d.ms_rtv_heap, D3D12_DESCRIPTOR_HEAP_TYPE_RTV, MAX_OFF_RTS + (u32)slot); }''',
    '''static D3D12_CPU_DESCRIPTOR_HANDLE xs_rtv(int slot) { return ms_heap_cpu(s_d3d.ms_rtv_heap, D3D12_DESCRIPTOR_HEAP_TYPE_RTV, MAX_OFF_RTS + (u32)slot); }
static D3D12_CPU_DESCRIPTOR_HANDLE xw_rtv(int slot) { return ms_heap_cpu(s_d3d.ms_rtv_heap, D3D12_DESCRIPTOR_HEAP_TYPE_RTV, 2u * MAX_OFF_RTS + (u32)slot); }''')
# ms_alloc: the twin only; the full image is created by ms_xres_get
rep('''/* The twin and the sample image of target `slot` (resources and views only;
 * no commands, so the bind step can call it). A new twin is stale: res holds
 * the surface's contents until the first broadcast. */
static int ms_alloc(int slot)
{
    OffRT* r = &s_d3d.off_rt[slot];
    if (r->ms && r->xres) return 1;''', '''/* The twin of target `slot` (resource and views only; no commands, so the
 * bind step can call it). A new twin is stale: res holds the surface's
 * contents until the first broadcast. */
static int ms_alloc(int slot)
{
    OffRT* r = &s_d3d.off_rt[slot];
    if (r->ms) return 1;''')
rep('''    ms_srv(MSRT_SRV_BASE + (u32)slot, r->ms, (DXGI_FORMAT)r->dxgi);
    td.Width = 2u * r->w; td.SampleDesc.Count = 1; td.SampleDesc.Quality = 0;
    if (!r->xres && FAILED(s_d3d.device->lpVtbl->CreateCommittedResource(s_d3d.device, &hp, D3D12_HEAP_FLAG_NONE, &td,
            D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE, &cv, &IID_ID3D12Resource, (void**)&r->xres))) {
        r->xres = NULL; s_msc.failed++; return 0;
    }
    r->x_st = D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE;
    s_d3d.device->lpVtbl->CreateRenderTargetView(s_d3d.device, r->xres, NULL, xs_rtv(slot));
    r->ss_newer = 1; r->ms_newer = 0; r->ms_gen = ++s_ms_seq; r->x_gen = 0;
    s_msc.allocs++;
    { static int _n = 0; if (PS3_LOG_FIRST(_n, 8))
        fprintf(stderr, "[msaa] 0x%08X %ux%u: 2-sample twin, %ux%u sample image%c", r->off, r->w, r->h, 2u * r->w, r->h, 10); }
    return 1;
}''', '''    ms_srv(MSRT_SRV_BASE + (u32)slot, r->ms, (DXGI_FORMAT)r->dxgi);
    r->ss_newer = 1; r->ms_newer = 0; r->ms_gen = ++s_ms_seq; r->x_gen = 0;
    s_msc.allocs++;
    { static int _n = 0; if (PS3_LOG_FIRST(_n, 8))
        fprintf(stderr, "[msaa] 0x%08X %ux%u: 2-sample twin%c", r->off, r->w, r->h, 10); }
    return 1;
}

/* The whole 2W x H sample image of `slot` (a read of exactly that size). */
static ID3D12Resource* ms_xres_get(int slot)
{
    OffRT* r = &s_d3d.off_rt[slot];
    if (r->xres) return r->xres;
    D3D12_HEAP_PROPERTIES hp = {0}; hp.Type = D3D12_HEAP_TYPE_DEFAULT;
    D3D12_RESOURCE_DESC td = {0};
    td.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    td.Width = 2u * r->w; td.Height = r->h; td.DepthOrArraySize = 1; td.MipLevels = 1;
    td.Format = (DXGI_FORMAT)r->dxgi; td.SampleDesc.Count = 1;
    td.Flags = D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;
    D3D12_CLEAR_VALUE cv = {0}; cv.Format = td.Format;
    if (FAILED(s_d3d.device->lpVtbl->CreateCommittedResource(s_d3d.device, &hp, D3D12_HEAP_FLAG_NONE, &td,
            D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE, &cv, &IID_ID3D12Resource, (void**)&r->xres))) {
        r->xres = NULL; s_msc.failed++; return NULL;
    }
    r->x_st = D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE; r->x_gen = 0;
    s_d3d.device->lpVtbl->CreateRenderTargetView(s_d3d.device, r->xres, NULL, xs_rtv(slot));
    return r->xres;
}''')
# the window: render-target capable, expanded into directly
rep('''/* The window of `slot`'s sample image at w x h (record time). */
static ID3D12Resource* xwin_get(int slot, u32 w, u32 h)
{
    const OffRT* r = &s_d3d.off_rt[slot];
    return win_get(&s_xwin[slot], r->dxgi, w, h, r->off, 2u * r->w, r->h, r->aa, r->gpitch);
}''', '''/* The top-left w x h of `slot`'s sample image, as its own texture the expand
 * pass renders into directly (record time). A second size for the same
 * target in one frame gets NULL (the caller falls back, counted); a replaced
 * window is released after the frames in flight (rtwin_retire), no wait. */
static ID3D12Resource* xwin_get(int slot, u32 w, u32 h)
{
    const OffRT* r = &s_d3d.off_rt[slot];
    RtWin* v = &s_xwin[slot];
    if (v->res && v->w == w && v->h == h && v->dxgi == r->dxgi) { v->frame = s_d3d.frame_count; return v->res; }
    if (v->res) {
        if (v->frame == s_d3d.frame_count) return NULL;
        rtwin_retire(v);
    }
    D3D12_HEAP_PROPERTIES hp = {0}; hp.Type = D3D12_HEAP_TYPE_DEFAULT;
    D3D12_RESOURCE_DESC td = {0};
    td.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    td.Width = w; td.Height = h; td.DepthOrArraySize = 1; td.MipLevels = 1;
    td.Format = (DXGI_FORMAT)r->dxgi; td.SampleDesc.Count = 1;
    td.Flags = D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;
    D3D12_CLEAR_VALUE cv = {0}; cv.Format = td.Format;
    if (FAILED(s_d3d.device->lpVtbl->CreateCommittedResource(s_d3d.device, &hp, D3D12_HEAP_FLAG_NONE, &td,
            D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE, &cv, &IID_ID3D12Resource, (void**)&v->res))) {
        v->res = NULL; s_msc.failed++; return NULL;
    }
    v->w = w; v->h = h; v->dxgi = r->dxgi; v->src_id = 0; v->gen = 0; v->frame = s_d3d.frame_count;
    v->st = D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE;
    s_d3d.device->lpVtbl->CreateRenderTargetView(s_d3d.device, v->res, NULL, xw_rtv(slot));
    { static int _n = 0; if (PS3_LOG_FIRST(_n, 16))
        fprintf(stderr, "[msaa] 0x%08X: sample window %ux%u of %ux%u%c", r->off, w, h, 2u * r->w, r->h, 10); }
    return v->res;
}''')
rep('''/* Replay, before a draw samples `slot`: its sample image (and window) current. */
static void ms_expand_refresh(int slot, int bound)
{
    OffRT* r = &s_d3d.off_rt[slot];
    if (!r->ms || !r->xres) return;
    if (r->ss_newer && !ms_broadcast(slot)) return;
    if (r->x_gen != r->ms_gen || bound) {
        ID3D12PipelineState* p = ms_util_pso(MSU_EXPAND, (DXGI_FORMAT)r->dxgi);
        if (!p) return;
        res_transition(r->ms, &r->ms_st, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
        res_transition(r->xres, &r->x_st, D3D12_RESOURCE_STATE_RENDER_TARGET);
        ms_util_draw(p, MSRT_SRV_BASE + (u32)slot, xs_rtv(slot), 2u * r->w, r->h);
        res_transition(r->xres, &r->x_st, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
        r->x_gen = r->ms_gen;
        if (bound) {   /* back to the pass; the draws after this one change it again */
            res_transition(r->ms, &r->ms_st, D3D12_RESOURCE_STATE_RENDER_TARGET);
            r->ms_gen = ++s_ms_seq;
        }
        s_msc.expands++;
    }
    RtWin* v = &s_xwin[slot];
    if (v->res && v->gen != r->x_gen) {
        res_transition(r->xres, &r->x_st, D3D12_RESOURCE_STATE_COPY_SOURCE);
        win_copy(v, r->xres);
        res_transition(r->xres, &r->x_st, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
        v->gen = r->x_gen;
        s_msc.xwin_copies++;
    }
}''', '''/* Replay, before a draw samples `slot`: the image it binds (its window, or
 * the whole sample image) current. The expand pass writes only the texels
 * that image holds. */
static void ms_expand_refresh(int slot, int bound, int windowed)
{
    OffRT* r = &s_d3d.off_rt[slot];
    RtWin* v = &s_xwin[slot];
    ID3D12Resource* dst = windowed ? v->res : r->xres;
    D3D12_RESOURCE_STATES* dst_st = windowed ? &v->st : &r->x_st;
    u64* dst_gen = windowed ? &v->gen : &r->x_gen;
    if (!r->ms || !dst) return;
    if (r->ss_newer && !ms_broadcast(slot)) return;
    if (*dst_gen == r->ms_gen && !bound) return;
    ID3D12PipelineState* p = ms_util_pso(MSU_EXPAND, (DXGI_FORMAT)r->dxgi);
    if (!p) return;
    res_transition(r->ms, &r->ms_st, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
    res_transition(dst, dst_st, D3D12_RESOURCE_STATE_RENDER_TARGET);
    ms_util_draw(p, MSRT_SRV_BASE + (u32)slot, windowed ? xw_rtv(slot) : xs_rtv(slot),
                 windowed ? v->w : 2u * r->w, windowed ? v->h : r->h);
    res_transition(dst, dst_st, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
    *dst_gen = r->ms_gen;
    if (bound) {   /* back to the pass; the draws after this one change it again */
        res_transition(r->ms, &r->ms_st, D3D12_RESOURCE_STATE_RENDER_TARGET);
        r->ms_gen = ++s_ms_seq;
    }
    s_msc.expands += windowed ? 0u : 1u;
    s_msc.xwin_copies += windowed ? 1u : 0u;   /* reported as window expands */
}''')
# bind step: window flag and lazy full image
rep('''                        ID3D12Resource* _xr = (_mr >= 0 && ms_alloc(rt)) ?
                            (_mr ? xwin_get(rt, _mw, _mh) : s_d3d.off_rt[rt].xres) : NULL;
                        if (_mr < 0) s_msc.read_other++;
                        if (_xr) {
                            dr->tex_xms |= (u16)(1u << _u);''', '''                        ID3D12Resource* _xr = (_mr >= 0 && ms_alloc(rt)) ?
                            (_mr ? xwin_get(rt, _mw, _mh) : ms_xres_get(rt)) : NULL;
                        if (!_xr) s_msc.read_other++;
                        if (_xr) {
                            dr->tex_xms |= (u16)(1u << _u);
                            if (_mr) dr->tex_win |= (u16)(1u << _u);   /* reads its window */''')
rep('''                        ms_expand_refresh(rt, s_pass_ms && (rt == cur_rt || rt == cur_m[0] ||
                                                            rt == cur_m[1] || rt == cur_m[2]));''',
    '''                        ms_expand_refresh(rt, s_pass_ms && (rt == cur_rt || rt == cur_m[0] ||
                                                            rt == cur_m[1] || rt == cur_m[2]),
                                          (int)((dr->tex_win >> _u) & 1u));''')
rep('''                    " window_copies %llu zeta_images %llu''', '''                    " window_expands %llu zeta_images %llu''')
open(p, 'w', newline='', encoding='utf-8').write(s.replace('\n', '\r\n'))
print('ok')
