/* MSPR_PATCH: the RPCS3 community patch list in effect (port main.cpp).
 *
 * Unset, the list is MSPR_PATCH_DEFAULT, "drs,audiothread". drs: races stay at full resolution
 * instead of the game dropping them to about 56% when it falls under 30 fps
 * (viewportquality.xml); every test race since Kk49 ran with it. audiothread: the
 * audio update on its own guest thread (audio_thread.cpp). A value
 * replaces the default list; "none" or an empty value turns every patch off.
 *
 * mspr_patch_spec() takes the variable as a parameter so the choice can be
 * tested without the process environment (port-vkgame/tests/test_mspr_patch.c). */
#ifndef MSPR_PATCH_H
#define MSPR_PATCH_H

#include <string.h>

#define MSPR_PATCH_DEFAULT "drs,audiothread"

static const char* mspr_patch_spec(const char* env)
{
    if (!env) return MSPR_PATCH_DEFAULT;
    if (!strcmp(env, "none")) return "";
    return env;
}

#endif
