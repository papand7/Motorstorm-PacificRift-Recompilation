"""T145: RSX_SHADER_WINDOW=1 -- WPOS in the guest's SET_SHADER_WINDOW system.

One-shot edit of the ps3recomp-t145 tree (CRLF kept). Every anchor must match
exactly once; nothing is written unless all of them do.

  python patch_t145.py <ps3recomp-t145>
"""
import sys
from pathlib import Path

R = Path(sys.argv[1])
V = R / 'libs' / 'video'
edits = {
    'rsx_commands.h': [
        ('#define NV4097_SET_SHADER_CONTROL               0x00001D60\n',
         '#define NV4097_SET_SHADER_CONTROL               0x00001D60\n'
         '/* height [11:0], origin [15:12] (1 = bottom), pixel centre [19:16] (rsx_shader_window.h) */\n'
         '#define NV4097_SET_SHADER_WINDOW                0x00001D88\n'),
        ('    u32 aa_ctl, aa_ctl_set;\n',
         '    u32 aa_ctl, aa_ctl_set;\n'
         '    /* SET_SHADER_WINDOW (0x1D88): the system WPOS is expressed in.\n'
         '     * shader_window_set: the register was written at least once. */\n'
         '    u32 shader_window, shader_window_set;\n'),
    ],
    'rsx_commands.c': [
        ('    if (method == NV4097_SET_ANTI_ALIASING_CONTROL) {\n'
         '        state->aa_ctl = data;\n'
         '        state->aa_ctl_set = 1;\n'
         '        return 0;\n'
         '    }\n',
         '    if (method == NV4097_SET_ANTI_ALIASING_CONTROL) {\n'
         '        state->aa_ctl = data;\n'
         '        state->aa_ctl_set = 1;\n'
         '        return 0;\n'
         '    }\n'
         '    if (method == NV4097_SET_SHADER_WINDOW) {\n'
         '        state->shader_window = data;\n'
         '        state->shader_window_set = 1;\n'
         '        return 0;\n'
         '    }\n'),
    ],
    'rsx_d3d12_backend.c': [
        ('#include "rsx_color_xfer.h"   /* sRGB output / texture gamma the guest asks for */\n',
         '#include "rsx_color_xfer.h"   /* sRGB output / texture gamma the guest asks for */\n'
         '#include "rsx_shader_window.h"   /* RSX_SHADER_WINDOW: WPOS in the guest window */\n'),
        ('    u32 g_shader_packer;   /* SET_SHADER_PACKER at draw time (nonzero = sRGB output) */\n',
         '    u32 g_shader_packer;   /* SET_SHADER_PACKER at draw time (nonzero = sRGB output) */\n'
         '    u32 g_shader_window, g_shader_window_set;   /* SET_SHADER_WINDOW and whether it was written */\n'),
        ('    u8 xf_srgb, xf_gamma[16], xf_expand[16];\n    ID3D12PipelineState* pso;\n} VPFPEntry;\n',
         '    u8 xf_srgb, xf_gamma[16], xf_expand[16];\n'
         '    u32 wpos_key;           /* RSX_SHADER_WINDOW (PSO key): rsx_sw_key, 0 = WPOS read as SV_Position */\n'
         '    ID3D12PipelineState* pso;\n} VPFPEntry;\n'),
        ('static ID3D12PipelineState* vp_get_fp_pso(int vs_idx, u32 fp_addr, u32 blend, int nrt,\n'
         '                                          DXGI_FORMAT rtfmt, int exp32, u32 cmask, u32 cull,\n',
         '/* RSX_SHADER_WINDOW=1 (read once, off by default): the draw\'s window\n'
         ' * (rsx_sw_key), set by the two callers right before vp_get_fp_pso. Only a\n'
         ' * program that reads WPOS takes it into its key and its text. */\n'
         'static u32 s_fp_wpos_req;\n'
         'static u64 s_wpos_draws, s_wpos_progs;\n'
         'static int shader_window_on(void)\n'
         '{\n'
         '    static int on = -1;\n'
         '    if (on < 0) on = rsx_sw_switch_parse(getenv("RSX_SHADER_WINDOW"));\n'
         '    return on;\n'
         '}\n'
         'static u32 dr_wpos_req(const D3D12DrawRecord* dr)\n'
         '{\n'
         '    if (!shader_window_on()) return 0u;\n'
         '    const u32 k = rsx_sw_key(dr->g_shader_window, dr->g_shader_window_set);\n'
         '    if (!k && dr->g_shader_window_set) { static int _n = 0; if (PS3_LOG_FIRST(_n, 8))\n'
         '        fprintf(stderr, "[WPOS] SET_SHADER_WINDOW 0x%08X: origin/centre undefined, WPOS read as before%c",\n'
         '                dr->g_shader_window, 10); }\n'
         '    return k;\n'
         '}\n'
         'static ID3D12PipelineState* vp_get_fp_pso(int vs_idx, u32 fp_addr, u32 blend, int nrt,\n'
         '                                          DXGI_FORMAT rtfmt, int exp32, u32 cmask, u32 cull,\n'),
        ('    const int xmasks = (rsx_fp_texture_gamma_units(vm_base + off, fsz, xg) |\n'
         '                        rsx_fp_texture_expand_units(vm_base + off, fsz, xe)) != 0;\n',
         '    const int xmasks = (rsx_fp_texture_gamma_units(vm_base + off, fsz, xg) |\n'
         '                        rsx_fp_texture_expand_units(vm_base + off, fsz, xe)) != 0;\n'
         '    /* RSX_SHADER_WINDOW: the window keys only a program that reads WPOS. */\n'
         '    const u32 wk = s_fp_wpos_req && rsx_fp_wpos_reads(vm_base + off, fsz) ? s_fp_wpos_req : 0u;\n'
         '    if (wk) s_wpos_draws++;\n'),
        # its own reject step: test_t110_pins pins the xf_expand line of the key verbatim
        ('        if (s_d3d.vp_fp[i].ucode_hash != uhash) continue;   /* cheap reject first */\n',
         '        if (s_d3d.vp_fp[i].ucode_hash != uhash) continue;   /* cheap reject first */\n'
         '        else if (s_d3d.vp_fp[i].wpos_key != wk) continue;   /* RSX_SHADER_WINDOW key */\n'),
        ('        xs = 0;\n'
         '    }\n'
         '    /* FP_LIST=1: every program the title actually compiles, with its size. A\n',
         '        xs = 0;\n'
         '    }\n'
         '    /* RSX_SHADER_WINDOW: WPOS reads in the guest window\'s origin, centre and\n'
         '     * height (rsx_fp_apply_shader_window). A text it cannot rewrite keeps\n'
         '     * SV_Position and says so. */\n'
         '    if (wk) {\n'
         '        const int _r = rsx_fp_apply_shader_window(hlsl, sizeof(hlsl), wk);\n'
         '        if (_r > 0) s_wpos_progs++;\n'
         '        { static int _n = 0; if (PS3_LOG_FIRST(_n, 16))\n'
         '            fprintf(stderr, "[WPOS] fp=0x%08X window=0x%05X (h=%u origin=%s centre=%s): %d read(s) %s%c",\n'
         '                    fp_addr, wk & 0xFFFFFu, rsx_sw_height(wk), rsx_sw_origin(wk) ? "bottom" : "top",\n'
         '                    rsx_sw_center(wk) ? "integer" : "half", _r,\n'
         '                    _r > 0 ? "remapped" : "NOT remapped (text not rewritable)", 10); }\n'
         '    }\n'
         '    /* FP_LIST=1: every program the title actually compiles, with its size. A\n'),
        ('    memcpy(s_d3d.vp_fp[s_d3d.vp_fp_n].xf_expand, xe, sizeof xe);\n'
         '    s_d3d.vp_fp[s_d3d.vp_fp_n].pso     = pso;\n',
         '    memcpy(s_d3d.vp_fp[s_d3d.vp_fp_n].xf_expand, xe, sizeof xe);\n'
         '    s_d3d.vp_fp[s_d3d.vp_fp_n].wpos_key = wk;\n'
         '    s_d3d.vp_fp[s_d3d.vp_fp_n].pso     = pso;\n'),
        ('            fp_memo* _fm = &s_fpm[_d];\n',
         '            fp_memo* _fm = &s_fpm[_d];\n'
         '            s_fp_wpos_req = dr_wpos_req(dr);\n'),
        ('                rsx_color_xfer _xf;\n'
         '                ID3D12PipelineState* dpso = _fmu ? _fm->pso :\n',
         '                rsx_color_xfer _xf;\n'
         '                s_fp_wpos_req = dr_wpos_req(dr);\n'
         '                ID3D12PipelineState* dpso = _fmu ? _fm->pso :\n'),
        ('               dr->g_shader_packer = 0; return; }\n',
         '               dr->g_shader_window = dr->g_shader_window_set = 0;\n'
         '               dr->g_shader_packer = 0; return; }\n'),
        ('    dr->g_shader_packer = st->shader_packer;\n',
         '    dr->g_shader_packer = st->shader_packer;\n'
         '    dr->g_shader_window = st->shader_window; dr->g_shader_window_set = st->shader_window_set;\n'),
        ('                dr->g_shader_packer, xf.srgb_output);\n'
         '    fprintf(f, ",\\"raster\\":{',
         '                dr->g_shader_packer, xf.srgb_output);\n'
         '    fprintf(f, ",\\"shader_window\\":\\"0x%08X\\",\\"shader_window_set\\":%u,\\"wpos_remap\\":%u",\n'
         '            dr->g_shader_window, dr->g_shader_window_set, dr_wpos_req(dr) ? 1u : 0u);\n'
         '    fprintf(f, ",\\"raster\\":{'),
    ],
}

out = {}
for name, reps in edits.items():
    p = V / name
    raw = p.read_bytes()
    crlf = b'\r\n' in raw
    text = raw.decode('utf-8').replace('\r\n', '\n')
    for a, b in reps:
        n = text.count(a)
        if n != 1:
            sys.exit('%s: anchor matches %d times: %r' % (name, n, a[:80]))
        text = text.replace(a, b)
    out[p] = text.replace('\n', '\r\n') if crlf else text
for p, t in out.items():
    p.write_bytes(t.encode('utf-8'))
    print('patched', p)
