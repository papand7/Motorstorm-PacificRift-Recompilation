MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T102: bench_vp_expand gets S5 (vp_expand.h, what the backend now runs) and
three workload sizes. Asserting replacements."""
import pathlib
p = pathlib.Path((MS_ROOT + r'\ps3recomp-t102\libs\video\tests\bench_vp_expand.c'))
s = p.read_text(encoding='utf-8')
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, (old[:70], n)
    s = s.replace(old, new)


rep(''' *   S4 idx+compact: S3 writing only the enabled attributes (theoretical: the
 *                  VS input layout would have to change).
''', ''' *   S4 idx+compact: S3 writing only the enabled attributes (theoretical: the
 *                  VS input layout would have to change).
 *   S5 vpx       : include/ps3emu/vp_expand.h, what the backend runs since
 *                  T102: S2 plus a per-draw template for the slots whose fetch
 *                  cannot depend on the index (disabled / stride 0), so a
 *                  conversion fetches only the enabled attributes. Same output
 *                  bytes as S0 (checked).
''')
rep(''' * S1 and S2 are checked byte-for-byte against S0''', ''' * Sizes (T102): 1400 batches (432k expanded vertices, T99), 1700 (about 525k,
 * a T98 race guest frame) and 3240 (about 1M), S0 against S5.
 *
 * S1, S2 and S5 are checked byte-for-byte against S0''')
rep('#include "ps3emu/prim_stream.h"\n', '#include "ps3emu/prim_stream.h"\n#include "ps3emu/vp_expand.h"\n')
rep('#define NB 1400u                               /* batches: about one race guest frame */',
    '#define NB_MAX 3240u                           /* batches: about 1M expanded vertices */\n'
    'static u32 NB = 1400u;                         /* batches in the current run */')
rep('''    vm_base = calloc(1, (size_t)IDX_BASE + NB * BI * 2u + 64);''',
    '''    vm_base = calloc(1, (size_t)IDX_BASE + NB_MAX * BI * 2u + 64);''')
rep('''    make_indices();
    const size_t cap = (size_t)NB * 309u * VSTRIDE;   /* 110 MB */''',
    '''    NB = NB_MAX; make_indices(); NB = 1400u;          /* indices for the largest run */
    const size_t cap = (size_t)NB_MAX * 309u * VSTRIDE;   /* 256 MB */''')
rep('''    u8* wci = alloc_wc((size_t)NB * 309u * 2u, &wc2);''', '''    u8* wci = alloc_wc((size_t)NB_MAX * 309u * 2u, &wc2);''')
rep('''    const u32 nverts = NB * 205u;''', '''    const u32 nverts = NB_MAX * 205u;''')

# S5 runner after run_s2
rep('''/* S3/S4: unique vertices once (per batch, base-relative), plus u16 indices. */''',
    '''static void s5_attr(const void* st, int idx, uint32_t vi, float out[4]) { rsx_fetch_attrib((const rsx_state*)st, idx, vi, out); }
static vpx_cache s5c;
static res run_s5(const rsx_state* st, u8* wc, int unused)
{
    (void)unused;
    static u32 tri[3 * BI];
    res r = {0, 0, 0}; u64 off = 0;
    int act[16];
    for (int i = 0; i < 16; i++) act[i] = st->vertex_attribs[i].enabled && st->vertex_attribs[i].stride != 0;
    const double t0 = now_s();
    for (u32 b = 0; b < NB; b++) {
        vpx_begin(&s5c, st, s5_attr, NULL, act, (const float (*)[4])st->vertex_data4f);   /* one draw per batch */
        const u32 n = batch_tris(b, tri);
        for (u32 k = 0; k < n; k++) { vpx_emit(&s5c, tri[k], wc + off); off += VSTRIDE; }
        r.verts += n;
    }
    r.s = now_s() - t0; r.bytes = off;
    return r;
}
/* S3/S4: unique vertices once (per batch, base-relative), plus u16 indices. */''')
rep('''        run_s2(&st, chk);     const int ok2 = memcmp(chk, ref, r0.bytes) == 0;''',
    '''        run_s2(&st, chk);     const int ok2 = memcmp(chk, ref, r0.bytes) == 0;
        run_s5(&st, chk, 0);  const int ok5 = memcmp(chk, ref, r0.bytes) == 0;''')
rep('''        CHECK(ok1 && ok2 && ok3, "layout %d attrs: S1, S2 and S3 (re-expanded) equal S0 byte for byte", layouts[li]);''',
    '''        CHECK(ok1 && ok2 && ok3 && ok5, "layout %d attrs: S1, S2, S5 and S3 (re-expanded) equal S0 byte for byte", layouts[li]);''')
rep('''        res s4 = run_s3(&st, wc, wci, 1, &nu, &ib); for (int i = 0; i < 4; i++) { res x = run_s3(&st, wc, wci, 1, &nu, &ib); if (x.s < s4.s) s4 = x; }''',
    '''        res s4 = run_s3(&st, wc, wci, 1, &nu, &ib); for (int i = 0; i < 4; i++) { res x = run_s3(&st, wc, wci, 1, &nu, &ib); if (x.s < s4.s) s4 = x; }
        res s5 = best(run_s5, &st, wc, 0);''')
rep('''        const res* rs[5] = { &a, &s1, &s2, &s3, &s4 };
        const char* nm[5] = { "S0 current", "S1 staged", "S2 vcache", "S3 indexed", "S4 idx+compact" };
        for (int k = 0; k < 5; k++)''', '''        const res* rs[6] = { &a, &s1, &s2, &s3, &s4, &s5 };
        const char* nm[6] = { "S0 current", "S1 staged", "S2 vcache", "S3 indexed", "S4 idx+compact", "S5 vpx (T102)" };
        for (int k = 0; k < 6; k++)''')
rep('''    /* Per-draw shader lookups hash guest microcode byte-wise (FNV-1a):''',
    '''    /* T102 sizes: S0 (pre-T102 backend) against S5 (T102 backend). */
    { const u32 sizes[3] = { 1400u, 1700u, 3240u };
      for (int li = 0; li < 3; li++) {
          rsx_state st; make_state(&st, layouts[li], nverts);
          for (int si = 0; si < 3; si++) {
              NB = sizes[si];
              res a = best(run_s0, &st, wc, 0), b = best(run_s5, &st, wc, 0);
              printf("[INFO] size %u batches, layout %d: %llu expanded vertices, %.0f MB: S0 %.1f ms, S5 %.1f ms, x%.2f, "
                     "conversions per expanded vertex 1.00 -> %.2f\\n", NB, layouts[li], (unsigned long long)a.verts,
                     a.bytes / 1048576.0, a.s * 1e3, b.s * 1e3, a.s / b.s, 205.0 / 309.0);
          }
          NB = 1400u;
      } }
    /* Per-draw shader lookups hash guest microcode byte-wise (FNV-1a):''')
s = s.replace('\n', '\r\n') if crlf else s
p.write_text(s, encoding='utf-8', newline='')
print('ok')
