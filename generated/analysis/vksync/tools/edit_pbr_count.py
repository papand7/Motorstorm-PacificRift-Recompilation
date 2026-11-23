"""RSX_TEX_PBR: log how many draws use a rewritten program and how many of them got a PBR map,
averaged over 300 frames (at most 64 lines). Kk65 stills could not tell whether the sand is lit.
rsx_draw_engine.c is CRLF.

usage: py -3 edit_pbr_count.py"""
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
("""    u32 ab;                           /* RSX_TEX_PBR_AB period in frames, 0 = off */
} s_pbr = { 0, {0, 0, 0}, {{0}}, {0}, 0, -1.0f, 0 };
""",
"""    u32 ab;                           /* RSX_TEX_PBR_AB period in frames, 0 = off */
    u32 since, draws, mapped;         /* rewritten draws, and those with a map, since frame `since` */
} s_pbr = { 0, {0, 0, 0}, {{0}}, {0}, 0, -1.0f, 0, 0, 0, 0 };
"""),

("""        s_pbr.n = 0;
        s_pbr.frame = g.frames;
""",
"""        s_pbr.n = 0;
        s_pbr.frame = g.frames;
        if (g.frames - s_pbr.since >= 300u) {
            static u32 logs = 0;
            const u32 nf = g.frames - s_pbr.since;
            if (s_pbr.since && PS3_LOG_FIRST(logs, 64))
                fprintf(stderr, "[tex-pbr] frames %u-%u: %.1f rewritten draw(s) a frame, %.1f with a map\\n",
                        s_pbr.since, g.frames - 1u, (double)s_pbr.draws / nf, (double)s_pbr.mapped / nf);
            s_pbr.since = g.frames;
            s_pbr.draws = s_pbr.mapped = 0;
        }
"""),

("""        eng_pbr_vote(pp);
        if (((tex_mask >> su) & 1u) && s_unit_pbr[su]) {
            textures[pu] = s_unit_pbr[su];""",
"""        eng_pbr_vote(pp);
        s_pbr.draws++;
        if (((tex_mask >> su) & 1u) && s_unit_pbr[su]) {
            s_pbr.mapped++;
            textures[pu] = s_unit_pbr[su];"""),
])
