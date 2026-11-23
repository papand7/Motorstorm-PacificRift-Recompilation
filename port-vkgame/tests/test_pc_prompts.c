/* pc_prompts.h: key cap labels from the live layout, the BC3 block coder, the
 * texture table lookup and the icon redraw.
 *   generated\analysis\pcmenu\tools\build_tests.cmd
 * With arguments it is also the private preview tool:
 *   test_pc_prompts <in.bc3> <w> <h> <table index> <label> <out.bc3>
 * (level-0 blocks in, the patched blocks out; prompts/tools/preview.py makes PNGs). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pc_keys.h"
#include "pc_prompts.h"

static int fails;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)

static int label_is(const pad_kb_layout* l, int b, const char* want)
{
    char t[16];
    if (!pcpr_button_label(l, b, t, sizeof t)) return want == NULL;
    return want && !strcmp(t, want);
}

static int preview(int argc, char** argv)
{
    if (argc < 7) return 2;
    const uint32_t w = (uint32_t)atoi(argv[2]), h = (uint32_t)atoi(argv[3]);
    const int idx = atoi(argv[4]);
    const size_t n = (size_t)((w + 3) / 4) * ((h + 3) / 4) * 16;
    uint8_t* d = (uint8_t*)malloc(n);
    FILE* f = fopen(argv[1], "rb");
    if (!f || !d || fread(d, 1, n, f) != n) return 3;
    fclose(f);
    const int found = pcpr_find(0xA8, w, h, d, (w + 3) / 4 * 16);
    printf("table %d (asked %d)\n", found, idx);
    const char* label = argv[5];
    if (!strcmp(label, "LEFT")) label = "\x01";
    if (!strcmp(label, "RIGHT")) label = "\x02";
    if (!strcmp(label, "ENTER")) label = "\x05";
    if (!strcmp(label, "SPACE")) label = "\x06";
    if (!strcmp(label, "SHIFT")) label = "\x07";
    printf("blocks %d\n", pcpr_patch_bc3(d, w, h, (w + 3) / 4 * 16, 0, &k_pcpr_icons[idx], label));
    f = fopen(argv[6], "wb");
    if (!f) return 4;
    fwrite(d, 1, n, f);
    fclose(f);
    free(d);
    return found == idx ? 0 : 1;
}

int main(int argc, char** argv)
{
    if (argc > 1) return preview(argc, argv);

    /* labels: the default layout, then the user's (key.circle = X, key.start = P, l1/r1 none) */
    pad_kb_layout l = pad_kb_layout_default();
    CHECK(label_is(&l, PCPR_CROSS, "\x05"));   /* Enter: the return arrow */
    CHECK(label_is(&l, PCPR_SQUARE, "Q"));
    CHECK(label_is(&l, PCPR_TRIANGLE, "E"));
    CHECK(label_is(&l, PCPR_START, "P"));
    CHECK(label_is(&l, PCPR_SELECT, "C"));
    CHECK(label_is(&l, PCPR_CIRCLE, NULL));   /* no key: the original icon stays */
    CHECK(label_is(&l, PCPR_L1, NULL));
    CHECK(label_is(&l, PCPR_LEFT, "\x01"));
    CHECK(label_is(&l, PCPR_RIGHT, "\x02"));
    l.vk[PAD_ACT_CIRCLE][0] = 'X';
    CHECK(label_is(&l, PCPR_CIRCLE, "X"));
    /* a rebind is seen at once: the first key of the action */
    l.vk[PAD_ACT_CROSS][0] = PAD_VK_CONTROL; l.vk[PAD_ACT_CROSS][1] = PAD_VK_RETURN;
    CHECK(label_is(&l, PCPR_CROSS, "CTRL"));
    l.vk[PAD_ACT_CROSS][0] = 0;
    CHECK(label_is(&l, PCPR_CROSS, "\x05"));
    l.vk[PAD_ACT_START][0] = 0;
    CHECK(label_is(&l, PCPR_START, "ESC"));   /* Esc always pauses */
    l.vk[PAD_ACT_SQUARE][0] = 0;
    CHECK(label_is(&l, PCPR_SQUARE, "\x06"));   /* the handbrake key is the square button */
    l.vk[PAD_ACT_SELECT][0] = 0x70 + 4;
    CHECK(label_is(&l, PCPR_SELECT, "F5"));
    l.vk[PAD_ACT_SELECT][0] = 0x20;
    CHECK(label_is(&l, PCPR_SELECT, "\x06"));
    l.vk[PAD_ACT_SELECT][0] = 0x10;
    CHECK(label_is(&l, PCPR_SELECT, "\x07"));
    l.vk[PAD_ACT_SELECT][0] = 0x26;
    CHECK(label_is(&l, PCPR_SELECT, "\x03"));

    /* the user's settings.ini (key lines parsed by pck_parse, as pcmenu_boot does): labels follow the file */
    {
        pad_kb_layout u = pad_kb_layout_default();
        const char* ini = "key.cross = Enter, Ctrl\nkey.square = Q\nkey.triangle = E\nkey.circle = X\n"
                          "key.start = P\nkey.select = C\nkey.l1 = none\nkey.r1 = none\n";
        CHECK(pck_parse(&u, ini) == 8);
        CHECK(label_is(&u, PCPR_CROSS, "\x05"));       /* Enter (first key) */
        CHECK(label_is(&u, PCPR_SQUARE, "Q"));
        CHECK(label_is(&u, PCPR_TRIANGLE, "E"));
        CHECK(label_is(&u, PCPR_CIRCLE, "X"));
        CHECK(label_is(&u, PCPR_START, "P"));
        CHECK(label_is(&u, PCPR_SELECT, "C"));
        CHECK(label_is(&u, PCPR_L1, NULL));             /* none: original icon stays */
        CHECK(label_is(&u, PCPR_R1, NULL));
    }

    /* every glyph the labels can use is in the font: none falls back to '?' except '?' itself */
    {
        const char* all = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789;=,-+*./\\[]`'\x01\x02\x03\x04\x05\x06\x07";
        const char* q = pcpr_glyph('?');
        for (const char* c = all; *c; c++) CHECK(pcpr_glyph(*c) != q);
        pcpr_seg s[PCPR_SEG_MAX];
        float tw;
        CHECK(pcpr_layout("ENTER", s, PCPR_SEG_MAX, &tw) > 10 && tw > 20.0f);
        CHECK(pcpr_layout(".", s, PCPR_SEG_MAX, &tw) == 1 && s[0].x0 == s[0].x1);   /* a dot */
    }

    /* BC3: an encoded flat block decodes to itself; a two-tone block keeps both tones */
    {
        uint8_t px[16][4], out[16][4], blk[16];
        for (int i = 0; i < 16; i++) { px[i][0] = px[i][1] = px[i][2] = 200; px[i][3] = 255; }
        pcpr_bc3_encode((const uint8_t(*)[4])px, blk);
        pcpr_bc3_decode(blk, out);
        int ok = 1;
        for (int i = 0; i < 16; i++) ok &= abs(out[i][0] - 200) <= 4 && out[i][3] == 255;
        CHECK(ok);
        for (int i = 0; i < 16; i++) { const int on = i & 1; px[i][0] = px[i][1] = px[i][2] = on ? 240 : 20; px[i][3] = on ? 255 : 0; }
        pcpr_bc3_encode((const uint8_t(*)[4])px, blk);
        pcpr_bc3_decode(blk, out);
        ok = 1;
        for (int i = 0; i < 16; i++) ok &= abs(out[i][0] - px[i][0]) <= 6 && out[i][3] == px[i][3];
        CHECK(ok);
        CHECK((blk[8] | blk[9] << 8) > (blk[10] | blk[11] << 8));   /* four-colour order */
    }

    /* the table: a texture of a known size but other bytes is not known; an unknown size is not hashed */
    {
        static uint8_t tex[500 / 4 * 84 / 4 * 16];
        memset(tex, 0x5A, sizeof tex);
        CHECK(pcpr_find(0xA8, 500, 84, tex, 500 / 4 * 16) < 0);
        CHECK(pcpr_find(0x88, 500, 84, tex, 500 / 4 * 16) < 0);
        CHECK(pcpr_find(0x85, 500, 84, tex, 500 / 4 * 16) < 0);   /* not BC3 */
        /* every entry: its hash names it and no other */
        for (int i = 0; i < PCPR_ICON_COUNT; i++)
            for (int j = 0; j < PCPR_ICON_COUNT; j++)
                if (i != j) CHECK(!(k_pcpr_icons[i].hash == k_pcpr_icons[j].hash && k_pcpr_icons[i].w == k_pcpr_icons[j].w));

        /* the redraw: a transparent bar gets an opaque cap at the icon, nothing far from it */
        memset(tex, 0, sizeof tex);   /* alpha 0 everywhere (a0 = a1 = 0) */
        const pcpr_icon* ic = &k_pcpr_icons[0];   /* x_to_skip_prompt: centre 232.5, 37.5 */
        const int nb = pcpr_patch_bc3(tex, 500, 84, 500 / 4 * 16, 0, ic, "CTRL");
        CHECK(nb > 20 && nb < 200);
        uint8_t px[16][4];
        pcpr_bc3_decode(tex + (37 / 4) * (500 / 4 * 16) + (232 / 4) * 16, px);
        CHECK(px[0][3] == 255);                  /* the cap's middle is opaque */
        pcpr_bc3_decode(tex + 0, px);
        CHECK(px[0][3] == 0);                    /* the corner is untouched */
        pcpr_bc3_decode(tex + (37 / 4) * (500 / 4 * 16) + (100 / 4) * 16, px);
        CHECK(px[5][3] == 0);                    /* the bar left of the icon too */
        /* the label is drawn: some texels in the cap are bright, some dark */
        int bright = 0, dark = 0;
        for (int by = 5; by <= 13; by++)
            for (int bx = 52; bx <= 64; bx++) {
                pcpr_bc3_decode(tex + by * (500 / 4 * 16) + bx * 16, px);
                for (int i = 0; i < 16; i++) if (px[i][3] == 255) { if (px[i][0] > 180) bright++; else if (px[i][0] < 60) dark++; }
            }
        CHECK(bright > 30 && dark > 30);
        /* the cap stays within the entry's widest */
        int minx = 1000, maxx = -1;
        for (int bx = 0; bx < 125; bx++) {
            pcpr_bc3_decode(tex + 9 * (500 / 4 * 16) + bx * 16, px);
            for (int i = 0; i < 16; i++) if (px[i][3]) { const int x = bx * 4 + (i & 3); if (x < minx) minx = x; if (x > maxx) maxx = x; }
        }
        CHECK(minx >= (int)(ic->cx - ic->rw * 0.5f) && maxx <= (int)(ic->cx + ic->rw * 0.5f));   /* never past the icon */
    }

    printf("test_pc_prompts: %s (%d failed)\n", fails ? "FAIL" : "ok", fails);
    return fails ? 1 : 0;
}
