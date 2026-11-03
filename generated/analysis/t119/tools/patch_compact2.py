"""T119 commit 4, part 2 (after patch_compact.py): keep the reservation one vp_reserve statement and the
RSXI query bracketing exactly the DrawInstanced (tools/test_draw_rejection.py, test_rsxi_geom.py).

  py -3 patch_compact2.py <worktree>
"""
import pathlib, sys

wt = pathlib.Path(sys.argv[1])
p = wt / 'libs/video/rsx_d3d12_backend.c'
raw = p.read_bytes().decode('utf-8')
assert raw.count('\r\n') == raw.count('\n')
t = raw.replace('\r\n', '\n')


def rep(a, b, n=1):
    global t
    assert t.count(a) == n, (t.count(a), a[:90])
    t = t.replace(a, b)


rep('''    const u32 vwant = vp_strip_verts(&s_prim_stream, state, first, count, 1);
    int cact[VPC_SLOTS]; u32 cmask = 0;
    const int cn = vp_compact_active(state, cact, &cmask);   /* RSX_VP_COMPACT: 0 = 256-byte vertices */
    const u32 cs = vpc_stride(cn);
    u32 maxv;
    if (cn) maxv = vpc_max_verts(vp_reserve((vwant && vwant != 0xFFFFFFFFu) ? vpc_units(vwant, cs) : vwant,
                                            state, fan ? "fan" : "strip", 1, first, count), cs);
    else maxv = vp_reserve(vwant, state, fan ? "fan" : "strip", 1, first, count);
''', '''    int cact[VPC_SLOTS]; u32 cmask = 0;
    const int cn = vp_compact_active(state, cact, &cmask);   /* RSX_VP_COMPACT: 0 = 256-byte vertices */
    const u32 cs = vpc_stride(cn);
    u32 maxv = vp_reserve(vpc_want(cn, cs, vp_strip_verts(&s_prim_stream, state, first, count, 1)), state, fan ? "fan" : "strip", 1, first, count);
    if (cn) maxv = vpc_max_verts(maxv, cs);   /* units -> whole triangles */
''')
rep('''        return (cn && v && v != 0xFFFFFFFFu) ? vpc_units(v, vpc_stride(cn)) : v;''',
    '''        return vpc_want(cn, vpc_stride(cn), v);''')
rep('''                if (s_rsxi.active) rsxi_on_draw(d, dr, cur_rt, cur_m, dpso, dvp_x, dvp_y, dvp_w, dvp_h);
                if (dr->vp_cstride) {   /* RSX_VP_COMPACT record: its own views, from vertex 0 */
                    vpc_bind(s_d3d.cmd_list, vbv.BufferLocation, vbv.SizeInBytes, dr);
                    s_d3d.cmd_list->lpVtbl->DrawInstanced(s_d3d.cmd_list, dr->vertex_count, 1, 0, 0);
                } else {
                    if (vp_compact_mode() && !s_vpc_fat_bound)
                        vpc_bind(s_d3d.cmd_list, vbv.BufferLocation, vbv.SizeInBytes, NULL);
                    s_d3d.cmd_list->lpVtbl->DrawInstanced(s_d3d.cmd_list,
                        dr->vertex_count, 1, dr->vb_byte_offset / 256, 0);
                }''', '''                if (dr->vp_cstride)   /* RSX_VP_COMPACT record: its own views (same start vertex) */
                    vpc_bind(s_d3d.cmd_list, vbv.BufferLocation, vbv.SizeInBytes, dr);
                else if (vp_compact_mode() && !s_vpc_fat_bound)
                    vpc_bind(s_d3d.cmd_list, vbv.BufferLocation, vbv.SizeInBytes, NULL);
                if (s_rsxi.active) rsxi_on_draw(d, dr, cur_rt, cur_m, dpso, dvp_x, dvp_y, dvp_w, dvp_h);
                s_d3d.cmd_list->lpVtbl->DrawInstanced(s_d3d.cmd_list,
                    dr->vertex_count, 1, dr->vb_byte_offset / 256, 0);''')
p.write_bytes(t.replace('\n', '\r\n').encode('utf-8'))

h = wt / 'include/ps3emu/vp_compact.h'
ht = h.read_text()
a = '''/* Most vertices `units` units hold'''
assert ht.count(a) == 1
ht = ht.replace(a, '''/* What a draw of `verts` vertices reserves: the vertex count itself when it is
 * written fat (nact 0) or is not a count (0 = nothing to draw, ~0 = refused as
 * too big: both keep their meaning for vp_reserve), else its units. */
static inline uint32_t vpc_want(int nact, uint32_t s, uint32_t verts)
{
    return (nact && verts && verts != 0xFFFFFFFFu) ? vpc_units(verts, s) : verts;
}
''' + a)
h.write_text(ht)
print('patched')
