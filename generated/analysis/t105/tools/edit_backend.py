MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T105: wire RACE_PRESENT_PROBE into rsx_d3d12_backend.c (ps3recomp-t105)."""
import pathlib
W = pathlib.Path((MS_ROOT + r'\ps3recomp-t105'))
p = W / 'libs/video/rsx_d3d12_backend.c'
s = p.read_bytes().decode('utf-8')
nl = '\r\n' if '\r\n' in s else '\n'
blk = (pathlib.Path(__file__).parent / 'rpp_block.c').read_text(encoding='utf-8').replace('\r\n', '\n').replace('\n', nl)


def rep(old, new):
    global s
    old = old.replace('\n', nl); new = new.replace('\n', nl)
    assert s.count(old) == 1, (old, s.count(old))
    s = s.replace(old, new)


rep('#include "ps3emu/race_display_diag.h"  /* CELLMARK_DUMP_PRESENT_ONLY, RTPOOL_LOG (T100) */\n',
    '#include "ps3emu/race_display_diag.h"  /* CELLMARK_DUMP_PRESENT_ONLY, RTPOOL_LOG (T100) */\n'
    '#include "ps3emu/race_present_probe.h" /* RACE_PRESENT_PROBE: where a race frame turns black */\n')
rep('static void render_frame(void)\n{\n', blk + 'static void render_frame(void)\n{\n')
rep('    s_dbg_last_draws = s_d3d.draw_count;\n',
    '    rpp_note_replay(!keep_targets);   /* RACE_PRESENT_PROBE */\n    s_dbg_last_draws = s_d3d.draw_count;\n')
rep('    composite_present(fi);\n',
    '    composite_present(fi);\n    rpp_maybe_queue(fi);   /* RACE_PRESENT_PROBE: after every host composite */\n')
rep('    rsxi_frame_finish();        /* RSXI: one GPU wait, write the captured frame */\n',
    '    rsxi_frame_finish();        /* RSXI: one GPU wait, write the captured frame */\n'
    '    rpp_collect();              /* RACE_PRESENT_PROBE */\n')
rep('        const unsigned op0 = cellGcm_stall_op(GSW_OP_SWAP);   /* GCM_STALL_MS */\n',
    '        const unsigned op0 = cellGcm_stall_op(GSW_OP_SWAP);   /* GCM_STALL_MS */\n'
    '        const u32 sc_idx = s_d3d.swap_chain->lpVtbl->GetCurrentBackBufferIndex(s_d3d.swap_chain);\n')
rep('        pp_present();\n        cellGcm_stall_op(op0);\n',
    '        pp_present();\n        cellGcm_stall_op(op0);\n'
    '        rpp_after_present(phr, sc_idx, dumping);   /* RACE_PRESENT_PROBE */\n')
p.write_bytes(s.encode('utf-8'))
print('ok')
