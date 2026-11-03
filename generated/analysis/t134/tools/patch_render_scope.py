"""T134: RSX_RECORD as a cleanup-scoped span inside render_frame (the GSW_OP_SCOPE idiom) instead of
a wrapper function, so the render_frame source pins of test_vp_flush / test_rf_phase /
test_draw_rejection / test_tex_snapshot_epoch keep reading the real body. One-shot patch."""
from pathlib import Path
import sys

W = Path(sys.argv[1])
p = W / 'libs/video/rsx_d3d12_backend.c'
raw = p.read_text(encoding='utf-8')
crlf = '\r\n' in raw
t = raw.replace('\r\n', '\n')

old = '''static void render_frame_body(void);
/* PS3_FTRACE / PS3_CRITICAL_PATH_TRACE (T134): the whole replay, a = 0, b = presented. */
static void render_frame(void)
{
    const uint64_t ft_t0 = PS3_FT_ON() ? ps3_ft_now() : 0;
    render_frame_body();
    if (ft_t0) ps3_ft_span(PS3_FT_RSX_RECORD, 0, 0, (uint32_t)s_present_this_frame, ft_t0, ps3_ft_now());
}

static void render_frame_body(void)
{
    pp_note(PP_REPLAY);'''
new = '''/* PS3_FTRACE / PS3_CRITICAL_PATH_TRACE (T134): the whole replay as one span, closed on every
 * return like GSW_OP_SCOPE; a = 0, b = presented. */
static void rf_ft_end(const uint64_t* t0)
{
    if (*t0) ps3_ft_span(PS3_FT_RSX_RECORD, 0, 0, (uint32_t)s_present_this_frame, *t0, ps3_ft_now());
}

static void render_frame(void)
{
    const uint64_t ft_rf0 __attribute__((cleanup(rf_ft_end))) = PS3_FT_ON() ? ps3_ft_now() : 0;
    pp_note(PP_REPLAY);'''
assert t.count(old) == 1
t = t.replace(old, new)
if crlf:
    t = t.replace('\n', '\r\n')
p.write_text(t, encoding='utf-8', newline='')

q = W / 'tools/test_tex_snapshot_epoch.py'
s = q.read_text(encoding='utf-8')
o = "            and 'tsnap_epoch_init();' in (body(be, 'render_frame_body') or body(be, 'render_frame'))   # T134: render_frame wraps the body\n"
assert s.count(o) == 1
s = s.replace(o, "            and 'tsnap_epoch_init();' in body(be, 'render_frame')\n")
q.write_text(s, encoding='utf-8')

r = W / 'tools/test_cpath_trace.py'
u = r.read_text(encoding='utf-8')
o = "        'if (ft_t0) ps3_ft_span(PS3_FT_RSX_RECORD, 0, 0, (uint32_t)s_present_this_frame, ft_t0, ps3_ft_now());',\n"
assert u.count(o) == 1
u = u.replace(o, "        'if (*t0) ps3_ft_span(PS3_FT_RSX_RECORD, 0, 0, (uint32_t)s_present_this_frame, *t0, ps3_ft_now());',\n"
                 "        'const uint64_t ft_rf0 __attribute__((cleanup(rf_ft_end))) = PS3_FT_ON() ? ps3_ft_now() : 0;',\n")
r.write_text(u, encoding='utf-8')
print('patched')
