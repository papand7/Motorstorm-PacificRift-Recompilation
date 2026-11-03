"""T119 commit 1: RSX_DRAW_SPLIT stage timers in rsx_d3d12_backend.c (CRLF file; edits on LF text).

  py -3 patch_split.py <worktree>
"""
import pathlib, sys

p = pathlib.Path(sys.argv[1]) / 'libs/video/rsx_d3d12_backend.c'
raw = p.read_bytes().decode('utf-8')
assert raw.count('\r\n') == raw.count('\n')
t = raw.replace('\r\n', '\n')


def rep(a, b, n=1):
    global t
    assert t.count(a) == n, (t.count(a), a[:80])
    t = t.replace(a, b)


# 1. State, stamps and the per-frame line, next to RSX_FRAME_PERF.
rep('''static int s_fpf_on = 0;
static rfpf_state s_fpf;
''', '''static int s_fpf_on = 0;
static rfpf_state s_fpf;
/* RSX_DRAW_SPLIT=1 (with RSX_FRAME_PERF): the VP draw callbacks' time by stage
 * (ps3emu/draw_split.h), one [rsx-draw-split] line per [rsx-frame-perf] line.
 * Off: one predictable branch per stage boundary. Draw callbacks run on one
 * thread at a time (the drain), so the counters are plain. */
static int s_dspl_on = 0;
static dspl_counts s_dspl;
static u64 s_dspl_t;              /* the open stage's start (cycle counter) */
static u64 s_dspl_skip;           /* early-replay / compile ticks inside the open stage */
static u64 s_dspl_c0, s_dspl_us0; /* calibration: cycle counter and us at init */
static int s_dspl_open;           /* inside an indexed draw callback: shared helpers mark only then */
static inline void dspl_open(void) { if (s_dspl_on) { s_dspl_t = __rdtsc(); s_dspl_skip = 0; s_dspl_open = 1; } }
static inline void dspl_mark(int k)
{
    if (!s_dspl_on || !s_dspl_open) return;
    const u64 now = __rdtsc(), d = now - s_dspl_t;
    s_dspl.ticks[k] += d > s_dspl_skip ? d - s_dspl_skip : 0;
    s_dspl_t = now; s_dspl_skip = 0;
}
''')
rep('''    rfpf_init(&s_fpf, first, every, maxl);
    s_fpf_on = 1;
''', '''    rfpf_init(&s_fpf, first, every, maxl);
    s_fpf_on = 1;
    { const char* d = getenv("RSX_DRAW_SPLIT");
      if (d && d[0] == '1' && !d[1]) { s_dspl_on = 1; dspl_reset(&s_dspl); s_dspl_c0 = __rdtsc(); s_dspl_us0 = fpf_now_us(); } }
''')
rep('''        rfpf_format(b, sizeof b, s_fpf.guest_frames, s_d3d.frame_count, c, wall);
        fprintf(stderr, "%s%c", b, 10);
    }
    rfpf_reset(&s_fpf);
''', '''        rfpf_format(b, sizeof b, s_fpf.guest_frames, s_d3d.frame_count, c, wall);
        fprintf(stderr, "%s%c", b, 10);
        if (s_dspl_on) {
            const u64 us = fpf_now_us() - s_dspl_us0;
            dspl_format(b, sizeof b, s_fpf.guest_frames, &s_dspl, us ? (double)(__rdtsc() - s_dspl_c0) * 1000.0 / (double)us : 1.0);
            fprintf(stderr, "%s%c", b, 10);
        }
    }
    rfpf_reset(&s_fpf);
    if (s_dspl_on) dspl_reset(&s_dspl);
''')
rep('#include "ps3emu/rsx_frame_perf.h"     /* RSX_FRAME_PERF: per-guest-frame time split */\n',
    '#include "ps3emu/rsx_frame_perf.h"     /* RSX_FRAME_PERF: per-guest-frame time split */\n'
    '#include "ps3emu/draw_split.h"        /* RSX_DRAW_SPLIT: the draw callbacks by stage */\n#include <intrin.h>\n')

# 2. Early replays inside a stage are not that stage's time.
rep('''    const u64 ft0 = s_fpf_on ? fpf_now_us() : 0;
    render_frame();
    if (s_fpf_on) s_fpf.cur.flush_us += fpf_now_us() - ft0;
''', '''    const u64 ft0 = s_fpf_on ? fpf_now_us() : 0;
    const u64 dt0 = s_dspl_on ? __rdtsc() : 0;
    render_frame();
    if (s_fpf_on) s_fpf.cur.flush_us += fpf_now_us() - ft0;
    if (s_dspl_on) s_dspl_skip += __rdtsc() - dt0;
''')
# 3. A VS compile is not vs-stage time (the same miss rule as RSX_FRAME_PERF).
rep('''    if (s_d3d.vp_vs_n != n0 || dt >= 1000u) { s_fpf.cur.vs_miss++; s_fpf.cur.vs_miss_us += dt; }
    return r;
''', '''    if (s_d3d.vp_vs_n != n0 || dt >= 1000u) {
        s_fpf.cur.vs_miss++; s_fpf.cur.vs_miss_us += dt;
        if (s_dspl_on) s_dspl_skip += (u64)((double)dt * (double)(__rdtsc() - s_dspl_c0) / (double)(fpf_now_us() - s_dspl_us0 + 1));
    }
    return r;
''')

# 4. Stage marks: the indexed draw body (MotorStorm's race geometry).
rep('''static void d3d12_draw_indexed_body(void* ud, u32 primitive, u32 first, u32 count)
{
    s_rec_indexed = 1;
''', '''static void d3d12_draw_indexed_body(void* ud, u32 primitive, u32 first, u32 count)
{
    dspl_open();
    if (s_dspl_on) s_dspl.callbacks++;
    s_rec_indexed = 1;
''')
rep('''    u32 carry = 0;
    if (primitive == RSX_PRIMITIVE_QUADS || primitive == RSX_PRIMITIVE_TRIANGLES ||
        primitive == RSX_PRIMITIVE_TRIANGLE_STRIP || primitive == RSX_PRIMITIVE_TRIANGLE_FAN)
        carry = vp_make_room(s_d3d.current_rsx_state, primitive, first, count, 1);
    u32 emitted = 0;
    u32 rec = s_d3d.vp_vb_offset - carry * VP_VERT_STRIDE;
    if (primitive == RSX_PRIMITIVE_QUADS)             emitted = upload_quads_vp_indexed(''',
    '''    u32 carry = 0;
    dspl_mark(DSPL_ENTRY);
    if (primitive == RSX_PRIMITIVE_QUADS || primitive == RSX_PRIMITIVE_TRIANGLES ||
        primitive == RSX_PRIMITIVE_TRIANGLE_STRIP || primitive == RSX_PRIMITIVE_TRIANGLE_FAN)
        carry = vp_make_room(s_d3d.current_rsx_state, primitive, first, count, 1);
    dspl_mark(DSPL_ROOM);
    u32 emitted = 0;
    u32 rec = s_d3d.vp_vb_offset - carry * VP_VERT_STRIDE;
    if (primitive == RSX_PRIMITIVE_QUADS)             emitted = upload_quads_vp_indexed(''')
rep('''    if (emitted) emitted += carry;   /* the moved partial triangle leads this record */
    /* Same BEGIN/END batch concatenation as the non-indexed path: this title's
     * fluid arrives as ~3000 DRAW_INDEX_ARRAY batches of 256, and 256 is not a
     * multiple of 3, so every batch after the first assembled out of phase. */
    if (emitted && s_d3d.merge_prev_draw && s_d3d.draw_count > 0 &&
        s_d3d.merge_first_end == first && primitive == RSX_PRIMITIVE_TRIANGLES) {
        D3D12DrawRecord* pv = &s_d3d.draws[s_d3d.draw_count - 1];
        u32 fpnow = s_d3d.current_rsx_state
                    ? s_d3d.current_rsx_state->shader_program : 0;
        if (pv->is_vp && pv->topology == RSX_TOPOLOGY_TRIANGLES &&
            pv->fp_addr == fpnow &&
            pv->begin_epoch == (s_d3d.current_rsx_state
                                ? s_d3d.current_rsx_state->begin_epoch : 0) &&
            pv->vb_byte_offset + pv->vertex_count * VP_VERT_STRIDE == rec) {
            pv->vertex_count += emitted;
            s_d3d.merge_first_end = first + count;
            s_da_merged = 1;
            return;
        }
    }
    if (emitted && batch_room()) {
        D3D12DrawRecord* dr = &s_d3d.draws[s_d3d.draw_count];
        dr->vb_byte_offset = rec;
        dr->vertex_count   = emitted;
        dr->topology       = RSX_TOPOLOGY_TRIANGLES;
        dr->textured       = s_d3d.tex_bound;
        dr->is_vp          = 1;''', '''    if (emitted) emitted += carry;   /* the moved partial triangle leads this record */
    if (s_dspl_on) s_dspl.verts += emitted;
    /* Same BEGIN/END batch concatenation as the non-indexed path: this title's
     * fluid arrives as ~3000 DRAW_INDEX_ARRAY batches of 256, and 256 is not a
     * multiple of 3, so every batch after the first assembled out of phase. */
    if (emitted && s_d3d.merge_prev_draw && s_d3d.draw_count > 0 &&
        s_d3d.merge_first_end == first && primitive == RSX_PRIMITIVE_TRIANGLES) {
        D3D12DrawRecord* pv = &s_d3d.draws[s_d3d.draw_count - 1];
        u32 fpnow = s_d3d.current_rsx_state
                    ? s_d3d.current_rsx_state->shader_program : 0;
        if (pv->is_vp && pv->topology == RSX_TOPOLOGY_TRIANGLES &&
            pv->fp_addr == fpnow &&
            pv->begin_epoch == (s_d3d.current_rsx_state
                                ? s_d3d.current_rsx_state->begin_epoch : 0) &&
            pv->vb_byte_offset + pv->vertex_count * VP_VERT_STRIDE == rec) {
            pv->vertex_count += emitted;
            s_d3d.merge_first_end = first + count;
            s_da_merged = 1;
            dspl_mark(DSPL_POST);
            return;
        }
    }
    dspl_mark(DSPL_POST);
    if (emitted && batch_room()) {
        D3D12DrawRecord* dr = &s_d3d.draws[s_d3d.draw_count];
        if (s_dspl_on) s_dspl.records++;
        dr->vb_byte_offset = rec;
        dr->vertex_count   = emitted;
        dr->topology       = RSX_TOPOLOGY_TRIANGLES;
        dr->textured       = s_d3d.tex_bound;
        dr->is_vp          = 1;''')
rep('''        dr->tex_slot = -1;
        dr->vs_idx = vp_get_vs(s_d3d.current_rsx_state);
        dr->is_clear = 0;
        dr->blend = s_d3d.current_rsx_state ? s_d3d.current_rsx_state->blend_enable : 1;
        dr->blend_key = rsx_blend_key(s_d3d.current_rsx_state, dr->blend);
                rec_guest_extra(dr, primitive, first, count);''', '''        dr->tex_slot = -1;
        dspl_mark(DSPL_FIELDS);
        dr->vs_idx = vp_get_vs(s_d3d.current_rsx_state);
        dspl_mark(DSPL_VS);
        dr->is_clear = 0;
        dr->blend = s_d3d.current_rsx_state ? s_d3d.current_rsx_state->blend_enable : 1;
        dr->blend_key = rsx_blend_key(s_d3d.current_rsx_state, dr->blend);
                rec_guest_extra(dr, primitive, first, count);''')
rep('''        dr->cb_slot = s_d3d.draw_count;
                vp_record_tex_snap(dr); vp_record_cb(s_d3d.draw_count, dr->vs_idx, dr);
        s_d3d.draw_count++;
        /* Anchor for merging the next batch of this indexed stream. */''', '''        dr->cb_slot = s_d3d.draw_count;
        dspl_mark(DSPL_EXTRA);
                vp_record_tex_snap(dr);
        dspl_mark(DSPL_TEXSNAP);
        vp_record_cb(s_d3d.draw_count, dr->vs_idx, dr);
        dspl_mark(DSPL_CB_REST);
        s_d3d.draw_count++;
        /* Anchor for merging the next batch of this indexed stream. */''')

# 5. Inside the strip/fan expander and vp_record_cb.
rep('''    u32 maxv = vp_reserve(vp_strip_verts(&s_prim_stream, state, first, count, 1), state, fan ? "fan" : "strip", 1, first, count);
    VPSlot* out = (VPSlot*)((u8*)s_d3d.vp_vb_mapped
        + (u64)s_d3d.vp_parity * s_vpvb.cap * VP_VERT_STRIDE + s_d3d.vp_vb_offset);
    u32 o = 0;
    const vp_idx_rd ir = vp_idx_begin(state);''', '''    dspl_mark(DSPL_ENTRY);
    u32 maxv = vp_reserve(vp_strip_verts(&s_prim_stream, state, first, count, 1), state, fan ? "fan" : "strip", 1, first, count);
    dspl_mark(DSPL_COUNT);
    VPSlot* out = (VPSlot*)((u8*)s_d3d.vp_vb_mapped
        + (u64)s_d3d.vp_parity * s_vpvb.cap * VP_VERT_STRIDE + s_d3d.vp_vb_offset);
    u32 o = 0;
    const vp_idx_rd ir = vp_idx_begin(state);''')
rep('''        vpx_emit(&s_vpx, tri[2], &out[o*16]); o++;
    }
    if (!o) return 0;   /* vp_reserve named it: too_few_vertices or vertex_buffer_full */
    s_d3d.vp_vb_offset += o * VP_VERT_STRIDE;
    return o;
}

/* Guest state carried on a draw record''', '''        vpx_emit(&s_vpx, tri[2], &out[o*16]); o++;
    }
    dspl_mark(DSPL_EMIT);
    if (!o) return 0;   /* vp_reserve named it: too_few_vertices or vertex_buffer_full */
    s_d3d.vp_vb_offset += o * VP_VERT_STRIDE;
    return o;
}

/* Guest state carried on a draw record''')
rep('''    char* dst = (char*)s_d3d.vp_cb_mapped
        + ((u64)s_d3d.vp_parity * MAX_DRAWS + slot) * VP_CB_STRIDE;
    memcpy(dst, st->vertex_constants, RSX_MAX_VERTEX_CONSTANTS * 16);
''', '''    dspl_mark(DSPL_CB_FP);
    char* dst = (char*)s_d3d.vp_cb_mapped
        + ((u64)s_d3d.vp_parity * MAX_DRAWS + slot) * VP_CB_STRIDE;
    memcpy(dst, st->vertex_constants, RSX_MAX_VERTEX_CONSTANTS * 16);
    dspl_mark(DSPL_CB_VP);
''')

# 6. The callback is over: helpers shared with other draw paths stop marking.
rep('''    d3d12_draw_indexed(ud, primitive, first, count);
    s_fpf.cur.draw_calls++; s_fpf.cur.draw_us += fpf_now_us() - t0;''', '''    d3d12_draw_indexed(ud, primitive, first, count);
    s_dspl_open = 0;
    s_fpf.cur.draw_calls++; s_fpf.cur.draw_us += fpf_now_us() - t0;''')

p.write_bytes(t.replace('\n', '\r\n').encode('utf-8'))
print('patched', p)
