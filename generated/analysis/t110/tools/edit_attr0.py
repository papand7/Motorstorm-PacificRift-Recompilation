"""T110: route the six VP-path attribute-0 rejections through rsx_attr0_gate.h
(RSX_ATTR0_CONST=1). Each replacement must match exactly.  py -3 -I edit_attr0.py <tree>"""
import sys
from pathlib import Path

p = Path(sys.argv[1]) / 'libs/video/rsx_d3d12_backend.c'
s = p.read_text(encoding='utf-8')


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, f'{n} matches (want {count}) for:\n{old[:200]}'
    s = s.replace(old, new)


rep('#include "rsx_sampler_xlate.h" /* guest sampler words -> host sampler (RSX_GUEST_SAMPLERS) */\n',
    '#include "rsx_sampler_xlate.h" /* guest sampler words -> host sampler (RSX_GUEST_SAMPLERS) */\n'
    '#include "rsx_attr0_gate.h"    /* draws with attribute 0 off (RSX_ATTR0_CONST) */\n')

gate = '    if (!state->vertex_attribs[0].enabled) { da_fail(DA_R_POSITION_ATTRIB_DISABLED); return 0; }\n'
rep(gate, '    if (a0_drop(state)) { da_fail(DA_R_POSITION_ATTRIB_DISABLED); return 0; }\n', 6)

helper = r'''/* RSX_ATTR0_CONST=1: a VP-path draw whose attribute-0 array is off renders
 * with SET_VERTEX_DATA4F constants, as on RSX, unless rsx_attr0_gate.h says
 * it has no position to give (no guest program, or one reading no input).
 * Off: every such draw is dropped, as before. RSX_ATTR0_LOG=<n> prints the
 * first n admitted draws (program, input mask, constant v0). */
static u32 s_a0_admitted;
static int a0_drop(const rsx_state* state)
{
    static int fix = -1, logn = 0, shown = 0;
    if (fix < 0) {
        const char* e = getenv("RSX_ATTR0_CONST"); fix = (e && e[0] == '1' && !e[1]) ? 1 : 0;
        e = getenv("RSX_ATTR0_LOG"); logn = e ? atoi(e) : 0;
    }
    const int g = rsx_attr0_gate(fix, state->vertex_attribs[0].enabled, state->vp_ucode_bytes,
                                 state->vertex_attrib_input_mask);
    if (g == RSX_A0_RENDER && !state->vertex_attribs[0].enabled) {
        s_a0_admitted++;
        if (logn && !(s_a0_admitted & (s_a0_admitted - 1u)) && s_a0_admitted >= 1024u)
            fprintf(stderr, "[attr0] %u draws admitted so far%c", s_a0_admitted, 10);
        if (shown < logn) { shown++;
            fprintf(stderr, "[attr0] admitted: fp=0x%08X input_mask=0x%04X prim=%u v0=(%g,%g,%g,%g) surface_color=0x%08X%c",
                    state->shader_program, state->vertex_attrib_input_mask & 0xFFFFu, state->primitive_type,
                    state->vertex_data4f[0][0], state->vertex_data4f[0][1], state->vertex_data4f[0][2],
                    state->vertex_data4f[0][3], state->surface_color_offset[0], 10); }
    }
    return g != RSX_A0_RENDER;
}

static u32 upload_quads_vp(const rsx_state* state, u32 first, u32 count)
'''
rep('static u32 upload_quads_vp(const rsx_state* state, u32 first, u32 count)\n', helper)

p.write_text(s, encoding='utf-8')
print('ok')
