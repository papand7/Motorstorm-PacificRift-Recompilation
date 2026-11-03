"""T142: units the fragment program does not fetch claim no RSX_RT_WINDOW / RSX_MSAA window.
Edits libs/video/rsx_d3d12_backend.c in the given worktree (keeps CRLF)."""
import sys
from pathlib import Path

p = Path(sys.argv[1]) / 'libs/video/rsx_d3d12_backend.c'
s = p.read_bytes().decode('utf-8').replace('\r\n', '\n')


def sub(old, new):
    global s
    assert s.count(old) == 1, (old[:90], s.count(old))
    s = s.replace(old, new)


sub('''                    const OffRT* _r = &s_d3d.off_rt[rt];
                    ID3D12Resource* _sr = _r->res;
                    /* RSX_MSAA: an antialias-3 surface is read as its samples. */
                    if (rt_ms_read(rt)) {
                        u32 _mw, _mh;
                        const int _mr = rsx_msaa_read_window(dr->tex[_u].w, dr->tex[_u].h, 3u, _r->w, _r->h, &_mw, &_mh);
                        ID3D12Resource* _xr = (_mr >= 0 && ms_alloc(rt)) ?
                            (_mr ? xwin_get(rt, _mw, _mh) : ms_xres_get(rt)) : NULL;
                        if (!_xr) s_msc.read_other++;
                        if (_xr) {
                            dr->tex_xms |= (u16)(1u << _u);
                            if (_mr) dr->tex_win |= (u16)(1u << _u);   /* reads its window */
''', '''                    const OffRT* _r = &s_d3d.off_rt[rt];
                    ID3D12Resource* _sr = _r->res;
                    /* Only a unit the program fetches may claim a window. A target
                     * keeps one window size per frame (win_get, xwin_get), and RSX
                     * keeps a unit's state until it is changed: a unit left over
                     * from an earlier pass, declaring LAST frame's size of a scene
                     * whose size moves every frame, claimed the window first and
                     * the unit the program reads fell back to the whole, stretched
                     * surface (T142). An unfetched unit binds the whole resource. */
                    const int _fetched = (int)((dr->fp_units >> _u) & 1u);
                    /* RSX_MSAA: an antialias-3 surface is read as its samples. */
                    if (rt_ms_read(rt)) {
                        u32 _mw, _mh;
                        int _mr = rsx_msaa_read_window(dr->tex[_u].w, dr->tex[_u].h, 3u, _r->w, _r->h, &_mw, &_mh);
                        if (_mr == 1 && !_fetched) _mr = 0;   /* the whole sample image */
                        ID3D12Resource* _xr = (_mr >= 0 && ms_alloc(rt)) ?
                            (_mr ? xwin_get(rt, _mw, _mh) : ms_xres_get(rt)) : NULL;
                        if (!_xr) s_msc.read_other++;
                        if (_xr) {
                            dr->tex_xms |= (u16)(1u << _u);
                            if (_mr) dr->tex_win |= (u16)(1u << _u);   /* reads its window */
''')
sub('''                    if (rtwin_on() && rsx_rt_window_of(dr->tex[_u].w, dr->tex[_u].h, dr->tex[_u].pitch,
                                                       _r->aa, _r->gpitch, _r->w, _r->h, &_win)) {
                        ID3D12Resource* _wr = rtwin_get(rt, _win.w, _win.h);''',
    '''                    if (rtwin_on() && _fetched && rsx_rt_window_of(dr->tex[_u].w, dr->tex[_u].h, dr->tex[_u].pitch,
                                                                   _r->aa, _r->gpitch, _r->w, _r->h, &_win)) {
                        ID3D12Resource* _wr = rtwin_get(rt, _win.w, _win.h);''')
# A second size of one target in one frame among FETCHED units still binds the whole target: say so.
sub('''    if (v->res && v->w == w && v->h == h && v->dxgi == dxgi) { v->frame = s_d3d.frame_count; return v->res; }
    if (v->res) {
        if (v->frame == s_d3d.frame_count) return NULL;
        rtwin_retire(v);
    }
    D3D12_HEAP_PROPERTIES hp = {0}; hp.Type = D3D12_HEAP_TYPE_DEFAULT;
    D3D12_RESOURCE_DESC td = {0};
    td.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    td.Width = w; td.Height = h; td.DepthOrArraySize = 1; td.MipLevels = 1;
    td.Format = (DXGI_FORMAT)dxgi; td.SampleDesc.Count = 1;
    if (FAILED''', '''    if (v->res && v->w == w && v->h == h && v->dxgi == dxgi) { v->frame = s_d3d.frame_count; return v->res; }
    if (v->res) {
        if (v->frame == s_d3d.frame_count) {
            static int _n = 0;
            if (PS3_LOG_FIRST(_n, 8))
                fprintf(stderr, "[rtwin] 0x%08X: a second size %ux%u in one frame (window is %ux%u): "
                                "this read binds the whole target%c", off, w, h, v->w, v->h, 10);
            return NULL;
        }
        rtwin_retire(v);
    }
    D3D12_HEAP_PROPERTIES hp = {0}; hp.Type = D3D12_HEAP_TYPE_DEFAULT;
    D3D12_RESOURCE_DESC td = {0};
    td.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    td.Width = w; td.Height = h; td.DepthOrArraySize = 1; td.MipLevels = 1;
    td.Format = (DXGI_FORMAT)dxgi; td.SampleDesc.Count = 1;
    if (FAILED''')
p.write_bytes(s.replace('\n', '\r\n').encode('utf-8'))
print('patched')
