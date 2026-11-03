"""T137: lazy resolve before every direct reader of an off-screen target's res (one-shot)."""
import sys
p = sys.argv[1] + '/libs/video/rsx_d3d12_backend.c'
s = open(p, newline='', encoding='utf-8').read().replace('\r\n', '\n')


def rep(a, b, cnt=1):
    global s
    n = s.count(a)
    assert n == cnt, (a[:100], n)
    s = s.replace(a, b)


rep('''static DXGI_FORMAT rsx_surface_dxgi(u32 fmt);
''', '''static DXGI_FORMAT rsx_surface_dxgi(u32 fmt);
/* RSX_MSAA: before a direct read of off_rt[slot].res (not through off_rt_transition). */
static void ms_sync(int slot)
{
    if (slot >= 0 && slot < MAX_OFF_RTS && s_d3d.off_rt[slot].ms && s_d3d.off_rt[slot].ms_newer) ms_resolve(slot);
}
''')
rep('''        snprintf(path, sizeof path, "%s/rt_%08X.bmp", dir, r->off);
        cap_readback_write(r->res, r->w, r->h, r->dxgi, r->st, fi, path);''',
    '''        snprintf(path, sizeof path, "%s/rt_%08X.bmp", dir, r->off);
        ms_sync(i);
        cap_readback_write(r->res, r->w, r->h, r->dxgi, r->st, fi, path);''')
rep('''            OffRT* r = &s_d3d.off_rt[s];
            if (rsxi_rt_wanted(r->off))
                rsxi_queue_copy(r->res, r->w, r->h, r->dxgi, r->st, "pass", (int)d - 1, s, r->off);''',
    '''            OffRT* r = &s_d3d.off_rt[s];
            if (rsxi_rt_wanted(r->off)) {
                ms_sync(s);
                rsxi_queue_copy(r->res, r->w, r->h, r->dxgi, r->st, "pass", (int)d - 1, s, r->off);
            }''')
rep('''            OffRT* r = &s_d3d.off_rt[old_rt];
            if (rsxi_rt_wanted(r->off))
                rsxi_queue_copy(r->res, r->w, r->h, r->dxgi, r->st, "pass", (int)d - 1, old_rt, r->off);''',
    '''            OffRT* r = &s_d3d.off_rt[old_rt];
            if (rsxi_rt_wanted(r->off)) {
                ms_sync(old_rt);
                rsxi_queue_copy(r->res, r->w, r->h, r->dxgi, r->st, "pass", (int)d - 1, old_rt, r->off);
            }''')
rep('''        if (!r->res || !r->used || !rsxi_rt_wanted(r->off)) continue;
        rsxi_queue_copy(r->res, r->w, r->h, r->dxgi, r->st, "end", -1, i, r->off);''',
    '''        if (!r->res || !r->used || !rsxi_rt_wanted(r->off)) continue;
        ms_sync(i);
        rsxi_queue_copy(r->res, r->w, r->h, r->dxgi, r->st, "end", -1, i, r->off);''')
rep('''        if (rt >= 0 && s_d3d.off_rt[rt].res) {
            OffRT* r = &s_d3d.off_rt[rt];''', '''        if (rt >= 0 && s_d3d.off_rt[rt].res) {
            OffRT* r = &s_d3d.off_rt[rt];
            ms_sync(rt);''')
rep('''    if (i < 0 || !s_d3d.off_rt[i].res) return;
''', '''    if (i < 0 || !s_d3d.off_rt[i].res) return;
    ms_sync(i);   /* RSX_MSAA */
''')
# The pass ends before RSXI snapshots the targets being left.
rep('''                    if (s_rsxi.active) rsxi_on_retarget(d, dr, cur_rt, cur_m, want, wantm);
                    ms_pass_end();''', '''                    ms_pass_end();
                    if (s_rsxi.active) rsxi_on_retarget(d, dr, cur_rt, cur_m, want, wantm);''')
open(p, 'w', newline='', encoding='utf-8').write(s.replace('\n', '\r\n'))
print('ok')
