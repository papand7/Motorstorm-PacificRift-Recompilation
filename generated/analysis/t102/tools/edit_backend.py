MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T102: vertex cache in the strip/indexed-list expanders, per-draw index base,
and reuse of the prepass guest-FP pipeline lookup in the draw loop.
Every replacement asserts its match count (CRLF-aware)."""
import sys
sys.path.insert(0, __import__('tempfile').gettempdir())
from t96rep import R

W = (MS_ROOT + r'\ps3recomp-t102')
r = R(W + r'\libs\video\rsx_d3d12_backend.c')

r.rep('#include "ps3emu/rsx_frame_perf.h"     /* RSX_FRAME_PERF: per-guest-frame time split */\n',
      '#include "ps3emu/rsx_frame_perf.h"     /* RSX_FRAME_PERF: per-guest-frame time split */\n'
      '#include "ps3emu/vp_expand.h"          /* each guest vertex converted once per draw */\n')

# ---- vertex cache, after read_vp_vertex -----------------------------------
r.rep('''            rsx_vtx_pos_dbg(state, out16[0].v, n);
        }
    }
}
''', '''            rsx_vtx_pos_dbg(state, out16[0].v, n);
        }
    }
}

/* The same 16 slots through vpx_cache (vp_expand.h): an expander that writes
 * a guest vertex several times (strips, fans, indexed lists) converts it once
 * per draw and copies 256 bytes for each further use. Slots whose fetch does
 * not depend on the vertex index (rsx_fetch_attrib returns the constant
 * register: disabled, stride 0) come from a per-draw template. Same bytes as
 * read_vp_vertex. One cache: draw callbacks are not reentrant. */
static vpx_cache s_vpx;
static void vpx_attr(const void* st, int idx, uint32_t vi, float out[4])
{
    rsx_fetch_attrib((const rsx_state*)st, idx, vi, out);
}
static void vpx_pos_dbg(const void* st, const float v[16][4])
{
    const rsx_vertex_attrib* a = &((const rsx_state*)st)->vertex_attribs[0];
    u32 n = a->size ? a->size : 4; if (n > 4) n = 4;
    rsx_vtx_pos_dbg((const rsx_state*)st, v[0], n);
}
static void vp_vx_begin(const rsx_state* state)
{
    extern uint8_t* vm_base;
    int act[16];
    for (int i = 0; i < 16; i++)
        act[i] = state->vertex_attribs[i].enabled && state->vertex_attribs[i].stride != 0 && vm_base != NULL;
    vpx_begin(&s_vpx, state, vpx_attr, vpx_pos_dbg, act, (const float (*)[4])state->vertex_data4f);
}
''')

# ---- per-draw index base ---------------------------------------------------
r.rep('''static u32 read_guest_index(const rsx_state* st, u32 k)
{''', '''/* read_guest_index with the array base resolved once per draw (it does not
 * depend on k). */
typedef struct { const u8* p; int u16; } vp_idx_rd;
static vp_idx_rd vp_idx_begin(const rsx_state* st)
{
    extern uint8_t* vm_base;
    extern u32 cellGcmResolveLocated(int local, u32 offset);
    vp_idx_rd r;
    r.p = vm_base + cellGcmResolveLocated((st->index_array_dma & 0xF) == 0, st->index_array_offset);
    r.u16 = ((st->index_array_dma >> 4) & 0xF) == 1;
    return r;
}
static inline u32 vp_idx_at(const vp_idx_rd* r, u32 k)
{
    if (r->u16) { const u8* p = r->p + (u64)k * 2; return ((u32)p[0] << 8) | p[1]; }
    const u8* p = r->p + (u64)k * 4;
    return ((u32)p[0] << 24) | ((u32)p[1] << 16) | ((u32)p[2] << 8) | p[3];
}

static u32 read_guest_index(const rsx_state* st, u32 k)
{''')
r.rep('''static u32 read_guest_index(const rsx_state* st, u32 k);
typedef struct { const rsx_state* st; u32 first; int indexed; } vp_fetch_ctx;''',
      '''static u32 read_guest_index(const rsx_state* st, u32 k);
typedef struct { const u8* p; int u16; } vp_idx_rd;
static vp_idx_rd vp_idx_begin(const rsx_state* st);
static inline u32 vp_idx_at(const vp_idx_rd* r, u32 k);
typedef struct { const rsx_state* st; u32 first; int indexed; vp_idx_rd ir; } vp_fetch_ctx;''')
r.rep('''    return c->indexed ? read_guest_index(c->st, c->first + k) : c->first + k;''',
      '''    return c->indexed ? vp_idx_at(&c->ir, c->first + k) : c->first + k;''')
r.rep('''    vp_fetch_ctx c = { st, first, indexed };''',
      '''    vp_fetch_ctx c = { st, first, indexed, { NULL, 0 } };
    if (indexed) c.ir = vp_idx_begin(st);''')
# the first definition now duplicates the forward typedef: drop the second typedef
r.rep('''/* read_guest_index with the array base resolved once per draw (it does not
 * depend on k). */
typedef struct { const u8* p; int u16; } vp_idx_rd;
static vp_idx_rd vp_idx_begin''', '''/* read_guest_index with the array base resolved once per draw (it does not
 * depend on k). */
static vp_idx_rd vp_idx_begin''')

# ---- non-indexed strip/fan --------------------------------------------------
r.rep('''    u32 o = 0;
    for (u32 k = 0; k < count; k++) {
        u32 tri[3];
        if (!ps3_prim_stream_push(&s_prim_stream, first + k, tri) || o + 3 > maxv) continue;
        read_vp_vertex(state, tri[0], &out[o*16]); o++;
        read_vp_vertex(state, tri[1], &out[o*16]); o++;
        read_vp_vertex(state, tri[2], &out[o*16]); o++;
    }''', '''    u32 o = 0;
    vp_vx_begin(state);
    for (u32 k = 0; k < count; k++) {
        u32 tri[3];
        if (!ps3_prim_stream_push(&s_prim_stream, first + k, tri) || o + 3 > maxv) continue;
        vpx_emit(&s_vpx, tri[0], &out[o*16]); o++;
        vpx_emit(&s_vpx, tri[1], &out[o*16]); o++;
        vpx_emit(&s_vpx, tri[2], &out[o*16]); o++;
    }''')

# ---- indexed strip/fan ------------------------------------------------------
r.rep('''    u32 o = 0;
    for (u32 k = 0; k < count; k++) {
        u32 tri[3];
        const u32 idx = read_guest_index(state, first + k);
        if (restart && idx == state->restart_index) { ps3_prim_stream_restart(&s_prim_stream); continue; }
        if (!ps3_prim_stream_push(&s_prim_stream, idx, tri)
            || o + 3 > maxv) continue;
        read_vp_vertex(state, tri[0], &out[o*16]); o++;
        read_vp_vertex(state, tri[1], &out[o*16]); o++;
        read_vp_vertex(state, tri[2], &out[o*16]); o++;
    }''', '''    u32 o = 0;
    const vp_idx_rd ir = vp_idx_begin(state);
    vp_vx_begin(state);
    for (u32 k = 0; k < count; k++) {
        u32 tri[3];
        const u32 idx = vp_idx_at(&ir, first + k);
        if (restart && idx == state->restart_index) { ps3_prim_stream_restart(&s_prim_stream); continue; }
        if (!ps3_prim_stream_push(&s_prim_stream, idx, tri)
            || o + 3 > maxv) continue;
        vpx_emit(&s_vpx, tri[0], &out[o*16]); o++;
        vpx_emit(&s_vpx, tri[1], &out[o*16]); o++;
        vpx_emit(&s_vpx, tri[2], &out[o*16]); o++;
    }''')

# ---- indexed triangle list ---------------------------------------------------
r.rep('''      for (u32 k = 0; k < count; k++)
          read_vp_vertex(state, read_guest_index(state, first + k), &out[k*16]);''',
      '''      const vp_idx_rd ir = vp_idx_begin(state);
      vp_vx_begin(state);
      for (u32 k = 0; k < count; k++)
          vpx_emit(&s_vpx, vp_idx_at(&ir, first + k), &out[k*16]);''')

# ---- guest-FP pipeline: the draw loop reuses the prepass lookup -------------
r.rep('''static u32 s_vp_fp_last_uhash;          /* code hash of the last vp_get_fp_pso call */''',
      '''static u32 s_vp_fp_last_uhash;          /* code hash of the last vp_get_fp_pso call */
/* The replay looks each record's pipeline up twice with the same arguments:
 * in the prepass (to build it before recording) and in the draw loop. The
 * draw loop reuses the prepass result while it is still the cache's answer:
 * same pass (s_fpm_epoch moves at every prepass), no cache entry released
 * since (eviction moves it too) and the same VS generation. Otherwise it
 * calls vp_get_fp_pso as before. */
typedef struct { ID3D12PipelineState* pso; u32 uhash, epoch, gen; int ok; } fp_memo;
static fp_memo s_fpm[2048];
static u32 s_fpm_epoch = 1;
static u64 s_fpm_hits, s_fpm_calls;''')
r.rep('''    if (s_d3d.vp_fp_n >= VP_FP_CACHE) {
        if (s_d3d.vp_fp[0].pso) s_d3d.vp_fp[0].pso->lpVtbl->Release(s_d3d.vp_fp[0].pso);''',
      '''    if (s_d3d.vp_fp_n >= VP_FP_CACHE) {
        s_fpm_epoch++;   /* a remembered pipeline may be the one released here */
        if (s_d3d.vp_fp[0].pso) s_d3d.vp_fp[0].pso->lpVtbl->Release(s_d3d.vp_fp[0].pso);''')
r.rep('''    for (u32 _d = 0; _d < s_d3d.draw_count && _d < MAX_DRAWS; _d++) {
        D3D12DrawRecord* dr = &s_d3d.draws[_d];
        if (dr->is_vp && dr->is_clear) zeta_note_writes(dr);''',
      '''    s_fpm_epoch++;   /* pipelines remembered by an earlier pass are not reused */
    for (u32 _d = 0; _d < s_d3d.draw_count && _d < MAX_DRAWS; _d++) {
        D3D12DrawRecord* dr = &s_d3d.draws[_d];
        s_fpm[_d].ok = 0;
        if (dr->is_vp && dr->is_clear) zeta_note_writes(dr);''')
r.rep('''            vp_get_fp_pso(dr->vs_idx, dr->fp_addr, dr->blend_key,
                          dr_num_rts(dr),
                          dr->rt_off ? rsx_surface_dxgi(dr->rt_fmt)
                                     : DXGI_FORMAT_R8G8B8A8_UNORM,
                          dr->fp_exp32, dr->cmask, dr->cull, dr_cube_mask(dr), _sd, _sk,
                          dr_depth_key(dr));''',
      '''            fp_memo* _fm = &s_fpm[_d];
            _fm->pso =
            vp_get_fp_pso(dr->vs_idx, dr->fp_addr, dr->blend_key,
                          dr_num_rts(dr),
                          dr->rt_off ? rsx_surface_dxgi(dr->rt_fmt)
                                     : DXGI_FORMAT_R8G8B8A8_UNORM,
                          dr->fp_exp32, dr->cmask, dr->cull, dr_cube_mask(dr), _sd, _sk,
                          dr_depth_key(dr));
            _fm->uhash = s_vp_fp_last_uhash; _fm->epoch = s_fpm_epoch; _fm->gen = s_d3d.vp_gen; _fm->ok = 1;''')
r.rep('''                rsx_fp_shadow_desc _sd[RSX_DSP_NUM_TEXTURES];
                const u32 _sk = dr->fp_addr ? dr_shadow(dr, _sd) : 0;
                ID3D12PipelineState* dpso =
                    dr->fp_addr ? vp_get_fp_pso(''',
      '''                rsx_fp_shadow_desc _sd[RSX_DSP_NUM_TEXTURES];
                const fp_memo* _fm = &s_fpm[d];
                const int _fmu = dr->fp_addr && _fm->ok && _fm->epoch == s_fpm_epoch && _fm->gen == s_d3d.vp_gen;
                s_fpm_calls += dr->fp_addr ? 1u : 0u; s_fpm_hits += _fmu ? 1u : 0u;
                if (_fmu) s_vp_fp_last_uhash = _fm->uhash;   /* what the call would have left for the trace */
                const u32 _sk = dr->fp_addr && !_fmu ? dr_shadow(dr, _sd) : 0;
                ID3D12PipelineState* dpso = _fmu ? _fm->pso :
                    dr->fp_addr ? vp_get_fp_pso(''')
r.save()
print('ok')
