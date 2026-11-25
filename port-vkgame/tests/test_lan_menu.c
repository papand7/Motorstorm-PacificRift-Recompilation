/* LAN play screen logic (port-vkgame/lan_menu.h) against a stand-in backend. No sockets, no guest memory.
 * Build: generated/analysis/lan_menu/tools/build_tests.cmd */
#include "lan_menu.h"

#include <stdio.h>

static int fails;
#define CHECK(c) do { if (!(c)) { fails++; printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)

/* the stand-in */
static int g_hosting, g_host_rc, g_n, g_touch, g_left, g_joined = -1;
static struct { char name[40]; char value[40]; int ok; } g_e[12];

static int b_hosting(void) { return g_hosting; }
static int b_set_host(int on)
{
    if (on && g_host_rc) return -1;
    g_hosting = on;
    return 0;
}
static void b_status(char* o, size_t c) { snprintf(o, c, "%s", g_hosting ? "Hosting." : "Idle."); }
static void b_touch(void) { g_touch++; }
static int b_entries(void) { return g_n; }
static int b_entry(int i, char* l, size_t lc, char* v, size_t vc, int* ok)
{
    if (i < 0 || i >= g_n) return 0;
    snprintf(l, lc, "%s", g_e[i].name);
    snprintf(v, vc, "%s", g_e[i].value);
    *ok = g_e[i].ok;
    return 1;
}
static int b_join(int i, char* msg, size_t cap)
{
    if (g_hosting) { snprintf(msg, cap, "Stop hosting first."); return -1; }
    if (i < 0 || i >= g_n || !g_e[i].ok) { snprintf(msg, cap, "That game is full."); return -1; }
    g_joined = i;
    snprintf(msg, cap, "Joining %s.", g_e[i].name);
    return 0;
}
static void b_leave(void) { g_left++; g_joined = -1; }

static const lm_backend be = { b_hosting, b_set_host, b_status, b_touch, b_entries, b_entry, b_join, b_leave };

static void fill(int n)
{
    g_n = n;
    for (int i = 0; i < n; i++) {
        snprintf(g_e[i].name, sizeof g_e[i].name, "PC-%d", i);
        snprintf(g_e[i].value, sizeof g_e[i].value, "Lobby  %d/8  %d ms", i, 5 + i);
        g_e[i].ok = 1;
    }
}

static int run(lm_state* s, const char* name, char* out, size_t cap)
{
    int sig = -9;
    const int f = lm_find(name, &sig);
    if (f < 0) { out[0] = 0; return -100; }
    CHECK(sig == lm_sig(f));
    return lm_call(&be, s, f, out, cap);
}

int main(void)
{
    char t[200];
    lm_state s;
    memset(&s, 0, sizeof s);

    /* names and signatures */
    int sig = 0;
    CHECK(lm_find("LanHost", &sig) == LMF_HOST && sig == LM_SIG_BOOL);
    CHECK(lm_find("LanLeave", &sig) == LMF_LEAVE && sig == LM_SIG_VOID);
    CHECK(lm_find("LanTitle", &sig) == LMF_TITLE && sig == LM_SIG_TEXT);
    CHECK(lm_find("LanRow0", &sig) == LMF_ROW && sig == LM_SIG_TEXT);
    CHECK(lm_find("LanRow4", &sig) == LMF_ROW + 4);
    CHECK(lm_find("LanRowInfo3", &sig) == LMF_ROW_INFO + 3 && sig == LM_SIG_TEXT);
    CHECK(lm_find("LanPick2", &sig) == LMF_PICK + 2 && sig == LM_SIG_BOOL);
    CHECK(lm_find("LanRow5", &sig) < 0);
    CHECK(lm_find("LanRow", &sig) < 0);
    CHECK(lm_find("LanRow12", &sig) < 0);
    CHECK(lm_find("LanPick-1", &sig) < 0);
    CHECK(lm_find("PcName0", &sig) < 0);
    CHECK(lm_find("Lan", &sig) < 0);
    CHECK(lm_find("LanHostX", &sig) < 0);
    {   /* every function has a unique name through lm_find, and the signature table agrees */
        static const char* const names[] = { "LanTitle", "LanFindTitle", "LanHostLabel", "LanHostInfo", "LanFindLabel",
            "LanFindInfo", "LanLeaveLabel", "LanLeaveInfo", "LanStatus", "LanHost", "LanLeave", "LanTouch",
            "LanPagePrev", "LanPageNext" };
        for (int i = 0; i < (int)(sizeof names / sizeof names[0]); i++) {
            CHECK(lm_find(names[i], &sig) == i);
            CHECK(lm_sig(i) == sig);
        }
        CHECK((int)(sizeof names / sizeof names[0]) == LMF_ROW);
        CHECK(lm_sig(LMF_COUNT) < 0 && lm_sig(-1) < 0);
    }

    /* paging maths */
    CHECK(lm_pages(0) == 1 && lm_pages(1) == 1 && lm_pages(5) == 1 && lm_pages(6) == 2 && lm_pages(10) == 2 && lm_pages(11) == 3);
    s.page = 1;
    CHECK(lm_row_entry(&s, 0, 8) == 5 && lm_row_entry(&s, 2, 8) == 7 && lm_row_entry(&s, 3, 8) == -1);
    CHECK(lm_row_entry(&s, -1, 8) == -1 && lm_row_entry(&s, LM_ROWS, 99) == -1);
    lm_clamp(&s, 3);
    CHECK(s.page == 0);
    s.page = 7;
    lm_clamp(&s, 11);
    CHECK(s.page == 2);

    /* empty list: a searching line in row 0 only; picking does nothing */
    fill(0);
    memset(&s, 0, sizeof s);
    run(&s, "LanRow0", t, sizeof t);
    CHECK(!strcmp(t, "Searching for LAN games..."));
    run(&s, "LanRow1", t, sizeof t);
    CHECK(t[0] == 0);
    run(&s, "LanRowInfo0", t, sizeof t);
    CHECK(strstr(t, "No LAN games found"));
    CHECK(run(&s, "LanPick0", t, sizeof t) == 0);
    CHECK(g_joined == -1);
    run(&s, "LanStatus", t, sizeof t);
    CHECK(!strcmp(t, "No game in this row."));

    /* a page of games */
    fill(3);
    memset(&s, 0, sizeof s);
    run(&s, "LanRow1", t, sizeof t);
    CHECK(!strcmp(t, "PC-1   Lobby  1/8  6 ms"));
    run(&s, "LanRow3", t, sizeof t);
    CHECK(t[0] == 0);
    run(&s, "LanRowInfo2", t, sizeof t);
    CHECK(strstr(t, "Join PC-2's game") && !strstr(t, "Page"));
    CHECK(run(&s, "LanPick1", t, sizeof t) == 1);
    CHECK(g_joined == 1 && s.msg[0] == 0);
    g_e[2].ok = 0;
    run(&s, "LanRowInfo2", t, sizeof t);
    CHECK(strstr(t, "cannot be joined"));
    CHECK(run(&s, "LanPick2", t, sizeof t) == 0);
    run(&s, "LanStatus", t, sizeof t);
    CHECK(!strcmp(t, "That game is full."));
    CHECK(run(&s, "LanPick4", t, sizeof t) == 0);   /* an empty row */

    /* a status that is not the failure's goes back to the backend's once a pick works */
    CHECK(run(&s, "LanPick0", t, sizeof t) == 1);
    run(&s, "LanStatus", t, sizeof t);
    CHECK(!strcmp(t, "Idle."));

    /* paging over 12 games: 5 + 5 + 2, wrapping */
    fill(12);
    memset(&s, 0, sizeof s);
    run(&s, "LanRowInfo0", t, sizeof t);
    CHECK(strstr(t, "Page 1 of 3"));
    run(&s, "LanPageNext", t, sizeof t);
    CHECK(s.page == 1);
    run(&s, "LanRow0", t, sizeof t);
    CHECK(!strncmp(t, "PC-5 ", 5));
    run(&s, "LanPageNext", t, sizeof t);
    run(&s, "LanRow1", t, sizeof t);
    CHECK(!strncmp(t, "PC-11 ", 6));
    run(&s, "LanRow2", t, sizeof t);
    CHECK(t[0] == 0);
    CHECK(run(&s, "LanPick1", t, sizeof t) == 1 && g_joined == 11);
    run(&s, "LanPageNext", t, sizeof t);
    CHECK(s.page == 0);
    run(&s, "LanPagePrev", t, sizeof t);
    CHECK(s.page == 2);
    run(&s, "LanPagePrev", t, sizeof t);
    CHECK(s.page == 1);
    /* the list shrinks under the page */
    fill(2);
    run(&s, "LanRow0", t, sizeof t);
    CHECK(s.page == 0 && !strncmp(t, "PC-0 ", 5));
    run(&s, "LanPageNext", t, sizeof t);
    CHECK(s.page == 0);   /* one page: stays */

    /* names from the network: control characters and length */
    fill(1);
    memset(&s, 0, sizeof s);
    snprintf(g_e[0].name, sizeof g_e[0].name, "A\tB\x01" "A very long computer name");
    run(&s, "LanRow0", t, sizeof t);
    CHECK(!strncmp(t, "A?B?A very long comput   Lobby", 30));
    CHECK(strlen(t) < 22 + 3 + 40);

    /* Host */
    g_hosting = 0; g_host_rc = 0;
    memset(&s, 0, sizeof s);
    CHECK(run(&s, "LanHost", t, sizeof t) == 1 && g_hosting == 1);
    CHECK(run(&s, "LanHost", t, sizeof t) == 1 && g_hosting == 1);   /* again: still hosting */
    run(&s, "LanHostInfo", t, sizeof t);
    CHECK(strstr(t, "Hosting."));
    /* joining while hosting is refused and says why */
    fill(2);
    CHECK(run(&s, "LanPick0", t, sizeof t) == 0);
    run(&s, "LanStatus", t, sizeof t);
    CHECK(!strcmp(t, "Stop hosting first."));
    /* Leave: leaves, stops hosting, clears the message */
    g_left = 0;
    run(&s, "LanLeave", t, sizeof t);
    CHECK(g_left == 1 && g_hosting == 0);
    run(&s, "LanStatus", t, sizeof t);
    CHECK(!strcmp(t, "Idle."));
    run(&s, "LanLeaveInfo", t, sizeof t);
    CHECK(strstr(t, "Leave the LAN game"));
    /* Host fails: false, and the status says what the backend said */
    g_host_rc = -1;
    CHECK(run(&s, "LanHost", t, sizeof t) == 0 && g_hosting == 0);
    run(&s, "LanStatus", t, sizeof t);
    CHECK(!strcmp(t, "Idle."));

    /* touch and labels */
    g_touch = 0;
    run(&s, "LanTouch", t, sizeof t);
    run(&s, "LanTouch", t, sizeof t);
    CHECK(g_touch == 2);
    run(&s, "LanTitle", t, sizeof t);
    CHECK(!strcmp(t, "LAN Game"));
    run(&s, "LanHostLabel", t, sizeof t);
    CHECK(!strcmp(t, "HOST A GAME"));
    run(&s, "LanFindLabel", t, sizeof t);
    CHECK(!strcmp(t, "FIND A GAME"));
    run(&s, "LanLeaveLabel", t, sizeof t);
    CHECK(!strcmp(t, "LEAVE"));
    /* every text fits the game's 127-character buffers */
    for (int f = 0; f < LMF_COUNT; f++) {
        if (lm_sig(f) != LM_SIG_TEXT) continue;
        char big[128];
        lm_call(&be, &s, f, big, sizeof big);
        CHECK(strlen(big) < 128);
    }

    printf("test_lan_menu: %d failure(s)\n", fails);
    return fails ? 1 : 0;
}
