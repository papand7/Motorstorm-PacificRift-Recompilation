r"""RSX_TEX_BORDER=1 (opt-in): the Vulkan engine sampler takes the guest's SET_TEXTURE_BORDER_COLOR (nearest
of Vulkan's three built-in border colours, rsx_tex_border.h) for units whose wrap is BORDER, instead of
always transparent black. Each distinct border word met on a BORDER unit is logged once (16 at most).
RSX_ENGINE_PASS_DUMP_ALPHA's draws.txt lines also get each texture's raw wrap and border words.
Keeps every file's line ends. usage: py -3 patch_tex_border.py"""
import pathlib

V = pathlib.Path(__file__).resolve().parents[4] / 'ps3recomp-vkgame' / 'libs' / 'video'


def patch(name, pairs):
    p = V / name
    b = p.read_bytes()
    crlf = b'\r\n' in b
    s = b.decode('utf-8').replace('\r\n', '\n')
    for old, new in pairs:
        assert s.count(old) == 1, (name, old[:70])
        s = s.replace(old, new)
    p.write_bytes((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
    print('patched', name, 'CRLF' if crlf else 'LF')


patch('rsx_draw_engine.h', [(
    "    float lod_bias;           /* FILTER [12:0] with RSX_TEX_LOD_BIAS=1, else 0 */\n"
    "} rsx_be_sampler_desc;\n",
    "    float lod_bias;           /* FILTER [12:0] with RSX_TEX_LOD_BIAS=1, else 0 */\n"
    "    u8  border;               /* RSX_TEX_BORDER=1: rsx_tex_border.h class of BORDER_COLOR\n"
    "                               * on a BORDER unit; else 0, transparent black */\n"
    "} rsx_be_sampler_desc;\n")])

patch('rsx_draw_engine.c', [
    ('#include "rsx_shadow_cap.h"\n',
     '#include "rsx_shadow_cap.h"\n#include "rsx_tex_border.h"\n'),
    ("static void eng_decode_sampler(u32 filter, u32 wrap, u32 control0,\n"
     "                               rsx_be_sampler_desc* out)\n"
     "{\n",
     "/* RSX_TEX_BORDER=1: a BORDER unit's sampler takes the guest's border colour\n"
     " * (rsx_tex_border.h). */\n"
     "static int eng_tex_border_on(void)\n"
     "{\n"
     "    static int on = -1;\n"
     "    if (on < 0) { const char* e = getenv(\"RSX_TEX_BORDER\"); on = (e && e[0] == '1' && !e[1]) ? 1 : 0; }\n"
     "    return on;\n"
     "}\n"
     "\n"
     "static void eng_decode_sampler(u32 filter, u32 wrap, u32 control0, u32 border_color,\n"
     "                               rsx_be_sampler_desc* out)\n"
     "{\n"
     "    out->border = RSX_TEX_BORDER_TRANSPARENT_BLACK;\n"
     "    if (eng_tex_border_on() && rsx_tex_border_used(wrap)) {\n"
     "        int exact = 0;\n"
     "        out->border = rsx_tex_border_class(border_color, &exact);\n"
     "        static u32 seen[16];\n"
     "        static u32 n_seen;\n"
     "        u32 i = 0;\n"
     "        while (i < n_seen && seen[i] != border_color) i++;\n"
     "        if (i == n_seen && n_seen < 16u) {\n"
     "            seen[n_seen++] = border_color;\n"
     "            static const char* const name[3] = { \"transparent black\", \"opaque black\", \"opaque white\" };\n"
     "            fprintf(stderr, \"[rsx engine] texture border colour 0x%08X (wrap 0x%05X): %s%s\\n\",\n"
     "                    border_color, wrap & 0xFFFFFu, name[out->border], exact ? \"\" : \" (nearest)\");\n"
     "        }\n"
     "    }\n"),
    ("        eng_decode_sampler(t.filter, t.wrap, t.control0, &samplers[u]);\n",
     "        eng_decode_sampler(t.filter, t.wrap, t.control0, t.border_color, &samplers[u]);\n"),
    ("        eng_decode_sampler(vt.filter, vt.wrap, vt.control0, &samplers[u]);\n",
     "        eng_decode_sampler(vt.filter, vt.wrap, vt.control0, vt.border_color, &samplers[u]);\n"),
    ("            fprintf(s_pd.draws_log, \" t%u %u:0x%08X f%02X %ux%u\", u, t.location, t.offset,\n"
     "                    t.format & 0xFFu, t.width, t.height);\n",
     "            fprintf(s_pd.draws_log, \" t%u %u:0x%08X f%02X %ux%u\", u, t.location, t.offset,\n"
     "                    t.format & 0xFFu, t.width, t.height);\n"
     "            if (getenv(\"RSX_ENGINE_PASS_DUMP_ALPHA\"))\n"
     "                fprintf(s_pd.draws_log, \" w%05X b%08X\", t.wrap & 0xFFFFFu, t.border_color);\n"),
])

patch('rsx_vulkan_backend.c', [
    ("                  | ((u64)(lo >> 16) << 16) | ((u64)(hi >> 16) << 32) | ((u64)aniso << 48);\n",
     "                  | ((u64)(lo >> 16) << 16) | ((u64)(hi >> 16) << 32) | ((u64)aniso << 48)\n"
     "                  | ((u64)(d->border & 3u) << 56);\n"),
    ("        .mipLodBias = bias, .minLod = min_lod, .maxLod = max_lod,\n"
     "        .borderColor = VK_BORDER_COLOR_FLOAT_TRANSPARENT_BLACK };\n",
     "        .mipLodBias = bias, .minLod = min_lod, .maxLod = max_lod,\n"
     "        /* rsx_tex_border.h's classes; 0 unless RSX_TEX_BORDER=1. */\n"
     "        .borderColor = d->border == 2u ? VK_BORDER_COLOR_FLOAT_OPAQUE_WHITE\n"
     "                     : d->border == 1u ? VK_BORDER_COLOR_FLOAT_OPAQUE_BLACK\n"
     "                                       : VK_BORDER_COLOR_FLOAT_TRANSPARENT_BLACK };\n"),
])
