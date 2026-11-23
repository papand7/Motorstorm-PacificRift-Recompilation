"""RSX_TEX_PBR_AB=<n> (diagnostic): the PBR lighting on and off by turns every n presented frames, each
switch logged with the wall-clock second, for pictures of both in one race. rsx_draw_engine.c is CRLF.

usage: py -3 edit_pbr_engine2.py"""
import pathlib

V = pathlib.Path(__file__).resolve().parents[4] / 'ps3recomp-vkgame' / 'libs' / 'video'


def edit(name, subs):
    p = V / name
    raw = p.read_bytes().decode('utf-8')
    crlf = '\r\n' in raw
    s = raw.replace('\r\n', '\n')
    for a, b in subs:
        assert s.count(a) == 1, (name, a[:80], s.count(a))
        s = s.replace(a, b)
    if crlf:
        s = s.replace('\n', '\r\n')
    p.write_bytes(s.encode('utf-8'))
    print('edited', name)


edit('rsx_draw_engine.c', [
("""    u32 n;
    float strength;
} s_pbr = { 0, {0, 0, 0}, {{0}}, {0}, 0, -1.0f };""",
"""    u32 n;
    float strength;
    u32 ab;                           /* RSX_TEX_PBR_AB period in frames, 0 = off */
} s_pbr = { 0, {0, 0, 0}, {{0}}, {0}, 0, -1.0f, 0 };"""),
("""        s_pbr.n = 0;
        s_pbr.frame = g.frames;
    }""",
"""        s_pbr.n = 0;
        s_pbr.frame = g.frames;
        if (s_pbr.ab && g.frames % s_pbr.ab == 0) {
            static u32 logs = 0;
            if (PS3_LOG_FIRST(logs, 400))
                fprintf(stderr, "[tex-pbr] A/B: %s from frame %u (t=%lld)\\n",
                        (g.frames / s_pbr.ab) & 1u ? "off" : "on", g.frames, (long long)time(NULL));
        }
    }"""),
("""/* RSX_TEX_PBR_STRENGTH (default 0.6, 0..2): how far the detail normal bends the sun's light. */
static float eng_pbr_strength(void)
{
    if (s_pbr.strength < 0.0f) {
        const char* e = getenv("RSX_TEX_PBR_STRENGTH");
        float k = e && *e ? (float)atof(e) : 0.6f;
        s_pbr.strength = k < 0.0f ? 0.0f : k > 2.0f ? 2.0f : k;
    }
    return s_pbr.strength;
}""",
"""/* RSX_TEX_PBR_STRENGTH (default 0.6, 0..2): how far the detail normal bends the sun's light.
 * RSX_TEX_PBR_AB=<n> (diagnostic): on and off by turns every n presented frames. */
static float eng_pbr_strength(void)
{
    if (s_pbr.strength < 0.0f) {
        const char* e = getenv("RSX_TEX_PBR_STRENGTH");
        float k = e && *e ? (float)atof(e) : 0.6f;
        s_pbr.strength = k < 0.0f ? 0.0f : k > 2.0f ? 2.0f : k;
        const char* ab = getenv("RSX_TEX_PBR_AB");
        s_pbr.ab = ab && *ab ? (u32)atoi(ab) : 0u;
    }
    if (s_pbr.ab && ((g.frames / s_pbr.ab) & 1u)) return 0.0f;
    return s_pbr.strength;
}"""),
])
