/* pc_keys.h: key names, settings.ini key.* lines, rebinding and its conflicts,
 * the default keyboard layout (keyboard only), and the key-capture state machine.
 *   generated\analysis\pcmenu\tools\build_tests.cmd */
#include <stdio.h>
#include <string.h>
#include "pc_keys.h"

static int fails;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)

static const char* s_down;   /* the held keys, as virtual-key codes */
static int down(int vk, void* user) { (void)user; for (const char* p = s_down; *p; p++) if ((unsigned char)*p == vk) return 1; return 0; }

static pad_kb_state press(const pad_kb_layout* l, const char* keys)
{
    s_down = keys;
    return pad_keyboard_map_layout(l, down, NULL, CELL_PAD_CTRL_SQUARE);
}

/* the actions with no default key */
static int unbound_default(int a) { return a == PAD_ACT_CIRCLE || a == PAD_ACT_L1 || a == PAD_ACT_R1; }

int main(void)
{
    char b[32], buf[2048];
    pad_kb_layout l = pad_kb_layout_default();

    /* The table: every action has its page strings and a unique name; the default
     * keys are the agreed set, and CIRCLE, L1, R1 have none. */
    for (int a = 0; a < PCK_COUNT; a++) {
        CHECK(k_pck_actions[a].key && k_pck_actions[a].name && k_pck_actions[a].info);
        CHECK(strlen(k_pck_actions[a].name) < 24 && strlen(k_pck_actions[a].info) < 60);
        CHECK(pck_find(k_pck_actions[a].key) == a);
        CHECK(pck_is_default(&l, a));
        if (unbound_default(a)) CHECK(l.vk[a][0] == 0 && l.vk[a][1] == 0);
        else CHECK(l.vk[a][0] != 0);
    }
    CHECK(PCK_COUNT == PAD_ACT_COUNT);
    CHECK(l.vk[PAD_ACT_ACCEL][0] == 'W' && l.vk[PAD_ACT_ACCEL][1] == PAD_VK_UP);
    CHECK(l.vk[PAD_ACT_BRAKE][0] == 'S' && l.vk[PAD_ACT_BRAKE][1] == PAD_VK_DOWN);
    CHECK(l.vk[PAD_ACT_STEER_L][0] == 'A' && l.vk[PAD_ACT_STEER_L][1] == PAD_VK_LEFT);
    CHECK(l.vk[PAD_ACT_STEER_R][0] == 'D' && l.vk[PAD_ACT_STEER_R][1] == PAD_VK_RIGHT);
    CHECK(l.vk[PAD_ACT_HANDBRAKE][0] == PAD_VK_SPACE && l.vk[PAD_ACT_HANDBRAKE][1] == 0);
    CHECK(l.vk[PAD_ACT_CROSS][0] == PAD_VK_RETURN && l.vk[PAD_ACT_CROSS][1] == PAD_VK_CONTROL);
    CHECK(l.vk[PAD_ACT_SQUARE][0] == 'Q' && l.vk[PAD_ACT_TRIANGLE][0] == 'E');
    CHECK(l.vk[PAD_ACT_START][0] == 'P' && l.vk[PAD_ACT_SELECT][0] == 'C');
    CHECK(l.vk[PAD_ACT_UP][0] == PAD_VK_UP && l.vk[PAD_ACT_DOWN][0] == PAD_VK_DOWN);
    CHECK(l.vk[PAD_ACT_LEFT][0] == PAD_VK_LEFT && l.vk[PAD_ACT_RIGHT][0] == PAD_VK_RIGHT);

    /* What the defaults press. */
    CHECK(press(&l, "W").buttons == CELL_PAD_CTRL_R2 && press(&l, "W").r2 == 255);
    CHECK(press(&l, "S").buttons == CELL_PAD_CTRL_L2 && press(&l, "S").l2 == 255);
    CHECK(press(&l, "A").lx == 0 && press(&l, "D").lx == 255 && press(&l, "AD").lx == 128);
    { const char k[] = { PAD_VK_UP, 0 };    CHECK(press(&l, k).buttons == (CELL_PAD_CTRL_R2 | CELL_PAD_CTRL_UP)); }
    { const char k[] = { PAD_VK_DOWN, 0 };  CHECK(press(&l, k).buttons == (CELL_PAD_CTRL_L2 | CELL_PAD_CTRL_DOWN)); }
    { const char k[] = { PAD_VK_LEFT, 0 };  CHECK(press(&l, k).buttons == CELL_PAD_CTRL_LEFT && press(&l, k).lx == 0); }
    { const char k[] = { PAD_VK_RIGHT, 0 }; CHECK(press(&l, k).buttons == CELL_PAD_CTRL_RIGHT && press(&l, k).lx == 255); }
    { const char k[] = { PAD_VK_SPACE, 0 };   CHECK(press(&l, k).buttons == CELL_PAD_CTRL_SQUARE); }
    { const char k[] = { PAD_VK_CONTROL, 0 }; CHECK(press(&l, k).buttons == CELL_PAD_CTRL_CROSS); }
    { const char k[] = { PAD_VK_RETURN, 0 }; CHECK(press(&l, k).buttons == CELL_PAD_CTRL_CROSS); }
    { const char k[] = { 'P', 0 }; CHECK(press(&l, k).buttons == CELL_PAD_CTRL_START); }
    { const char k[] = { 'C', 0 };           CHECK(press(&l, k).buttons == CELL_PAD_CTRL_SELECT); }
    CHECK(press(&l, "Q").buttons == CELL_PAD_CTRL_SQUARE && press(&l, "E").buttons == CELL_PAD_CTRL_TRIANGLE);
    CHECK(press(&l, "XRF12Z").buttons == 0);   /* the old keys are unbound now */
    /* the framework's no-layout entry point is the same layout */
    s_down = "WAZ";
    { const pad_kb_state a = pad_keyboard_map(down, NULL, CELL_PAD_CTRL_SQUARE);
      const pad_kb_state c = pad_keyboard_map_layout(&l, down, NULL, CELL_PAD_CTRL_SQUARE);
      CHECK(!memcmp(&a, &c, sizeof a)); }

    /* Names: letters, digits, words; any case; 0xNN; none. */
    CHECK(!strcmp(pck_vk_name('W', b, sizeof b), "W") && !strcmp(pck_vk_name('7', b, sizeof b), "7"));
    CHECK(!strcmp(pck_vk_name(PAD_VK_CONTROL, b, sizeof b), "Ctrl") && !strcmp(pck_vk_name(0x70, b, sizeof b), "F1"));
    CHECK(!strcmp(pck_vk_name(0x87, b, sizeof b), "F24") && !strcmp(pck_vk_name(0x65, b, sizeof b), "Num5"));
    CHECK(!strcmp(pck_vk_name(PAD_VK_UP, b, sizeof b), "Up") && !strcmp(pck_vk_name(PAD_VK_RETURN, b, sizeof b), "Enter"));
    CHECK(!strcmp(pck_vk_name(0, b, sizeof b), "none") && !strcmp(pck_vk_name(0xE7, b, sizeof b), "0xE7"));
    CHECK(pck_vk_parse("w") == 'W' && pck_vk_parse("W") == 'W' && pck_vk_parse("5") == '5');
    CHECK(pck_vk_parse("space") == PAD_VK_SPACE && pck_vk_parse("CTRL") == PAD_VK_CONTROL && pck_vk_parse("f12") == 0x7B);
    CHECK(pck_vk_parse("up") == PAD_VK_UP && pck_vk_parse("ENTER") == PAD_VK_RETURN);
    CHECK(pck_vk_parse("Num0") == 0x60 && pck_vk_parse("NumPlus") == 0x6B && pck_vk_parse("0x41") == 'A');
    CHECK(pck_vk_parse("none") == 0);
    CHECK(pck_vk_parse("") == -1 && pck_vk_parse("Banana") == -1 && pck_vk_parse("F25") == -1 && pck_vk_parse("0x") == -1);
    CHECK(pck_vk_parse("Escape") == -1 && pck_vk_parse("Alt") == -1 && pck_vk_parse("0x1B") == -1);   /* not bindable */
    for (int vk = 7; vk < 0xFF; vk++) {       /* every bindable key round-trips through its name */
        if (!pad_kb_vk_bindable(vk)) continue;
        pck_vk_name(vk, b, sizeof b);
        CHECK(pck_vk_parse(b) == vk);
    }

    /* The file: the default layout writes and reads back unchanged. */
    CHECK(pck_format(&l, buf, sizeof buf) > 0);
    CHECK(strstr(buf, "key.accelerate = W, Up\n") && strstr(buf, "key.brake = S, Down\n"));
    CHECK(strstr(buf, "key.steerleft = A, Left\n") && strstr(buf, "key.cross = Enter, Ctrl\n"));
    CHECK(strstr(buf, "key.handbrake = Space\n") && strstr(buf, "key.start = P\n") && strstr(buf, "key.select = C\n"));
    CHECK(strstr(buf, "key.circle = none\n") && strstr(buf, "key.l1 = none\n") && strstr(buf, "key.r1 = none\n"));
    pad_kb_layout m;
    memset(&m, 0, sizeof m);
    CHECK(pck_parse(&m, buf) == PCK_COUNT);
    CHECK(!memcmp(&l, &m, sizeof l));

    /* Reading: any case, spaces, CRLF, junk and bad keys ignored (the action keeps its keys). */
    m = pad_kb_layout_default();
    CHECK(pck_parse(&m, "# c\r\nKEY.ACCELERATE = Num1\r\n key.brake=  Down , Num2 \nkey.bogus = A\nkey.square = Banana\n"
                        "key.triangle = A, B, C\nkey.circle = none\nvsync = Off\nkey.l1\n") == 3);
    CHECK(m.vk[PAD_ACT_ACCEL][0] == 0x61 && m.vk[PAD_ACT_ACCEL][1] == 0);
    CHECK(m.vk[PAD_ACT_BRAKE][0] == PAD_VK_DOWN && m.vk[PAD_ACT_BRAKE][1] == 0x62);
    CHECK(m.vk[PAD_ACT_SQUARE][0] == 'Q');                                  /* unreadable: kept */
    CHECK(m.vk[PAD_ACT_TRIANGLE][0] == 'E');                                /* three keys: refused as a whole */
    CHECK(m.vk[PAD_ACT_CIRCLE][0] == 0 && m.vk[PAD_ACT_CIRCLE][1] == 0);   /* none */
    CHECK(m.vk[PAD_ACT_L1][0] == 0);                                        /* no '=': skipped, still unbound */
    /* settings.ini lines of the other settings do not disturb it */
    m = pad_kb_layout_default();
    CHECK(pck_parse(&m, "display = Fullscreen\nfsr = Quality\n") == 0 && !memcmp(&m, &l, sizeof l));

    /* Rebinding: the one key replaces the action's keys. */
    m = pad_kb_layout_default();
    CHECK(pck_bind(&m, PAD_ACT_ACCEL, 'T') == -1);
    CHECK(m.vk[PAD_ACT_ACCEL][0] == 'T' && m.vk[PAD_ACT_ACCEL][1] == 0);
    CHECK(press(&m, "T").buttons == CELL_PAD_CTRL_R2 && press(&m, "W").buttons == 0);
    { const char k[] = { PAD_VK_UP, 0 };   /* Up is the d-pad only now */
      CHECK(press(&m, k).buttons == CELL_PAD_CTRL_UP); }
    CHECK(!pck_is_default(&m, PAD_ACT_ACCEL) && pck_is_default(&m, PAD_ACT_BRAKE));
    pck_format_keys(&m, PAD_ACT_ACCEL, b, sizeof b);
    CHECK(!strcmp(b, "T"));
    pck_format_keys(&m, PAD_ACT_CROSS, b, sizeof b);
    CHECK(!strcmp(b, "Enter, Ctrl"));

    /* A conflict: the key is taken from its owner. An owner left without a key
     * gets the key the rebound action gave up (a swap). */
    m = pad_kb_layout_default();
    CHECK(pck_bind(&m, PAD_ACT_STEER_L, 'D') == PAD_ACT_STEER_R);   /* D moves from steer right */
    CHECK(m.vk[PAD_ACT_STEER_L][0] == 'D' && m.vk[PAD_ACT_STEER_L][1] == 0);
    CHECK(m.vk[PAD_ACT_STEER_R][0] == PAD_VK_RIGHT);                /* it keeps its arrow */
    CHECK(press(&m, "D").lx == 0 && press(&m, "A").lx == 128);
    CHECK(pck_owner(&m, 'D', PAD_ACT_STEER_L) == -1);               /* no duplicate left */
    /* the owner has no other key: it takes the key that was given up */
    m = pad_kb_layout_default();
    CHECK(pck_bind(&m, PAD_ACT_SQUARE, 'E') == PAD_ACT_TRIANGLE);   /* E moves from triangle */
    CHECK(m.vk[PAD_ACT_SQUARE][0] == 'E' && m.vk[PAD_ACT_TRIANGLE][0] == 'Q');
    CHECK(m.vk[PAD_ACT_SQUARE][1] == 0 && m.vk[PAD_ACT_TRIANGLE][1] == 0);
    /* accelerate takes S from brake; brake keeps its arrow */
    m = pad_kb_layout_default();
    CHECK(pck_bind(&m, PAD_ACT_ACCEL, 'S') == PAD_ACT_BRAKE);
    CHECK(m.vk[PAD_ACT_ACCEL][0] == 'S' && m.vk[PAD_ACT_BRAKE][0] == PAD_VK_DOWN && m.vk[PAD_ACT_BRAKE][1] == 0);
    /* the same key again changes nothing and finds no owner */
    CHECK(pck_bind(&m, PAD_ACT_ACCEL, 'S') == -1 && m.vk[PAD_ACT_ACCEL][0] == 'S');
    /* an action's own key as its new one */
    m = pad_kb_layout_default();
    CHECK(pck_bind(&m, PAD_ACT_CROSS, PAD_VK_CONTROL) == -1);
    CHECK(m.vk[PAD_ACT_CROSS][0] == PAD_VK_CONTROL && m.vk[PAD_ACT_CROSS][1] == 0);
    /* keys that cannot be bound change nothing */
    m = pad_kb_layout_default();
    CHECK(pck_bind(&m, PAD_ACT_ACCEL, PAD_VK_ESCAPE) == -2 && pck_bind(&m, PAD_ACT_ACCEL, PAD_VK_MENU) == -2 &&
          pck_bind(&m, PAD_ACT_ACCEL, 0x5B) == -2 && pck_bind(&m, PAD_ACT_ACCEL, 0) == -2 && pck_bind(&m, 99, 'A') == -2);
    CHECK(!memcmp(&m, &l, sizeof l));
    /* binding every action to one key in turn: only the last one holds it */
    m = pad_kb_layout_default();
    for (int a = 0; a < PCK_COUNT; a++) pck_bind(&m, a, 'K');
    for (int c = 0; c < PCK_COUNT - 1; c++) CHECK(pck_owner(&m, 'K', c) == -1 || pck_owner(&m, 'K', c) > c);
    CHECK(m.vk[PCK_COUNT - 1][0] == 'K');
    CHECK(pck_owner(&m, 'K', PCK_COUNT - 1) == -1);

    /* Reset: the defaults come back. A key taken from another action leaves it
     * with its own defaults again when they are free. */
    m = pad_kb_layout_default();
    pck_bind(&m, PAD_ACT_ACCEL, 'T');          /* accelerate: T only; W and Up are free */
    pck_bind(&m, PAD_ACT_BRAKE, 'W');          /* brake: W; takes it from nobody (accelerate lost it) */
    pck_reset(&m, PAD_ACT_ACCEL);              /* W back to accelerate, taken from brake */
    CHECK(pck_is_default(&m, PAD_ACT_ACCEL));
    CHECK(pck_owner(&m, 'W', PAD_ACT_ACCEL) == -1);
    CHECK(m.vk[PAD_ACT_BRAKE][0] == 'S' && m.vk[PAD_ACT_BRAKE][1] == PAD_VK_DOWN);   /* brake gets its defaults back */
    CHECK(pck_is_default(&m, PAD_ACT_BRAKE));
    /* Up is shared: accelerate's default and the d-pad up's, so a reset keeps both */
    CHECK(pck_is_default(&m, PAD_ACT_UP) && m.vk[PAD_ACT_UP][0] == PAD_VK_UP);
    /* a changed layout survives the file */
    m = pad_kb_layout_default();
    pck_bind(&m, PAD_ACT_HANDBRAKE, 'V');
    pck_bind(&m, PAD_ACT_START, 0x70);
    CHECK(pck_format(&m, buf, sizeof buf) > 0);
    pad_kb_layout n2 = pad_kb_layout_default();
    CHECK(pck_parse(&n2, buf) == PCK_COUNT && !memcmp(&m, &n2, sizeof m));
    CHECK(strstr(buf, "key.handbrake = V\n") && strstr(buf, "key.start = F1\n"));

    /* The capture, as the keyboard poll drives it. */
    pad_kb_capture c;
    pad_kb_capture_begin(&c, 1000);
    CHECK(pad_kb_capture_active(&c) && pad_kb_capture_take(&c) == 0);
    pad_kb_capture_step(&c, 1010, 1, 'Z', 0);            /* the key that opened it is still down: ignored */
    CHECK(c.state == PAD_CAP_WAIT_RELEASE && pad_kb_capture_take(&c) == 0);
    pad_kb_capture_step(&c, 1050, 0, 0, 0);              /* released */
    CHECK(c.state == PAD_CAP_WAIT_KEY);
    pad_kb_capture_step(&c, 1100, 0, 0, 0);
    CHECK(c.state == PAD_CAP_WAIT_KEY);
    pad_kb_capture_step(&c, 1200, 1, 'T', 0);            /* the answer */
    CHECK(c.state == PAD_CAP_HOLD && pad_kb_capture_active(&c) && pad_kb_capture_take(&c) == 0);
    pad_kb_capture_step(&c, 1300, 1, 'T', 0);            /* still held: still swallowed, not published */
    CHECK(pad_kb_capture_active(&c) && pad_kb_capture_take(&c) == 0);
    pad_kb_capture_step(&c, 1400, 0, 0, 0);              /* up: published */
    CHECK(!pad_kb_capture_active(&c) && pad_kb_capture_take(&c) == 'T' && pad_kb_capture_take(&c) == 0);
    /* Esc cancels */
    pad_kb_capture_begin(&c, 2000);
    pad_kb_capture_step(&c, 2001, 0, 0, 0);
    pad_kb_capture_step(&c, 2100, 1, 0, 1);
    pad_kb_capture_step(&c, 2200, 0, 0, 0);
    CHECK(pad_kb_capture_take(&c) == -1);
    /* no key for the timeout cancels */
    pad_kb_capture_begin(&c, 3000);
    pad_kb_capture_step(&c, 3001, 0, 0, 0);
    pad_kb_capture_step(&c, 3001 + PAD_KB_CAPTURE_TIMEOUT_MS + 1, 0, 0, 0);
    pad_kb_capture_step(&c, 3002 + PAD_KB_CAPTURE_TIMEOUT_MS + 1, 0, 0, 0);
    CHECK(pad_kb_capture_take(&c) == -1);
    /* a key stuck down cannot lock the keyboard */
    pad_kb_capture_begin(&c, 4000);
    pad_kb_capture_step(&c, 4010, 1, 0, 0);
    pad_kb_capture_step(&c, 4010 + PAD_KB_CAPTURE_TIMEOUT_MS + 5, 1, 0, 0);   /* gives up waiting for release: cancel */
    CHECK(c.state == PAD_CAP_HOLD);
    pad_kb_capture_step(&c, 4010 + PAD_KB_CAPTURE_TIMEOUT_MS + 5 + 3001, 1, 0, 0);
    CHECK(!pad_kb_capture_active(&c) && pad_kb_capture_take(&c) == -1);
    /* folding and what can be bound */
    CHECK(pad_kb_vk_fold(0xA0) == PAD_VK_SHIFT && pad_kb_vk_fold(0xA3) == PAD_VK_CONTROL && pad_kb_vk_fold('A') == 'A');
    CHECK(pad_kb_vk_bindable('A') && pad_kb_vk_bindable(PAD_VK_SPACE) && pad_kb_vk_bindable(PAD_VK_CONTROL) &&
          pad_kb_vk_bindable(PAD_VK_SHIFT) && pad_kb_vk_bindable(0x70));
    CHECK(!pad_kb_vk_bindable(1) && !pad_kb_vk_bindable(PAD_VK_ESCAPE) && !pad_kb_vk_bindable(PAD_VK_MENU) && !pad_kb_vk_bindable(0x5B));

    printf("test_pc_keys: %d failure(s)\n", fails);
    return fails ? 1 : 0;
}
