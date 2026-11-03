"""T137: keep T120's dr_depth_key and shared-depth clear verbatim; the 2-sample bits sit beside them (one-shot)."""
import sys
p = sys.argv[1] + '/libs/video/rsx_d3d12_backend.c'
s = open(p, newline='', encoding='utf-8').read().replace('\r\n', '\n')


def rep(a, b, cnt=1):
    global s
    n = s.count(a)
    assert n == cnt, (a[:100], n)
    s = s.replace(a, b)


rep('''static u64 dr_depth_key(const D3D12DrawRecord* dr)
{
    /* RSX_MSAA: sample count and coverage state in the key's top byte. */
    const u64 ms = dr_ms(dr) ? rsx_msaa_key(2, dr->g_aa_ctl, (int)dr->g_aa_set) : 0;
    if (ds_state_on()) return dr->g_ds_key | ms;
    return ((dr->g_depth >> 16) & 1u) | ms;
}''', '''/* RSX_MSAA: sample count and coverage state, in the pipeline key's top byte
 * (OR-ed onto dr_depth_key where the guest-FP pipeline is looked up). */
static u64 dr_ms_key(const D3D12DrawRecord* dr)
{
    return dr_ms(dr) ? rsx_msaa_key(2, dr->g_aa_ctl, (int)dr->g_aa_set) : 0;
}

static u64 dr_depth_key(const D3D12DrawRecord* dr)
{
    if (ds_state_on()) return dr->g_ds_key;
    return (dr->g_depth >> 16) & 1u;
}''')
rep('                          dr_depth_key(dr), dr_xfer_req(dr, &_xf));\n',
    '                          dr_depth_key(dr) | dr_ms_key(dr), dr_xfer_req(dr, &_xf));\n')
rep('                                                dr_depth_key(dr), dr_xfer_req(dr, &_xf)) : NULL;\n',
    '                                                dr_depth_key(dr) | dr_ms_key(dr), dr_xfer_req(dr, &_xf)) : NULL;\n')
rep('''                    if (want_z < 0)
                        s_d3d.cmd_list->lpVtbl->ClearDepthStencilView(s_d3d.cmd_list, cur_dsv,
                            D3D12_CLEAR_FLAG_DEPTH | D3D12_CLEAR_FLAG_STENCIL, 1.0f, 0, 0, NULL);''',
    '''                    if (want_z < 0)
                        s_d3d.cmd_list->lpVtbl->ClearDepthStencilView(s_d3d.cmd_list, dsv_handle,
                            D3D12_CLEAR_FLAG_DEPTH | D3D12_CLEAR_FLAG_STENCIL, 1.0f, 0, 0, NULL);
                    if (want_z < 0 && pass_ms)   /* RSX_MSAA: the 2-sample shared buffer, likewise */
                        s_d3d.cmd_list->lpVtbl->ClearDepthStencilView(s_d3d.cmd_list, cur_dsv,
                            D3D12_CLEAR_FLAG_DEPTH | D3D12_CLEAR_FLAG_STENCIL, 1.0f, 0, 0, NULL);''')
open(p, 'w', newline='', encoding='utf-8').write(s.replace('\n', '\r\n'))
t = sys.argv[1] + '/tools/test_msaa.py'
u = open(t, encoding='utf-8').read()
u = u.replace("check('const u64 ms = dr_ms(dr) ? rsx_msaa_key(2, dr->g_aa_ctl, (int)dr->g_aa_set) : 0;' in be and",
              "check('return dr_ms(dr) ? rsx_msaa_key(2, dr->g_aa_ctl, (int)dr->g_aa_set) : 0;' in be and\n"
              "      be.count('dr_depth_key(dr) | dr_ms_key(dr)') == 2 and")
open(t, 'w', encoding='utf-8').write(u)
print('ok')
