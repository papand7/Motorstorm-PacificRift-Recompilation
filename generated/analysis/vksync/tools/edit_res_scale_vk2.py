"""RSX_RES_SCALE in rsx_vulkan_backend.c, part 2: the depth readback picks one texel per guest pixel,
and vk_eng_reinterpret (RSX_GPU_REINTERP) runs at the host size, resizing the engine's guest-size
texture to it once. usage: py -3 edit_res_scale_vk2.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[4] / 'ps3recomp-vkgame' / 'libs' / 'video' / 'rsx_vulkan_backend.c'
s = p.read_bytes().decode('utf-8')
assert '\r\n' not in s


def sub(a, b, count=1):
    global s
    assert s.count(a) == count, (a[:80], s.count(a))
    s = s.replace(a, b)


sub('''        if (!rc) {
            vk_invalidate(&st);
            for (u32 row = 0; row < h; row++)
                memcpy((u8*)out + (size_t)row * out_pitch,
                       (const u8*)st.ptr + (size_t)row * w * 4u, (size_t)w * 4u);
        }''',
    '''        if (!rc) {
            vk_invalidate(&st);
            if (scaled)
                vk_rs_downsample((const u8*)st.ptr, w * 4u, gx, gy, gw, gh, 4u, out, out_pitch);
            else
                for (u32 row = 0; row < h; row++)
                    memcpy((u8*)out + (size_t)row * out_pitch,
                           (const u8*)st.ptr + (size_t)row * w * 4u, (size_t)w * 4u);
        }''')

# The reinterpret target: under the scale the engine's guest-size texture is remade at the host size
# (same format, crossbar and usage as vk_eng_texture_create gives it), then filled from the host texels.
sub('''static int vk_eng_reinterpret(void* user, u32 texture, u32 src, u32 mode, u32 w, u32 h, void* check)
{
    (void)user;
    if (mode > RSX_BE_REINTERP_RGBA8_AS_Y16X16F || !w || !h) return -1;
    const int depth = (mode == RSX_BE_REINTERP_Z24_AS_ARGB8);
    vk_eng_obj* t = vk_eng_get(texture, VK_ENG_TEXTURE);
    const vk_eng_obj* s = vk_eng_get(src, depth ? VK_ENG_DEPTH : VK_ENG_COLOR);''',
    '''/* RSX_RES_SCALE: remake a reinterpret texture (one level, not a cube) at w x h. */
static int vk_eng_texture_resize(vk_eng_obj* o, u32 w, u32 h)
{
    if (o->cube || !w || !h || w > vk_max_dim() || h > vk_max_dim()) return -1;
    vk_image im = {0};
    if (vk_create_image(&im, o->fmt, w, h, VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT,
                        VK_IMAGE_ASPECT_COLOR_BIT)) {
        vk_destroy_image(&im); return -1;
    }
    /* vk_create_image's view has the identity crossbar; the texture's own replaces it. */
    VkImageView view = VK_NULL_HANDLE;
    if (vk_eng_make_view(im.img, o->fmt, 1, vk_remap(o->remap, o->rsx_fmt), 0, &view)) {
        vk_destroy_image(&im); return -1;
    }
    if (im.view) pvkDestroyImageView(s_vk.device, im.view, NULL);
    im.view = view;
    if (vk_begin()) { vk_destroy_image(&im); return -1; }
    vk_barrier_image(im.img, VK_IMAGE_ASPECT_COLOR_BIT, VK_IMAGE_LAYOUT_UNDEFINED);
    if (vk_op_end()) { vk_destroy_image(&im); return -1; }
    vk_destroy_image(&o->im);
    o->im = im;
    o->w = w; o->h = h; o->rs_scaled = 1;
    return 0;
}

static int vk_eng_reinterpret(void* user, u32 texture, u32 src, u32 mode, u32 w, u32 h, void* check)
{
    (void)user;
    if (mode > RSX_BE_REINTERP_RGBA8_AS_Y16X16F || !w || !h) return -1;
    const int depth = (mode == RSX_BE_REINTERP_Z24_AS_ARGB8);
    vk_eng_obj* t = vk_eng_get(texture, VK_ENG_TEXTURE);
    const vk_eng_obj* s = vk_eng_get(src, depth ? VK_ENG_DEPTH : VK_ENG_COLOR);
    if (vk_rs_on()) {
        /* The host texels of the guest w x h; the self-check compares guest texels, so it is
         * left to the guest-memory route. */
        if (check || !t || !s) return -1;
        const u32 hw = rsx_rs_len(vk_rs(), w), hh = rsx_rs_len(vk_rs(), h);
        if (!t->rs_scaled || t->w != hw || t->h != hh) {
            if (t->rs_scaled || t->w != w || t->h != h || vk_eng_texture_resize(t, hw, hh)) return -1;
        }
        w = hw; h = hh;
    }''')

p.write_bytes(s.encode('utf-8'))
print('ok')
