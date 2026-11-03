"""T133: decode SET_ANTI_ALIASING_CONTROL (0x1D7C) into rsx_state and record it in RSXI (one-shot)."""
import sys
root = sys.argv[1]


def patch(path, pairs):
    s = open(path, newline='', encoding='utf-8').read().replace('\r\n', '\n')
    for a, b in pairs:
        assert s.count(a) == 1, (path, a[:80], s.count(a))
        s = s.replace(a, b)
    open(path, 'w', newline='', encoding='utf-8').write(s.replace('\n', '\r\n'))


V = root + '/libs/video/'
patch(V + 'rsx_commands.h', [
    ('#define NV4097_SET_ZSTENCIL_CLEAR_VALUE        0x00001D8C\n',
     '#define NV4097_SET_ZSTENCIL_CLEAR_VALUE        0x00001D8C\n'
     '/* [0] multisample enable, [4] alpha to coverage, [8] alpha to one, [31:16] sample mask */\n'
     '#define NV4097_SET_ANTI_ALIASING_CONTROL       0x00001D7C\n'),
    ('    u32 color_mask_mrt, blend_enable_mrt, mrt_regs_set;\n',
     '    u32 color_mask_mrt, blend_enable_mrt, mrt_regs_set;\n'
     '    /* SET_ANTI_ALIASING_CONTROL (0x1D7C), recorded for RSXI only: the D3D12\n'
     '     * targets are single-sampled, so neither alpha to coverage nor the sample\n'
     '     * mask is applied. aa_ctl_set: the register was written at least once. */\n'
     '    u32 aa_ctl, aa_ctl_set;\n'),
])
patch(V + 'rsx_commands.c', [
    ('''    if (method == NV4097_SET_BLEND_ENABLE_MRT) {
        state->blend_enable_mrt = data;
        state->mrt_regs_set |= 2u;
        return 0;
    }
''', '''    if (method == NV4097_SET_BLEND_ENABLE_MRT) {
        state->blend_enable_mrt = data;
        state->mrt_regs_set |= 2u;
        return 0;
    }
    if (method == NV4097_SET_ANTI_ALIASING_CONTROL) {
        state->aa_ctl = data;
        state->aa_ctl_set = 1;
        return 0;
    }
'''),
])
patch(V + 'rsx_d3d12_backend.c', [
    ('    u32 g_mrt_cmask, g_mrt_blend, g_mrt_set;   /* COLOR_MASK_MRT, BLEND_ENABLE_MRT, written bits (RSXI) */\n',
     '    u32 g_mrt_cmask, g_mrt_blend, g_mrt_set;   /* COLOR_MASK_MRT, BLEND_ENABLE_MRT, written bits (RSXI) */\n'
     '    u32 g_aa_ctl, g_aa_set;                    /* ANTI_ALIASING_CONTROL and whether it was written (RSXI) */\n'),
    ('               dr->g_mrt_cmask = dr->g_mrt_blend = dr->g_mrt_set = 0; ',
     '               dr->g_mrt_cmask = dr->g_mrt_blend = dr->g_mrt_set = 0; dr->g_aa_ctl = dr->g_aa_set = 0; '),
    ('      dr->g_mrt_set = st->mrt_regs_set;\n',
     '      dr->g_mrt_set = st->mrt_regs_set;\n'
     '      dr->g_aa_ctl = st->aa_ctl; dr->g_aa_set = st->aa_ctl_set;\n'),
    (r'''\"mrt_regs\":{\"cmask\":\"0x%04X\",\"blend\":\"0x%X\",\"set\":%u},''',
     r'''\"mrt_regs\":{\"cmask\":\"0x%04X\",\"blend\":\"0x%X\",\"set\":%u},\"aa_ctl\":{\"value\":\"0x%08X\",\"set\":%u},'''),
    ('dr->g_mrt_cmask & 0xFFFFu, dr->g_mrt_blend, dr->g_mrt_set, dr->blend,',
     'dr->g_mrt_cmask & 0xFFFFu, dr->g_mrt_blend, dr->g_mrt_set, dr->g_aa_ctl, dr->g_aa_set, dr->blend,'),
])
print('ok')
