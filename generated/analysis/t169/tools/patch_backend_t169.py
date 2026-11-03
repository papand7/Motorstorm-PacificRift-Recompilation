"""T169: applies the RSX_VISUAL_PROFILE and RSX_VISUAL_DIAG hooks. Each anchor must match exactly once, else nothing
is written. usage: py -3 patch_backend_t169.py <tree>"""
import sys
from pathlib import Path

p = Path(sys.argv[1]) / 'libs/video/rsx_d3d12_backend.c'
s = p.read_bytes().decode('utf-8')
NL = '\r\n'
EDITS = [
    ('#include "rsx_vehicle_diag.h"  /* RSX_VEHICLE_DIAG read-only per-draw line (T165) */' + NL,
     '#include "rsx_vehicle_diag.h"  /* RSX_VEHICLE_DIAG read-only per-draw line (T165) */' + NL +
     '#include "rsx_visual_diag.h"   /* RSX_VISUAL_DIAG read-only state and work lines (T169) */' + NL +
     '#include "rsx_visual_profile.h" /* RSX_VISUAL_PROFILE: the guest-requested corrections as one opt-in (T169) */' + NL),
    ('#define CreateGraphicsPipelineState(self, ...)       CreateGraphicsPipelineState((GP_N(GP_C_PSO_CREATE, 1), self), __VA_ARGS__)' + NL,
     '#define CreateGraphicsPipelineState(self, ...)       CreateGraphicsPipelineState((GP_N(GP_C_PSO_CREATE, 1), self), __VA_ARGS__)' + NL +
     'static rsx_visdiag s_visd;   /* RSX_VISUAL_DIAG */' + NL +
     '#define D3DCompile(...)                              (s_visd.w.compiles++, D3DCompile(__VA_ARGS__))' + NL),
    ('    if (added) {' + NL + '        D3D12_SAMPLER_DESC d; gs_xl_desc(&x, &d);' + NL,
     '    if (added) {' + NL + '        s_visd.w.samplers_new++;' + NL + '        D3D12_SAMPLER_DESC d; gs_xl_desc(&x, &d);' + NL),
    ('    cl->lpVtbl->SetGraphicsRootDescriptorTable(cl, GS_ROOT_BASE + (UINT)u, g);' + NL,
     '    cl->lpVtbl->SetGraphicsRootDescriptorTable(cl, GS_ROOT_BASE + (UINT)u, g);' + NL + '    s_visd.w.sampler_binds++;' + NL),
    ('    s_texmip.uploads++;' + NL,
     '    s_texmip.uploads++;' + NL + '    s_visd.w.uploads++; s_visd.w.upload_bytes += _nb0;' + NL),
    ('static int d3d12_init(void* ud, u32 width, u32 height)' + NL + '{' + NL,
     'static int d3d12_init(void* ud, u32 width, u32 height)' + NL + '{' + NL +
     '    { const unsigned vm = rsx_visual_profile_parse(getenv("RSX_VISUAL_PROFILE"));' + NL +
     '      for (unsigned i = 0; vm && i < RSX_VISUAL_SWITCH_N; i++) {' + NL +
     '          const char* v = rsx_visual_profile_value(vm, i, getenv(rsx_visual_switches[i].name));' + NL +
     '          if (v) _putenv_s(rsx_visual_switches[i].name, v);' + NL +
     '      }' + NL +
     '      if (vm) fprintf(stderr, "[visual] RSX_VISUAL_PROFILE=0x%X%c", vm, 10); }' + NL),
    ('          rsx_vdiag_print(stderr, st, s_fpf.guest_frames, st->fragment_program_addr, primitive, count, s_rec_indexed); }' + NL,
     '          rsx_vdiag_print(stderr, st, s_fpf.guest_frames, st->fragment_program_addr, primitive, count, s_rec_indexed); }' + NL +
     '    if ((s_visd.on || !s_visd.init) && rsx_visdiag_active(&s_visd)) {' + NL +
     '        rsx_visdiag_frame(stderr, &s_visd, s_fpf.guest_frames);' + NL +
     '        if (rsx_visdiag_take(&s_visd, st->fragment_program_addr)) {' + NL +
     '            rsx_visdiag_unit vu[RSX_DSP_NUM_TEXTURES];' + NL +
     '            for (int u = 0; u < RSX_DSP_NUM_TEXTURES; u++) {' + NL +
     '                vu[u].set = (u32)dr->tex[u].set; vu[u].off = dr->tex[u].off; vu[u].fmt = dr->tex[u].fmt;' + NL +
     '                vu[u].filter = dr->tex[u].filter; vu[u].address = dr->tex[u].address; vu[u].control0 = dr->tex[u].control0;' + NL +
     '            }' + NL +
     '            rsx_visdiag_draw(stderr, s_fpf.guest_frames, st->fifo_cmd_off, st->surface_color_offset[0], st->surface_format,' + NL +
     '                             st->surface_zeta_offset, st->fragment_program_addr, st->shader_control, st->shader_packer,' + NL +
     '                             count, vu, RSX_DSP_NUM_TEXTURES);' + NL +
     '        }' + NL +
     '    }' + NL),
]
for old, new in EDITS:
    n = s.count(old)
    if n != 1:
        sys.exit(f'anchor matched {n} times, nothing written: {old[:70]!r}')
    s = s.replace(old, new)
p.write_bytes(s.encode('utf-8'))
for h in ('rsx_visual_profile.h', 'rsx_visual_diag.h'):
    q = p.parent / h
    b = q.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    q.write_bytes(b)
print('patched', len(EDITS))
