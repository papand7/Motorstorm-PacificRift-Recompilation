r"""rsx_draw_engine.c: RSX_ENGINE_PASS_DUMP_ALPHA=1 (diagnostic, off by default) also writes each dumped
colour surface's alpha channel to <name>_a.pgm next to its .ppm, and adds the alpha blend factors and the
blend equations ("ba <sf_a>/<df_a> eq <rgb>/<a>") to each draws.txt line. Rendering is unchanged.
Keeps the file's CRLF line ends. usage: py -3 patch_pd_alpha.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[4] / 'ps3recomp-vkgame' / 'libs' / 'video' / 'rsx_draw_engine.c'
b = p.read_bytes()
nl = b'\r\n' if b'\r\n' in b else b'\n'
s = b.decode('utf-8').replace('\r\n', '\n')
if 'RSX_ENGINE_PASS_DUMP_ALPHA' in s:
    print('already patched'); raise SystemExit


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:60]
    s = s.replace(old, new)


rep(" * also writes one line per draw to <dir>/draws.txt: its pipeline, colour\n"
    " * mask, blend, depth state and the textures it samples.\n",
    " * also writes one line per draw to <dir>/draws.txt: its pipeline, colour\n"
    " * mask, blend, depth state and the textures it samples.\n"
    " * RSX_ENGINE_PASS_DUMP_ALPHA=1 also writes each colour target's alpha to\n"
    " * <name>_a.pgm beside its .ppm, and puts each draw's alpha blend factors and\n"
    " * blend equations (\"ba sf/df eq rgb/a\") in its draws.txt line.\n")

rep("/* One colour surface to a binary PPM, alpha dropped, floats clamped to [0,1]. */\n"
    "static void pd_write_surface(u32 slot, const char* path)\n",
    "/* One colour surface to a binary PPM, floats clamped to [0,1]; with\n"
    " * RSX_ENGINE_PASS_DUMP_ALPHA its alpha to a PGM beside it (\".ppm\" -> \"_a.pgm\"). */\n"
    "static void pd_write_surface(u32 slot, const char* path)\n")

rep("    u8* rgb = (u8*)malloc((size_t)s->w * s->h * 3u);\n"
    "    FILE* f = (raw && rgb) ? fopen(path, \"wb\") : NULL;\n",
    "    u8* rgb = (u8*)malloc((size_t)s->w * s->h * 3u);\n"
    "    u8* alpha = getenv(\"RSX_ENGINE_PASS_DUMP_ALPHA\") ? (u8*)malloc((size_t)s->w * s->h) : NULL;\n"
    "    FILE* f = (raw && rgb) ? fopen(path, \"wb\") : NULL;\n")

rep("            if (s->fmt == RSX_BE_FMT_R8G8B8A8) {\n"
    "                o[0] = p[0]; o[1] = p[1]; o[2] = p[2];\n"
    "            } else if (s->fmt == RSX_BE_FMT_R16G16B16A16F) {\n"
    "                for (u32 c = 0; c < 3; c++) {\n"
    "                    u16 h; memcpy(&h, p + c * 2u, 2);\n"
    "                    o[c] = pd_unit(pd_half(h));\n"
    "                }\n"
    "            } else if (s->fmt == RSX_BE_FMT_R32G32B32A32F) {\n"
    "                for (u32 c = 0; c < 3; c++) {\n"
    "                    float v; memcpy(&v, p + c * 4u, 4);\n"
    "                    o[c] = pd_unit(v);\n"
    "                }\n"
    "            } else {\n"
    "                float v; memcpy(&v, p, 4);\n"
    "                o[0] = o[1] = o[2] = pd_unit(v);\n"
    "            }\n",
    "            u8 a = 255;\n"
    "            if (s->fmt == RSX_BE_FMT_R8G8B8A8) {\n"
    "                o[0] = p[0]; o[1] = p[1]; o[2] = p[2];\n"
    "                a = p[3];\n"
    "            } else if (s->fmt == RSX_BE_FMT_R16G16B16A16F) {\n"
    "                for (u32 c = 0; c < 3; c++) {\n"
    "                    u16 h; memcpy(&h, p + c * 2u, 2);\n"
    "                    o[c] = pd_unit(pd_half(h));\n"
    "                }\n"
    "                u16 h; memcpy(&h, p + 6u, 2);\n"
    "                a = pd_unit(pd_half(h));\n"
    "            } else if (s->fmt == RSX_BE_FMT_R32G32B32A32F) {\n"
    "                for (u32 c = 0; c < 3; c++) {\n"
    "                    float v; memcpy(&v, p + c * 4u, 4);\n"
    "                    o[c] = pd_unit(v);\n"
    "                }\n"
    "                float v; memcpy(&v, p + 12u, 4);\n"
    "                a = pd_unit(v);\n"
    "            } else {\n"
    "                float v; memcpy(&v, p, 4);\n"
    "                o[0] = o[1] = o[2] = pd_unit(v);\n"
    "            }\n"
    "            if (alpha) alpha[i] = a;\n")

rep("        fprintf(f, \"P6\\n%u %u\\n255\\n\", s->w, s->h);\n"
    "        fwrite(rgb, 1, (size_t)s->w * s->h * 3u, f);\n"
    "        fclose(f);\n"
    "    }\n"
    "    free(raw);\n"
    "    free(rgb);\n",
    "        fprintf(f, \"P6\\n%u %u\\n255\\n\", s->w, s->h);\n"
    "        fwrite(rgb, 1, (size_t)s->w * s->h * 3u, f);\n"
    "        fclose(f);\n"
    "        const size_t n = strlen(path);\n"
    "        char apath[1024];\n"
    "        if (alpha && n > 4 && n < sizeof apath - 4) {\n"
    "            memcpy(apath, path, n - 4);\n"
    "            memcpy(apath + n - 4, \"_a.pgm\", 7);\n"
    "            FILE* fa = fopen(apath, \"wb\");\n"
    "            if (fa) {\n"
    "                fprintf(fa, \"P5\\n%u %u\\n255\\n\", s->w, s->h);\n"
    "                fwrite(alpha, 1, (size_t)s->w * s->h, fa);\n"
    "                fclose(fa);\n"
    "            }\n"
    "        }\n"
    "    }\n"
    "    free(raw);\n"
    "    free(rgb);\n"
    "    free(alpha);\n")

rep("                rs->blend_enable, rs->sf_rgb, rs->df_rgb, rs->depth_test, rs->depth_write,\n"
    "                rs->alpha_test_enable);\n",
    "                rs->blend_enable, rs->sf_rgb, rs->df_rgb, rs->depth_test, rs->depth_write,\n"
    "                rs->alpha_test_enable);\n"
    "        if (getenv(\"RSX_ENGINE_PASS_DUMP_ALPHA\"))\n"
    "            fprintf(s_pd.draws_log, \" ba %X/%X eq %X/%X cmrt %08X\", rs->sf_a, rs->df_a,\n"
    "                    rs->eq_rgb, rs->eq_a, rs->color_mask_mrt);\n")

p.write_bytes(s.replace('\n', nl.decode()).encode('utf-8'))
print('patched', p.name, 'CRLF' if nl == b'\r\n' else 'LF')
