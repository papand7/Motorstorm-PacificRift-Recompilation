"""T143: add RSX_GPU_PROF timestamps/stage times and RSX_BIND_DEDUP call sites to the backend (one-shot edit)."""
import sys
p = sys.argv[1]
b = open(p, 'rb').read()
s = b.decode('utf-8').replace('\r\n', '\n')


def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (old[:90], s.count(old))
    s = s.replace(old, new)


rep('        s_fpm[_d].ok = 0;\n',
    '        s_fpm[_d].ok = 0;\n        s_srvw_of[_d] = _d;   /* RSX_SRV_REUSE: its own window unless srvw_finish shares one */\n')
rep('''static int perf_on(void)
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

/* RSX_GPU_PROF=<frames per report>[,<max reports>] (rsx_gpu_prof.h): one
 * gp_frame per render_frame. CPU stages from QPC on the render thread; GPU
 * stages from four timestamps in the frame's main command list (begin, replay
 * loop start, replay loop end, end), resolved into a readback buffer and read
 * at the next render_frame, after its GPU drain. Counts come from the method
 * wrappers above (calls from any thread, unsynchronised: approximate). */
enum { GP_Q_BEGIN, GP_Q_LOOP0, GP_Q_LOOP1, GP_Q_END, GP_Q_N };
static ID3D12QueryHeap* s_gp_qh = NULL;
static ID3D12Resource* s_gp_rb = NULL;
static u64 s_gp_freq = 0, s_gp_last_end = 0;
static u32 s_gp_mask = 0;      /* timestamps written into this frame's list */
static int s_gp_pending = 0;   /* a resolved set waits to be read */
static double s_gp_srv = 0.0;  /* the pre-pass's SRV window fill, this frame */
static double gp_now_ms(void)
{
    static LARGE_INTEGER f; LARGE_INTEGER c;
    if (!f.QuadPart) QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&c);
    return (double)c.QuadPart * 1000.0 / (double)f.QuadPart;
}
static void gp_setup(void)
{
    static int done = 0;
    if (done) return;
    done = 1;
    int frames = 0; unsigned maxr = 0;
    if (!gp_parse(getenv("RSX_GPU_PROF"), &frames, &maxr) || !gp_init(&s_gp, frames, maxr)) return;
    D3D12_QUERY_HEAP_DESC qd = {0};
    qd.Type = D3D12_QUERY_HEAP_TYPE_TIMESTAMP; qd.Count = GP_Q_N;
    D3D12_HEAP_PROPERTIES hp = {0}; hp.Type = D3D12_HEAP_TYPE_READBACK;
    D3D12_RESOURCE_DESC rd = {0};
    rd.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER; rd.Width = GP_Q_N * sizeof(u64);
    rd.Height = 1; rd.DepthOrArraySize = 1; rd.MipLevels = 1; rd.SampleDesc.Count = 1;
    rd.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    if (FAILED(s_d3d.cmd_queue->lpVtbl->GetTimestampFrequency(s_d3d.cmd_queue, &s_gp_freq)) || !s_gp_freq ||
        FAILED(s_d3d.device->lpVtbl->CreateQueryHeap(s_d3d.device, &qd, &IID_ID3D12QueryHeap, (void**)&s_gp_qh)) ||
        FAILED(s_d3d.device->lpVtbl->CreateCommittedResource(s_d3d.device, &hp, D3D12_HEAP_FLAG_NONE, &rd,
               D3D12_RESOURCE_STATE_COPY_DEST, NULL, &IID_ID3D12Resource, (void**)&s_gp_rb))) {
        if (s_gp_qh) { s_gp_qh->lpVtbl->Release(s_gp_qh); s_gp_qh = NULL; }
        fprintf(stderr, "[gpu-prof] no timestamp queries on this queue: CPU times and counts only%c", 10);
    }
    fprintf(stderr, "[gpu-prof] on: a report every %d frames, at most %u; timestamps %s (%llu Hz)%c",
            frames, maxr, s_gp_qh ? "on" : "off", (unsigned long long)s_gp_freq, 10);
}
static void gp_ts(int i)
{
    if (!s_gp_qh) return;
    s_d3d.cmd_list->lpVtbl->EndQuery(s_d3d.cmd_list, s_gp_qh, D3D12_QUERY_TYPE_TIMESTAMP, (UINT)i);
    s_gp_mask |= 1u << i;
}
/* Before Close: a stage that did not run gets a zero-length span. */
static void gp_resolve(void)
{
    if (!s_gp_qh) return;
    if (!(s_gp_mask & (1u << GP_Q_LOOP0))) gp_ts(GP_Q_LOOP0);
    if (!(s_gp_mask & (1u << GP_Q_LOOP1))) gp_ts(GP_Q_LOOP1);
    gp_ts(GP_Q_END);
    s_d3d.cmd_list->lpVtbl->ResolveQueryData(s_d3d.cmd_list, s_gp_qh, D3D12_QUERY_TYPE_TIMESTAMP, 0, GP_Q_N, s_gp_rb, 0);
    s_gp_pending = (s_gp_mask & 1u) ? 1 : 0;
    s_gp_mask = 0;
}
/* After a GPU drain: the last resolved frame's GPU stages into s_gp.cur. */
static void gp_collect(void)
{
    if (!s_gp_pending) return;
    s_gp_pending = 0;
    u64* q = NULL;
    D3D12_RANGE r = { 0, GP_Q_N * sizeof(u64) };
    if (FAILED(s_gp_rb->lpVtbl->Map(s_gp_rb, 0, &r, (void**)&q)) || !q) return;
    u64 t[GP_Q_N]; memcpy(t, q, sizeof t);
    D3D12_RANGE w = { 0, 0 };
    s_gp_rb->lpVtbl->Unmap(s_gp_rb, 0, &w);
    const double k = 1000.0 / (double)s_gp_freq;
    if (t[GP_Q_END] < t[GP_Q_BEGIN]) return;
    s_gp.cur.t[GP_T_GPU_TOTAL] = (double)(t[GP_Q_END] - t[GP_Q_BEGIN]) * k;
    s_gp.cur.t[GP_T_GPU_PRE]   = (double)(t[GP_Q_LOOP0] - t[GP_Q_BEGIN]) * k;
    s_gp.cur.t[GP_T_GPU_LOOP]  = (double)(t[GP_Q_LOOP1] - t[GP_Q_LOOP0]) * k;
    s_gp.cur.t[GP_T_GPU_POST]  = (double)(t[GP_Q_END] - t[GP_Q_LOOP1]) * k;
    s_gp.cur.t[GP_T_GPU_IDLE]  = s_gp_last_end && t[GP_Q_BEGIN] > s_gp_last_end
                                     ? (double)(t[GP_Q_BEGIN] - s_gp_last_end) * k : 0.0;
    s_gp_last_end = t[GP_Q_END];
    s_gp.cur.has_gpu = 1;
}
''')
rep('''static void wait_for_gpu(void)
{
    GSW_OP_SCOPE(GSW_OP_GPU_WAIT);''', '''static void wait_for_gpu_(void);
static void wait_for_gpu(void)
{
    if (!s_gp.on) { wait_for_gpu_(); return; }
    const double t0 = gp_now_ms();
    wait_for_gpu_();
    s_gp.cur.t[GP_T_CPU_WAIT] += gp_now_ms() - t0;
    s_gp.cur.c[GP_C_WAIT]++;
}
static void wait_for_gpu_(void)
{
    GSW_OP_SCOPE(GSW_OP_GPU_WAIT);''')
rep('''    double _rf0 = perf_on() ? perf_now() : 0.0;
    u32 fi = s_d3d.frame_index;
''', '''    double _rf0 = perf_on() ? perf_now() : 0.0;
    u32 fi = s_d3d.frame_index;
    gp_setup();
    double _g_rf0 = 0.0, _g_t = 0.0;   /* RSX_GPU_PROF */
    if (s_gp.on) _g_rf0 = gp_now_ms();
''')
rep('''    rfp_at(RFP_GPU_DRAIN);
    wait_for_gpu();
''', '''    rfp_at(RFP_GPU_DRAIN);
    wait_for_gpu();
    if (s_gp.on) {   /* the GPU is idle: close the last frame with its GPU stages, open this one */
        const double drain = gp_now_ms() - _g_rf0;
        gp_collect();
        gp_end_frame(&s_gp, stderr);
        s_gp.cur.t[GP_T_CPU_DRAIN] = drain;
        s_gp_srv = 0.0;
        _g_t = gp_now_ms();
    }
''')
rep('''    s_d3d.cmd_list->lpVtbl->Reset(s_d3d.cmd_list, s_d3d.cmd_allocators[fi], NULL);

    /* Upload the bound font atlas''', '''    s_d3d.cmd_list->lpVtbl->Reset(s_d3d.cmd_list, s_d3d.cmd_allocators[fi], NULL);
    s_gp_mask = 0;
    gp_ts(GP_Q_BEGIN);

    /* Upload the bound font atlas''')
rep('''            double _rec0 = perf_on() ? perf_now() : 0.0;
            int seen_small_vp = 0, captured = 0;''', '''            double _rec0 = perf_on() ? perf_now() : 0.0;
            if (s_gp.on) {
                const double n = gp_now_ms();
                s_gp.cur.t[GP_T_CPU_PRE] += n - _g_t; s_gp.cur.t[GP_T_CPU_SRV] += s_gp_srv; _g_t = n;
                gp_ts(GP_Q_LOOP0);
            }
            rsx_bind_shadow _bd;   /* RSX_BIND_DEDUP */
            rsx_bd_begin(&_bd, bind_dedup_on(), s_bind_gen);
            int seen_small_vp = 0, captured = 0;''')
rep('''            ms_pass_end();   /* RSX_MSAA */
            if (perf_on()) s_perf_gpu += perf_now() - _rec0;   /* reuse: record time */''', '''            ms_pass_end();   /* RSX_MSAA */
            if (perf_on()) s_perf_gpu += perf_now() - _rec0;   /* reuse: record time */
            if (s_gp.on) {
                const double n = gp_now_ms();
                s_gp.cur.t[GP_T_CPU_LOOP] += n - _g_t; _g_t = n;
                gp_ts(GP_Q_LOOP1);
            }''')
rep('''    rfp_at(RFP_SUBMIT);
    /* Close and execute */
    const HRESULT close_hr = s_d3d.cmd_list->lpVtbl->Close(s_d3d.cmd_list);
    ID3D12CommandList* cmd_lists[] = {(ID3D12CommandList*)s_d3d.cmd_list};
    s_d3d.cmd_queue->lpVtbl->ExecuteCommandLists(s_d3d.cmd_queue, 1, cmd_lists);''', '''    rfp_at(RFP_SUBMIT);
    gp_resolve();   /* RSX_GPU_PROF */
    if (s_gp.on) { const double n = gp_now_ms(); s_gp.cur.t[GP_T_CPU_POST] += n - _g_t; _g_t = n; }
    /* Close and execute */
    const HRESULT close_hr = s_d3d.cmd_list->lpVtbl->Close(s_d3d.cmd_list);
    ID3D12CommandList* cmd_lists[] = {(ID3D12CommandList*)s_d3d.cmd_list};
    s_d3d.cmd_queue->lpVtbl->ExecuteCommandLists(s_d3d.cmd_queue, 1, cmd_lists);
    if (s_gp.on) { const double n = gp_now_ms(); s_gp.cur.t[GP_T_CPU_SUBMIT] += n - _g_t; _g_t = n; }''')
rep('''    rfp_at(RFP_PRESENT);
    const uint64_t vs_t0 = vstat_on() ? vstat_now_us() : 0;''', '''    rfp_at(RFP_PRESENT);
    if (s_gp.on) { const double n = gp_now_ms(); s_gp.cur.t[GP_T_CPU_POST] += n - _g_t; _g_t = n; }
    const uint64_t vs_t0 = vstat_on() ? vstat_now_us() : 0;''')
rep('''    rfp_at(RFP_NEXT_FRAME);
    move_to_next_frame();
    rfp_at(RFP_TAIL);''', '''    if (s_gp.on) { const double n = gp_now_ms(); s_gp.cur.t[GP_T_CPU_PRESENT] += n - _g_t; _g_t = n; }
    rfp_at(RFP_NEXT_FRAME);
    move_to_next_frame();
    rfp_at(RFP_TAIL);
    if (s_gp.on) { const double n = gp_now_ms(); s_gp.cur.t[GP_T_CPU_NEXT] += n - _g_t; s_gp.cur.t[GP_T_CPU_RF] += n - _g_rf0; }''')
rep('''                s_d3d.cmd_list->lpVtbl->SetPipelineState(s_d3d.cmd_list,
                                                         dpso ? dpso : vpso);
                if (dpso && ((dr_depth_key(dr) >> 6) & 1u))
                    s_d3d.cmd_list->lpVtbl->OMSetStencilRef(s_d3d.cmd_list, (dr->g_stencil >> 8) & 0xFFu);''', '''                if (rsx_bd_need_ptr(&_bd, s_bind_gen, RSX_BD_PSO, dpso ? dpso : vpso)) {
                    s_d3d.cmd_list->lpVtbl->SetPipelineState(s_d3d.cmd_list,
                                                             dpso ? dpso : vpso);
                    rsx_bd_issued(&_bd, s_bind_gen);
                } else GP_N(GP_C_PSO_SKIP, 1);
                if (dpso && ((dr_depth_key(dr) >> 6) & 1u)) {
                    if (rsx_bd_need_sref(&_bd, s_bind_gen, (dr->g_stencil >> 8) & 0xFFu)) {
                        s_d3d.cmd_list->lpVtbl->OMSetStencilRef(s_d3d.cmd_list, (dr->g_stencil >> 8) & 0xFFu);
                        rsx_bd_issued(&_bd, s_bind_gen);
                    } else GP_N(GP_C_SREF_SKIP, 1);
                }''')
rep('''                    dvp_x = dvp.TopLeftX; dvp_y = dvp.TopLeftY;
                    dvp_w = dvp.Width;    dvp_h = dvp.Height;
                    s_d3d.cmd_list->lpVtbl->RSSetViewports(s_d3d.cmd_list, 1, &dvp);
                    s_d3d.cmd_list->lpVtbl->RSSetScissorRects(s_d3d.cmd_list, 1, &dsc);''', '''                    dvp_x = dvp.TopLeftX; dvp_y = dvp.TopLeftY;
                    dvp_w = dvp.Width;    dvp_h = dvp.Height;
                    const float _bv[6] = { dvp.TopLeftX, dvp.TopLeftY, dvp.Width, dvp.Height, dvp.MinDepth, dvp.MaxDepth };
                    const int32_t _bs[4] = { (int32_t)dsc.left, (int32_t)dsc.top, (int32_t)dsc.right, (int32_t)dsc.bottom };
                    if (rsx_bd_need_vp(&_bd, s_bind_gen, _bv, _bs)) {
                        s_d3d.cmd_list->lpVtbl->RSSetViewports(s_d3d.cmd_list, 1, &dvp);
                        s_d3d.cmd_list->lpVtbl->RSSetScissorRects(s_d3d.cmd_list, 1, &dsc);
                        rsx_bd_issued(&_bd, s_bind_gen);
                    } else GP_N(GP_C_VP_SKIP, 1);''')
rep('''                gh.ptr += (u64)(DRAW_SRV_BASE + s_srvw_of[d] * RSX_DSP_NUM_TEXTURES) * s_d3d.srv_inc;
                s_d3d.cmd_list->lpVtbl->SetGraphicsRootDescriptorTable(s_d3d.cmd_list, 1, gh);
                gs_bind_draw(s_d3d.cmd_list, dr);   /* RSX_GUEST_SAMPLERS */
                /* Per-draw constants: this draw's vp_cb + FP texscale slots. */
                s_d3d.cmd_list->lpVtbl->SetGraphicsRootConstantBufferView(s_d3d.cmd_list, 0,
                    s_d3d.vp_cb->lpVtbl->GetGPUVirtualAddress(s_d3d.vp_cb)
                    + ((u64)s_d3d.vp_parity * MAX_DRAWS + dr->cb_slot) * VP_CB_STRIDE);
                if (s_d3d.vp_fpcb)
                    s_d3d.cmd_list->lpVtbl->SetGraphicsRootConstantBufferView(s_d3d.cmd_list, 2,
                        s_d3d.vp_fpcb->lpVtbl->GetGPUVirtualAddress(s_d3d.vp_fpcb)
                        + ((u64)s_d3d.vp_parity * MAX_DRAWS + dr->cb_slot) * VP_FPCB_STRIDE);''', '''                gh.ptr += (u64)(DRAW_SRV_BASE + s_srvw_of[d] * RSX_DSP_NUM_TEXTURES) * s_d3d.srv_inc;
                if (rsx_bd_need_u64(&_bd, s_bind_gen, RSX_BD_TABLE, gh.ptr)) {
                    s_d3d.cmd_list->lpVtbl->SetGraphicsRootDescriptorTable(s_d3d.cmd_list, 1, gh);
                    rsx_bd_issued(&_bd, s_bind_gen);
                } else GP_N(GP_C_TABLE_SKIP, 1);
                /* RSX_GUEST_SAMPLERS: its own per-unit dedup (s_gs_cur), on other
                 * root slots: its sets resync a shadow that was current. */
                { const u32 _g0 = s_bind_gen; gs_bind_draw(s_d3d.cmd_list, dr);
                  if (s_bind_gen != _g0 && _bd.gen == _g0) rsx_bd_issued(&_bd, s_bind_gen); }
                /* Per-draw constants: this draw's vp_cb + FP texscale slots. */
                { const u64 _cb0 = s_d3d.vp_cb->lpVtbl->GetGPUVirtualAddress(s_d3d.vp_cb)
                                 + ((u64)s_d3d.vp_parity * MAX_DRAWS + dr->cb_slot) * VP_CB_STRIDE;
                  if (rsx_bd_need_u64(&_bd, s_bind_gen, RSX_BD_CB0, _cb0)) {
                      s_d3d.cmd_list->lpVtbl->SetGraphicsRootConstantBufferView(s_d3d.cmd_list, 0, _cb0);
                      rsx_bd_issued(&_bd, s_bind_gen);
                  } else GP_N(GP_C_CBV_SKIP, 1); }
                if (s_d3d.vp_fpcb) {
                    const u64 _cb2 = s_d3d.vp_fpcb->lpVtbl->GetGPUVirtualAddress(s_d3d.vp_fpcb)
                                   + ((u64)s_d3d.vp_parity * MAX_DRAWS + dr->cb_slot) * VP_FPCB_STRIDE;
                    if (rsx_bd_need_u64(&_bd, s_bind_gen, RSX_BD_CB2, _cb2)) {
                        s_d3d.cmd_list->lpVtbl->SetGraphicsRootConstantBufferView(s_d3d.cmd_list, 2, _cb2);
                        rsx_bd_issued(&_bd, s_bind_gen);
                    } else GP_N(GP_C_CBV_SKIP, 1);
                }''')
rep('''static rsx_srv_set* s_srvw_sets;''', '''/* RSX_BIND_DEDUP (rsx_bind_dedup.h): opt-in "1", read once. */
static int bind_dedup_on(void)
{
    static int on = -1;
    if (on < 0) { const char* e = getenv("RSX_BIND_DEDUP"); on = (e && e[0] == '1' && !e[1]) ? 1 : 0; }
    return on;
}
static rsx_srv_set* s_srvw_sets;''')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('utf-8'))
print('ok')
