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
    return lm_call(&s_be, &s_st, fn, out, cap);
}

extern "C" int lanmenu_find(const char* name, int* sig)
{
    return lm_find(name, sig);
}
