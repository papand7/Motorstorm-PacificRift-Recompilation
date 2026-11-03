"""T110: RSX_COLOR_XFER - compile guest FPs with the colour transfers the draw
asks for (T107 section 9). Each replacement must match exactly.
  py -3 -I edit_xfer.py <tree>"""
import sys
from pathlib import Path

p = Path(sys.argv[1]) / 'libs/video/rsx_d3d12_backend.c'
s = p.read_text(encoding='utf-8')


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, f'{n} matches (want {count}) for:\n{old[:300]}'
    s = s.replace(old, new)


# 1. PSO key fields
rep('''    u32 shadow_key;         /* depth-compare units + functions (PSO key), 0 = none */
    ID3D12PipelineState* pso;
} VPFPEntry;''', '''    u32 shadow_key;         /* depth-compare units + functions (PSO key), 0 = none */
    /* RSX_COLOR_XFER (PSO key): sRGB output and, per unit the program fetches,
     * its gamma and expand lane masks. All zero = no transfer compiled in. */
    u8 xf_srgb, xf_gamma[16], xf_expand[16];
    ID3D12PipelineState* pso;
} VPFPEntry;''')

# 2. signature (definition, wrapper, macro'd calls)
sig_old = '''                                          u32 cube_mask, const rsx_fp_shadow_desc* shadow,
                                          u32 shadow_key, u32 depth)
{
    s_vp_fp_last_uhash = 0;     /* 0 until the program is located and hashed */'''
sig_new = '''                                          u32 cube_mask, const rsx_fp_shadow_desc* shadow,
                                          u32 shadow_key, u32 depth, const rsx_color_xfer* xf)
{
    s_vp_fp_last_uhash = 0;     /* 0 until the program is located and hashed */'''
rep(sig_old, sig_new)
rep('''                                              u32 cube_mask, const rsx_fp_shadow_desc* shadow,
                                              u32 shadow_key, u32 depth)
{
    if (!s_fpf_on)
        return vp_get_fp_pso(vs_idx, fp_addr, blend, nrt, rtfmt, exp32, cmask, cull, cube_mask, shadow, shadow_key, depth);''',
    '''                                              u32 cube_mask, const rsx_fp_shadow_desc* shadow,
                                              u32 shadow_key, u32 depth, const rsx_color_xfer* xf)
{
    if (!s_fpf_on)
        return vp_get_fp_pso(vs_idx, fp_addr, blend, nrt, rtfmt, exp32, cmask, cull, cube_mask, shadow, shadow_key, depth, xf);''')
rep('''    ID3D12PipelineState* p = vp_get_fp_pso(vs_idx, fp_addr, blend, nrt, rtfmt, exp32, cmask, cull, cube_mask,
                                           shadow, shadow_key, depth);''',
    '''    ID3D12PipelineState* p = vp_get_fp_pso(vs_idx, fp_addr, blend, nrt, rtfmt, exp32, cmask, cull, cube_mask,
                                           shadow, shadow_key, depth, xf);''')

# 3. effective masks + key compare
rep('''    if (shadow_key)
        shadow_key = shadow_key_of(shadow, rsx_fp_texture_units(vm_base + off, 4096));
''', '''    if (shadow_key)
        shadow_key = shadow_key_of(shadow, rsx_fp_texture_units(vm_base + off, 4096));
    /* RSX_COLOR_XFER: only the transfers this program performs key it, so a
     * unit it never samples cannot split its pipeline. */
    u8 xs = 0, xg[16], xe[16];
    memset(xg, 0, sizeof xg); memset(xe, 0, sizeof xe);
    if (xf) {
        const u32 gu = rsx_fp_texture_gamma_units(vm_base + off, 4096, xf->gamma);
        const u32 eu = rsx_fp_texture_expand_units(vm_base + off, 4096, xf->expand);
        for (int _u = 0; _u < 16; _u++) {
            if ((gu >> _u) & 1u) xg[_u] = xf->gamma[_u];
            if ((eu >> _u) & 1u) xe[_u] = xf->expand[_u];
        }
        xs = xf->srgb_output;
    }
    const int xmasks = (rsx_fp_texture_gamma_units(vm_base + off, 4096, xg) |
                        rsx_fp_texture_expand_units(vm_base + off, 4096, xe)) != 0;
''')
rep('''            s_d3d.vp_fp[i].cube_mask == cube_mask &&
            s_d3d.vp_fp[i].shadow_key == shadow_key)
            return s_d3d.vp_fp[i].pso;''', '''            s_d3d.vp_fp[i].cube_mask == cube_mask &&
            s_d3d.vp_fp[i].shadow_key == shadow_key &&
            s_d3d.vp_fp[i].xf_srgb == xs && !memcmp(s_d3d.vp_fp[i].xf_gamma, xg, sizeof xg) &&
            !memcmp(s_d3d.vp_fp[i].xf_expand, xe, sizeof xe))
            return s_d3d.vp_fp[i].pso;''')

# 4. decompile with masks; sRGB output after
rep('''    int n = rsx_fp_decompile_shadow_ex(vm_base + off, 4096, fp_ctrl, cube_mask,
                                       shadow_key ? shadow : NULL, hlsl, sizeof(hlsl));
    if (n <= 0 && shadow_key) {''', '''    int n = xmasks ? rsx_fp_decompile_shadow_color_expand_ex(vm_base + off, 4096, fp_ctrl, cube_mask,
                                                             shadow_key ? shadow : NULL, xg, xe,
                                                             hlsl, sizeof(hlsl))
                   : rsx_fp_decompile_shadow_ex(vm_base + off, 4096, fp_ctrl, cube_mask,
                                                shadow_key ? shadow : NULL, hlsl, sizeof(hlsl));
    if (n <= 0 && shadow_key) {''')
rep('''        n = rsx_fp_decompile_shadow_ex(vm_base + off, 4096, fp_ctrl, cube_mask, NULL,
                                       hlsl, sizeof(hlsl));
    }''', '''        n = xmasks ? rsx_fp_decompile_shadow_color_expand_ex(vm_base + off, 4096, fp_ctrl, cube_mask, NULL,
                                                             xg, xe, hlsl, sizeof(hlsl))
                   : rsx_fp_decompile_shadow_ex(vm_base + off, 4096, fp_ctrl, cube_mask, NULL,
                                                hlsl, sizeof(hlsl));
    }''')
rep('''    if (shtrace_on()) { char x[24]; snprintf(x, sizeof x, "instrs=%d", n);
                        shtrace("translated", fp_addr, uhash, cube_mask, rtfmt, nrt, x); }''',
    '''    if (shtrace_on()) { char x[24]; snprintf(x, sizeof x, "instrs=%d", n);
                        shtrace("translated", fp_addr, uhash, cube_mask, rtfmt, nrt, x); }
    /* RSX_COLOR_XFER sRGB output: the packer's linear-to-sRGB on the colour
     * the program exports, before the blend unit (rsx_fp_apply_srgb_output).
     * A program text the rewrite cannot parse keeps its plain output, and
     * says so: compiling nothing would drop the draw instead. */
    if (xs && rsx_fp_apply_srgb_output(hlsl, sizeof(hlsl)) <= 0) {
        static int _n = 0; if (PS3_LOG_FIRST(_n, 8))
            fprintf(stderr, "[XFER] fp=0x%08X: sRGB output not applicable to this program text;"
                            " compiled without it%c", fp_addr, 10);
        xs = 0;
    }''')

# 5. store the key
rep('''    s_d3d.vp_fp[s_d3d.vp_fp_n].shadow_key = shadow_key;
    s_d3d.vp_fp[s_d3d.vp_fp_n].pso     = pso;''', '''    s_d3d.vp_fp[s_d3d.vp_fp_n].shadow_key = shadow_key;
    s_d3d.vp_fp[s_d3d.vp_fp_n].xf_srgb = xs;
    memcpy(s_d3d.vp_fp[s_d3d.vp_fp_n].xf_gamma, xg, sizeof xg);
    memcpy(s_d3d.vp_fp[s_d3d.vp_fp_n].xf_expand, xe, sizeof xe);
    s_d3d.vp_fp[s_d3d.vp_fp_n].pso     = pso;''')

# 6. per-draw request (mode mask) next to dr_color_xfer
rep('''static void rsxi_on_draw(u32 d, const D3D12DrawRecord* dr, int cur_rt, const int* cur_m,''',
    '''/* RSX_COLOR_XFER=<mask>: honour the transfers dr_color_xfer reports when
 * compiling the draw's fragment program. 0x1 texture gamma, 0x2 sign
 * expansion, 0x4 sRGB output (SET_SHADER_PACKER); 7 = all. Unset: none,
 * exactly as before (NULL request, all-zero PSO key fields). */
static u32 xfer_mode(void)
{
    static int m = -1;
    if (m < 0) { const char* e = getenv("RSX_COLOR_XFER"); m = e ? (int)(strtoul(e, NULL, 0) & 7u) : 0; }
    return (u32)m;
}
static const rsx_color_xfer* dr_xfer_req(const D3D12DrawRecord* dr, rsx_color_xfer* x)
{
    const u32 m = xfer_mode();
    if (!m || !dr_color_xfer(dr, dr->rt_fmt, x)) return NULL;
    if (!(m & 1u)) memset(x->gamma, 0, sizeof x->gamma);
    if (!(m & 2u)) memset(x->expand, 0, sizeof x->expand);
    if (!(m & 4u)) x->srgb_output = 0;
    return x;
}

static void rsxi_on_draw(u32 d, const D3D12DrawRecord* dr, int cur_rt, const int* cur_m,''')

# 7. call sites
rep('''            rsx_fp_shadow_desc _sd[RSX_DSP_NUM_TEXTURES];
            u32 _sk = dr_shadow(dr, _sd);
            fp_memo* _fm = &s_fpm[_d];
            _fm->pso =
            vp_get_fp_pso(dr->vs_idx, dr->fp_addr, dr->blend_key,
                          dr_num_rts(dr),
                          dr->rt_off ? rsx_surface_dxgi(dr->rt_fmt)
                                     : DXGI_FORMAT_R8G8B8A8_UNORM,
                          dr->fp_exp32, dr->cmask, dr->cull, dr_cube_mask(dr), _sd, _sk,
                          dr_depth_key(dr));''', '''            rsx_fp_shadow_desc _sd[RSX_DSP_NUM_TEXTURES];
            u32 _sk = dr_shadow(dr, _sd);
            rsx_color_xfer _xf;
            fp_memo* _fm = &s_fpm[_d];
            _fm->pso =
            vp_get_fp_pso(dr->vs_idx, dr->fp_addr, dr->blend_key,
                          dr_num_rts(dr),
                          dr->rt_off ? rsx_surface_dxgi(dr->rt_fmt)
                                     : DXGI_FORMAT_R8G8B8A8_UNORM,
                          dr->fp_exp32, dr->cmask, dr->cull, dr_cube_mask(dr), _sd, _sk,
                          dr_depth_key(dr), dr_xfer_req(dr, &_xf));''')
rep('''                const u32 _sk = dr->fp_addr && !_fmu ? dr_shadow(dr, _sd) : 0;''',
    '''                const u32 _sk = dr->fp_addr && !_fmu ? dr_shadow(dr, _sd) : 0;
                rsx_color_xfer _xf;''')
rep('''                                                dr_cube_mask(dr), _sd, _sk,
                                                dr_depth_key(dr)) : NULL;''', '''                                                dr_cube_mask(dr), _sd, _sk,
                                                dr_depth_key(dr), dr_xfer_req(dr, &_xf)) : NULL;''')

# 8. RSXI / RSX_XFER_LOG: "host_xfer" and "-- not applied" stay truthful
p.write_text(s, encoding='utf-8')
print('ok')

s = p.read_text(encoding='utf-8')
rep('''    fprintf(f, ",\\"shader_packer\\":\\"0x%08X\\",\\"srgb_output\\":%d,\\"host_xfer\\":\\"none\\"",
            dr->g_shader_packer, xf.srgb_output);''',
    '''    if (xfer_mode())   /* RSX_COLOR_XFER: what the compile was asked to honour */
        fprintf(f, ",\\"shader_packer\\":\\"0x%08X\\",\\"srgb_output\\":%d,\\"host_xfer\\":\\"mode_0x%X\\"",
                dr->g_shader_packer, xf.srgb_output, xfer_mode());
    else
        fprintf(f, ",\\"shader_packer\\":\\"0x%08X\\",\\"srgb_output\\":%d,\\"host_xfer\\":\\"none\\"",
                dr->g_shader_packer, xf.srgb_output);''')
rep('''              fprintf(stderr, " -- not applied%c", 10);''',
    '''              if (xfer_mode()) fprintf(stderr, " -- RSX_COLOR_XFER=0x%X applies it%c", xfer_mode(), 10);
              else fprintf(stderr, " -- not applied%c", 10);''')
p.write_text(s, encoding='utf-8')
print('ok2')
