/* PC button prompts: the game's PS3 button icons redrawn as keyboard key caps.
 *
 * The prompts ("Press (X) to Skip", the menus' button bar, the pause prompt)
 * are not font glyphs: each icon is baked into a GUI texture (DXT5/BC3) of the
 * game's .gui packs, either a texture of its own (x_button.dds, 40x40) or part
 * of a larger one (x_to_skip_prompt.dds, 500x84: the bar with the icon in it).
 * generated/analysis/prompts/RESULTS.md has the evidence. This header knows
 * those textures by size and a hash of their level-0 bytes (k_pcpr_icons: no
 * game data, only where each icon is and which button it shows) and, as the
 * draw engine uploads one (rsx_draw_engine_set_tex_patch), redraws its icon
 * area as a key cap labelled with the first key bound to that button.
 *
 * The art is our own: a rounded key cap and a small built-in stroke font
 * (upper case, digits, a few signs, arrows), drawn procedurally. Nothing of
 * the original icon is kept but the pixels around it.
 *
 * Header-only and free of process state: tested by port-vkgame/tests/
 * test_pc_prompts.c. pc_menu.cpp owns the mode (settings.ini "prompts") and the
 * live key layout and registers the hook. */
#ifndef PC_PROMPTS_H
#define PC_PROMPTS_H

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cellPad.h"
#include "pad_keyboard_map.h"

enum { PCPR_CROSS, PCPR_CIRCLE, PCPR_SQUARE, PCPR_TRIANGLE, PCPR_START, PCPR_SELECT, PCPR_L1, PCPR_R1,
       PCPR_LEFT, PCPR_RIGHT, PCPR_BUTTONS };

/* One icon in one known texture: the original icon's own rectangle (centre
 * cx, cy and size rw x rh, level-0 texels). The key cap fills exactly that
 * rectangle and never more, so text the game lays out round the icon is never
 * covered; a long key name is drawn as a symbol or condensed and scaled down to
 * fit. clear: the texture is the icon alone (cleared to transparent first). */
typedef struct {
    uint16_t w, h;
    uint64_t hash;      /* pcpr_hash of level 0 */
    uint8_t  button;    /* PCPR_* */
    uint8_t  clear;
    float    cx, cy, rw, rh;
    const char* name;   /* for the log */
} pcpr_icon;

/* Found with generated/analysis/prompts/tools/find_icons.py over the 1.00 GUI
 * packs; every texture below was checked by eye (prompts/icons/). The rects
 * are the icon's ring, pill or glyph (with its glow for the icon-only ones). */
static const pcpr_icon k_pcpr_icons[] = {
    /* the race HUD's skip prompts (osd-main*, results pages): the 35 px ring */
    { 500,  84, 0xF86E70327AB00205ull, PCPR_CROSS,  0, 232.5f, 37.5f, 35, 35, "x_to_skip_prompt" },
    { 500,  84, 0xDA96211D23ECF327ull, PCPR_CROSS,  0, 234.0f, 37.5f, 34, 34, "x_to_skip_prompt (results)" },
    { 500,  84, 0x8AC20CA9B6704BC3ull, PCPR_CIRCLE, 0, 232.5f, 37.5f, 35, 35, "o_to_skip_prompt" },
    /* the intro video pages */
    { 420, 120, 0x0EA8E167DB3E8F1Aull, PCPR_CROSS,  0, 205.5f, 58.5f, 35, 35, "x_intro_page" },
    { 420, 120, 0xCBD4E3A508C3943Full, PCPR_CROSS,  0, 343.5f, 58.5f, 35, 35, "x_intro_page_alt" },
    { 420, 120, 0x00C0E95191085646ull, PCPR_CROSS,  0,  76.5f, 61.5f, 35, 35, "x_intro_page (de)" },
    { 800, 120, 0x87F7817A893AC733ull, PCPR_CROSS,  0, 364.5f, 58.5f, 35, 35, "x_intro_page_extended" },
    { 420, 120, 0xB1C06FF387242F4Aull, PCPR_CIRCLE, 0, 210.0f, 59.0f, 20, 20, "o_intro_page" },
    /* reset to track (SELECT): the pill */
    { 600, 100, 0xAE1FED3FFCD7F262ull, PCPR_SELECT, 0, 153.5f, 45.0f, 60, 40, "Reset_to_track_prompt" },
    { 600, 100, 0xC0AF92AE0BFF3DB5ull, PCPR_SELECT, 0, 152.5f, 45.0f, 56, 37, "Reset_to_track_prompt_SS" },
    { 488,  92, 0x43DEF3287CC90A69ull, PCPR_SQUARE, 0, 334.5f, 44.0f, 18, 18, "gallery_controls_square_button" },
    /* the menus' button bars and pop-ups: textures that are the icon alone */
    {  40,  40, 0x4B438CE0C67E49B5ull, PCPR_CROSS,    1, 22.0f, 20.5f, 22, 22, "x_button" },
    {  40,  40, 0xFAB85063BE738AD0ull, PCPR_CIRCLE,   1, 20.0f, 20.5f, 24, 24, "o_button" },
    {  40,  40, 0x32A5E4C155929E8Dull, PCPR_SQUARE,   1, 19.5f, 20.0f, 23, 23, "square_button" },
    {  40,  40, 0x58E8EF6D6D49F42Aull, PCPR_TRIANGLE, 1, 19.5f, 19.5f, 24, 23, "triangle_button" },
    {  56,  56, 0x03803D441A417A94ull, PCPR_SQUARE,   1, 27.5f, 27.5f, 23, 23, "square" },
    {  56,  56, 0x91CBD9DDBA2B0492ull, PCPR_TRIANGLE, 1, 27.5f, 28.0f, 26, 24, "Triangle" },
    {  56,  56, 0xD5840CB25BD168AAull, PCPR_START,    1, 30.0f, 27.5f, 24, 20, "start" },
    {  80,  80, 0x08E5B54A86585322ull, PCPR_START,    1, 39.0f, 39.0f, 32, 24, "pause_start_button_prompt" },
    {  48,  48, 0x27C1BAA5D32A5F00ull, PCPR_CROSS,    1, 24.0f, 24.5f, 22, 22, "pop_up_x_button_prompt" },
    {  80,  40, 0x00B711D2F71A391Bull, PCPR_R1,       1, 40.0f, 19.0f, 58, 24, "r1_button" },
    {  60,  28, 0xE5ADC794747AA934ull, PCPR_L1,       1, 29.0f, 13.0f, 52, 22, "L1" },
    {  60,  28, 0xF863F3B23A2FCCA1ull, PCPR_R1,       1, 30.0f, 13.0f, 52, 22, "R1" },
};
#define PCPR_ICON_COUNT ((int)(sizeof k_pcpr_icons / sizeof k_pcpr_icons[0]))

/* ---- which key a button shows ---- */

/* The key cap's text for a key code (upper case; arrows are the codes 1..4). */
static inline void pcpr_vk_label(int vk, char* out, size_t n)
{
    static const struct { int vk; const char* t; } k[] = {
        { 0x08, "BKSP" }, { 0x09, "TAB" }, { 0x0D, "\x05" }, { 0x10, "\x07" }, { 0x11, "CTRL" },
        { 0x13, "PAUSE" }, { 0x14, "CAPS" }, { 0x1B, "ESC" }, { 0x20, "\x06" }, { 0x21, "PGUP" }, { 0x22, "PGDN" },
        { 0x23, "END" }, { 0x24, "HOME" }, { 0x25, "\x01" }, { 0x26, "\x03" }, { 0x27, "\x02" }, { 0x28, "\x04" },
        { 0x2D, "INS" }, { 0x2E, "DEL" }, { 0x6A, "NUM*" }, { 0x6B, "NUM+" }, { 0x6D, "NUM-" }, { 0x6E, "NUM." },
        { 0x6F, "NUM/" }, { 0x90, "NUMLK" }, { 0x91, "SCRLK" }, { 0xBA, ";" }, { 0xBB, "=" }, { 0xBC, "," },
        { 0xBD, "-" }, { 0xBE, "." }, { 0xBF, "/" }, { 0xC0, "`" }, { 0xDB, "[" }, { 0xDC, "\\" }, { 0xDD, "]" },
        { 0xDE, "'" },
    };
    if ((vk >= '0' && vk <= '9') || (vk >= 'A' && vk <= 'Z')) { out[0] = (char)vk; out[1] = 0; return; }
    if (vk >= 0x60 && vk <= 0x69) { snprintf(out, n, "NUM%d", vk - 0x60); return; }
    if (vk >= 0x70 && vk <= 0x87) { snprintf(out, n, "F%d", vk - 0x6F); return; }
    for (unsigned i = 0; i < sizeof k / sizeof k[0]; i++)
        if (k[i].vk == vk) { snprintf(out, n, "%s", k[i].t); return; }
    snprintf(out, n, "?");
}

/* The first key bound to a button in layout l, as a cap label; 0 when the
 * button has no key (the original icon is then left as it is). START falls
 * back to Esc (which always pauses), SQUARE to the handbrake key when that is
 * the square button (the default). */
static inline int pcpr_button_label(const pad_kb_layout* l, int button, char* out, size_t n)
{
    static const int act[PCPR_BUTTONS] = { PAD_ACT_CROSS, PAD_ACT_CIRCLE, PAD_ACT_SQUARE, PAD_ACT_TRIANGLE,
                                           PAD_ACT_START, PAD_ACT_SELECT, PAD_ACT_L1, PAD_ACT_R1,
                                           PAD_ACT_LEFT, PAD_ACT_RIGHT };
    if (button < 0 || button >= PCPR_BUTTONS) return 0;
    const int a = act[button];
    int vk = l->vk[a][0] ? l->vk[a][0] : l->vk[a][1];
    if (!vk && button == PCPR_START) vk = PAD_VK_ESCAPE;
    if (!vk && button == PCPR_SQUARE) vk = l->vk[PAD_ACT_HANDBRAKE][0] ? l->vk[PAD_ACT_HANDBRAKE][0] : l->vk[PAD_ACT_HANDBRAKE][1];
    if (!vk) return 0;
    pcpr_vk_label(vk, out, n);
    return 1;
}

/* ---- the textures ---- */

/* FNV-1a 64 over level 0's block rows (w/4 blocks of 16 bytes each, rows apart). */
static inline uint64_t pcpr_hash(const uint8_t* data, uint32_t w, uint32_t h, uint32_t row_bytes)
{
    const uint32_t rb = ((w + 3u) / 4u) * 16u, rows = (h + 3u) / 4u;
    uint64_t x = 0xcbf29ce484222325ull;
    for (uint32_t y = 0; y < rows; y++) {
        const uint8_t* p = data + (size_t)y * row_bytes;
        for (uint32_t i = 0; i < rb; i++) { x ^= p[i]; x *= 0x100000001b3ull; }
    }
    return x;
}

static inline int pcpr_fmt_bc3(uint32_t fmt) { return (fmt & ~0x60u) == 0x88u; }

/* The table entry for a texture, or -1. Only BC3 sizes in the table are hashed. */
static inline int pcpr_find(uint32_t fmt, uint32_t w, uint32_t h, const uint8_t* data, uint32_t row_bytes)
{
    if (!pcpr_fmt_bc3(fmt) || row_bytes < ((w + 3u) / 4u) * 16u) return -1;
    int any = 0;
    for (int i = 0; i < PCPR_ICON_COUNT; i++) if (k_pcpr_icons[i].w == w && k_pcpr_icons[i].h == h) any = 1;
    if (!any) return -1;
    const uint64_t x = pcpr_hash(data, w, h, row_bytes);
    for (int i = 0; i < PCPR_ICON_COUNT; i++)
        if (k_pcpr_icons[i].w == w && k_pcpr_icons[i].h == h && k_pcpr_icons[i].hash == x) return i;
    return -1;
}

/* ---- BC3 blocks ---- */

static inline void pcpr_565(uint16_t c, int* r, int* g, int* b)
{
    *r = ((c >> 11) & 31) * 255 / 31; *g = ((c >> 5) & 63) * 255 / 63; *b = (c & 31) * 255 / 31;
}

/* One 16-byte BC3 block into 16 RGBA texels (row-major). */
static inline void pcpr_bc3_decode(const uint8_t* b, uint8_t px[16][4])
{
    int al[8];
    const int a0 = b[0], a1 = b[1];
    al[0] = a0; al[1] = a1;
    if (a0 > a1) for (int i = 1; i < 7; i++) al[i + 1] = ((7 - i) * a0 + i * a1) / 7;
    else { for (int i = 1; i < 5; i++) al[i + 1] = ((5 - i) * a0 + i * a1) / 5; al[6] = 0; al[7] = 255; }
    uint64_t abits = 0;
    for (int i = 0; i < 6; i++) abits |= (uint64_t)b[2 + i] << (8 * i);
    const uint16_t c0 = (uint16_t)(b[8] | b[9] << 8), c1 = (uint16_t)(b[10] | b[11] << 8);
    int col[4][3];
    pcpr_565(c0, &col[0][0], &col[0][1], &col[0][2]);
    pcpr_565(c1, &col[1][0], &col[1][1], &col[1][2]);
    for (int k = 0; k < 3; k++) {
        col[2][k] = (2 * col[0][k] + col[1][k]) / 3;
        col[3][k] = (col[0][k] + 2 * col[1][k]) / 3;
    }
    const uint32_t cb = (uint32_t)(b[12] | b[13] << 8 | b[14] << 16 | (uint32_t)b[15] << 24);
    for (int i = 0; i < 16; i++) {
        const int ci = (cb >> (2 * i)) & 3;
        px[i][0] = (uint8_t)col[ci][0]; px[i][1] = (uint8_t)col[ci][1]; px[i][2] = (uint8_t)col[ci][2];
        px[i][3] = (uint8_t)al[(abits >> (3 * i)) & 7];
    }
}

static inline uint16_t pcpr_to565(int r, int g, int b)
{
    return (uint16_t)(((r * 31 + 127) / 255) << 11 | ((g * 63 + 127) / 255) << 5 | ((b * 31 + 127) / 255));
}

/* 16 RGBA texels into a BC3 block: colour endpoints at the darkest and the
 * brightest texel (the prompts are near grey), four-colour order (c0 > c1);
 * alpha endpoints at the min and max, eight-value order. */
static inline void pcpr_bc3_encode(const uint8_t px[16][4], uint8_t* b)
{
    int lo = 0, hi = 0, amin = 255, amax = 0;
    for (int i = 0; i < 16; i++) {
        const int l = px[i][0] * 3 + px[i][1] * 6 + px[i][2];
        const int ll = px[lo][0] * 3 + px[lo][1] * 6 + px[lo][2], lh = px[hi][0] * 3 + px[hi][1] * 6 + px[hi][2];
        if (l < ll) lo = i;
        if (l > lh) hi = i;
        if (px[i][3] < amin) amin = px[i][3];
        if (px[i][3] > amax) amax = px[i][3];
    }
    uint16_t c0 = pcpr_to565(px[hi][0], px[hi][1], px[hi][2]), c1 = pcpr_to565(px[lo][0], px[lo][1], px[lo][2]);
    uint32_t cb = 0;
    if (c0 < c1) { const uint16_t t = c0; c0 = c1; c1 = t; }
    if (c0 != c1) {
        int col[4][3];
        pcpr_565(c0, &col[0][0], &col[0][1], &col[0][2]);
        pcpr_565(c1, &col[1][0], &col[1][1], &col[1][2]);
        for (int k = 0; k < 3; k++) {
            col[2][k] = (2 * col[0][k] + col[1][k]) / 3;
            col[3][k] = (col[0][k] + 2 * col[1][k]) / 3;
        }
        for (int i = 0; i < 16; i++) {
            int best = 0, bd = 1 << 30;
            for (int c = 0; c < 4; c++) {
                const int dr = px[i][0] - col[c][0], dg = px[i][1] - col[c][1], db = px[i][2] - col[c][2];
                const int d = dr * dr + dg * dg + db * db;
                if (d < bd) { bd = d; best = c; }
            }
            cb |= (uint32_t)best << (2 * i);
        }
    }
    /* alpha: a0 = max > a1 = min (eight values); equal: every index 0 */
    uint64_t abits = 0;
    if (amax != amin) {
        int al[8];
        al[0] = amax; al[1] = amin;
        for (int i = 1; i < 7; i++) al[i + 1] = ((7 - i) * amax + i * amin) / 7;
        for (int i = 0; i < 16; i++) {
            int best = 0, bd = 1 << 30;
            for (int c = 0; c < 8; c++) { const int d = abs(px[i][3] - al[c]); if (d < bd) { bd = d; best = c; } }
            abits |= (uint64_t)best << (3 * i);
        }
    }
    b[0] = (uint8_t)amax; b[1] = (uint8_t)amin;
    for (int i = 0; i < 6; i++) b[2 + i] = (uint8_t)(abits >> (8 * i));
    b[8] = (uint8_t)c0; b[9] = (uint8_t)(c0 >> 8); b[10] = (uint8_t)c1; b[11] = (uint8_t)(c1 >> 8);
    b[12] = (uint8_t)cb; b[13] = (uint8_t)(cb >> 8); b[14] = (uint8_t)(cb >> 16); b[15] = (uint8_t)(cb >> 24);
}

/* ---- the key cap ---- */

/* The stroke font: each glyph is polylines on a 4 x 6 grid (y down), "x,y x,y|x,y ..."; a point alone is a dot. */
static inline const char* pcpr_glyph(char c)
{
    switch (c) {
    case 'A': return "0,6 0,2 2,0 4,2 4,6|0,4 4,4";
    case 'B': return "0,0 0,6 3,6 4,5 4,4 3,3 0,3|0,0 3,0 4,1 4,2 3,3";
    case 'C': return "4,1 3,0 1,0 0,1 0,5 1,6 3,6 4,5";
    case 'D': return "0,0 0,6 2,6 4,4 4,2 2,0 0,0";
    case 'E': return "4,0 0,0 0,6 4,6|0,3 3,3";
    case 'F': return "4,0 0,0 0,6|0,3 3,3";
    case 'G': return "4,1 3,0 1,0 0,1 0,5 1,6 3,6 4,5 4,3 2,3";
    case 'H': return "0,0 0,6|4,0 4,6|0,3 4,3";
    case 'I': return "1,0 3,0|2,0 2,6|1,6 3,6";
    case 'J': return "4,0 4,5 3,6 1,6 0,5";
    case 'K': return "0,0 0,6|4,0 0,4|1,3 4,6";
    case 'L': return "0,0 0,6 4,6";
    case 'M': return "0,6 0,0 2,3 4,0 4,6";
    case 'N': return "0,6 0,0 4,6 4,0";
    case 'O': return "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0";
    case 'P': return "0,6 0,0 3,0 4,1 4,2 3,3 0,3";
    case 'Q': return "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0|2,4 4,6";
    case 'R': return "0,6 0,0 3,0 4,1 4,2 3,3 0,3|2,3 4,6";
    case 'S': return "4,1 3,0 1,0 0,1 0,2 1,3 3,3 4,4 4,5 3,6 1,6 0,5";
    case 'T': return "0,0 4,0|2,0 2,6";
    case 'U': return "0,0 0,5 1,6 3,6 4,5 4,0";
    case 'V': return "0,0 2,6 4,0";
    case 'W': return "0,0 1,6 2,3 3,6 4,0";
    case 'X': return "0,0 4,6|4,0 0,6";
    case 'Y': return "0,0 2,3 4,0|2,3 2,6";
    case 'Z': return "0,0 4,0 0,6 4,6";
    case '0': return "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0|4,1 0,5";
    case '1': return "1,1 2,0 2,6|1,6 3,6";
    case '2': return "0,1 1,0 3,0 4,1 4,2 0,6 4,6";
    case '3': return "0,1 1,0 3,0 4,1 4,2 3,3 4,4 4,5 3,6 1,6 0,5|1,3 3,3";
    case '4': return "3,6 3,0 0,4 4,4";
    case '5': return "4,0 0,0 0,3 3,3 4,4 4,5 3,6 1,6 0,5";
    case '6': return "3,0 1,0 0,1 0,5 1,6 3,6 4,5 4,4 3,3 0,3";
    case '7': return "0,0 4,0 1,6";
    case '8': return "1,0 3,0 4,1 4,2 3,3 1,3 0,2 0,1 1,0|1,3 0,4 0,5 1,6 3,6 4,5 4,4 3,3";
    case '9': return "4,3 1,3 0,2 0,1 1,0 3,0 4,1 4,5 3,6 1,6";
    case ';': return "2,2|2,5 1,6";
    case '=': return "0,2 4,2|0,4 4,4";
    case ',': return "2,5 1,6";
    case '-': return "0,3 4,3";
    case '+': return "0,3 4,3|2,1 2,5";
    case '*': return "2,1 2,5|0,2 4,4|0,4 4,2";
    case '.': return "2,6";
    case '/': return "4,0 0,6";
    case '\\': return "0,0 4,6";
    case '[': return "3,0 1,0 1,6 3,6";
    case ']': return "1,0 3,0 3,6 1,6";
    case '`': return "1,0 2,1";
    case '\'': return "2,0 2,2";
    case '\x01': return "0,3 4,3|2,1 0,3 2,5";   /* left arrow */
    case '\x02': return "0,3 4,3|2,1 4,3 2,5";   /* right */
    case '\x03': return "2,6 2,0|0,2 2,0 4,2";   /* up */
    case '\x04': return "2,0 2,6|0,4 2,6 4,4";   /* down */
    case '\x05': return "4,0 4,4 0,4|2,2 0,4 2,6";   /* return arrow (Enter) */
    case '\x06': return "0,3 0,5 4,5 4,3";   /* open box (Space) */
    case '\x07': return "2,0 4,3 3,3 3,6 1,6 1,3 0,3 2,0";   /* outlined up arrow (Shift) */
    default:   return "0,1 1,0 3,0 4,1 4,2 2,3 2,4|2,6";   /* ? */
    }
}

#define PCPR_SEG_MAX 64
typedef struct { float x0, y0, x1, y1; } pcpr_seg;

/* A label's strokes in glyph units (6 high), laid out left to right; returns the count, *width the advance. */
static inline int pcpr_layout(const char* label, pcpr_seg* s, int max, float* width)
{
    int n = 0;
    float ox = 0.0f;
    for (const char* c = label; *c; c++) {
        const char* g = pcpr_glyph(*c);
        float px = 0, py = 0;
        int have = 0;
        while (*g) {
            if (*g == '|') { if (have == 1 && n < max) { s[n].x0 = s[n].x1 = ox + px; s[n].y0 = s[n].y1 = py; n++; } have = 0; g++; continue; }
            if (*g == ' ') { g++; continue; }
            const float x = (float)(*g - '0'); g += 2;   /* "d," */
            const float y = (float)(*g - '0'); g++;
            if (have && n < max) { s[n].x0 = ox + px; s[n].y0 = py; s[n].x1 = ox + x; s[n].y1 = y; n++; have = 2; }
            else have = have ? 2 : 1;
            px = x; py = y;
        }
        if (have == 1 && n < max) { s[n].x0 = s[n].x1 = ox + px; s[n].y0 = s[n].y1 = py; n++; }
        ox += c[1] ? 5.6f : 4.0f;
    }
    *width = ox;
    return n;
}

static inline float pcpr_clamp01(float v) { return v < 0.0f ? 0.0f : v > 1.0f ? 1.0f : v; }

static inline float pcpr_seg_dist(float px, float py, const pcpr_seg* s)
{
    const float dx = s->x1 - s->x0, dy = s->y1 - s->y0;
    const float l2 = dx * dx + dy * dy;
    float t = l2 > 0.0f ? ((px - s->x0) * dx + (py - s->y0) * dy) / l2 : 0.0f;
    t = pcpr_clamp01(t);
    const float ex = px - (s->x0 + t * dx), ey = py - (s->y0 + t * dy);
    return sqrtf(ex * ex + ey * ey);
}

typedef struct {
    float x0, y0, w, h;        /* the cap, in texels of the level drawn: the icon's own rect */
    float hw;                  /* stroke half width, texels */
    float border;              /* outline width, texels */
    int   nseg;
    pcpr_seg seg[PCPR_SEG_MAX];   /* the label's strokes, in texels */
} pcpr_cap;

/* The cap for an icon at a level (texels scaled by 1 >> level): exactly the
 * icon's rect. The label is fitted inside the outline: a single key at about
 * 0.58 of the height, a word at 0.42; a word too wide is condensed (down to
 * 0.62 of its width) and then scaled down. The cap never grows. */
static inline void pcpr_cap_make(pcpr_cap* c, const pcpr_icon* ic, const char* label, int level)
{
    const float k = 1.0f / (float)(1 << level);
    float tw;
    c->nseg = pcpr_layout(label, c->seg, PCPR_SEG_MAX, &tw);
    const size_t n = strlen(label);
    const float W = ic->rw * k, H = ic->rh * k;
    c->w = W; c->h = H;
    c->x0 = ic->cx * k - W * 0.5f;
    c->y0 = ic->cy * k - H * 0.5f;
    c->border = H * 0.075f; if (c->border < 1.0f) c->border = 1.0f;
    const float pad_x = c->border + H * 0.12f, pad_y = c->border + H * 0.14f;
    const float aw = W - 2.0f * pad_x, ah = H - 2.0f * pad_y;
    float th = H * (n == 1 ? 0.58f : 0.42f);   /* text height: 6 glyph units */
    if (th > ah) th = ah;
    float xs = 1.0f;
    const float want = tw * th / 6.0f;
    if (want > aw && want > 0.0f) {
        xs = aw / want;
        if (xs < 0.62f) { th *= xs / 0.62f; xs = 0.62f; }
    }
    if (th < 1.0f) th = 1.0f;
    const float sy = th / 6.0f, sx = sy * xs;
    const float ox = ic->cx * k - tw * sx * 0.5f, oy = ic->cy * k - th * 0.5f;
    for (int i = 0; i < c->nseg; i++) {
        c->seg[i].x0 = ox + c->seg[i].x0 * sx; c->seg[i].x1 = ox + c->seg[i].x1 * sx;
        c->seg[i].y0 = oy + c->seg[i].y0 * sy; c->seg[i].y1 = oy + c->seg[i].y1 * sy;
    }
    c->hw = th * (n == 1 ? 0.085f : 0.075f); if (c->hw < 0.5f) c->hw = 0.5f;
}

/* The cap's RGBA at texel centre (px, py), premultiplied coverage in a. */
static inline void pcpr_cap_texel(const pcpr_cap* c, float px, float py, float rgba[4])
{
    const float r = (c->w < c->h ? c->w : c->h) * 0.22f;
    const float hx = c->w * 0.5f - r, hy = c->h * 0.5f - r;
    float qx = fabsf(px - (c->x0 + c->w * 0.5f)) - hx, qy = fabsf(py - (c->y0 + c->h * 0.5f)) - hy;
    const float ax = qx > 0 ? qx : 0, ay = qy > 0 ? qy : 0;
    const float d = sqrtf(ax * ax + ay * ay) + (qx > qy ? (qx < 0 ? qx : 0) : (qy < 0 ? qy : 0)) - r;   /* < 0 inside */
    const float cover = pcpr_clamp01(0.5f - d);
    if (cover <= 0.0f) { rgba[0] = rgba[1] = rgba[2] = rgba[3] = 0.0f; return; }
    const float edge = pcpr_clamp01(d + c->border + 0.5f);   /* 1 on the outline, 0 inside it */
    float tx = 0.0f;
    if (c->nseg) {
        float dm = 1e9f;   /* the strokes are in texels (pcpr_cap_make) */
        for (int i = 0; i < c->nseg; i++) { const float s = pcpr_seg_dist(px, py, &c->seg[i]); if (s < dm) dm = s; }
        tx = pcpr_clamp01(c->hw + 0.5f - dm);
    }
    const float fill = 22.0f, line = 236.0f;
    float v = fill + (line - fill) * (edge > tx ? edge : tx);
    rgba[0] = rgba[1] = rgba[2] = v;
    rgba[3] = cover;
}

/* Redraw icon ic in a BC3 level (w x h texels, row_bytes apart) with a cap
 * reading label. Returns the number of blocks rewritten. */
static inline int pcpr_patch_bc3(uint8_t* data, uint32_t w, uint32_t h, uint32_t row_bytes, int level,
                                 const pcpr_icon* ic, const char* label)
{
    if (!w || !h) return 0;
    pcpr_cap c;
    pcpr_cap_make(&c, ic, label, level);
    if (c.h < 6.0f) return 0;
    const uint32_t bw = (w + 3u) / 4u, bh = (h + 3u) / 4u;
    uint32_t bx0 = 0, by0 = 0, bx1 = bw, by1 = bh;
    if (!ic->clear) {
        const float x0 = c.x0 - 1.0f, y0 = c.y0 - 1.0f, x1 = c.x0 + c.w + 1.0f, y1 = c.y0 + c.h + 1.0f;
        bx0 = x0 < 0 ? 0u : (uint32_t)x0 / 4u; by0 = y0 < 0 ? 0u : (uint32_t)y0 / 4u;
        bx1 = (uint32_t)(x1 / 4.0f) + 1u; by1 = (uint32_t)(y1 / 4.0f) + 1u;
        if (bx1 > bw) bx1 = bw;
        if (by1 > bh) by1 = bh;
    }
    int n = 0;
    for (uint32_t by = by0; by < by1; by++) {
        for (uint32_t bx = bx0; bx < bx1; bx++) {
            uint8_t* blk = data + (size_t)by * row_bytes + (size_t)bx * 16u;
            uint8_t px[16][4];
            pcpr_bc3_decode(blk, px);
            int touched = ic->clear;
            for (int i = 0; i < 16; i++) {
                const float fx = (float)(bx * 4u + (uint32_t)(i & 3)) + 0.5f, fy = (float)(by * 4u + (uint32_t)(i >> 2)) + 0.5f;
                float k[4];
                pcpr_cap_texel(&c, fx, fy, k);
                if (ic->clear) { px[i][0] = px[i][1] = px[i][2] = 0; px[i][3] = 0; }
                if (k[3] <= 0.0f) continue;
                touched = 1;
                const float a = k[3], da = px[i][3] / 255.0f;
                const float oa = a + da * (1.0f - a);
                for (int ch = 0; ch < 3; ch++) {
                    const float v = (k[ch] * a + px[i][ch] * da * (1.0f - a)) / (oa > 0.0f ? oa : 1.0f);
                    px[i][ch] = (uint8_t)(v + 0.5f);
                }
                px[i][3] = (uint8_t)(oa * 255.0f + 0.5f);
            }
            if (touched) { pcpr_bc3_encode((const uint8_t(*)[4])px, blk); n++; }
        }
    }
    return n;
}

#endif
