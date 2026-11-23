"""RSX_RES_SCALE in libs/video/rsx_vulkan_backend.c (an LF file): targets at the scaled size, every
guest rectangle converted, readbacks downsampled, writes and seeds upsampled, the display image and
window at the scaled size, the engine's canvas at the guest size. Exact replacements, each asserted
to match once. usage: py -3 edit_res_scale_vk.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[4] / 'ps3recomp-vkgame' / 'libs' / 'video' / 'rsx_vulkan_backend.c'
s = p.read_bytes().decode('utf-8')
assert '\r\n' not in s


def sub(a, b, count=1):
    global s
    assert s.count(a) == count, (a[:80], s.count(a))
    s = s.replace(a, b)


# -- include, state ---------------------------------------------------------------------------
sub('#include "rsx_poly_offset.h"\n',
    '#include "rsx_poly_offset.h"\n#include "rsx_res_scale.h"\n')
sub('    u32              width, height;\n',
    '    u32              width, height;   /* the display image and window: guest size x RSX_RES_SCALE */\n'
    '    u32              guest_w, guest_h;/* the engine\'s canvas, in guest pixels */\n')

# -- init: display at the scaled size, the engine's canvas at the guest size -----------------
sub('    s_vk.width  = width  ? width  : 1280;\n    s_vk.height = height ? height : 720;\n',
    '    s_vk.guest_w = width  ? width  : 1280;\n    s_vk.guest_h = height ? height : 720;\n'
    '    {   /* RSX_RES_SCALE (rsx_res_scale.h): the display image and window at the scaled size */\n'
    '        const rsx_res_scale rs = rsx_res_scale_get();\n'
    '        s_vk.width  = rsx_rs_len(rs, s_vk.guest_w);\n'
    '        s_vk.height = rsx_rs_len(rs, s_vk.guest_h);\n'
    '        if (rsx_res_scale_on(rs))\n'
    '            VK_LOG("RSX_RES_SCALE %u/%u: targets and display at %ux%u for a %ux%u guest frame\\n",\n'
    '                   rs.n, rs.d, s_vk.width, s_vk.height, s_vk.guest_w, s_vk.guest_h);\n'
    '    }\n')
sub('rsx_draw_engine_init(s_vk.width, s_vk.height) == 0)',
    'rsx_draw_engine_init(s_vk.guest_w, s_vk.guest_h) == 0)')

# -- the object: guest size of a target ---------------------------------------------------------
sub('    u8       snapshot;               /* COLOR: a feedback copy, never a target */\n} vk_eng_obj;\n',
    '    u8       snapshot;               /* COLOR: a feedback copy, never a target */\n'
    '    u8       rs_scaled;              /* TEXTURE: resized to the scale by vk_eng_reinterpret */\n'
    '    u32      gw, gh;                 /* COLOR/DEPTH target: guest size (w, h: host texels) */\n'
    '} vk_eng_obj;\n\n'
    '/* RSX_RES_SCALE: the engine hands guest units, targets are n/d times larger. */\n'
    'static rsx_res_scale vk_rs(void) { return rsx_res_scale_get(); }\n'
    'static int vk_rs_on(void) { return rsx_res_scale_on(rsx_res_scale_get()); }\n\n'
    '/* The host rectangle a guest rectangle covers, edges rounded outwards. */\n'
    'static void vk_rs_rect(u32* x, u32* y, u32* w, u32* h)\n'
    '{\n'
    '    const rsx_res_scale rs = vk_rs();\n'
    '    const u32 x0 = rsx_rs_lo(rs, *x), y0 = rsx_rs_lo(rs, *y);\n'
    '    const u32 x1 = rsx_rs_hi(rs, *x + *w), y1 = rsx_rs_hi(rs, *y + *h);\n'
    '    *x = x0; *y = y0; *w = x1 - x0; *h = y1 - y0;\n'
    '}\n\n'
    '/* Guest rows of w x h texels of `bpp` bytes, repeated over the host texels\n'
    ' * whose centres they cover: the host rectangle of vk_rs_rect(x, y, w, h).\n'
    ' * Returns a malloc\'d buffer of tight host rows, or NULL. */\n'
    'static u8* vk_rs_upsample(u32 x, u32 y, u32 w, u32 h, u32 bpp, const void* rows, u32 row_bytes,\n'
    '                          u32* hx, u32* hy, u32* hw, u32* hh)\n'
    '{\n'
    '    const rsx_res_scale rs = vk_rs();\n'
    '    *hx = x; *hy = y; *hw = w; *hh = h;\n'
    '    vk_rs_rect(hx, hy, hw, hh);\n'
    '    u8* out = (u8*)malloc((size_t)*hw * *hh * bpp);\n'
    '    if (!out) return NULL;\n'
    '    for (u32 j = 0; j < *hh; j++) {\n'
    '        u32 gy = rsx_rs_h2g(rs, *hy + j);\n'
    '        gy = gy < y ? y : gy >= y + h ? y + h - 1u : gy;\n'
    '        const u8* src = (const u8*)rows + (size_t)(gy - y) * row_bytes;\n'
    '        u8* dst = out + (size_t)j * *hw * bpp;\n'
    '        for (u32 i = 0; i < *hw; i++) {\n'
    '            u32 gx = rsx_rs_h2g(rs, *hx + i);\n'
    '            gx = gx < x ? x : gx >= x + w ? x + w - 1u : gx;\n'
    '            memcpy(dst + (size_t)i * bpp, src + (size_t)(gx - x) * bpp, bpp);\n'
    '        }\n'
    '    }\n'
    '    return out;\n'
    '}\n\n'
    '/* The host rectangle whose texels hold the centres of a guest rectangle\'s\n'
    ' * pixels: from the first pixel\'s centre texel to the last one\'s. */\n'
    'static void vk_rs_centres(u32 x, u32 y, u32 w, u32 h, u32* hx, u32* hy, u32* hw, u32* hh)\n'
    '{\n'
    '    const rsx_res_scale rs = vk_rs();\n'
    '    *hx = rsx_rs_g2h(rs, x); *hy = rsx_rs_g2h(rs, y);\n'
    '    *hw = rsx_rs_g2h(rs, x + w - 1u) + 1u - *hx;\n'
    '    *hh = rsx_rs_g2h(rs, y + h - 1u) + 1u - *hy;\n'
    '}\n\n'
    '/* Tight host rows of the vk_rs_centres rectangle -> one texel per guest pixel. */\n'
    'static void vk_rs_downsample(const u8* host, u32 host_tight, u32 x, u32 y, u32 w, u32 h, u32 bpp,\n'
    '                             void* out, u32 out_pitch)\n'
    '{\n'
    '    const rsx_res_scale rs = vk_rs();\n'
    '    const u32 hx0 = rsx_rs_g2h(rs, x), hy0 = rsx_rs_g2h(rs, y);\n'
    '    for (u32 j = 0; j < h; j++) {\n'
    '        const u8* src = host + (size_t)(rsx_rs_g2h(rs, y + j) - hy0) * host_tight;\n'
    '        u8* dst = (u8*)out + (size_t)j * out_pitch;\n'
    '        for (u32 i = 0; i < w; i++)\n'
    '            memcpy(dst + (size_t)i * bpp, src + (size_t)(rsx_rs_g2h(rs, x + i) - hx0) * bpp, bpp);\n'
    '    }\n'
    '}\n')

# -- colour target create: host size, seed upsampled ------------------------------------------------
sub('''    (void)user;
    u32 bpp;
    const VkFormat vf = vk_eng_format(fmt, &bpp);
    /* Only formats the E2 passes are built for (vk_eng_rt_index). */
    if (vk_eng_rt_index(vf) < 0 || !w || !h || w > vk_max_dim() || h > vk_max_dim()) {
        VK_LOG("engine: colour target format %d %ux%u not supported yet\\n", (int)fmt, w, h);
        return 0;
    }
    const u32 hd = vk_eng_alloc();
    if (!hd) return 0;
    vk_eng_obj* o = &s_eobj[hd];
    if (vk_create_image(&o->im, vf, w, h,''',
    '''    (void)user;
    u32 bpp;
    const VkFormat vf = vk_eng_format(fmt, &bpp);
    const u32 gw = w, gh = h;
    if (vk_rs_on()) { w = rsx_rs_len(vk_rs(), gw); h = rsx_rs_len(vk_rs(), gh); }   /* host texels */
    /* Only formats the E2 passes are built for (vk_eng_rt_index). */
    if (vk_eng_rt_index(vf) < 0 || !w || !h || w > vk_max_dim() || h > vk_max_dim()) {
        VK_LOG("engine: colour target format %d %ux%u not supported yet\\n", (int)fmt, w, h);
        return 0;
    }
    const u32 hd = vk_eng_alloc();
    if (!hd) return 0;
    vk_eng_obj* o = &s_eobj[hd];
    if (vk_create_image(&o->im, vf, w, h,''')
sub('    o->kind = VK_ENG_COLOR; o->fmt = vf; o->bpp = bpp; o->w = w; o->h = h;\n'
    '    /* UNDEFINED -> GENERAL, then the guest\'s own bytes',
    '    o->kind = VK_ENG_COLOR; o->fmt = vf; o->bpp = bpp; o->w = w; o->h = h; o->gw = gw; o->gh = gh;\n'
    '    /* UNDEFINED -> GENERAL, then the guest\'s own bytes')
sub('''    if (seed && seed_row_bytes)
        vk_eng_upload(o->im.img, 0, 0, w, h, bpp, seed, seed_row_bytes);
    return hd;''',
    '''    if (seed && seed_row_bytes) {
        if (vk_rs_on()) {
            u32 hx, hy, hw, hh;
            u8* up = vk_rs_upsample(0, 0, gw, gh, bpp, seed, seed_row_bytes, &hx, &hy, &hw, &hh);
            if (up && hw <= w && hh <= h) vk_eng_upload(o->im.img, 0, 0, hw, hh, bpp, up, hw * bpp);
            free(up);
        } else {
            vk_eng_upload(o->im.img, 0, 0, w, h, bpp, seed, seed_row_bytes);
        }
    }
    return hd;''')

# -- depth target create ----------------------------------------------------------------------------
sub('''    (void)user;
    if (!w || !h || w > vk_max_dim() || h > vk_max_dim()) return 0;
    const u32 hd = vk_eng_alloc();
    if (!hd) return 0;
    vk_eng_obj* o = &s_eobj[hd];
    if (vk_create_image(&o->im, s_vk.depth_format, w, h,''',
    '''    (void)user;
    const u32 gw = w, gh = h;
    if (vk_rs_on()) { w = rsx_rs_len(vk_rs(), gw); h = rsx_rs_len(vk_rs(), gh); }   /* host texels */
    if (!w || !h || w > vk_max_dim() || h > vk_max_dim()) return 0;
    const u32 hd = vk_eng_alloc();
    if (!hd) return 0;
    vk_eng_obj* o = &s_eobj[hd];
    if (vk_create_image(&o->im, s_vk.depth_format, w, h,''')
sub('    o->kind = VK_ENG_DEPTH; o->fmt = s_vk.depth_format; o->w = w; o->h = h;\n',
    '    o->kind = VK_ENG_DEPTH; o->fmt = s_vk.depth_format; o->w = w; o->h = h; o->gw = gw; o->gh = gh;\n')

# -- depth/stencil clear inside a rectangle ---------------------------------------------------------
sub('''    vk_eng_obj* o = vk_eng_get(depth, VK_ENG_DEPTH);
    if (!o) return;
    if (x >= o->w || y >= o->h) return;''',
    '''    vk_eng_obj* o = vk_eng_get(depth, VK_ENG_DEPTH);
    if (!o) return;
    if (vk_rs_on()) vk_rs_rect(&x, &y, &w, &h);   /* guest -> host texels */
    if (x >= o->w || y >= o->h) return;''')

# -- guest rows written into a colour target: upsampled ---------------------------------------------
sub('''    if (!o || o->fmt != VK_FORMAT_R8G8B8A8_UNORM) return;   /* rows are R,G,B,A */
    if (!rows || !w || !h || x + w > o->w || y + h > o->h) return;
    vk_eng_upload_region(o->im.img, 0, 0, x, y, w, h, (size_t)w * o->bpp, h, rows, row_bytes);''',
    '''    if (!o || o->fmt != VK_FORMAT_R8G8B8A8_UNORM) return;   /* rows are R,G,B,A */
    if (vk_rs_on()) {
        if (!rows || !w || !h || x + w > o->gw || y + h > o->gh) return;
        u32 hx, hy, hw, hh;
        u8* up = vk_rs_upsample(x, y, w, h, o->bpp, rows, row_bytes, &hx, &hy, &hw, &hh);
        if (up && hx + hw <= o->w && hy + hh <= o->h)
            vk_eng_upload_region(o->im.img, 0, 0, hx, hy, hw, hh, (size_t)hw * o->bpp, hh, up, hw * o->bpp);
        free(up);
        return;
    }
    if (!rows || !w || !h || x + w > o->w || y + h > o->h) return;
    vk_eng_upload_region(o->im.img, 0, 0, x, y, w, h, (size_t)w * o->bpp, h, rows, row_bytes);''')

# -- asynchronous readback: the centres' rectangle, picked at collect --------------------------------
sub('''    vk_buffer buf;
    u64       seq;                     /* the batch holding the copy */
    size_t    tight;
    u32       h;
    int       busy;
} s_rbq[VK_RB_SLOTS];''',
    '''    vk_buffer buf;
    u64       seq;                     /* the batch holding the copy */
    size_t    tight;
    u32       h;
    int       busy;
    u32       gx, gy, gw, gh, bpp;     /* RSX_RES_SCALE: the guest rectangle, picked at collect */
    int       scaled;
} s_rbq[VK_RB_SLOTS];''')
sub('''    vk_eng_obj* o = vk_eng_get(surface, VK_ENG_COLOR);
    if (!s_b.on || !o || !w || !h || x + w > o->w || y + h > o->h) return 0;
    u32 k = 0;''',
    '''    vk_eng_obj* o = vk_eng_get(surface, VK_ENG_COLOR);
    const int scaled = vk_rs_on();
    const u32 gx = x, gy = y, gw = w, gh = h;
    if (scaled) {
        if (!o || !w || !h || x + w > o->gw || y + h > o->gh) return 0;
        vk_rs_centres(gx, gy, gw, gh, &x, &y, &w, &h);
    }
    if (!s_b.on || !o || !w || !h || x + w > o->w || y + h > o->h) return 0;
    u32 k = 0;''')
sub('''    s_rbq[k].tight = tight;
    s_rbq[k].h = h;
    s_rbq[k].busy = 1;''',
    '''    s_rbq[k].tight = tight;
    s_rbq[k].h = h;
    s_rbq[k].busy = 1;
    s_rbq[k].scaled = scaled;
    s_rbq[k].gx = gx; s_rbq[k].gy = gy; s_rbq[k].gw = gw; s_rbq[k].gh = gh; s_rbq[k].bpp = o->bpp;''')
sub('''    vk_buffer* b = &s_rbq[k].buf;
    vk_invalidate(b);
    for (u32 row = 0; row < s_rbq[k].h; row++)''',
    '''    vk_buffer* b = &s_rbq[k].buf;
    vk_invalidate(b);
    if (s_rbq[k].scaled) {
        vk_rs_downsample((const u8*)b->ptr, (u32)s_rbq[k].tight, s_rbq[k].gx, s_rbq[k].gy,
                         s_rbq[k].gw, s_rbq[k].gh, s_rbq[k].bpp, out, out_pitch);
        return 1;
    }
    for (u32 row = 0; row < s_rbq[k].h; row++)''')

# -- synchronous readback ---------------------------------------------------------------------------
sub('''    vk_eng_obj* o = vk_eng_get(surface, VK_ENG_COLOR);
    if (!o || !out || !out_pitch || !w || !h || x + w > o->w || y + h > o->h) return;
    const size_t tight = (size_t)w * o->bpp;''',
    '''    vk_eng_obj* o = vk_eng_get(surface, VK_ENG_COLOR);
    const int scaled = vk_rs_on();
    const u32 gx = x, gy = y, gw = w, gh = h;
    if (scaled) {
        if (!o || !out || !out_pitch || !w || !h || x + w > o->gw || y + h > o->gh) return;
        vk_rs_centres(gx, gy, gw, gh, &x, &y, &w, &h);
    }
    if (!o || !out || !out_pitch || !w || !h || x + w > o->w || y + h > o->h) return;
    const size_t tight = (size_t)w * o->bpp;''')
sub('''        if (!rb_rc) {
            vk_invalidate(&st);
            for (u32 row = 0; row < h; row++)
                memcpy((u8*)out + (size_t)row * out_pitch, (const u8*)st.ptr + (size_t)row * tight, tight);
        }''',
    '''        if (!rb_rc) {
            vk_invalidate(&st);
            if (scaled)
                vk_rs_downsample((const u8*)st.ptr, (u32)tight, gx, gy, gw, gh, o->bpp, out, out_pitch);
            else
                for (u32 row = 0; row < h; row++)
                    memcpy((u8*)out + (size_t)row * out_pitch, (const u8*)st.ptr + (size_t)row * tight, tight);
        }''')

# -- texture objects remember their crossbar (vk_eng_reinterpret may resize them) -------------------
sub('    o->kind = VK_ENG_TEXTURE; o->fmt = vf; o->w = w; o->h = h; o->cube = (u8)cube;\n',
    '    o->kind = VK_ENG_TEXTURE; o->fmt = vf; o->w = w; o->h = h; o->cube = (u8)cube;\n'
    '    o->remap = remap; o->rsx_fmt = rsx_fmt; o->rs_scaled = 0;\n')

# -- colour window: guest size -> host ------------------------------------------------------------
sub('''static u32 vk_eng_color_window(void* user, u32 surface, u32 w, u32 h)
{
    return vk_eng_color_copy(user, surface, w, h);
}''',
    '''static u32 vk_eng_color_window(void* user, u32 surface, u32 w, u32 h)
{
    if (vk_rs_on()) {   /* the guest window's host texels */
        const vk_eng_obj* t = vk_eng_get(surface, VK_ENG_COLOR);
        if (!t) return 0;
        w = rsx_rs_len(vk_rs(), w); h = rsx_rs_len(vk_rs(), h);
        if (w > t->w) w = t->w;
        if (h > t->h) h = t->h;
    }
    return vk_eng_color_copy(user, surface, w, h);
}''')

# -- depth snapshot: guest size -> host ---------------------------------------------------------------
sub('''        return 0;
    }
    if (w > z->w) w = z->w;
    if (h > z->h) h = z->h;
    if (!w || !h) return 0;

    u32 snap = z->surface;''',
    '''        return 0;
    }
    if (vk_rs_on()) { w = rsx_rs_len(vk_rs(), w); h = rsx_rs_len(vk_rs(), h); }   /* host texels */
    if (w > z->w) w = z->w;
    if (h > z->h) h = z->h;
    if (!w || !h) return 0;

    u32 snap = z->surface;''')

# -- depth readback ------------------------------------------------------------------------------------
sub('''    vk_eng_obj* z = vk_eng_get(depth, VK_ENG_DEPTH);
    if (!z || !out || !w || !h || x + w > z->w || y + h > z->h ||
        out_pitch < w * 4u || (s_vk.depth_format != VK_FORMAT_D32_SFLOAT &&
                                  s_vk.depth_format != VK_FORMAT_D32_SFLOAT_S8_UINT))
        return -1;''',
    '''    vk_eng_obj* z = vk_eng_get(depth, VK_ENG_DEPTH);
    const int scaled = vk_rs_on();
    const u32 gx = x, gy = y, gw = w, gh = h;
    if (scaled) {
        if (!z || !out || !w || !h || x + w > z->gw || y + h > z->gh || out_pitch < w * 4u) return -1;
        vk_rs_centres(gx, gy, gw, gh, &x, &y, &w, &h);
    }
    if (!z || !out || !w || !h || x + w > z->w || y + h > z->h ||
        (!scaled && out_pitch < w * 4u) || (s_vk.depth_format != VK_FORMAT_D32_SFLOAT &&
                                               s_vk.depth_format != VK_FORMAT_D32_SFLOAT_S8_UINT))
        return -1;''')

# -- viewport and scissor: guest -> host ------------------------------------------------------------
sub('''static void vk_eng_set_viewport(void* user, float x, float y, float w, float h)
{
    (void)user;
    s_e2.vp[0] = x;''',
    '''static void vk_eng_set_viewport(void* user, float x, float y, float w, float h)
{
    (void)user;
    if (vk_rs_on()) {   /* every target is n/d times its guest size */
        const float k = (float)vk_rs().n / (float)vk_rs().d;
        x *= k; y *= k; w *= k; h *= k;
    }
    s_e2.vp[0] = x;''')
sub('''static void vk_eng_set_scissor(void* user, u32 x, u32 y, u32 w, u32 h)
{
    (void)user;
    s_e2.sc[0] = x;''',
    '''static void vk_eng_set_scissor(void* user, u32 x, u32 y, u32 w, u32 h)
{
    (void)user;
    if (vk_rs_on()) vk_rs_rect(&x, &y, &w, &h);
    s_e2.sc[0] = x;''')

# -- polygon offset: the slope term per guest pixel -------------------------------------------------
sub('            ras.depthBiasSlopeFactor = o.slope;\n',
    '            /* a host pixel is 1/scale of a guest one: keep the bias per guest pixel */\n'
    '            ras.depthBiasSlopeFactor = vk_rs_on() ? o.slope * (float)vk_rs().n / (float)vk_rs().d\n'
    '                                                  : o.slope;\n')

p.write_bytes(s.encode('utf-8'))
print('ok')
