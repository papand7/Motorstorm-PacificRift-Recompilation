/* PC key bindings: the keyboard layout of the keyboard fallback (libs/input
 * pad_keyboard_map.h), as settings.ini lines and the rules for changing it.
 *
 *   key.accelerate = W, Up       up to two keys per action, by name; "none" = unbound
 *
 * Only actions listed here are written; a missing line keeps the action's
 * default keys, an unreadable one is ignored (the action keeps its keys).
 * Header-only and free of process state, so the rules are tested off the game
 * (port-vkgame/tests/test_pc_keys.c). The default layout is the framework's
 * (pad_kb_layout_default); the port's own table here only names things.
 *
 * Changing a key (pck_bind):
 *   - the action's keys are replaced by the one key;
 *   - a key that another action already uses is taken from it; if that leaves
 *     the other action without a key it gets the key this action had (a swap),
 *     so no action is left unbound by a rebind;
 *   - pck_reset puts an action's default keys back, taking them from any other
 *     action that holds them now, except where that action's own default is the
 *     key (shared defaults such as Up); an action that thereby lost its last key
 *     gets its own defaults back when they are free.
 * Defaults with a shared key: Up (accelerate, d-pad up), Down (brake, d-pad down),
 * Left (steer left, d-pad left), Right (steer right, d-pad right). Circle, L1 and
 * R1 have no default key.
 * Which keys can be bound at all is pad_kb_vk_bindable. */
#ifndef PC_KEYS_H
#define PC_KEYS_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cellPad.h"            /* CELL_PAD_CTRL_* for pad_keyboard_map.h */
#include "pad_keyboard_map.h"

typedef struct {
    const char* key;      /* settings.ini key suffix: key.<key> */
    const char* name;     /* shown on the page */
    const char* info;     /* the info line */
} pck_action;

/* In PAD_ACT_* order. The d-pad actions are the menu movement and also the
 * stick; steering left/right also answers the left/right arrows. */
static const pck_action k_pck_actions[PAD_ACT_COUNT] = {
    { "accelerate", "Accelerate", "Throttle (R2)." },
    { "brake",      "Brake / Reverse", "Brake and reverse (L2)." },
    { "steerleft",  "Steer Left", "Steer left (the left arrow steers too)." },
    { "steerright", "Steer Right", "Steer right (the right arrow steers too)." },
    { "handbrake",  "Handbrake", "The handbrake (Square unless PAD_KEY_HANDBRAKE is set)." },
    { "cross",      "Boost / Accept", "Boost in a race, accept in menus (Cross)." },
    { "square",     "Square", "The Square button." },
    { "triangle",   "Triangle", "The Triangle button." },
    { "circle",     "Back / Circle", "Back in menus (Circle)." },
    { "l1",         "L1", "The L1 button." },
    { "r1",         "R1", "The R1 button." },
    { "start",      "Pause / Start", "Pause (Start)." },
    { "select",     "Select", "The Select button." },
    { "up",         "Up", "Menu up and the d-pad up." },
    { "down",       "Down", "Menu down and the d-pad down." },
    { "left",       "Left", "Menu left and the d-pad left." },
    { "right",      "Right", "Menu right and the d-pad right." },
};
#define PCK_COUNT PAD_ACT_COUNT

/* Key names: letters and digits are themselves; the rest are words without
 * spaces. Ctrl, Shift are the generic codes (either side). */
static const struct { int vk; const char* name; } k_pck_names[] = {
    { 0x08, "Backspace" }, { 0x09, "Tab" }, { 0x0D, "Enter" }, { 0x10, "Shift" }, { 0x11, "Ctrl" },
    { 0x13, "Pause" }, { 0x14, "CapsLock" }, { 0x20, "Space" }, { 0x21, "PageUp" }, { 0x22, "PageDown" },
    { 0x23, "End" }, { 0x24, "Home" }, { 0x25, "Left" }, { 0x26, "Up" }, { 0x27, "Right" }, { 0x28, "Down" },
    { 0x2D, "Insert" }, { 0x2E, "Delete" },
    { 0x6A, "NumMultiply" }, { 0x6B, "NumPlus" }, { 0x6D, "NumMinus" }, { 0x6E, "NumDecimal" }, { 0x6F, "NumDivide" },
    { 0x90, "NumLock" }, { 0x91, "ScrollLock" },
    { 0xBA, "Semicolon" }, { 0xBB, "Equals" }, { 0xBC, "Comma" }, { 0xBD, "Minus" }, { 0xBE, "Period" },
    { 0xBF, "Slash" }, { 0xC0, "Backquote" }, { 0xDB, "LBracket" }, { 0xDC, "Backslash" }, { 0xDD, "RBracket" },
    { 0xDE, "Quote" },
};

/* The name of a key code into out ("none" for 0, "0xNN" when it has no name). */
static inline const char* pck_vk_name(int vk, char* out, size_t n)
{
    if (!vk) { snprintf(out, n, "none"); return out; }
    if ((vk >= '0' && vk <= '9') || (vk >= 'A' && vk <= 'Z')) { snprintf(out, n, "%c", vk); return out; }
    if (vk >= 0x60 && vk <= 0x69) { snprintf(out, n, "Num%d", vk - 0x60); return out; }
    if (vk >= 0x70 && vk <= 0x87) { snprintf(out, n, "F%d", vk - 0x6F); return out; }
    for (unsigned i = 0; i < sizeof k_pck_names / sizeof k_pck_names[0]; i++)
        if (k_pck_names[i].vk == vk) { snprintf(out, n, "%s", k_pck_names[i].name); return out; }
    snprintf(out, n, "0x%02X", vk);
    return out;
}

static inline int pck_ieq(const char* a, const char* b)
{
    for (; *a && *b; a++, b++) {
        char x = *a, y = *b;
        if (x >= 'A' && x <= 'Z') x += 32;
        if (y >= 'A' && y <= 'Z') y += 32;
        if (x != y) return 0;
    }
    return *a == *b;
}

/* A key name (any case) or 0xNN to its code; 0 for "none"; -1 for anything else
 * or a key that cannot be bound. */
static inline int pck_vk_parse(const char* t)
{
    if (pck_ieq(t, "none")) return 0;
    int vk = -1;
    if (t[0] && !t[1] && ((t[0] >= '0' && t[0] <= '9') || (t[0] >= 'a' && t[0] <= 'z') || (t[0] >= 'A' && t[0] <= 'Z')))
        vk = t[0] >= 'a' ? t[0] - 32 : t[0];
    else if ((t[0] == 'N' || t[0] == 'n') && (t[1] == 'u' || t[1] == 'U') && (t[2] == 'm' || t[2] == 'M') &&
             t[3] >= '0' && t[3] <= '9' && !t[4])
        vk = 0x60 + (t[3] - '0');
    else if ((t[0] == 'F' || t[0] == 'f') && t[1] >= '1' && t[1] <= '9') {
        char* e;
        const long f = strtol(t + 1, &e, 10);
        if (!*e && f >= 1 && f <= 24) vk = 0x6F + (int)f;
    } else if (t[0] == '0' && (t[1] == 'x' || t[1] == 'X')) {
        char* e;
        const long v = strtol(t + 2, &e, 16);
        if (t[2] && !*e && v > 0 && v < 256) vk = (int)v;
    } else {
        for (unsigned i = 0; i < sizeof k_pck_names / sizeof k_pck_names[0]; i++)
            if (pck_ieq(t, k_pck_names[i].name)) { vk = k_pck_names[i].vk; break; }
    }
    return vk > 0 && pad_kb_vk_bindable(vk) ? vk : -1;
}

static inline int pck_find(const char* suffix)
{
    for (int i = 0; i < PCK_COUNT; i++)
        if (pck_ieq(k_pck_actions[i].key, suffix)) return i;
    return -1;
}

/* "W, 2" for the page, and for the file. */
static inline void pck_format_keys(const pad_kb_layout* l, int act, char* out, size_t n)
{
    char a[24], b[24];
    const int k0 = l->vk[act][0], k1 = l->vk[act][1];
    if (k0 && k1) snprintf(out, n, "%s, %s", pck_vk_name(k0, a, sizeof a), pck_vk_name(k1, b, sizeof b));
    else if (k0 || k1) snprintf(out, n, "%s", pck_vk_name(k0 ? k0 : k1, a, sizeof a));
    else snprintf(out, n, "none");
}

/* One value ("W, 2", "W", "none") into the two slots of act; 0 when it is not
 * all readable (the slots are then unchanged). */
static inline int pck_parse_keys(pad_kb_layout* l, int act, const char* v)
{
    int k[PAD_KEYS_PER_ACTION] = { 0, 0 }, n = 0;
    char buf[96];
    snprintf(buf, sizeof buf, "%s", v);
    for (char* t = buf; t && *t; ) {
        char* c = strchr(t, ',');
        if (c) *c++ = 0;
        while (*t == ' ' || *t == '\t') t++;
        for (char* p = t + strlen(t); p > t && (p[-1] == ' ' || p[-1] == '\t' || p[-1] == '\r'); ) *--p = 0;
        const int vk = pck_vk_parse(t);
        if (vk < 0 || n >= PAD_KEYS_PER_ACTION) return 0;
        if (vk) k[n++] = vk;
        t = c;
    }
    for (int i = 0; i < PAD_KEYS_PER_ACTION; i++) l->vk[act][i] = (uint8_t)k[i];
    return 1;
}

/* settings.ini text into l (which keeps what the text does not name); returns
 * the number of actions read. Lines are "key.<action> = <keys>". */
static inline int pck_parse(pad_kb_layout* l, const char* text)
{
    int got = 0;
    while (text && *text) {
        const char* e = strchr(text, '\n');
        size_t n = e ? (size_t)(e - text) : strlen(text);
        char line[160];
        if (n >= sizeof line) n = sizeof line - 1;
        memcpy(line, text, n);
        line[n] = 0;
        text = e ? e + 1 : NULL;
        char* eq = strchr(line, '=');
        if (line[0] == '#' || line[0] == ';' || !eq) continue;
        *eq = 0;
        char *k = line, *v = eq + 1;
        while (*k == ' ' || *k == '\t') k++;
        for (char* p = k + strlen(k); p > k && (p[-1] == ' ' || p[-1] == '\t'); ) *--p = 0;
        if (strlen(k) < 5 || (k[0] | 0x20) != 'k' || (k[1] | 0x20) != 'e' ||
            (k[2] | 0x20) != 'y' || k[3] != '.') continue;
        const int a = pck_find(k + 4);
        if (a >= 0 && pck_parse_keys(l, a, v)) got++;
    }
    return got;
}

static inline int pck_format(const pad_kb_layout* l, char* out, size_t n)
{
    int w = 0;
    for (int i = 0; i < PCK_COUNT && w >= 0 && (size_t)w < n; i++) {
        char v[64];
        pck_format_keys(l, i, v, sizeof v);
        w += snprintf(out + w, n - (size_t)w, "key.%s = %s\n", k_pck_actions[i].key, v);
    }
    return w;
}

/* Which action (other than skip) uses vk, or -1. */
static inline int pck_owner(const pad_kb_layout* l, int vk, int skip)
{
    for (int a = 0; a < PCK_COUNT; a++)
        for (int k = 0; k < PAD_KEYS_PER_ACTION; k++)
            if (a != skip && l->vk[a][k] == vk) return a;
    return -1;
}

static inline void pck_drop_key(pad_kb_layout* l, int act, int vk)
{
    int keep[PAD_KEYS_PER_ACTION] = { 0, 0 }, n = 0;
    for (int k = 0; k < PAD_KEYS_PER_ACTION; k++)
        if (l->vk[act][k] && l->vk[act][k] != vk) keep[n++] = l->vk[act][k];
    for (int k = 0; k < PAD_KEYS_PER_ACTION; k++) l->vk[act][k] = (uint8_t)keep[k];
}

/* Make vk the only key of act. Returns the action that lost the key (it may
 * have been given act's old key), or -1. vk must be bindable (else -2, nothing
 * changed). */
static inline int pck_bind(pad_kb_layout* l, int act, int vk)
{
    if (act < 0 || act >= PCK_COUNT || !pad_kb_vk_bindable(vk)) return -2;
    const int old = l->vk[act][0] ? l->vk[act][0] : l->vk[act][1];
    int lost = -1;
    for (int a; (a = pck_owner(l, vk, act)) >= 0; ) {
        lost = a;
        pck_drop_key(l, a, vk);
        if (!l->vk[a][0] && old && old != vk)
            l->vk[a][0] = (uint8_t)old;   /* the swap: it takes the key act gave up */
    }
    l->vk[act][0] = (uint8_t)vk;
    l->vk[act][1] = 0;
    return lost;
}

/* Is vk one of action a's default keys? Some keys are shared by design (Up is
 * both accelerate and the d-pad up), and a reset leaves a shared default alone. */
static inline int pck_is_default_key(int a, int vk)
{
    const pad_kb_layout d = pad_kb_layout_default();
    for (int k = 0; k < PAD_KEYS_PER_ACTION; k++) if (vk && d.vk[a][k] == vk) return 1;
    return 0;
}

/* Does another action hold vk without it being that action's own default? */
static inline int pck_blocked(const pad_kb_layout* l, int a, int vk)
{
    for (int b = 0; b < PCK_COUNT; b++) {
        if (b == a || pck_is_default_key(b, vk)) continue;
        for (int k = 0; k < PAD_KEYS_PER_ACTION; k++) if (vk && l->vk[b][k] == vk) return 1;
    }
    return 0;
}

/* Put act's default keys back, taking them from whoever holds them (except
 * where the holder's own default is that key). */
static inline void pck_reset(pad_kb_layout* l, int act)
{
    const pad_kb_layout d = pad_kb_layout_default();
    for (int k = 0; k < PAD_KEYS_PER_ACTION; k++) {
        const int vk = d.vk[act][k];
        if (!vk) continue;
        for (int a = 0; a < PCK_COUNT; a++)
            if (a != act && !pck_is_default_key(a, vk)) pck_drop_key(l, a, vk);
    }
    for (int k = 0; k < PAD_KEYS_PER_ACTION; k++) l->vk[act][k] = d.vk[act][k];
    /* an action that lost its last key to this gets its own defaults back, when free */
    for (int a = 0; a < PCK_COUNT; a++) {
        if (a == act || l->vk[a][0] || l->vk[a][1]) continue;
        int free_ = 1;
        for (int k = 0; k < PAD_KEYS_PER_ACTION; k++)
            if (d.vk[a][k] && pck_blocked(l, a, d.vk[a][k])) free_ = 0;
        if (free_) for (int k = 0; k < PAD_KEYS_PER_ACTION; k++) l->vk[a][k] = d.vk[a][k];
    }
}

static inline int pck_is_default(const pad_kb_layout* l, int act)
{
    const pad_kb_layout d = pad_kb_layout_default();
    return !memcmp(l->vk[act], d.vk[act], PAD_KEYS_PER_ACTION);
}

#endif
