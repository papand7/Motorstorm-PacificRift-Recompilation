"""RSX_TEX_PBR engine glue: rsx_texture_pack.h lists and loads <pack>/pbr/<key>.dds, rsx_draw_engine.c
rewrites lit fragment programs with rsx_pbr.h, keeps each replacement's PBR map beside it, binds it per
draw on the unit the rewrite chose and passes fp_pbr (strength, sun estimate). Both files are CRLF.

usage: py -3 edit_pbr_engine.py"""
import pathlib

V = pathlib.Path(__file__).resolve().parents[4] / 'ps3recomp-vkgame' / 'libs' / 'video'


def edit(name, subs):
    p = V / name
    raw = p.read_bytes().decode('utf-8')
    crlf = '\r\n' in raw
    s = raw.replace('\r\n', '\n')
    for a, b in subs:
        assert s.count(a) == 1, (name, a[:80], s.count(a))
        s = s.replace(a, b)
    if crlf:
        s = s.replace('\n', '\r\n')
    p.write_bytes(s.encode('utf-8'))
    print('edited', name)


# ---- rsx_texture_pack.h ------------------------------------------------------------------------
edit('rsx_texture_pack.h', [
(""" * The key is "<w>x<h>_<rsx format>_<64-bit hash of the guest bytes>": the
""",
""" * RSX_TEX_PBR=1 (with RSX_TEX_PACK, off by default): a replacement whose key
 * also has <dir>/pbr/<key>.dds (BC3: RGB detail normal, A roughness) loads
 * that map beside it, and lit fragment programs light with it (rsx_pbr.h).
 *
 * The key is "<w>x<h>_<rsx format>_<64-bit hash of the guest bytes>": the
"""),
("""    char      (*pack_keys)[RSX_TP_KEY_MAX];   /* keys in the pack, sorted */
    u32         pack_n;
    u32         loaded, load_fail;
} rsx_tp_state;""",
"""    char      (*pack_keys)[RSX_TP_KEY_MAX];   /* keys in the pack, sorted */
    u32         pack_n;
    u32         loaded, load_fail;
    int         pbr_on;                       /* RSX_TEX_PBR=1 and the pack has PBR maps */
    char      (*pbr_keys)[RSX_TP_KEY_MAX];    /* keys in <pack>/pbr, sorted */
    u32         pbr_n, pbr_loaded;
} rsx_tp_state;"""),
("""/* The pack's keys: every "<key>.dds" in the directory (not its subdirectories). */
static void rsx_tp_list_pack(const char* dir)
{""",
"""/* A directory's keys: every "<key>.dds" in it (not its subdirectories). */
static void rsx_tp_list(const char* dir, char (**keys)[RSX_TP_KEY_MAX], u32* count)
{"""),
("""        if (len > 4 && len - 4 < RSX_TP_KEY_MAX && !strcmp(name + len - 4, ".dds")) {
            if (s_tp.pack_n == cap) {
                cap = cap ? cap * 2 : 256;
                void* p = realloc(s_tp.pack_keys, (size_t)cap * RSX_TP_KEY_MAX);
                if (!p) break;
                s_tp.pack_keys = (char (*)[RSX_TP_KEY_MAX])p;
            }
            memcpy(s_tp.pack_keys[s_tp.pack_n], name, len - 4);
            s_tp.pack_keys[s_tp.pack_n][len - 4] = 0;
            s_tp.pack_n++;
        }""",
"""        if (len > 4 && len - 4 < RSX_TP_KEY_MAX && !strcmp(name + len - 4, ".dds")) {
            if (*count == cap) {
                cap = cap ? cap * 2 : 256;
                void* p = realloc(*keys, (size_t)cap * RSX_TP_KEY_MAX);
                if (!p) break;
                *keys = (char (*)[RSX_TP_KEY_MAX])p;
            }
            memcpy((*keys)[*count], name, len - 4);
            (*keys)[*count][len - 4] = 0;
            (*count)++;
        }"""),
("""    if (s_tp.pack_n) qsort(s_tp.pack_keys, s_tp.pack_n, RSX_TP_KEY_MAX, rsx_tp_cmp);
}""",
"""    if (*count) qsort(*keys, *count, RSX_TP_KEY_MAX, rsx_tp_cmp);
}"""),
("""    if (s_tp.pack_dir) rsx_tp_list_pack(s_tp.pack_dir);
    if (s_tp.dump_dir || s_tp.pack_dir)
        fprintf(stderr, "[tex-pack] dump %s, pack %s (%u textures)\\n",
                s_tp.dump_dir ? s_tp.dump_dir : "off", s_tp.pack_dir ? s_tp.pack_dir : "off", s_tp.pack_n);
}""",
"""    if (s_tp.pack_dir) rsx_tp_list(s_tp.pack_dir, &s_tp.pack_keys, &s_tp.pack_n);
    const char* pb = getenv("RSX_TEX_PBR");
    if (s_tp.pack_dir && pb && pb[0] == '1' && !pb[1]) {
        char dir[1024];
        snprintf(dir, sizeof dir, "%s/pbr", s_tp.pack_dir);
        rsx_tp_list(dir, &s_tp.pbr_keys, &s_tp.pbr_n);
        s_tp.pbr_on = s_tp.pbr_n > 0;
    }
    if (s_tp.dump_dir || s_tp.pack_dir)
        fprintf(stderr, "[tex-pack] dump %s, pack %s (%u textures), PBR %s (%u maps)\\n",
                s_tp.dump_dir ? s_tp.dump_dir : "off", s_tp.pack_dir ? s_tp.pack_dir : "off", s_tp.pack_n,
                s_tp.pbr_on ? "on" : "off", s_tp.pbr_n);
}"""),
("""/* The pack's file for a key, read whole, or NULL. */
static inline u8* rsx_tp_load(const char* key, size_t* n)
{
    if (!s_tp.pack_n || !rsx_tp_has(s_tp.pack_keys, s_tp.pack_n, key)) return NULL;
    char path[1024];
    snprintf(path, sizeof path, "%s/%s.dds", s_tp.pack_dir, key);""",
"""/* A listed key's file, <pack>/<sub><key>.dds, read whole, or NULL. */
static inline u8* rsx_tp_read(const char* sub, char (*keys)[RSX_TP_KEY_MAX], u32 count,
                              const char* key, size_t* n)
{
    if (!count || !rsx_tp_has(keys, count, key)) return NULL;
    char path[1024];
    snprintf(path, sizeof path, "%s/%s%s.dds", s_tp.pack_dir, sub, key);"""),
("""    fclose(fp);
    *n = (size_t)len;
    return buf;
}
""",
"""    fclose(fp);
    *n = (size_t)len;
    return buf;
}

/* The pack's replacement for a key, or NULL. */
static inline u8* rsx_tp_load(const char* key, size_t* n)
{
    return rsx_tp_read("", s_tp.pack_keys, s_tp.pack_n, key, n);
}

/* Its PBR map (RSX_TEX_PBR), or NULL. */
static inline u8* rsx_tp_load_pbr(const char* key, size_t* n)
{
    return s_tp.pbr_on ? rsx_tp_read("pbr/", s_tp.pbr_keys, s_tp.pbr_n, key, n) : NULL;
}
"""),
])

# ---- rsx_draw_engine.c ------------------------------------------------------------------------
edit('rsx_draw_engine.c', [
('#include "rsx_primitives.h"\n', '#include "rsx_pbr.h"\n#include "rsx_primitives.h"\n'),
("""    u32 repl_shift;             /* RSX_TEX_PACK: log2 of the replacement's size over the guest's */
} eng_texture;""",
"""    u32 repl_shift;             /* RSX_TEX_PACK: log2 of the replacement's size over the guest's */
    u32 pbr_handle;             /* RSX_TEX_PBR: the replacement's PBR map, or 0 */
} eng_texture;"""),
("""    u64 fp_hash;            /* eng_fp_debug_hash of the guest fragment program */
} eng_pipeline;""",
"""    u64 fp_hash;            /* eng_fp_debug_hash of the guest fragment program */
    s8 pbr_unit, pbr_src;   /* RSX_TEX_PBR: the map's unit and the albedo unit, -1 = not rewritten */
    u8 pbr_n;               /* fragment constants the rewritten dots read */
    u16 pbr_consts[RSX_PBR_MAX_DOTS];
} eng_pipeline;"""),
("""/* The LOD shift of the texture eng_texture_slot last returned. */
static u32 s_tp_slot_shift;
""",
"""/* The LOD shift of the texture eng_texture_slot last returned. */
static u32 s_tp_slot_shift;
/* RSX_TEX_PBR: the PBR map eng_texture_upload loaded beside a replacement,
 * and that of the texture eng_texture_slot last returned. */
static u32 s_tp_up_pbr;
static u32 s_tp_slot_pbr;

/* A pack DDS's levels into a new backend texture, or 0. */
static u32 eng_tp_create(const u8* file, size_t n, u32 remap, u32 fmt, u32* w_out)
{
    rsx_be_format rf;
    u32 rw, rh, off[16], bytes[16];
    const u32 rl = rsx_tp_dds_parse(file, n, &rf, &rw, &rh, off, bytes);
    const u32 hd = rl ? g.be->texture_create(g.be->user, rf, rw, rh, rl, 1, remap, fmt) : 0;
    if (!hd) return 0;
    u32 lw = rw, lh = rh;
    for (u32 m = 0; m < rl; m++) {
        const int bc = rf != RSX_BE_FMT_R8G8B8A8;
        const u32 row_bytes = bc ? ((lw + 3u) / 4u) * (rf == RSX_BE_FMT_BC1 ? 8u : 16u) : lw * 4u;
        g.be->texture_upload(g.be->user, hd, 0, m, lw, lh, file + off[m], row_bytes,
                             bc ? (lh + 3u) / 4u : lh);
        lw = lw > 1u ? lw / 2u : 1u; lh = lh > 1u ? lh / 2u : 1u;
    }
    if (w_out) *w_out = rw;
    return hd;
}

/* RSX_TEX_PBR: the PBR map for a replacement's key, read through the identity
 * crossbar (the rewritten program takes the normal from .xyz, roughness from .w). */
static u32 eng_tp_pbr_load(const char* key)
{
    size_t n = 0;
    u8* file = rsx_tp_load_pbr(key, &n);
    if (!file) return 0;
    const u32 hd = eng_tp_create(file, n, 0xAAE4u, 0x88u /* DXT45 */, NULL);
    free(file);
    if (hd) {
        s_tp.pbr_loaded++;
        if ((s_tp.pbr_loaded & (s_tp.pbr_loaded - 1u)) == 0)
            fprintf(stderr, "[tex-pbr] %u PBR maps loaded (last %s)\\n", s_tp.pbr_loaded, key);
    }
    return hd;
}
"""),
("""    if (shift_out) *shift_out = 0;
    rsx_tex_level lv[RSX_MAX_TEXTURE_LEVELS];""",
"""    if (shift_out) *shift_out = 0;
    s_tp_up_pbr = 0;
    rsx_tex_level lv[RSX_MAX_TEXTURE_LEVELS];"""),
("""        if (file) {
            rsx_be_format rf;
            u32 rw, rh, off[16], bytes[16];
            const u32 rl = rsx_tp_dds_parse(file, n, &rf, &rw, &rh, off, bytes);
            const u32 rh_ = rl ? g.be->texture_create(g.be->user, rf, rw, rh, rl, 1, remap, fmt) : 0;
            if (rh_) {
                u32 lw = rw, lh = rh;
                for (u32 m = 0; m < rl; m++) {
                    const int bc = rf != RSX_BE_FMT_R8G8B8A8;
                    const u32 row_bytes = bc ? ((lw + 3u) / 4u) * (rf == RSX_BE_FMT_BC1 ? 8u : 16u) : lw * 4u;
                    g.be->texture_upload(g.be->user, rh_, 0, m, lw, lh, file + off[m], row_bytes,
                                         bc ? (lh + 3u) / 4u : lh);
                    lw = lw > 1u ? lw / 2u : 1u; lh = lh > 1u ? lh / 2u : 1u;
                }
                s_tp.loaded++;
                if ((s_tp.loaded & (s_tp.loaded - 1u)) == 0)
                    fprintf(stderr, "[tex-pack] %u textures replaced (last %s: %ux%u for %ux%u)\\n",
                            s_tp.loaded, tp_key, rw, rh, w, h);
                if (shift_out) *shift_out = rsx_tp_shift(rw, w);
                free(file);
                return rh_;
            }""",
"""        if (file) {
            u32 rw = 0;
            const u32 rh_ = eng_tp_create(file, n, remap, fmt, &rw);
            if (rh_) {
                s_tp.loaded++;
                if ((s_tp.loaded & (s_tp.loaded - 1u)) == 0)
                    fprintf(stderr, "[tex-pack] %u textures replaced (last %s: %u wide for %ux%u)\\n",
                            s_tp.loaded, tp_key, rw, w, h);
                if (shift_out) *shift_out = rsx_tp_shift(rw, w);
                free(file);
                s_tp_up_pbr = eng_tp_pbr_load(tp_key);
                return rh_;
            }"""),
("""    s_tp_slot_shift = 0;
    if (!w || !h || w > ENG_MAX_TEX_DIM || h > ENG_MAX_TEX_DIM) return 0;""",
"""    s_tp_slot_shift = 0;
    s_tp_slot_pbr = 0;
    if (!w || !h || w > ENG_MAX_TEX_DIM || h > ENG_MAX_TEX_DIM) return 0;"""),
("""                if (fresh) {
                    g.be->texture_release(g.be->user, e->handle);
                    e->handle = fresh;
                    e->content_hash = hash;
                    e->repl_shift = shift;
                }
            }
        }
        e->last_use_serial = ++g.texture_use_serial;
        s_tp_slot_shift = e->repl_shift;
        return e->handle;""",
"""                if (fresh) {
                    g.be->texture_release(g.be->user, e->handle);
                    if (e->pbr_handle) g.be->texture_release(g.be->user, e->pbr_handle);
                    e->handle = fresh;
                    e->content_hash = hash;
                    e->repl_shift = shift;
                    e->pbr_handle = s_tp_up_pbr;
                }
            }
        }
        e->last_use_serial = ++g.texture_use_serial;
        s_tp_slot_shift = e->repl_shift;
        s_tp_slot_pbr = e->pbr_handle;
        return e->handle;"""),
("""    e.handle = eng_texture_upload(location, offset, fmt, w, h, levels, pitch,
                                  cube, remap, depth, 1, &e.repl_shift);
    s_tp_slot_shift = e.handle ? e.repl_shift : 0;
    if (e.handle && evicted) g.be->texture_release(g.be->user, evicted);""",
"""    e.handle = eng_texture_upload(location, offset, fmt, w, h, levels, pitch,
                                  cube, remap, depth, 1, &e.repl_shift);
    e.pbr_handle = e.handle ? s_tp_up_pbr : 0;
    s_tp_slot_shift = e.handle ? e.repl_shift : 0;
    s_tp_slot_pbr = e.pbr_handle;
    if (e.handle && evicted) {
        g.be->texture_release(g.be->user, evicted);
        if (g.textures[index].pbr_handle) g.be->texture_release(g.be->user, g.textures[index].pbr_handle);
    }"""),
# the pipeline cache: rewrite, remember, and report the last one returned
("""static u32 eng_pipeline_get(const rsx_vertex_layout_plan* layout,
                            const rsx_be_render_state* rs,
                            rsx_be_format rt_fmt, u32 rt_count, int* out_fixed,
                            u32* out_tex_used, u64* out_fp_hash)
{
    *out_fixed = 1;""",
"""/* The pipeline eng_pipeline_get last returned, or NULL. */
static const eng_pipeline* s_pipe_last;

static u32 eng_pipeline_get(const rsx_vertex_layout_plan* layout,
                            const rsx_be_render_state* rs,
                            rsx_be_format rt_fmt, u32 rt_count, int* out_fixed,
                            u32* out_tex_used, u64* out_fp_hash)
{
    s_pipe_last = NULL;
    *out_fixed = 1;"""),
("""            if (g.pipelines[i].key == key) {
                *out_fixed = g.pipelines[i].fixed;
                *out_tex_used = g.pipelines[i].tex_used;
                *out_fp_hash = g.pipelines[i].fp_hash;
                return g.pipelines[i].handle;
            }
        }
    } else""",
"""            if (g.pipelines[i].key == key) {
                *out_fixed = g.pipelines[i].fixed;
                *out_tex_used = g.pipelines[i].tex_used;
                *out_fp_hash = g.pipelines[i].fp_hash;
                s_pipe_last = &g.pipelines[i];
                return g.pipelines[i].handle;
            }
        }
    } else"""),
("""        if (g.pipelines[i].key == key) {
            *out_fixed = g.pipelines[i].fixed;
            *out_tex_used = g.pipelines[i].tex_used;
            *out_fp_hash = g.pipelines[i].fp_hash;
            return g.pipelines[i].handle;
        }
    if (g.n_pipelines >= ENG_MAX_PIPELINES) return 0;""",
"""        if (g.pipelines[i].key == key) {
            *out_fixed = g.pipelines[i].fixed;
            *out_tex_used = g.pipelines[i].tex_used;
            *out_fp_hash = g.pipelines[i].fp_hash;
            s_pipe_last = &g.pipelines[i];
            return g.pipelines[i].handle;
        }
    if (g.n_pipelines >= ENG_MAX_PIPELINES) return 0;"""),
("""    u32 handle = 0;
    int vi = 1, fi = 1;
    u32 nconst = 0;
    if (fixed) {""",
"""    u32 handle = 0;
    int vi = 1, fi = 1;
    u32 nconst = 0;
    rsx_pbr_info pbr;
    memset(&pbr, 0, sizeof pbr);
    pbr.unit = pbr.src_unit = -1;
    if (fixed) {"""),
("""            rsx_fp_apply_alpha_test_buffered(s_ps_hlsl, sizeof s_ps_hlsl,
                                             rs->alpha_func) < 0)
            fi = -1;
    }
    if (vi > 0 && fi > 0)""",
"""            rsx_fp_apply_alpha_test_buffered(s_ps_hlsl, sizeof s_ps_hlsl,
                                             rs->alpha_func) < 0)
            fi = -1;
        /* RSX_TEX_PBR: sun-lit programs light with the texture pack's PBR maps
         * (rsx_pbr.h); the map takes a free unit the program declares 2D. */
        rsx_tp_init();
        if (fi > 0 && s_tp.pbr_on) {
            const int r = rsx_pbr_apply(s_ps_hlsl, sizeof s_ps_hlsl, cube_mask | vol_mask, &pbr);
            { static u32 logs = 0; if (r > 0 && PS3_LOG_FIRST(logs, 16))
                fprintf(stderr, "[tex-pbr] fp %016llx: %d dot(s) rewritten, albedo t%d, map t%d\\n",
                        (unsigned long long)eng_fp_debug_hash(fp_uc, fp_size), r, pbr.src_unit, pbr.unit); }
        }
    }
    if (vi > 0 && fi > 0)"""),
("""    g.pipelines[g.n_pipelines].tex_used =
        (u16)(fixed ? 0xFFFFu : eng_sampled_units(s_ps_hlsl));
    *out_tex_used = g.pipelines[g.n_pipelines].tex_used;""",
"""    g.pipelines[g.n_pipelines].tex_used =
        (u16)(fixed ? 0xFFFFu : eng_sampled_units(s_ps_hlsl) & ~(pbr.unit >= 0 ? 1u << pbr.unit : 0u));
    g.pipelines[g.n_pipelines].pbr_unit = (s8)pbr.unit;
    g.pipelines[g.n_pipelines].pbr_src = (s8)pbr.src_unit;
    g.pipelines[g.n_pipelines].pbr_n = (u8)pbr.n_consts;
    for (u32 k = 0; k < RSX_PBR_MAX_DOTS; k++)
        g.pipelines[g.n_pipelines].pbr_consts[k] = (u16)(k < pbr.n_consts ? pbr.consts[k] : 0u);
    s_pipe_last = &g.pipelines[g.n_pipelines];
    *out_tex_used = g.pipelines[g.n_pipelines].tex_used;"""),
# per-unit PBR maps while the fragment units bind
("""    u32 mask = 0;
    u32 feedback[RSX_BE_MAX_COLOR_TARGETS] = {0};
    u32 feedback_w[RSX_BE_MAX_COLOR_TARGETS] = {0}, feedback_h[RSX_BE_MAX_COLOR_TARGETS] = {0};
    for (u32 u = 0; u < RSX_BE_MAX_TEXTURES; u++) {
        rsx_dsp_texture t;
        rsx_dsp_get_texture(&g.rsx, u, &t);""",
"""    u32 mask = 0;
    u32 feedback[RSX_BE_MAX_COLOR_TARGETS] = {0};
    u32 feedback_w[RSX_BE_MAX_COLOR_TARGETS] = {0}, feedback_h[RSX_BE_MAX_COLOR_TARGETS] = {0};
    memset(s_unit_pbr, 0, sizeof s_unit_pbr);
    for (u32 u = 0; u < RSX_BE_MAX_TEXTURES; u++) {
        rsx_dsp_texture t;
        rsx_dsp_get_texture(&g.rsx, u, &t);"""),
("""        if (textures[u]) rsx_tp_sampler_shift(&samplers[u], s_tp_slot_shift);
    }
    return mask;
}""",
"""        if (textures[u]) rsx_tp_sampler_shift(&samplers[u], s_tp_slot_shift);
        if (textures[u]) s_unit_pbr[u] = s_tp_slot_pbr;
    }
    return mask;
}"""),
("""static u32 sink_bind_textures(const u32* target_slots, u32 n_targets,""",
"""/* RSX_TEX_PBR: each fragment unit's PBR map in the draw being bound, or 0. */
static u32 s_unit_pbr[RSX_BE_MAX_TEXTURES];

/* RSX_TEX_PBR: the sun the rewritten programs bend their light for. Each
 * rewritten draw votes with the unit vectors among the constants it dots;
 * a vector counts once per program. When a frame ends, the vector most
 * programs shared (at least 3) is the next frame's sun, so fog planes,
 * luminance weights and the like, seen in fewer programs, never qualify. */
#define ENG_PBR_CANDS 16
static struct {
    u32 frame;
    float sun[3];
    float cand[ENG_PBR_CANDS][3];
    u64 progs[ENG_PBR_CANDS];         /* programs (pipeline index mod 64) that dotted it */
    u32 n;
    float strength;
} s_pbr = { 0, {0, 0, 0}, {{0}}, {0}, 0, -1.0f };

static u32 eng_popcount64(u64 v) { u32 c = 0; for (; v; v &= v - 1u) c++; return c; }

static void eng_pbr_vote(const eng_pipeline* pp)
{
    if (s_pbr.frame != g.frames) {
        u32 best = 0, bv = 0;
        for (u32 i = 0; i < s_pbr.n; i++) {
            const u32 v = eng_popcount64(s_pbr.progs[i]);
            if (v > bv) { bv = v; best = i; }
        }
        if (bv >= 3) {
            const float* c = s_pbr.cand[best];
            const float d = c[0] * s_pbr.sun[0] + c[1] * s_pbr.sun[1] + c[2] * s_pbr.sun[2];
            { static u32 logs = 0; if (d < 0.9995f && PS3_LOG_FIRST(logs, 16))
                fprintf(stderr, "[tex-pbr] sun (%.4f, %.4f, %.4f), shared by %u programs\\n",
                        c[0], c[1], c[2], bv); }
            memcpy(s_pbr.sun, c, sizeof s_pbr.sun);
        }
        s_pbr.n = 0;
        s_pbr.frame = g.frames;
    }
    const u64 bit = 1ull << ((u32)(pp - g.pipelines) & 63u);
    for (u32 k = 0; k < pp->pbr_n; k++) {
        const u32 idx = pp->pbr_consts[k];
        if (idx >= g.fp_constants.count) continue;
        float v[3];
        memcpy(v, g.fp_constants.values[idx], sizeof v);
        const float l = sqrtf(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
        if (!(l > 0.98f && l < 1.02f)) continue;
        /* the shader compares |cos|, so v and -v are one candidate */
        const float lead = v[1] != 0.0f ? v[1] : v[0] != 0.0f ? v[0] : v[2];
        const float s = (lead < 0.0f ? -1.0f : 1.0f) / l;
        v[0] *= s; v[1] *= s; v[2] *= s;
        u32 i = 0;
        for (; i < s_pbr.n; i++)
            if (v[0] * s_pbr.cand[i][0] + v[1] * s_pbr.cand[i][1] + v[2] * s_pbr.cand[i][2] > 0.9995f) break;
        if (i == s_pbr.n) {
            if (s_pbr.n == ENG_PBR_CANDS) continue;
            memcpy(s_pbr.cand[i], v, sizeof v);
            s_pbr.progs[i] = 0;
            s_pbr.n++;
        }
        s_pbr.progs[i] |= bit;
    }
}

/* RSX_TEX_PBR_STRENGTH (default 0.6, 0..2): how far the detail normal bends the sun's light. */
static float eng_pbr_strength(void)
{
    if (s_pbr.strength < 0.0f) {
        const char* e = getenv("RSX_TEX_PBR_STRENGTH");
        float k = e && *e ? (float)atof(e) : 0.6f;
        s_pbr.strength = k < 0.0f ? 0.0f : k > 2.0f ? 2.0f : k;
    }
    return s_pbr.strength;
}

static u32 sink_bind_textures(const u32* target_slots, u32 n_targets,"""),
# the draw: bind the map, fill fp_pbr
("""    const u32 tex_mask = sink_bind_textures(targets, n_targets, zslot, tex_used,
                                            textures, samplers);
    if (tex_mask == ENG_INVALID) return;""",
"""    u32 tex_mask = sink_bind_textures(targets, n_targets, zslot, tex_used,
                                      textures, samplers);
    if (tex_mask == ENG_INVALID) return;
    /* RSX_TEX_PBR: the albedo texture's PBR map on the unit the rewrite chose,
     * sampled as the albedo is. Without one, fp_pbr.x = 0 keeps the program's
     * own lighting (the unit then reads the backend's placeholder). */
    const eng_pipeline* const pp = s_pipe_last;
    const int pbr_draw = pp && pp->pbr_unit >= 0;
    float pbr_k[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
    if (pbr_draw) {
        const u32 pu = (u32)pp->pbr_unit, su = (u32)pp->pbr_src;
        eng_pbr_vote(pp);
        if (((tex_mask >> su) & 1u) && s_unit_pbr[su]) {
            textures[pu] = s_unit_pbr[su];
            samplers[pu] = samplers[su];
            tex_mask |= 1u << pu;
            pbr_k[0] = eng_pbr_strength();
            memcpy(&pbr_k[1], s_pbr.sun, sizeof s_pbr.sun);
        }
    }"""),
("""    const u32 nslots = g.fp_constants.count ? g.fp_constants.count : 1u;
    const u32 fp_bytes = (nslots + 1u) * 16u;""",
"""    const u32 nslots = g.fp_constants.count ? g.fp_constants.count : 1u;
    const u32 fp_bytes = (nslots + 1u + (pbr_draw ? 1u : 0u)) * 16u;   /* + fp_pbr */"""),
("""    { float* alpha = (float*)(g.fp_cb + nslots * 16u);
      alpha[0] = rsx_fp_alpha_ref(rs.alpha_ref_raw, rs.alpha_ref_format);
      alpha[1] = alpha[2] = alpha[3] = 0.0f; }""",
"""    { float* alpha = (float*)(g.fp_cb + nslots * 16u);
      alpha[0] = rsx_fp_alpha_ref(rs.alpha_ref_raw, rs.alpha_ref_format);
      alpha[1] = alpha[2] = alpha[3] = 0.0f; }
    if (pbr_draw) memcpy(g.fp_cb + (nslots + 1u) * 16u, pbr_k, sizeof pbr_k);"""),
("""    for (u32 i = 0; i < g.n_textures; i++)
        if (g.textures[i].handle) g.be->texture_release(g.be->user, g.textures[i].handle);""",
"""    for (u32 i = 0; i < g.n_textures; i++) {
        if (g.textures[i].handle) g.be->texture_release(g.be->user, g.textures[i].handle);
        if (g.textures[i].pbr_handle) g.be->texture_release(g.be->user, g.textures[i].pbr_handle);
    }"""),
])
