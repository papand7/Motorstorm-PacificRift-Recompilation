"""T175: the direct conversion out of line, so the switch-off loop keeps its shape. usage: py -3 patch_ool_t175.py <tree>"""
import sys
F = sys.argv[1] + '/libs/video/rsx_d3d12_backend.c'
s = open(F, encoding='utf-8', errors='surrogateescape', newline='').read()
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')
a = '''                    if (direct) {
                        u8* vd = (u8*)out + VPC_UNIT + (size_t)nv * cs;
                        if (ff) vfp_vertex_direct(&s_vpx, &s_vfp, vi, vd); else vpx_vertex_direct(&s_vpx, vi, vd);
                    } else
'''
assert s.count(a) == 1
s = s.replace(a, '''                    if (direct) vpd_vertex(ff, vi, (u8*)out + VPC_UNIT + (size_t)nv * cs);
                    else
''')
a = 'static u32 upload_strip_vp_indexed(const rsx_state* state, u32 first, u32 count, int fan)\n{\n'
assert s.count(a) == 1
s = s.replace(a, '''static __declspec(noinline) void vpd_vertex(int ff, u32 vi, u8* d)
{
    if (ff) vfp_vertex_direct(&s_vpx, &s_vfp, vi, d);
    else vpx_vertex_direct(&s_vpx, vi, d);
}
''' + a)
if crlf:
    s = s.replace('\n', '\r\n')
open(F, 'w', encoding='utf-8', errors='surrogateescape', newline='').write(s)
