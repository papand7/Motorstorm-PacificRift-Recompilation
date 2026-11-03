"""T172: RSX_DEPTH_VOLUME, opt-in. usage: py -3 patch_t172.py <ps3recomp tree>"""
import sys
p = f'{sys.argv[1]}/libs/video/rsx_d3d12_backend.c'
s = open(p, encoding='utf-8', newline='').read()


def sub(a, b):
    global s
    a, b = a.replace('\n', '\r\n'), b.replace('\n', '\r\n')
    assert s.count(a) == 1, a
    s = s.replace(a, b)


sub("""static u64 dr_depth_key(const D3D12DrawRecord* dr)
{
    if (ds_state_on()) return dr->g_ds_key;
""", """/* RSX_DEPTH_VOLUME=1 (read once, off by default): a volume draw (fp 0x022C20C1:
 * back faces, GREATER, no writes, reading its zeta as colour) keeps its zeta
 * bound and the guest's depth/stencil state, without RSX_DEPTH_STATE's changes
 * to every other draw. The fallback tested it against an empty shared buffer,
 * so its faces shaded sky and scene alike (T172). */
static int depth_volume_on(void)
{
    static int on = -1;
    if (on < 0) { const char* e = getenv("RSX_DEPTH_VOLUME"); on = (e && e[0] == '1' && !e[1]) ? 1 : 0; }
    return on;
}
static int dr_volume(const D3D12DrawRecord* dr)
{
    return depth_volume_on() && rsx_ds_is_volume(dr->g_ds_key);
}

static u64 dr_depth_key(const D3D12DrawRecord* dr)
{
    if (ds_state_on() || dr_volume(dr)) return dr->g_ds_key;
""")
sub("!(ds_bind_exact() && zeta_sampled_only_as_color(dr, z))", "!((ds_bind_exact() || dr_volume(dr)) && zeta_sampled_only_as_color(dr, z))")
sub("""if (z >= 0 && z == cur_z && ((dr->fp_units >> _u) & 1u) && ds_bind_exact() &&
""", """if (z >= 0 && z == cur_z && ((dr->fp_units >> _u) & 1u) && (ds_bind_exact() || dr_volume(dr)) &&
""")
sub('rt_reinterp=%d shader_window=%d%c",', 'rt_reinterp=%d shader_window=%d depth_volume=%d%c",')
sub('rt_reinterp_on(), shader_window_on(), 10);', 'rt_reinterp_on(), shader_window_on(), depth_volume_on(), 10);')
sub("if (ds_bind_exact() && cur_z >= 0 &&
", "if ((ds_bind_exact() || (depth_volume_on() && !dr_volume(dr))) && cur_z >= 0 &&
")
open(p, 'w', encoding='utf-8', newline='').write(s)
print('patched')
