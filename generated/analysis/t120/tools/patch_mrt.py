"""T120: decode COLOR_MASK_MRT / BLEND_ENABLE_MRT into rsx_state and record them in RSXI (one-shot)."""
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
    ('#define NV4097_SET_STENCIL_MASK                 0x0000032C  /* write mask */\n',
     '#define NV4097_SET_STENCIL_MASK                 0x0000032C  /* write mask */\n'
     '#define NV4097_SET_BLEND_ENABLE_MRT             0x0000036C  /* bits 1..3: targets B..D */\n'
     '#define NV4097_SET_COLOR_MASK_MRT               0x00000370  /* nibble per target B..D at [4i+3:4i] */\n'),
    ('    /* Color mask — bits: [0] B, [8] G, [16] R, [24] A */\n    u32 color_mask;\n',
     '    /* Color mask — bits: [0] B, [8] G, [16] R, [24] A */\n    u32 color_mask;\n'
     '    /* MRT targets B..D: COLOR_MASK_MRT (0x0370) and BLEND_ENABLE_MRT (0x036C).\n'
     '     * mrt_regs_set: bit 0 = 0x0370 written, bit 1 = 0x036C written (a never-\n'
     '     * written register is not the same evidence as a written 0). Recorded\n'
     '     * for RSXI only; the D3D12 guest-FP pipeline still mirrors target A. */\n'
     '    u32 color_mask_mrt, blend_enable_mrt, mrt_regs_set;\n'),
])
patch(V + 'rsx_commands.c', [
    ('''    /* Color mask */
    if (method == NV4097_SET_COLOR_MASK) {
        state->color_mask = data;
        state->color_mask_dirty = 1;
        return 0;
    }
''', '''    /* Color mask */
    if (method == NV4097_SET_COLOR_MASK) {
        state->color_mask = data;
        state->color_mask_dirty = 1;
        return 0;
    }
    if (method == NV4097_SET_COLOR_MASK_MRT) {
        state->color_mask_mrt = data;
        state->mrt_regs_set |= 1u;
        return 0;
    }
    if (method == NV4097_SET_BLEND_ENABLE_MRT) {
        state->blend_enable_mrt = data;
        state->mrt_regs_set |= 2u;
        return 0;
    }
'''),
])
patch(V + 'rsx_d3d12_backend.c', [
    ('    u64 g_ds_key;          /* rsx_ds_key: full guest depth/stencil state (RSX_DEPTH_STATE) */\n',
     '    u64 g_ds_key;          /* rsx_ds_key: full guest depth/stencil state (RSX_DEPTH_STATE) */\n'
     '    u32 g_mrt_cmask, g_mrt_blend, g_mrt_set;   /* COLOR_MASK_MRT, BLEND_ENABLE_MRT, written bits (RSXI) */\n'),
    ('    if (!st) { dr->g_depth = dr->g_stencil = 0; dr->g_ds_key = 0; dr->g_sc_x',
     '    if (!st) { dr->g_depth = dr->g_stencil = 0; dr->g_ds_key = 0;\n'
     '               dr->g_mrt_cmask = dr->g_mrt_blend = dr->g_mrt_set = 0; dr->g_sc_x'),
    ('      dr->g_ds_key = rsx_ds_key(&ds);\n',
     '      dr->g_ds_key = rsx_ds_key(&ds);\n'
     '      dr->g_mrt_cmask = st->color_mask_mrt; dr->g_mrt_blend = st->blend_enable_mrt;\n'
     '      dr->g_mrt_set = st->mrt_regs_set;\n'),
    (r'''\"ds_key\":\"0x%012llX\",\"blend\":%d,"''',
     r'''\"ds_key\":\"0x%012llX\",\"mrt_regs\":{\"cmask\":\"0x%04X\",\"blend\":\"0x%X\",\"set\":%u},\"blend\":%d,"'''),
    ('(unsigned long long)dr->g_ds_key, dr->blend,',
     '(unsigned long long)dr->g_ds_key, dr->g_mrt_cmask & 0xFFFFu, dr->g_mrt_blend, dr->g_mrt_set, dr->blend,'),
])
print('ok')
