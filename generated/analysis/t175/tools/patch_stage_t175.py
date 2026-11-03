"""T175: TEMPORARY stage timers for the strip expander, every 16th draw, never committed. usage: py -3 patch_stage_t175.py <tree>
Timed with rdtsc around each operation. Stores can stall at a later operation, so a write-combined write's cost can land on the next stage."""
import sys
F = sys.argv[1] + '/libs/video/rsx_d3d12_backend.c'
s = open(F, encoding='utf-8', errors='surrogateescape', newline='').read()
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')


def sub(a, b, n=1):
    global s
    assert s.count(a) == n, (a, s.count(a))
    s = s.replace(a, b)


sub('static u32 upload_strip_vp_indexed(const rsx_state* state, u32 first, u32 count, int fan)\n{\n', '''enum { XS_BEGIN, XS_STREAM, XS_FIND, XS_CONV, XS_PUT, XS_IXCOPY, XS_TICKS, XS_N };
static unsigned long long xs[XS_N], xs_ops[XS_N], xs_draws, xs_n, xs_last, xs_hit, xs_miss; static int xs_on;
#define XS(k) do { if (xs_on) { const unsigned long long _t = __rdtsc(); xs[k] += _t - xs_last; xs_ops[k]++; xs_last = __rdtsc(); } } while (0)
static void xs_report(void)
{
    fprintf(stderr, "[xs] draws=%llu hit=%llu miss=%llu", xs_draws, xs_hit, xs_miss);
    for (int i = 0; i < XS_TICKS; i++) fprintf(stderr, " %d=%llu/%llu", i, xs[i], xs_ops[i]);
    fprintf(stderr, "%c", 10);
}
static u32 upload_strip_vp_indexed(const rsx_state* state, u32 first, u32 count, int fan)
{
    xs_on = (++xs_n & 15u) == 0; if (xs_on) { xs_draws++; xs_last = __rdtsc(); }
''')
sub('''    if (cn && maxv) vpc_put_template((u8*)out, (const float (*)[4])s_vpx.tmpl);
    if (ixo) {
''', '''    if (cn && maxv) vpc_put_template((u8*)out, (const float (*)[4])s_vpx.tmpl);
    XS(XS_BEGIN); const unsigned long long xh0 = s_vpx.hits, xm0 = s_vpx.misses;
    if (ixo) {
''')
sub('''            if (!ps3_prim_stream_push(&s_prim_stream, idx, tri)
                || o + 3 > ixc) continue;
            for (int c = 0; c < 3; c++) {
                int fresh;
                const u32 l = vpi_find(&s_vpi, tri[c], nv, &fresh);
                if (fresh) {
                    const u32 vi = tri[c];
                    vpc_put_vertex((u8*)out, nv, cs, ff ? vfp_vertex(&s_vpx, &s_vfp, vi, 0) : vpx_vertex(&s_vpx, vi), cact, cn);
                    nv++;
                }
                s_vpi_ix[o++] = (u16)l;
            }
        }
        dspl_mark(DSPL_EMIT);
        if (!o) return 0;
        memcpy((u8*)out + VPC_UNIT + (size_t)nv * cs, s_vpi_ix, (size_t)o * 2u);
''', '''            if (!ps3_prim_stream_push(&s_prim_stream, idx, tri)
                || o + 3 > ixc) { XS(XS_STREAM); continue; }
            XS(XS_STREAM);
            for (int c = 0; c < 3; c++) {
                int fresh;
                const u32 l = vpi_find(&s_vpi, tri[c], nv, &fresh);
                XS(XS_FIND);
                if (fresh) {
                    const u32 vi = tri[c];
                    const float (*xv)[4] = ff ? vfp_vertex(&s_vpx, &s_vfp, vi, 0) : vpx_vertex(&s_vpx, vi);
                    XS(XS_CONV);
                    vpc_put_vertex((u8*)out, nv, cs, xv, cact, cn);
                    XS(XS_PUT);
                    nv++;
                }
                s_vpi_ix[o++] = (u16)l;
            }
            XS(XS_FIND);
        }
        dspl_mark(DSPL_EMIT);
        if (!o) return 0;
        memcpy((u8*)out + VPC_UNIT + (size_t)nv * cs, s_vpi_ix, (size_t)o * 2u);
        XS(XS_IXCOPY); if (xs_on) { xs_hit += s_vpx.hits - xh0; xs_miss += s_vpx.misses - xm0; if ((xs_draws & 4095u) == 0) xs_report(); }
''')
for fn, call in (('ff', 'vfp_vertex(&s_vpx, &s_vfp, tri[%d], full)'), ('plain', 'vpx_vertex(&s_vpx, tri[%d])')):
    ind = '                ' if fn == 'ff' else '            '
    a = ''.join(f'{ind}vpc_put_vertex((u8*)out, o, cs, {call % i}, cact, cn); o++;\n' for i in range(3))
    b = ''.join(f'{ind}{{ const float (*xv)[4] = {call % i}; XS(XS_CONV); vpc_put_vertex((u8*)out, o, cs, xv, cact, cn); XS(XS_PUT); o++; }}\n' for i in range(3))
    sub(a, ind + 'XS(XS_STREAM);\n' + b + ind + 'if (xs_on && o + 3 >= maxv) { }\n')
sub('''    dspl_mark(DSPL_EMIT);
    if (!o) return 0;   /* vp_reserve named it: too_few_vertices or vertex_buffer_full */
''', '''    dspl_mark(DSPL_EMIT);
    if (xs_on) { xs_hit += s_vpx.hits - xh0; xs_miss += s_vpx.misses - xm0; if ((xs_draws & 4095u) == 0) xs_report(); }
    if (!o) return 0;   /* vp_reserve named it: too_few_vertices or vertex_buffer_full */
''')
if crlf:
    s = s.replace('\n', '\r\n')
open(F, 'w', encoding='utf-8', errors='surrogateescape', newline='').write(s)
