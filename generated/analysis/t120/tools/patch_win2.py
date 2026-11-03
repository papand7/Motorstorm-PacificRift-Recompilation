"""T120: RSX_RT_WINDOW without a GPU wait per size change (MotorStorm's scene
size moves every frame), and the window for zeta-as-colour reads (one-shot)."""
import sys
p = sys.argv[1]
s = open(p, newline='').read().replace('\r\n', '\n')


def rep(a, b, cnt=1):
    global s
    n = s.count(a)
    assert n == cnt, (a[:90], n)
    s = s.replace(a, b)


rep('''    int                   conv_ok;     /* cres holds the current depth */
    u64                   wseq;        /* last op that wrote it (zeta_seq order) */
} ZetaSurf;''', '''    int                   conv_ok;     /* cres holds the current depth */
    u64                   wseq;        /* last op that wrote it (zeta_seq order) */
    u32                   aa;          /* SET_SURFACE_FORMAT antialias of the pass that bound it (RSX_RT_WINDOW) */
    u64                   cgen;        /* bumped on every rebuild of cres (RSX_RT_WINDOW) */
} ZetaSurf;''')
# cgen bump in zeta_convert
rep('''    res_transition(e->cres, &e->cst, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
    e->conv_ok = 1;
''', '''    res_transition(e->cres, &e->cst, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
    e->conv_ok = 1;
    e->cgen++;
''')
# record aa at zeta_get pre-pass
rep('''        zeta_get(dr->g_zeta_off, rt >= 0 ? s_d3d.off_rt[rt].w : s_d3d.width,
                 rt >= 0 ? s_d3d.off_rt[rt].h : s_d3d.height);
    }
''', '''        { const int _z = zeta_get(dr->g_zeta_off, rt >= 0 ? s_d3d.off_rt[rt].w : s_d3d.width,
                                  rt >= 0 ? s_d3d.off_rt[rt].h : s_d3d.height);
          if (_z >= 0 && rt >= 0) s_d3d.zeta[_z].aa = s_d3d.off_rt[rt].aa; }
    }
''')
# window machinery: deferred release + zeta windows
rep('''typedef struct { ID3D12Resource* res; u32 w, h, dxgi, src_id; u64 gen, frame; D3D12_RESOURCE_STATES st; } RtWin;
static RtWin s_rtwin[MAX_OFF_RTS];

/* Record time: the window texture of target `slot` at w x h, or NULL to bind
 * the whole target (a second size for the same target in one frame). */
static ID3D12Resource* rtwin_get(int slot, u32 w, u32 h)
{
    const OffRT* r = &s_d3d.off_rt[slot];
    RtWin* v = &s_rtwin[slot];
    if (v->res && v->w == w && v->h == h && v->dxgi == r->dxgi) { v->frame = s_d3d.frame_count; return v->res; }
    if (v->res) {
        if (v->frame == s_d3d.frame_count) return NULL;
        wait_for_gpu();   /* the frame in flight may still read it (see off_rt_get) */
        v->res->lpVtbl->Release(v->res); v->res = NULL;
    }
    D3D12_HEAP_PROPERTIES hp = {0}; hp.Type = D3D12_HEAP_TYPE_DEFAULT;
    D3D12_RESOURCE_DESC td = {0};
    td.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    td.Width = w; td.Height = h; td.DepthOrArraySize = 1; td.MipLevels = 1;
    td.Format = (DXGI_FORMAT)r->dxgi; td.SampleDesc.Count = 1;
    if (FAILED(s_d3d.device->lpVtbl->CreateCommittedResource(s_d3d.device, &hp, D3D12_HEAP_FLAG_NONE, &td,
            D3D12_RESOURCE_STATE_COPY_DEST, NULL, &IID_ID3D12Resource, (void**)&v->res))) { v->res = NULL; return NULL; }
    v->w = w; v->h = h; v->dxgi = r->dxgi; v->src_id = 0; v->gen = 0; v->frame = s_d3d.frame_count;
    v->st = D3D12_RESOURCE_STATE_COPY_DEST;
    { static int _n = 0; if (PS3_LOG_FIRST(_n, 16))
        fprintf(stderr, "[rtwin] 0x%08X host %ux%u aa=%u pitch=%u: sampled through a %ux%u window%c",
                r->off, r->w, r->h, r->aa, r->gpitch, w, h, 10); }
    return v->res;
}

/* Replay: bring target `slot`'s window up to date before a draw samples it. */
static void rtwin_refresh(int slot)
{
    OffRT* r = &s_d3d.off_rt[slot];
    RtWin* v = &s_rtwin[slot];
    if (!v->res || (v->src_id == r->res_id && v->gen == r->rgen)) return;
    ID3D12GraphicsCommandList* cl = s_d3d.cmd_list;
    off_rt_transition(slot, D3D12_RESOURCE_STATE_COPY_SOURCE);
    D3D12_RESOURCE_BARRIER b = {0};''', '''typedef struct { ID3D12Resource* res; u32 w, h, dxgi, src_id; u64 gen, frame; D3D12_RESOURCE_STATES st; } RtWin;
static RtWin s_rtwin[MAX_OFF_RTS];
static RtWin s_zwin[MAX_ZETA];   /* zeta-as-colour reads (cres) */

/* A replaced window may still be read by a frame in flight. MotorStorm's scene
 * size moves by a few pixels almost every frame (1259..1265 x 708..712), so a
 * wait here would stall the GPU once per frame: retired windows are released
 * once FRAME_COUNT + 1 frames have been presented (move_to_next_frame has then
 * waited for the frame that last used them). */
static struct { ID3D12Resource* res; u64 frame; } s_rtwin_grave[64];
static int s_rtwin_ngrave;
static void rtwin_retire(RtWin* v)
{
    if (s_rtwin_ngrave == (int)(sizeof s_rtwin_grave / sizeof s_rtwin_grave[0])) {
        wait_for_gpu();
        for (int i = 0; i < s_rtwin_ngrave; i++) s_rtwin_grave[i].res->lpVtbl->Release(s_rtwin_grave[i].res);
        s_rtwin_ngrave = 0;
    }
    s_rtwin_grave[s_rtwin_ngrave].res = v->res;
    s_rtwin_grave[s_rtwin_ngrave].frame = v->frame;
    s_rtwin_ngrave++;
    v->res = NULL;
}
static void rtwin_frame_begin(void)
{
    int k = 0;
    for (int i = 0; i < s_rtwin_ngrave; i++) {
        if (s_d3d.frame_count > s_rtwin_grave[i].frame + FRAME_COUNT + 1)
            s_rtwin_grave[i].res->lpVtbl->Release(s_rtwin_grave[i].res);
        else s_rtwin_grave[k++] = s_rtwin_grave[i];
    }
    s_rtwin_ngrave = k;
}

/* Record time: window v at w x h in format dxgi, or NULL to bind the whole
 * surface (a second size for the same surface in one frame). */
static ID3D12Resource* win_get(RtWin* v, u32 dxgi, u32 w, u32 h, u32 off, u32 hw, u32 hh, u32 aa, u32 pitch)
{
    if (v->res && v->w == w && v->h == h && v->dxgi == dxgi) { v->frame = s_d3d.frame_count; return v->res; }
    if (v->res) {
        if (v->frame == s_d3d.frame_count) return NULL;
        rtwin_retire(v);
    }
    D3D12_HEAP_PROPERTIES hp = {0}; hp.Type = D3D12_HEAP_TYPE_DEFAULT;
    D3D12_RESOURCE_DESC td = {0};
    td.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    td.Width = w; td.Height = h; td.DepthOrArraySize = 1; td.MipLevels = 1;
    td.Format = (DXGI_FORMAT)dxgi; td.SampleDesc.Count = 1;
    if (FAILED(s_d3d.device->lpVtbl->CreateCommittedResource(s_d3d.device, &hp, D3D12_HEAP_FLAG_NONE, &td,
            D3D12_RESOURCE_STATE_COPY_DEST, NULL, &IID_ID3D12Resource, (void**)&v->res))) { v->res = NULL; return NULL; }
    v->w = w; v->h = h; v->dxgi = dxgi; v->src_id = 0; v->gen = 0; v->frame = s_d3d.frame_count;
    v->st = D3D12_RESOURCE_STATE_COPY_DEST;
    { static int _n = 0; if (PS3_LOG_FIRST(_n, 16))
        fprintf(stderr, "[rtwin] 0x%08X host %ux%u aa=%u pitch=%u: sampled through a %ux%u window%c",
                off, hw, hh, aa, pitch, w, h, 10); }
    return v->res;
}
static ID3D12Resource* rtwin_get(int slot, u32 w, u32 h)
{
    const OffRT* r = &s_d3d.off_rt[slot];
    return win_get(&s_rtwin[slot], r->dxgi, w, h, r->off, r->w, r->h, r->aa, r->gpitch);
}
static ID3D12Resource* zwin_get(int z, u32 w, u32 h)
{
    const ZetaSurf* e = &s_d3d.zeta[z];
    return win_get(&s_zwin[z], (u32)DXGI_FORMAT_R8G8B8A8_UNORM, w, h, e->off, e->w, e->h, e->aa, 0);
}

/* Replay: copy the box (0,0)-(w,h) of src (in PIXEL_SHADER_RESOURCE or
 * COPY_SOURCE) into window v, left readable. */
static void win_copy(RtWin* v, ID3D12Resource* src_res)
{
    ID3D12GraphicsCommandList* cl = s_d3d.cmd_list;
    D3D12_RESOURCE_BARRIER b = {0};''')
rep('''    D3D12_TEXTURE_COPY_LOCATION dst = {0}, src = {0};
    dst.pResource = v->res; dst.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    src.pResource = r->res; src.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    const D3D12_BOX box = {0, 0, 0, v->w, v->h, 1};
    cl->lpVtbl->CopyTextureRegion(cl, &dst, 0, 0, 0, &src, &box);
    b.Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_DEST;
    b.Transition.StateAfter = D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE;
    cl->lpVtbl->ResourceBarrier(cl, 1, &b);
    v->st = D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE;
    v->src_id = r->res_id; v->gen = r->rgen;
}
''', '''    D3D12_TEXTURE_COPY_LOCATION dst = {0}, src = {0};
    dst.pResource = v->res; dst.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    src.pResource = src_res; src.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    const D3D12_BOX box = {0, 0, 0, v->w, v->h, 1};
    cl->lpVtbl->CopyTextureRegion(cl, &dst, 0, 0, 0, &src, &box);
    b.Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_DEST;
    b.Transition.StateAfter = D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE;
    cl->lpVtbl->ResourceBarrier(cl, 1, &b);
    v->st = D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE;
}

/* Replay: bring target `slot`'s window up to date before a draw samples it. */
static void rtwin_refresh(int slot)
{
    OffRT* r = &s_d3d.off_rt[slot];
    RtWin* v = &s_rtwin[slot];
    if (!v->res || (v->src_id == r->res_id && v->gen == r->rgen)) return;
    off_rt_transition(slot, D3D12_RESOURCE_STATE_COPY_SOURCE);
    win_copy(v, r->res);
    v->src_id = r->res_id; v->gen = r->rgen;
}
''')
open(p, 'w', newline='').write(s.replace('\n', '\r\n'))
print('ok')
