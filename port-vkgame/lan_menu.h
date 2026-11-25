/* LAN play screen: the logic behind the pages tools/pcmenu/make_lanmenu.py makes from the game's own
 * Wreckreation page. Pure (no sockets, no guest memory): the backend is a table of functions, so the
 * tests (tests/test_lan_menu.c) run it against a stand-in and the port (lan_menu.cpp) against lan_play.
 *
 * The screen is reached from the game's ONLINE item (Wreckreation page): wreckreation-lan has Host a
 * game, Find a game and Leave; Find a game opens wreckreation-lanfind, the server browser, five games
 * to a page. Host and a join go on into the game's own online flow (the ONLINE item's original actions),
 * the game's Matching2 client then talks to the LAN room server (lan_play.cpp, np_psnr.c).
 *
 * The pages call these by name through ExecuteFunction (pc_menu.cpp answers the game's lookup for any
 * name starting "Lan"); the signature of each is in the table: void, bool (TestBoolean reads it) or
 * text (SetChannelValue(currentReturnValue, widget, text)). */
#ifndef LAN_MENU_H
#define LAN_MENU_H

#include <stddef.h>
#include <stdio.h>
#include <string.h>

#define LM_ROWS 5          /* games per page: the Wreckreation page's five items */
#define LM_NAME_MAX 22     /* host name characters shown in a row */

/* The signature numbers of the game's function table (pc_menu.cpp: PCMENU_SIG_*). */
enum { LM_SIG_VOID = 0, LM_SIG_BOOL = 16, LM_SIG_TEXT = 24 };

enum lm_fn {
    LMF_TITLE,        /* text: the root page's header */
    LMF_FIND_TITLE,   /* text: the browser's header */
    LMF_HOST_LABEL, LMF_HOST_INFO,
    LMF_FIND_LABEL, LMF_FIND_INFO,
    LMF_LEAVE_LABEL, LMF_LEAVE_INFO,
    LMF_STATUS,       /* text: the one-line status (the info bar after a failed action) */
    LMF_HOST,         /* bool: start hosting; false = could not (status says why) */
    LMF_LEAVE,        /* void: leave the joined game, stop hosting */
    LMF_TOUCH,        /* void: the browser is on screen (every frame) */
    LMF_PAGE_PREV, LMF_PAGE_NEXT,   /* void */
    LMF_ROW,          /* LM_ROWS texts: the row's line */
    LMF_ROW_INFO = LMF_ROW + LM_ROWS,    /* LM_ROWS texts: the info bar when the row is focused */
    LMF_PICK = LMF_ROW_INFO + LM_ROWS,   /* LM_ROWS bools: join the row's game; false = could not */
    LMF_COUNT = LMF_PICK + LM_ROWS
};

typedef struct {
    int (*hosting)(void);
    int (*set_host)(int on);
    void (*status)(char* out, size_t cap);
    void (*touch)(void);
    int (*entries)(void);
    int (*entry)(int i, char* label, size_t lc, char* value, size_t vc, int* joinable);
    int (*join)(int i, char* msg, size_t cap);
    void (*leave)(void);
} lm_backend;

typedef struct {
    int page;          /* the browser's page, 0-based */
    char msg[160];     /* the last action's result (shown instead of the backend's status) */
} lm_state;

static const struct { const char* name; int sig; } k_lm_fixed[LMF_ROW] = {
    { "LanTitle", LM_SIG_TEXT }, { "LanFindTitle", LM_SIG_TEXT },
    { "LanHostLabel", LM_SIG_TEXT }, { "LanHostInfo", LM_SIG_TEXT },
    { "LanFindLabel", LM_SIG_TEXT }, { "LanFindInfo", LM_SIG_TEXT },
    { "LanLeaveLabel", LM_SIG_TEXT }, { "LanLeaveInfo", LM_SIG_TEXT },
    { "LanStatus", LM_SIG_TEXT }, { "LanHost", LM_SIG_BOOL }, { "LanLeave", LM_SIG_VOID },
    { "LanTouch", LM_SIG_VOID }, { "LanPagePrev", LM_SIG_VOID }, { "LanPageNext", LM_SIG_VOID },
};

/* The function a name stands for (an lm_fn) and its signature, or -1. */
static inline int lm_find(const char* n, int* sig)
{
    if (strncmp(n, "Lan", 3)) return -1;
    for (int i = 0; i < LMF_ROW; i++)
        if (!strcmp(n, k_lm_fixed[i].name)) { *sig = k_lm_fixed[i].sig; return i; }
    static const struct { const char* p; int base, sig; } rows[] = {
        { "LanRowInfo", LMF_ROW_INFO, LM_SIG_TEXT }, { "LanRow", LMF_ROW, LM_SIG_TEXT },
        { "LanPick", LMF_PICK, LM_SIG_BOOL } };
    for (int k = 0; k < 3; k++) {
        const size_t l = strlen(rows[k].p);
        if (strncmp(n, rows[k].p, l)) continue;
        if (n[l] < '0' || n[l] >= '0' + LM_ROWS || n[l + 1]) return -1;
        *sig = rows[k].sig;
        return rows[k].base + (n[l] - '0');
    }
    return -1;
}

static inline int lm_sig(int fn)
{
    if (fn < 0 || fn >= LMF_COUNT) return -1;
    if (fn < LMF_ROW) return k_lm_fixed[fn].sig;
    return fn >= LMF_PICK ? LM_SIG_BOOL : LM_SIG_TEXT;
}

static inline int lm_pages(int n) { return n <= 0 ? 1 : (n + LM_ROWS - 1) / LM_ROWS; }

/* The list changed under the page: keep the page in range. */
static inline void lm_clamp(lm_state* s, int n)
{
    const int p = lm_pages(n);
    if (s->page >= p) s->page = p - 1;
    if (s->page < 0) s->page = 0;
}

/* The entry a row shows, or -1 (an empty row). */
static inline int lm_row_entry(const lm_state* s, int row, int n)
{
    const int i = s->page * LM_ROWS + row;
    return row >= 0 && row < LM_ROWS && i < n ? i : -1;
}

/* Host names are free text from the LAN: printable ASCII only, cut to LM_NAME_MAX. */
static inline void lm_clean_name(const char* in, char* out, size_t cap)
{
    size_t o = 0;
    for (; *in && o + 1 < cap && o < LM_NAME_MAX; in++) out[o++] = (*in >= 32 && *in < 127) ? *in : '?';
    out[o] = 0;
}

static inline void lm_text(char* out, size_t cap, const char* t) { snprintf(out, cap, "%s", t); }

/* The status line: the last action's result, else the backend's. */
static inline void lm_status(const lm_backend* b, const lm_state* s, char* out, size_t cap)
{
    if (s->msg[0]) { snprintf(out, cap, "%s", s->msg); return; }
    b->status(out, cap);
}

static inline void lm_row_text(const lm_backend* b, const lm_state* s, int row, char* out, size_t cap)
{
    const int n = b->entries();
    const int i = lm_row_entry(s, row, n);
    out[0] = 0;
    if (i < 0) {
        if (n == 0 && row == 0 && s->page == 0) lm_text(out, cap, "Searching for LAN games...");
        return;
    }
    char label[64], value[64], name[LM_NAME_MAX + 2];
    int ok = 0;
    if (!b->entry(i, label, sizeof label, value, sizeof value, &ok)) return;
    lm_clean_name(label, name, sizeof name);
    snprintf(out, cap, "%s   %s", name, value);
}

static inline void lm_row_info(const lm_backend* b, const lm_state* s, int row, char* out, size_t cap)
{
    const int n = b->entries();
    const int i = lm_row_entry(s, row, n);
    char pg[48] = "";
    if (lm_pages(n) > 1) snprintf(pg, sizeof pg, " Page %d of %d: Left and Right show more.", s->page + 1, lm_pages(n));
    if (i < 0) {
        if (n == 0) snprintf(out, cap, "%s", "No LAN games found yet. Another PC on this network must host one (LAN, Host a game).");
        else snprintf(out, cap, "%s", "No game in this row.");
        return;
    }
    char label[64], value[64], name[LM_NAME_MAX + 2];
    int ok = 0;
    if (!b->entry(i, label, sizeof label, value, sizeof value, &ok)) { out[0] = 0; return; }
    lm_clean_name(label, name, sizeof name);
    snprintf(out, cap, ok ? "Join %s's game: %s.%s" : "%s's game cannot be joined: %s.%s", name, value, pg);
}

/* Host: 1 when hosting. */
static inline int lm_host(const lm_backend* b, lm_state* s)
{
    if (b->set_host(1) != 0) { b->status(s->msg, sizeof s->msg); return 0; }
    s->msg[0] = 0;
    return 1;
}

static inline void lm_leave(const lm_backend* b, lm_state* s)
{
    b->leave();
    if (b->hosting()) b->set_host(0);
    s->msg[0] = 0;
    b->status(s->msg, sizeof s->msg);
}

/* Join the row's game: 1 on success. */
static inline int lm_pick(const lm_backend* b, lm_state* s, int row)
{
    const int i = lm_row_entry(s, row, b->entries());
    if (i < 0) { snprintf(s->msg, sizeof s->msg, "%s", "No game in this row."); return 0; }
    char msg[160];
    msg[0] = 0;
    if (b->join(i, msg, sizeof msg) != 0) { snprintf(s->msg, sizeof s->msg, "%s", msg[0] ? msg : "Cannot join."); return 0; }
    s->msg[0] = 0;
    return 1;
}

static inline void lm_page_step(lm_state* s, int n, int dir)
{
    const int p = lm_pages(n);
    s->page = ((s->page + dir) % p + p) % p;
}

/* Runs function fn. Returns its bool (bool functions), else 0; text functions fill out. */
static inline int lm_call(const lm_backend* b, lm_state* s, int fn, char* out, size_t cap)
{
    out[0] = 0;
    lm_clamp(s, b->entries());
    switch (fn) {
    case LMF_TITLE: lm_text(out, cap, "LAN Game"); return 0;
    case LMF_FIND_TITLE: lm_text(out, cap, "LAN Games"); return 0;
    case LMF_HOST_LABEL: lm_text(out, cap, "HOST A GAME"); return 0;
    case LMF_FIND_LABEL: lm_text(out, cap, "FIND A GAME"); return 0;
    case LMF_LEAVE_LABEL: lm_text(out, cap, "LEAVE"); return 0;
    case LMF_HOST_INFO: {
        char st[160];
        b->status(st, sizeof st);
        snprintf(out, cap, "Host a LAN game on this PC and open the online lobby. %s", st);
        return 0; }
    case LMF_FIND_INFO: lm_text(out, cap, "Browse the games hosted on this network and join one."); return 0;
    case LMF_LEAVE_INFO: {
        char st[160];
        b->status(st, sizeof st);
        snprintf(out, cap, "Leave the LAN game and stop hosting. %s", st);
        return 0; }
    case LMF_STATUS: lm_status(b, s, out, cap); return 0;
    case LMF_HOST: return lm_host(b, s);
    case LMF_LEAVE: lm_leave(b, s); return 0;
    case LMF_TOUCH: b->touch(); return 0;
    case LMF_PAGE_PREV: lm_page_step(s, b->entries(), -1); return 0;
    case LMF_PAGE_NEXT: lm_page_step(s, b->entries(), 1); return 0;
    }
    if (fn >= LMF_PICK && fn < LMF_COUNT) return lm_pick(b, s, fn - LMF_PICK);
    if (fn >= LMF_ROW_INFO && fn < LMF_PICK) { lm_row_info(b, s, fn - LMF_ROW_INFO, out, cap); return 0; }
    if (fn >= LMF_ROW && fn < LMF_ROW_INFO) { lm_row_text(b, s, fn - LMF_ROW, out, cap); return 0; }
    return 0;
}

#endif
