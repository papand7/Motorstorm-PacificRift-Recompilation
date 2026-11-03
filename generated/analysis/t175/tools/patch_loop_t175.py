"""T175: the direct path as its own loop; T174's loop stays as it was. usage: py -3 patch_loop_t175.py <tree>"""
import sys
F = sys.argv[1] + '/libs/video/rsx_d3d12_backend.c'
s = open(F, encoding='utf-8', errors='surrogateescape', newline='').read()
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')


def sub(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)


sub('''static __declspec(noinline) void vpd_vertex(int ff, u32 vi, u8* d)
{
    if (ff) vfp_vertex_direct(&s_vpx, &s_vfp, vi, d);
    else vpx_vertex_direct(&s_vpx, vi, d);
}
''', '')
sub('''                    if (direct) vpd_vertex(ff, vi, (u8*)out + VPC_UNIT + (size_t)nv * cs);
                    else
''', '')
sub('''        const int direct = vpd_mode();
        vpi_begin(&s_vpi);
        for (u32 k = 0; k < count; k++) {
''', '''        vpi_begin(&s_vpi);
        if (vpd_mode()) for (u32 k = 0; k < count; k++) {   /* the loop below, converting straight into the record */
            u32 tri[3];
            const u32 idx = vp_idx_at(&ir, first + k);
            if (restart && idx == state->restart_index) { ps3_prim_stream_restart(&s_prim_stream); continue; }
            if (!ps3_prim_stream_push(&s_prim_stream, idx, tri)
                || o + 3 > ixc) continue;
            for (int c = 0; c < 3; c++) {
                int fresh;
                const u32 l = vpi_find(&s_vpi, tri[c], nv, &fresh);
                if (fresh) {
                    u8* vd = (u8*)out + VPC_UNIT + (size_t)nv * cs;
                    if (ff) vfp_vertex_direct(&s_vpx, &s_vfp, tri[c], vd); else vpx_vertex_direct(&s_vpx, tri[c], vd);
                    nv++;
                }
                s_vpi_ix[o++] = (u16)l;
            }
        } else
        for (u32 k = 0; k < count; k++) {
''')
if crlf:
    s = s.replace('\n', '\r\n')
open(F, 'w', encoding='utf-8', errors='surrogateescape', newline='').write(s)
F = sys.argv[1] + '/tools/test_vp_direct.py'
s = open(F, encoding='utf-8', newline='').read()
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')
sub("check(b.count('vpd_mode()') == 2 and b.count('vpd_vertex(') == 2, 'one reader, one call site')\n",
    "check(b.count('vpd_mode()') == 2 and b.count('vfp_vertex_direct(') == 1 and b.count('vpx_vertex_direct(') == 1, 'one reader, one loop')\n")
sub("b.index('const int direct = vpd_mode();')", "b.index('if (vpd_mode()) for (u32 k = 0; k < count; k++) {')")
sub("check('vpc_put_vertex((u8*)out, nv, cs, ff ?", "check('} else\\n        for (u32 k = 0; k < count; k++) {' in b.replace('\\r\\n', '\\n') and 'vpc_put_vertex((u8*)out, nv, cs, ff ?")
if crlf:
    s = s.replace('\n', '\r\n')
open(F, 'w', encoding='utf-8', newline='').write(s)
