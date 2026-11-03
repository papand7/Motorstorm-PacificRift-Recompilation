"""One-off: strip the VPVB_GROW_AT_FRAME_END correction out of edit_backend.py (it lives in edit_fix.py)."""
from pathlib import Path
p = Path(__file__).with_name('edit_backend.py')
s = p.read_text(encoding='utf-8')


def cut(a, b):
    global s
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)


cut('''
/* VPVB_GROW_AT_FRAME_END=1 (T91 correction, off by default): grow the vertex
 * buffer after the frame's submission, when this frame's bytes are no longer
 * needed by the CPU, instead of before its replay -- where vp_vb_grow() copies
 * up to 256 MB back out of the old write-combined UPLOAD mapping. The old
 * buffer is kept until the next render_frame()'s GPU drain. */
static int s_vpvb_at_end = -1;
static rfp_vb_retire s_vb_retire;
''', '')
cut('''        if (s_vpvb_at_end > 0) {   /* a submitted frame may still read it */
            ID3D12Resource* prev = (ID3D12Resource*)rfp_vb_retire_put(&s_vb_retire, s_d3d.vp_vb,
                                                                      (u64)old_cap * 256u * 2u);
            if (prev) prev->lpVtbl->Release(prev);
        } else
            s_d3d.vp_vb->lpVtbl->Release(s_d3d.vp_vb);''', '''        s_d3d.vp_vb->lpVtbl->Release(s_d3d.vp_vb);''')
cut('''    if (s_vpvb_at_end < 0) {
        const char* e = getenv("VPVB_GROW_AT_FRAME_END"); s_vpvb_at_end = (e && atoi(e) > 0) ? 1 : 0;
        if (s_vpvb_at_end) fprintf(stderr, "[VPVB] growth at frame end (VPVB_GROW_AT_FRAME_END)%c", 10);
    }
''', '')
cut('''    /* The drain covers every submitted frame: a buffer retired by a growth at
     * the last frame's end is no longer read. */
    { ID3D12Resource* old = (ID3D12Resource*)rfp_vb_retire_take(&s_vb_retire);
      if (old) old->lpVtbl->Release(old); }
''', '')
cut('''    if (!s_vpvb_at_end && s_d3d.vp_vb && s_d3d.vp_vb_mapped) {''', '''    if (s_d3d.vp_vb && s_d3d.vp_vb_mapped) {''')
cut('''    /* VPVB_GROW_AT_FRAME_END: this frame is submitted and its per-frame offset
     * reset, so growing here copies nothing; the replaced buffer is retired. */
    if (s_vpvb_at_end > 0 && s_d3d.vp_vb && s_d3d.vp_vb_mapped) {
        rfp_at(RFP_VB_GROW);
        const u32 grow_to = vpvb_end_frame(&s_vpvb);
        if (grow_to) vp_vb_grow(grow_to);
        rfp_at(RFP_TAIL);
    }

''', '')
cut('"""T91: RF_PHASE_MS render_frame phase instrumentation + VPVB_GROW_AT_FRAME_END (off by default)."""',
    '"""T91 instrumentation: RF_PHASE_MS render_frame phases (off by default)."""')
p.write_text(s, encoding='utf-8')
print('split ok')
