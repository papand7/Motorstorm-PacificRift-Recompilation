/* LAN play screen, the port's side: lan_menu.h's logic on lan_play. pc_menu.cpp answers the game's
 * function lookup for the names lm_find knows and calls lanmenu_call for them. */
#include "lan_menu.h"
#include "lan_play.h"

static const lm_backend s_be = {
    lan_play_hosting, lan_play_set_host, lan_play_status, lan_play_touch,
    lan_play_entries, lan_play_entry, lan_play_join, lan_play_leave,
};
static lm_state s_st;   /* the game's UI thread only */

/* Runs function fn (an lm_fn); text functions fill out; returns the bool of a bool function. */
extern "C" int lanmenu_call(int fn, char* out, size_t cap)
{
    const int r = lm_call(&s_be, &s_st, fn, out, cap);
    if (fn == LMF_HOST || fn == LMF_LEAVE || (fn >= LMF_PICK && fn < LMF_COUNT)) {   /* the actions, not the texts */
        char st[160];
        lan_play_status(st, sizeof st);
        fprintf(stderr, "[lan-menu] %s -> %d (%s)\n", fn == LMF_HOST ? "Host" : fn == LMF_LEAVE ? "Leave" : "Pick", r,
                s_st.msg[0] ? s_st.msg : st);
    }
    return r;
}

extern "C" int lanmenu_find(const char* name, int* sig)
{
    return lm_find(name, sig);
}
