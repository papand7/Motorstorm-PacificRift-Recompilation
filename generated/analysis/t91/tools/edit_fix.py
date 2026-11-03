"""T91 correction on top of edit_backend.py: VPVB_GROW_AT_FRAME_END=1 (off by default)."""
from pathlib import Path
import sys
p = Path(sys.argv[1]) / 'libs/video/rsx_d3d12_backend.c'
s = p.read_text(encoding='utf-8')


def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("""static inline void rfp_at(int phase) { if (s_rfp_ms > 0) rfp_mark(&s_rfp, rfp_now_us(), phase); }
""", """static inline void rfp_at(int phase) { if (s_rfp_ms > 0) rfp_mark(&s_rfp, rfp_now_us(), phase); }

/* VPVB_GROW_AT_FRAME_END=1 (T91 correction, off by default): grow the vertex
 * buffer after the frame's submission, when this frame's bytes are no longer
 * needed by the CPU, instead of before its replay -- where vp_vb_grow() copies
 * up to 256 MB back out of the old write-combined UPLOAD mapping. The old
 * buffer is kept until the next render_frame()'s GPU drain. */
static int s_vpvb_at_end = -1;
static rfp_vb_retire s_vb_retire;
""")
rep("""                   s_d3d.vp_vb_offset);
        s_d3d.vp_vb->lpVtbl->Release(s_d3d.vp_vb);""", """                   s_d3d.vp_vb_offset);
        if (s_vpvb_at_end > 0) {   /* a submitted frame may still read it */
            ID3D12Resource* prev = (ID3D12Resource*)rfp_vb_retire_put(&s_vb_retire, s_d3d.vp_vb,
                                                                      (u64)old_cap * 256u * 2u);
            if (prev) prev->lpVtbl->Release(prev);
        } else
            s_d3d.vp_vb->lpVtbl->Release(s_d3d.vp_vb);""")
rep("""    if (s_rfp_ms > 0) {
        rfp_begin(&s_rfp, rfp_now_us());""", """    if (s_vpvb_at_end < 0) {
        const char* e = getenv("VPVB_GROW_AT_FRAME_END"); s_vpvb_at_end = (e && atoi(e) > 0) ? 1 : 0;
        if (s_vpvb_at_end) fprintf(stderr, "[VPVB] growth at frame end (VPVB_GROW_AT_FRAME_END)%c", 10);
    }
    if (s_rfp_ms > 0) {
        rfp_begin(&s_rfp, rfp_now_us());""")
rep("""    rfp_at(RFP_VB_GROW);

    /* The GPU is idle: if this frame's vertex-program geometry did not fit,
     * grow the buffer before the next frame records into it. */
    if (s_d3d.vp_vb && s_d3d.vp_vb_mapped) {""", """    rfp_at(RFP_VB_GROW);
    /* The drain covers every submitted frame: a buffer retired by a growth at
     * the last frame's end is no longer read. */
    { ID3D12Resource* old = (ID3D12Resource*)rfp_vb_retire_take(&s_vb_retire);
      if (old) old->lpVtbl->Release(old); }

    /* The GPU is idle: if this frame's vertex-program geometry did not fit,
     * grow the buffer before the next frame records into it. */
    if (!s_vpvb_at_end && s_d3d.vp_vb && s_d3d.vp_vb_mapped) {""")
rep("""    s_d3d.frame_count++;

    /* RSX_HEARTBEAT_MS=<ms>""", """    s_d3d.frame_count++;

    /* VPVB_GROW_AT_FRAME_END: this frame is submitted and its per-frame offset
     * reset, so growing here copies nothing; the replaced buffer is retired. */
    if (s_vpvb_at_end > 0 && s_d3d.vp_vb && s_d3d.vp_vb_mapped) {
        rfp_at(RFP_VB_GROW);
        const u32 grow_to = vpvb_end_frame(&s_vpvb);
        if (grow_to) vp_vb_grow(grow_to);
        rfp_at(RFP_TAIL);
    }

    /* RSX_HEARTBEAT_MS=<ms>""")
p.write_text(s, encoding='utf-8')
print('ok')
