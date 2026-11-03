"""T119 commit 2: read the per-draw / per-bind / per-record debug switches once (rsx_d3d12_backend.c, CRLF).

  py -3 patch_getenv.py <worktree>
"""
import pathlib, sys

p = pathlib.Path(sys.argv[1]) / 'libs/video/rsx_d3d12_backend.c'
raw = p.read_bytes().decode('utf-8')
assert raw.count('\r\n') == raw.count('\n')
t = raw.replace('\r\n', '\n')


def rep(a, b, n=1):
    global t
    assert t.count(a) == n, (t.count(a), a[:80])
    t = t.replace(a, b)


# vp_get_fp_pso, every record at replay
rep('''        if (getenv("FP_CONSTBUF") && getenv("FP_CONSTBUF")[0] == '0') {''',
    '''        static int fpcb_off = -1;   /* FP_CONSTBUF=0: hash the constants too (read once) */
        if (fpcb_off < 0) { const char* e = getenv("FP_CONSTBUF"); fpcb_off = (e && e[0] == '0') ? 1 : 0; }
        if (fpcb_off) {''')
# vp_record_cb, every record
rep('''        if (dr && !getenv("NO_ALPHATEST")) {''',
    '''        static int no_at = -1;
        if (no_at < 0) no_at = getenv("NO_ALPHATEST") ? 1 : 0;
        if (dr && !no_at) {''')
rep('''    if (getenv("VP_NOFIXPROJ")) garbage = 0;
    if ((garbage && uses_c03) || getenv("VP_FIXPROJ")) {''',
    '''    static int nofix = -1, fix = -1;
    if (nofix < 0) { nofix = getenv("VP_NOFIXPROJ") ? 1 : 0; fix = getenv("VP_FIXPROJ") ? 1 : 0; }
    if (nofix) garbage = 0;
    if ((garbage && uses_c03) || fix) {''')
# vp_attrs_dbg: every tris / quads draw
rep('''    if (!getenv("VP_ATTRS")) return;''',
    '''    static int on = -1;
    if (on < 0) on = getenv("VP_ATTRS") ? 1 : 0;
    if (!on) return;''')
# upload_tris_vp: every non-indexed tris draw
rep('''    if (getenv("VTX_DUMP") && state->surface_color_offset[0] == 0xCC0000) {''',
    '''    static int vtx_dump = -1;
    if (vtx_dump < 0) vtx_dump = getenv("VTX_DUMP") ? 1 : 0;
    if (vtx_dump && state->surface_color_offset[0] == 0xCC0000) {''')
# upload_quads_vp / upload_quads_vp_indexed: every quad
rep('''        for (int t = 0; t < 6; t++) { memcpy(&out[o*16], c[idx[t]], sizeof(c[0])); o++; }
        if (getenv("VTX_DUMP")) { static int _n=0; if (PS3_LOG_FIRST(_n, 4)) {''',
    '''        for (int t = 0; t < 6; t++) { memcpy(&out[o*16], c[idx[t]], sizeof(c[0])); o++; }
        static int vtx_dump = -1;
        if (vtx_dump < 0) vtx_dump = getenv("VTX_DUMP") ? 1 : 0;
        if (vtx_dump) { static int _n=0; if (PS3_LOG_FIRST(_n, 4)) {''')
rep('''        for (int t = 0; t < 6; t++) { memcpy(&out[o*16], c[idx[t]], sizeof(c[0])); o++; }
        if (getenv("VTX_DUMP")) { static int _n=0; if (PS3_LOG_FIRST(_n, 6)) {''',
    '''        for (int t = 0; t < 6; t++) { memcpy(&out[o*16], c[idx[t]], sizeof(c[0])); o++; }
        static int vtx_dump = -1;
        if (vtx_dump < 0) vtx_dump = getenv("VTX_DUMP") ? 1 : 0;
        if (vtx_dump) { static int _n=0; if (PS3_LOG_FIRST(_n, 6)) {''')
# d3d12_bind_texture: every bind
rep('''    if (getenv("MOVIE_BIND") &&''',
    '''    static int movie_bind = -1;
    if (movie_bind < 0) movie_bind = getenv("MOVIE_BIND") ? 1 : 0;
    if (movie_bind &&''')
rep('''        if (getenv("TEXFMTDBG")) { static u32 seen[64]; static int ns=0;''',
    '''        static int texfmtdbg = -1;
        if (texfmtdbg < 0) texfmtdbg = getenv("TEXFMTDBG") ? 1 : 0;
        if (texfmtdbg) { static u32 seen[64]; static int ns=0;''')

p.write_bytes(t.replace('\n', '\r\n').encode('utf-8'))
print('patched', p)
