"""Texture dump/replacement packs (libs/video/rsx_texture_pack.h) in libs/video/rsx_draw_engine.c:
eng_texture_upload looks the texture up in RSX_TEX_PACK (and returns the replacement's LOD shift) or
dumps its level 0 to RSX_TEX_DUMP; eng_texture_slot keeps the shift per entry; the fragment units
that bind a guest-memory texture shift their sampler's LOD clamp. Vertex units never take a pack
texture. Exact replacements, each asserted to match once. usage: py -3 edit_texpack_engine.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[4] / 'ps3recomp-vkgame' / 'libs' / 'video' / 'rsx_draw_engine.c'
s = p.read_bytes().decode('utf-8')
assert '\r\n' not in s


def sub(a, b, count=1):
    global s
    assert s.count(a) == count, (a[:90], s.count(a))
    s = s.replace(a, b)


sub('#include "rsx_shader_window.h"\n', '#include "rsx_shader_window.h"\n#include "rsx_texture_pack.h"\n')
sub('    u64 last_use_serial;\n    u32 depth;                  /* slices of a 3D texture, else 1 */\n} eng_texture;\n',
    '    u64 last_use_serial;\n    u32 depth;                  /* slices of a 3D texture, else 1 */\n'
    '    u32 repl_shift;             /* RSX_TEX_PACK: log2 of the replacement\'s size over the guest\'s */\n'
    '} eng_texture;\n')

# -- eng_texture_upload: pack lookup, dump of level 0 ------------------------------------------------
sub('''static u32 eng_texture_upload(u32 location, u32 offset, u32 fmt, u32 w, u32 h,
                              u32 levels, u32 pitch, int cube, u32 remap, u32 depth)
{
    rsx_tex_level lv[RSX_MAX_TEXTURE_LEVELS];''',
    '''/* RSX_TEX_PACK / RSX_TEX_DUMP (rsx_texture_pack.h): set while the vertex
 * units bind, which never take a pack texture (a height field upscaled would
 * move geometry). */
static int s_tp_suspend;
/* The LOD shift of the texture eng_texture_slot last returned. */
static u32 s_tp_slot_shift;

static u32 eng_texture_upload(u32 location, u32 offset, u32 fmt, u32 w, u32 h,
                              u32 levels, u32 pitch, int cube, u32 remap, u32 depth,
                              int allow_dump, u32* shift_out)
{
    if (shift_out) *shift_out = 0;
    rsx_tex_level lv[RSX_MAX_TEXTURE_LEVELS];''')
sub('''    const u32 span = eng_texture_span(fmt, w, h, levels, pitch, cube);
    const u8* src = eng_guest_ptr(NULL, location, offset, span);
    if (!src) return 0;

    const u32 handle = g.be->texture_create(g.be->user, eng_texfmt(lv[0].tl.fmt),
                                            w, h, nlv, faces, remap, fmt);
    if (!handle) return 0;
''',
    '''    const u32 span = eng_texture_span(fmt, w, h, levels, pitch, cube);
    const u8* src = eng_guest_ptr(NULL, location, offset, span);
    if (!src) return 0;

    /* A texture pack's replacement (its own size and mips, the same crossbar),
     * else note the key so level 0 is dumped once it is decoded. */
    char tp_key[RSX_TP_KEY_MAX];
    int tp_dump = 0;
    if (!cube && !s_tp_suspend && rsx_tp_on() && rsx_tp_format_ok(eng_texfmt(lv[0].tl.fmt))) {
        int readable = 0;
        const u64 th = eng_texture_content_hash(location, offset, span, &readable);
        rsx_tp_key(tp_key, w, h, fmt, th);
        size_t n = 0;
        u8* file = readable ? rsx_tp_load(tp_key, &n) : NULL;
        if (file) {
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
                if (shift_out) *shift_out = rsx_tp_shift(rw, w);
                free(file);
                return rh_;
            }
            s_tp.load_fail++;
            free(file);
        }
        tp_dump = allow_dump && readable && s_tp.dump_dir;
    }

    const u32 handle = g.be->texture_create(g.be->user, eng_texfmt(lv[0].tl.fmt),
                                            w, h, nlv, faces, remap, fmt);
    if (!handle) return 0;
''')
sub('''            rsx_texture_decode(g.tex_staging, tl->dst_row_bytes,
                               face + lv[m].offset, lv[m].w, lv[m].h, tl,
                               rsx_texture_argb_is_rgba());
            g.be->texture_upload(g.be->user, handle, f, m, lv[m].w, lv[m].h,
                                 g.tex_staging, tl->dst_row_bytes, tl->rows);''',
    '''            rsx_texture_decode(g.tex_staging, tl->dst_row_bytes,
                               face + lv[m].offset, lv[m].w, lv[m].h, tl,
                               rsx_texture_argb_is_rgba());
            if (tp_dump && f == 0 && m == 0)
                rsx_tp_dump(tp_key, eng_texfmt(tl->fmt), lv[0].w, lv[0].h, g.tex_staging,
                            tl->dst_row_bytes, tl->rows);
            g.be->texture_upload(g.be->user, handle, f, m, lv[m].w, lv[m].h,
                                 g.tex_staging, tl->dst_row_bytes, tl->rows);''')

# -- eng_texture_slot: the shift per entry, reported for the binding ----------------------------------
sub('''    if (!w || !h || w > ENG_MAX_TEX_DIM || h > ENG_MAX_TEX_DIM) return 0;
    if (!depth) depth = 1;
    const u32 span = depth > 1 ? eng_texture_span_3d(fmt, w, h, depth, levels, pitch)''',
    '''    s_tp_slot_shift = 0;
    if (!w || !h || w > ENG_MAX_TEX_DIM || h > ENG_MAX_TEX_DIM) return 0;
    if (!depth) depth = 1;
    const u32 span = depth > 1 ? eng_texture_span_3d(fmt, w, h, depth, levels, pitch)''')
sub('''                const u32 fresh = eng_texture_upload(location, offset, fmt, w, h,
                                                     levels, pitch, cube, remap, depth);
                if (fresh) {
                    g.be->texture_release(g.be->user, e->handle);
                    e->handle = fresh;
                    e->content_hash = hash;
                }''',
    '''                u32 shift = 0;
                const u32 fresh = eng_texture_upload(location, offset, fmt, w, h,
                                                     levels, pitch, cube, remap, depth, 0, &shift);
                if (fresh) {
                    g.be->texture_release(g.be->user, e->handle);
                    e->handle = fresh;
                    e->content_hash = hash;
                    e->repl_shift = shift;
                }''')
sub('''        e->last_use_serial = ++g.texture_use_serial;
        return e->handle;
    }''',
    '''        e->last_use_serial = ++g.texture_use_serial;
        s_tp_slot_shift = e->repl_shift;
        return e->handle;
    }''')
sub('''    e.handle = eng_texture_upload(location, offset, fmt, w, h, levels, pitch,
                                  cube, remap, depth);''',
    '''    e.handle = eng_texture_upload(location, offset, fmt, w, h, levels, pitch,
                                  cube, remap, depth, 1, &e.repl_shift);
    s_tp_slot_shift = e.handle ? e.repl_shift : 0;''')

# -- fragment units: the sampler follows the replacement's size ----------------------------------------
sub('''        textures[u] = eng_texture_slot(t.location, t.offset, t.format,
                                       t.width, t.height, t.mipmaps, t.pitch,
                                       (int)t.cubemap, t.remap & 0xFFFFu,
                                       (t.dimension == 3 && !t.cubemap) ? t.depth : 1u);
    }
    return mask;''',
    '''        textures[u] = eng_texture_slot(t.location, t.offset, t.format,
                                       t.width, t.height, t.mipmaps, t.pitch,
                                       (int)t.cubemap, t.remap & 0xFFFFu,
                                       (t.dimension == 3 && !t.cubemap) ? t.depth : 1u);
        if (textures[u]) rsx_tp_sampler_shift(&samplers[u], s_tp_slot_shift);
    }
    return mask;''')

# -- vertex units: never a pack texture ------------------------------------------------------------------
sub('''        textures[u] = eng_texture_slot(vt.location, vt.offset, vt.format,
                                       vt.width, vt.height, vt.mipmaps,
                                       vt.pitch, 0, 0xAAE4u, 1u);''',
    '''        s_tp_suspend = 1;
        textures[u] = eng_texture_slot(vt.location, vt.offset, vt.format,
                                       vt.width, vt.height, vt.mipmaps,
                                       vt.pitch, 0, 0xAAE4u, 1u);
        s_tp_suspend = 0;''')

p.write_bytes(s.encode('utf-8'))
print('ok')
