"""T120: apply the RSX_DEPTH_STATE edits to the T120 D3D12 backend (one-shot)."""
import sys
p = sys.argv[1]
s = open(p, newline='').read()
N = '\r\n'


def rep(a, b, cnt=1):
    global s
    a = a.replace('\n', N); b = b.replace('\n', N)
    n = s.count(a)
    assert n == cnt, (a[:90], n)
    s = s.replace(a, b)


rep('#include "rsx_rt_window.h"    /* the sub-rectangle of a target a guest texture covers (RSX_RT_WINDOW) */\n',
    '#include "rsx_rt_window.h"    /* the sub-rectangle of a target a guest texture covers (RSX_RT_WINDOW) */\n'
    '#include "rsx_depth_state.h"  /* guest depth/stencil state as a pipeline key (RSX_DEPTH_STATE) */\n')
rep('    u32 g_stencil;         /* test<<24 | (func&0xFF)<<16 | (ref&0xFF)<<8 | mask&0xFF */\n',
    '    u32 g_stencil;         /* test<<24 | (func&0xFF)<<16 | (ref&0xFF)<<8 | mask&0xFF */\n'
    '    u64 g_ds_key;          /* rsx_ds_key: full guest depth/stencil state (RSX_DEPTH_STATE) */\n')
rep('    u32 depth;              /* bit0: guest depth test enabled (PSO key) */\n',
    '    u64 depth;              /* dr_depth_key (PSO key): bit0 test enable, or rsx_ds_key */\n')
rep('u32 shadow_key, u32 depth, const rsx_color_xfer* xf)', 'u32 shadow_key, u64 depth, const rsx_color_xfer* xf)', 2)
rep('''/* Depth PSO key for a draw record: bit0 = the guest's depth test enable. */
static u32 dr_depth_key(const D3D12DrawRecord* dr)
{
    return (dr->g_depth >> 16) & 1u;
}
''', '''/* RSX_DEPTH_STATE=1: guest-FP pipelines take the guest's depth write mask,
 * depth compare and stencil state (rsx_depth_state.h), and a draw that reads
 * its own bound zeta as colour keeps that zeta as its depth target. Unset:
 * test enable only, writes on, LESS_EQUAL, no stencil, as before. */
static int ds_state_on(void)
{
    static int on = -1;
    if (on < 0) { const char* e = getenv("RSX_DEPTH_STATE"); on = (e && e[0] == '1' && !e[1]) ? 1 : 0; }
    return on;
}

/* Depth PSO key for a draw record: bit0 = the guest's depth test enable, or
 * with RSX_DEPTH_STATE=1 the full rsx_ds_key. */
static u64 dr_depth_key(const D3D12DrawRecord* dr)
{
    if (ds_state_on()) return dr->g_ds_key;
    return (dr->g_depth >> 16) & 1u;
}
''')
rep('''    if (!(depth & 1u)) {
        pd.DepthStencilState.DepthEnable = FALSE;
        pd.DepthStencilState.DepthWriteMask = D3D12_DEPTH_WRITE_MASK_ZERO;
    }
''', '''    if (!(depth & 1u)) {
        pd.DepthStencilState.DepthEnable = FALSE;
        pd.DepthStencilState.DepthWriteMask = D3D12_DEPTH_WRITE_MASK_ZERO;
    }
    /* RSX_DEPTH_STATE=1: the guest's write mask, compare and stencil. */
    { const rsx_ds_desc g = rsx_ds_decode(depth);
      if (g.full) {
          D3D12_DEPTH_STENCIL_DESC* ds = &pd.DepthStencilState;
          if (g.depth_enable) {
              ds->DepthWriteMask = g.depth_write ? D3D12_DEPTH_WRITE_MASK_ALL : D3D12_DEPTH_WRITE_MASK_ZERO;
              ds->DepthFunc = (D3D12_COMPARISON_FUNC)g.depth_func;
          }
          if (g.stencil_enable) {
              ds->StencilEnable = TRUE;
              ds->StencilReadMask  = (UINT8)g.read_mask;
              ds->StencilWriteMask = (UINT8)g.write_mask;
              ds->FrontFace.StencilFunc        = (D3D12_COMPARISON_FUNC)g.f_func;
              ds->FrontFace.StencilFailOp      = (D3D12_STENCIL_OP)g.f_fail;
              ds->FrontFace.StencilDepthFailOp = (D3D12_STENCIL_OP)g.f_zfail;
              ds->FrontFace.StencilPassOp      = (D3D12_STENCIL_OP)g.f_zpass;
              ds->BackFace.StencilFunc         = (D3D12_COMPARISON_FUNC)g.b_func;
              ds->BackFace.StencilFailOp       = (D3D12_STENCIL_OP)g.b_fail;
              ds->BackFace.StencilDepthFailOp  = (D3D12_STENCIL_OP)g.b_zfail;
              ds->BackFace.StencilPassOp       = (D3D12_STENCIL_OP)g.b_zpass;
          }
      } }
''')
rep('''    if (!st) { dr->g_depth = dr->g_stencil = 0; dr->g_sc_x''',
    '''    if (!st) { dr->g_depth = dr->g_stencil = 0; dr->g_ds_key = 0; dr->g_sc_x''')
rep('''                  | ((st->stencil_ref & 0xFFu) << 8) | (st->stencil_mask & 0xFFu);
''', '''                  | ((st->stencil_ref & 0xFFu) << 8) | (st->stencil_mask & 0xFFu);
    { const rsx_ds_state ds = { st->depth_test_enable, st->depth_mask, st->depth_func,
          st->stencil_test_enable, st->stencil_func, st->stencil_mask, st->stencil_write_mask,
          st->stencil_op_fail, st->stencil_op_zfail, st->stencil_op_zpass,
          st->stencil_two_sided, st->back_stencil_func, st->back_stencil_op_fail,
          st->back_stencil_op_zfail, st->back_stencil_op_zpass };
      dr->g_ds_key = rsx_ds_key(&ds);
      /* D3D12 has one reference and one pair of masks for both faces. */
      if (ds_state_on() && st->stencil_test_enable && st->stencil_two_sided &&
          (((st->back_stencil_ref ^ st->stencil_ref) |
            (st->back_stencil_mask ^ st->stencil_mask) |
            (st->back_stencil_write_mask ^ st->stencil_write_mask)) & 0xFFu)) {
          static int _n = 0; if (PS3_LOG_FIRST(_n, 4))
              fprintf(stderr, "[ds] two-sided stencil with a back ref/mask of its own"
                              " (ref %u/%u, mask %u/%u, write %u/%u): front values used%c",
                      st->stencil_ref & 0xFFu, st->back_stencil_ref & 0xFFu,
                      st->stencil_mask & 0xFFu, st->back_stencil_mask & 0xFFu,
                      st->stencil_write_mask & 0xFFu, st->back_stencil_write_mask & 0xFFu, 10);
      } }
''')
rep('''                s_d3d.cmd_list->lpVtbl->SetPipelineState(s_d3d.cmd_list,
                                                         dpso ? dpso : vpso);
''', '''                s_d3d.cmd_list->lpVtbl->SetPipelineState(s_d3d.cmd_list,
                                                         dpso ? dpso : vpso);
                if (dpso && ((dr_depth_key(dr) >> 6) & 1u))
                    s_d3d.cmd_list->lpVtbl->OMSetStencilRef(s_d3d.cmd_list, (dr->g_stencil >> 8) & 0xFFu);
''')
rep('''                        if (!dr->is_clear && zeta_sampled_unit(dr->tex_zeta, dr->fp_units, z) >= 0) {
                            want_z = -1;''', '''                        if (!dr->is_clear && zeta_sampled_unit(dr->tex_zeta, dr->fp_units, z) >= 0 &&
                            !(ds_state_on() && zeta_sampled_only_as_color(dr, z))) {
                            want_z = -1;''')
rep('''static int zeta_sampled_unit(const s8* tex_zeta, u32 fp_units, int z)
{
    for (int u = 0; u < RSX_DSP_NUM_TEXTURES; u++)
        if (tex_zeta[u] == z && ((fp_units >> u) & 1u)) return u;
    return -1;
}
''', '''static int zeta_sampled_unit(const s8* tex_zeta, u32 fp_units, int z)
{
    for (int u = 0; u < RSX_DSP_NUM_TEXTURES; u++)
        if (tex_zeta[u] == z && ((fp_units >> u) & 1u)) return u;
    return -1;
}

/* Every fetched unit reading zeta z reads it as colour: the program samples
 * the A8R8G8B8 image (cres), a resource of its own, so z can stay bound as
 * the depth target. The shore draws (fp 0x07200641, depth test on, writes
 * off) and the velocity pass (fp 0x0074CE81, stencil NOTEQUAL) read their own
 * zeta this way; the shared-buffer fallback tested them against nothing. */
static int zeta_sampled_only_as_color(const D3D12DrawRecord* dr, int z)
{
    for (int u = 0; u < RSX_DSP_NUM_TEXTURES; u++)
        if (dr->tex_zeta[u] == z && ((dr->fp_units >> u) & 1u) &&
            dr->tex_src[u] != RSXI_SRC_ZETA_AS_COLOR) return 0;
    return 1;
}
''')
rep('''                        int z = dr->tex_zeta[_u];
                        if (z < 0 || z == cur_z || !((dr->fp_units >> _u) & 1u)) continue;
                        if (dr->tex_src[_u] == RSXI_SRC_ZETA_AS_COLOR) {
                            if (!s_d3d.zeta[z].conv_ok) conv |= zeta_convert(z);
                        } else
                            zeta_transition(z, ZETA_READ_STATE);
                    }
''', '''                        int z = dr->tex_zeta[_u];
                        if (z < 0 || !((dr->fp_units >> _u) & 1u)) continue;
                        if (z == cur_z) {
                            /* RSX_DEPTH_STATE: the bound zeta read as colour
                             * (kept bound above). Its image is rebuilt from the
                             * depth so far, then it returns to depth target. */
                            if (ds_state_on() && dr->tex_src[_u] == RSXI_SRC_ZETA_AS_COLOR &&
                                !s_d3d.zeta[z].conv_ok && zeta_convert(z)) {
                                zeta_transition(z, D3D12_RESOURCE_STATE_DEPTH_WRITE);
                                conv = 1;
                            }
                            continue;
                        }
                        if (dr->tex_src[_u] == RSXI_SRC_ZETA_AS_COLOR) {
                            if (!s_d3d.zeta[z].conv_ok) conv |= zeta_convert(z);
                        } else
                            zeta_transition(z, ZETA_READ_STATE);
                    }
                    /* A draw that can write the bound zeta makes its colour
                     * image stale for the draws after it. */
                    if (ds_state_on() && cur_z >= 0 &&
                        ((((dr->g_depth >> 16) & 1u) && ((dr->g_depth >> 8) & 1u)) ||
                         ((dr->g_stencil >> 24) & 1u)))
                        s_d3d.zeta[cur_z].conv_ok = 0;
''')
rep(r'''"\"stencil\":{\"test\":%u,\"func\":%u,\"ref\":%u,\"mask\":%u},\"blend\":%d,"''',
    r'''"\"stencil\":{\"test\":%u,\"func\":%u,\"ref\":%u,\"mask\":%u},\"ds_key\":\"0x%012llX\",\"blend\":%d,"''')
rep('''            dr->g_stencil & 0xFFu, dr->blend, dr->blend_key, dr->cmask, dr->cull, dr->alpha_ctl,''',
    '''            dr->g_stencil & 0xFFu, (unsigned long long)dr->g_ds_key, dr->blend, dr->blend_key, dr->cmask, dr->cull, dr->alpha_ctl,''')
open(p, 'w', newline='').write(s)
print('ok')
