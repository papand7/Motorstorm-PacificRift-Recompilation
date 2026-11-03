"""T120: zeta-as-colour windows: SRV fill, replay refresh, frame begin, RSXI (one-shot)."""
import sys
p = sys.argv[1]
s = open(p, newline='').read().replace('\r\n', '\n')


def rep(a, b, cnt=1):
    global s
    n = s.count(a)
    assert n == cnt, (a[:90], n)
    s = s.replace(a, b)


rep('''    e->conv_ok = 1;
    e->cgen++;
''', '''    e->conv_ok = 1;
    { static u64 seq = 0; e->cgen = ++seq; }   /* unique across slot reuse */
''')
rep('''                        dr->tex_src[_u] = RSXI_SRC_ZETA_AS_COLOR;
                        s_d3d.zeta[z].used = 1;
                        srv_write(wslot, s_d3d.zeta[z].cres, DXGI_FORMAT_R8G8B8A8_UNORM,
                                  D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING);
                        continue;''', '''                        dr->tex_src[_u] = RSXI_SRC_ZETA_AS_COLOR;
                        s_d3d.zeta[z].used = 1;
                        /* RSX_RT_WINDOW: the scene depth read back as a 2528x711
                         * A8R8G8B8 texture covers 1264x711 of the 1280x720 zeta. */
                        ID3D12Resource* _zr = s_d3d.zeta[z].cres;
                        rsx_rt_window _win;
                        if (rtwin_on() && rsx_rt_window_of(dr->tex[_u].w, dr->tex[_u].h, dr->tex[_u].pitch,
                                                           s_d3d.zeta[z].aa, 0, s_d3d.zeta[z].w,
                                                           s_d3d.zeta[z].h, &_win)) {
                            ID3D12Resource* _wr = zwin_get(z, _win.w, _win.h);
                            if (_wr) { _zr = _wr; dr->tex_win |= (u16)(1u << _u); }
                        }
                        srv_write(wslot, _zr, DXGI_FORMAT_R8G8B8A8_UNORM,
                                  D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING);
                        continue;''')
rep('''    zeta_frame_begin();
    for (u32 _d = 0;''', '''    zeta_frame_begin();
    rtwin_frame_begin();
    for (u32 _d = 0;''')
# replay: after the conversion loop + stale marking, refresh zeta windows
rep('''                         ((dr->g_stencil >> 24) & 1u)))
                        s_d3d.zeta[cur_z].conv_ok = 0;
''', '''                         ((dr->g_stencil >> 24) & 1u)))
                        s_d3d.zeta[cur_z].conv_ok = 0;
                    /* RSX_RT_WINDOW: zeta-as-colour windows follow their image. */
                    for (int _u = 0; dr->tex_win && _u < RSX_DSP_NUM_TEXTURES; _u++) {
                        const int z = dr->tex_zeta[_u];
                        if (z < 0 || !((dr->tex_win >> _u) & 1u) || dr->tex_src[_u] != RSXI_SRC_ZETA_AS_COLOR) continue;
                        ZetaSurf* e = &s_d3d.zeta[z];
                        RtWin* v = &s_zwin[z];
                        if (!v->res || !e->cres || !e->conv_ok || v->gen == e->cgen) continue;
                        res_transition(e->cres, &e->cst, D3D12_RESOURCE_STATE_COPY_SOURCE);
                        win_copy(v, e->cres);
                        res_transition(e->cres, &e->cst, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
                        v->gen = e->cgen;
                    }
''')
rep('''                    dr->tex_zeta[u], zs->off,
                    (void*)(src == RSXI_SRC_ZETA ? zs->res : zs->cres), zs->w, zs->h,
                    dr->tex[u].shadow.enabled == 1 ? (unsigned)dr->tex[u].shadow.func : 0u);
''', '''                    dr->tex_zeta[u], zs->off,
                    (void*)(src == RSXI_SRC_ZETA ? zs->res : zs->cres), zs->w, zs->h,
                    dr->tex[u].shadow.enabled == 1 ? (unsigned)dr->tex[u].shadow.func : 0u);
            if ((dr->tex_win >> u) & 1u)
                fprintf(f, ",\\"window\\":[%u,%u]", s_zwin[dr->tex_zeta[u]].w, s_zwin[dr->tex_zeta[u]].h);
''')
open(p, 'w', newline='').write(s.replace('\n', '\r\n'))
print('ok')
