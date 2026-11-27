/* PC Settings: pages in the game's own Options menu, the port's side.
 *
 * The pages are the game's own: gui/optionz.gui (the Options page with a PC
 * SETTINGS item), gui/options-pc.gui (a hub like the Options page: Display,
 * Upscaling, Graphics, Driving keys, Button keys) and one page per hub item
 * (gui/options-pcd.gui ...: a page like Controller Options with one row per
 * setting or key binding, pc_pages.h) are generated from the user's disc
 * (tools/pcmenu/make_pcmenu.py) into a folder served by
 * PS3_VFS_OVERLAY (runtime/syscalls/vfs_overlay.h); nothing of the game is in
 * this source. Here:
 *   - settings.ini beside the executable becomes the environment before
 *     anything reads it (pc_settings.h), and its key.* lines the keyboard
 *     layout (pc_keys.h, libs/input pad_keyboard_map.h);
 *   - the GUI functions the pages call (PcName0, PcValue0, PcNext0, PcKey0,
 *     PcHubLabel0, PcTitle1 ...) are answered to the game's ExecuteFunction
 *     lookup when it finds no function of that name (pcmenu_lookup, called
 *     instead of the game's lookup by its lifted callers);
 *   - while the overlay has gui/optionz.gui, the page loader reads it for
 *     "gui/options.gui" (pcmenu_page_load on 1.02, pcmenu_load_sync on 1.03).
 * Without PS3_VFS_OVERLAY and a "pcmenu" folder beside the executable no page
 * reaches these functions and the game runs as before; settings.ini alone
 * still applies.
 *
 * Guest side, at PCMENU_EA (above the runtime's injection window, below the
 * raw SPU windows at 0x30000000, where no title allocation was seen): for each
 * function a functor {this, OPD} the lookup hands back, its OPD {entry, toc}
 * and a 128-byte string buffer. Each entry is a code address registered to a
 * host function (ppu_register_function), so the game's dispatcher calls the
 * host as it calls its own member function thunks. */
#include "ppu_recomp.h"
#include "cellPad.h"
#include "pc_settings.h"
#include "pc_keys.h"
#include "pc_pages.h"
#include "pad_wheel.h"   /* libs/input: the wheel.* lines of settings.ini */
#include "pc_prompts.h"  /* the button prompts as key caps */
#include "lan_menu.h"    /* the LAN play screen (lan_menu.cpp): Lan* functions */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <utility>
#ifdef _WIN32
#include <windows.h>
#endif

typedef void (*pcmenu_fn)(ppu_context*);
extern "C" void ppu_register_function(uint64_t addr, pcmenu_fn fn);
extern "C" void mspr_patch_set(uint32_t bit, int on);   /* main.cpp */
#ifdef _WIN32
/* libs/input/cellPad.c */
extern "C" void pad_keyboard_set_layout(const pad_kb_layout* l);
extern "C" void pad_keyboard_capture_begin(void);
extern "C" int pad_keyboard_capture_poll(void);
/* libs/input/pad_wheel_dinput.h (through cellPad.c): the wheel layer reads PAD_WHEEL* variables and settings.ini text */
extern "C" void pad_wheel_set_ini(const char* text);
extern "C" void pad_wheel_reload(void);
extern "C" int pad_host_device_present(void);   /* a gamepad or wheel was found by the last poll */
/* libs/video/rsx_vk_rt.h: 1 the GPU can trace, 0 it cannot, -1 not known yet. Without it in the link: -1. */
extern "C" int rsx_vk_rt_supported(void);
extern "C" int pcmenu_rt_unknown(void) { return -1; }
#pragma comment(linker, "/alternatename:rsx_vk_rt_supported=pcmenu_rt_unknown")
#endif

/* A lifted tail branch (b to another fragment) only sets this and returns; the
 * caller's DRAIN_TRAMPOLINE runs the target. The wrappers below drain it
 * themselves, so the wrapped call has really finished when they go on. */
extern "C" PPU_THREAD_LOCAL void (*g_trampoline_fn)(void*);
static void pcmenu_drain(ppu_context* ctx)
{
    while (g_trampoline_fn) {
        void (*f)(void*) = g_trampoline_fn;
        g_trampoline_fn = 0;
        f(ctx);
    }
}

#define PCMENU_EA      0x2FF00000u
#define PCMENU_FUNCTOR (PCMENU_EA + 0x0000u)   /* 8 bytes each */
#define PCMENU_OPD     (PCMENU_EA + 0x1000u)   /* 8 bytes each */
#define PCMENU_TEXT    (PCMENU_EA + 0x2000u)   /* 128 bytes each */
#define PCMENU_CODE    (PCMENU_EA + 0xE000u)   /* 4 bytes each, never run as guest code (moved up: more rows, more text;
                                                  0xE000 since the Performance page; audio_thread.cpp uses +0xF000) */
#define PCMENU_TOC     0x0109FBF0u
#define PCMENU_MISS    666u                    /* the lookup's "no such function" signature */
#define PCMENU_SIG_VOID 0u                     /* void() */
#define PCMENU_SIG_TEXT 24u                    /* const char*() */

/* Per row (setting or key binding): Name, Value, Info (text), Next, Prev, Key
 * (actions); then per page its hub item's label and info, the titles (0 the
 * hub, then the pages), and the Options item's own. */
enum { PCF_NAME, PCF_VALUE, PCF_INFO, PCF_NEXT, PCF_PREV, PCF_KEY, PCF_PER_ROW };
enum {
    PCF_ROWS_END = PCP_ROWS * PCF_PER_ROW,
    PCF_HUB_LABEL = PCF_ROWS_END,
    PCF_HUB_INFO = PCF_HUB_LABEL + PCP_COUNT,
    PCF_TITLE = PCF_HUB_INFO + PCP_COUNT,
    PCF_MENU_LABEL = PCF_TITLE + PCP_COUNT + 1,
    PCF_MENU_INFO,
    PCF_SAVE,
    PCF_LAN,                    /* the LAN play screen's functions (lan_menu.h), LMF_COUNT of them */
    PCF_COUNT = PCF_LAN + LMF_COUNT
};
static_assert(PCF_COUNT * 128 <= PCMENU_CODE - PCMENU_TEXT, "text buffers must fit between the text and the code addresses");
static_assert(PCF_COUNT * 4 <= 0xF000u - (PCMENU_CODE - PCMENU_EA), "code addresses must fit below PCMENU_EA + 0xF000 (audio_thread.cpp's OPD)");
static_assert(PCF_COUNT * 8 <= 0x1000, "functors must fit below the OPDs");

extern "C" int lanmenu_call(int fn, char* out, size_t cap);   /* lan_menu.cpp */

static const char* const k_pcf_kind[PCF_PER_ROW] = { "PcName", "PcValue", "PcInfo", "PcNext", "PcPrev", "PcKey" };

static pcs_state s_pcs, s_pcs_boot;   /* choices now, and at start */
static pad_kb_layout s_layout;
static pcw_cfg s_wcfg;               /* the wheel.* lines (kept as written, see pcmenu_save) */
static char s_ini[1024], s_dir[1024];
static int s_ready, s_alias;
static int s_unlock_vehicles;         /* settings.ini unlockvehicles (Cheats tab) or MSPR_UNLOCK_VEHICLES */
static int s_unlock_tracks;           /* settings.ini unlocktracks (Cheats tab) or MSPR_UNLOCK_TRACKS */
static int s_screens = 1;             /* settings.ini screens (launcher Display): 1, 2 or 3 monitors (pcs_screens) */
static int s_audio_thread = 1;        /* settings.ini audiothread (launcher Performance): On by default (pcs_audio_thread) */
static int s_thread_place;           /* settings.ini threadplace (launcher Performance): Off by default (pcs_thread_place) */
static char s_player[PCS_NAME_MAX + 1];   /* settings.ini playername (launcher), "" for none (pcs_player_name) */
static int s_cap_act = -1;            /* the key row waiting for a key, or -1 */
static int s_dxc_ok = -1;             /* a dxc.exe (with its dll) was found */

static int pcmenu_exists(const char* path)
{
    struct stat st;
    return stat(path, &st) == 0;
}

/* Why a choice cannot be used here, or NULL (pcs_avail_fn). */
static const char* pcmenu_avail(const char* key, int choice)
{
    if (choice <= 0) return NULL;   /* the first choice of each is "off"/the original */
    char p[1100];
    if (!strcmp(key, "textures") || !strcmp(key, "pbr")) {
        snprintf(p, sizeof p, "%s/textures/pack", s_dir);
        const char* tp = getenv("RSX_TEX_PACK");
        return pcmenu_exists(tp && *tp ? tp : p) ? NULL : "No pack";
    }
    if (!strcmp(key, "rtshadow")) {
        if (s_dxc_ok == 0) return "No DXC";
#ifdef _WIN32
        if (rsx_vk_rt_supported() == 0) return "No RT GPU";
#endif
        return NULL;
    }
    if (!strcmp(key, "fsrmode") && choice == 1) {
        const char* d = getenv("RSX_FSR3_DIR");
        snprintf(p, sizeof p, "%s/amd_fidelityfx_loader_vk.dll", d && *d ? d : s_dir);
        return pcmenu_exists(p) ? NULL : "No FSR3 DLL";
    }
    if (!strcmp(key, "framegen") && choice == 2) {   /* On: AMD FSR 3.1 frame generation (Light needs no DLL) */
        const char* d = getenv("RSX_FSR3_DIR");
        snprintf(p, sizeof p, "%s/amd_fidelityfx_framegeneration_vk.dll", d && *d ? d : s_dir);
        return pcmenu_exists(p) ? NULL : "No FSR3 FG DLL";
    }
    return NULL;
}

/* The Cheats switches the lifted unlock guards ask (generated/analysis/unlockall/tools/unlockall_lifted.py).
 * Vehicles: IsVehicleClassUnLocked, AllVehicleClassesLocked, TicketIsUnlocked. */
extern "C" int mspr_unlock_vehicles_on(void)
{
    return s_unlock_vehicles;
}
extern "C" int mspr_unlock_tracks_on(void)
{
    return s_unlock_tracks;
}

/* settings.ini: the choices, then the key bindings. */
static void pcmenu_save(void)
{
    char text[6144];
    int w = pcs_format(&s_pcs, text, sizeof text);
    if (w < 0 || (size_t)w >= sizeof text) return;
    w += pck_format(&s_layout, text + w, sizeof text - (size_t)w);
    if (w >= 0 && (size_t)w < sizeof text) pcw_format(&s_wcfg, text + w, sizeof text - (size_t)w);   /* wheel.* lines: only those set */
    char tmp[1100];
    snprintf(tmp, sizeof tmp, "%s.tmp", s_ini);
    FILE* f = fopen(tmp, "wb");
    if (!f) { fprintf(stderr, "[pc-menu] cannot write %s\n", s_ini); return; }
    fputs(text, f);
    if (s_unlock_vehicles) fputs("unlockvehicles = On\n", f);   /* Cheats: not page rows, kept while on */
    if (s_unlock_tracks) fputs("unlocktracks = On\n", f);
    if (s_screens > 1) fprintf(f, "screens = %s\n", k_pcs_screens[s_screens - 1]);   /* launcher only: kept */
    if (!s_audio_thread) fputs("audiothread = Off\n", f);   /* launcher only: kept while Off */
    if (s_thread_place) fputs("threadplace = Auto\n", f);   /* launcher only: kept while Auto */
    if (s_player[0]) fprintf(f, "playername = %s\n", s_player);   /* launcher only: kept */
    fclose(f);
#ifdef _WIN32
    if (!MoveFileExA(tmp, s_ini, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
        fprintf(stderr, "[pc-menu] cannot replace %s\n", s_ini);
#else
    rename(tmp, s_ini);
#endif
}

/* ---- Button prompts (pc_prompts.h) ----
 * The draw engine offers every texture it uploads (rsx_draw_engine_set_tex_patch); a known prompt texture
 * gets its icon redrawn as a key cap with the first key the live layout binds to that button. The layout is
 * this file's s_layout, the one handed to cellPad (settings.ini key.* lines, then any rebind on the key pages),
 * copied whole under a version: a rebind or a changed "prompts" choice changes pcmenu_prompts_gen, and the
 * engine then uploads the cached prompt textures again. */
extern "C" void rsx_draw_engine_set_tex_patch(int (*patch)(uint32_t, uint32_t, uint32_t, uint32_t, uint8_t*,
                                                            uint32_t, uint32_t, int),
                                              uint32_t (*gen)(void));
enum { PCPR_MODE_KEYBOARD, PCPR_MODE_CONTROLLER, PCPR_MODE_AUTO };
static volatile int s_prompts_mode;          /* PCPR_MODE_* */
static volatile uint32_t s_layout_ver = 1;   /* bumped on every layout change */
static pad_kb_layout s_prompt_layout[2];     /* double buffer: the engine thread reads [s_layout_ver & 1] */

static int pcmenu_prompts_mode_of(const char* v)
{
    if (v && (pcs_ieq(v, "controller") || pcs_ieq(v, "pad"))) return PCPR_MODE_CONTROLLER;
    if (v && pcs_ieq(v, "auto")) return PCPR_MODE_AUTO;
    return PCPR_MODE_KEYBOARD;
}

static int pcmenu_prompts_keys(void)
{
    const int m = s_prompts_mode;
    if (m == PCPR_MODE_CONTROLLER) return 0;
#ifdef _WIN32
    if (m == PCPR_MODE_AUTO && pad_host_device_present()) return 0;
#endif
    return 1;
}

static uint32_t pcmenu_prompts_gen(void)
{
    return pcmenu_prompts_keys() ? (s_layout_ver << 1) | 1u : 0u;
}

static int pcmenu_prompts_patch(uint32_t fmt, uint32_t w, uint32_t h, uint32_t level, uint8_t* data,
                                uint32_t row_bytes, uint32_t rows, int probe)
{
    (void)rows;
    static int s_idx = -1;   /* the probe's answer, for the levels that follow (one engine thread) */
    const pad_kb_layout* l = &s_prompt_layout[s_layout_ver & 1u];
    if (probe) {
        s_idx = pcpr_find(fmt, w, h, data, row_bytes);
        if (s_idx < 0) return 0;
        char t[16];
        const int on = pcmenu_prompts_keys() && pcpr_button_label(l, k_pcpr_icons[s_idx].button, t, sizeof t);
        static uint32_t logs;
        if (logs < 64) {
            logs++;
            fprintf(stderr, "[prompts] %s %ux%u: %s%s\n", k_pcpr_icons[s_idx].name, w, h, on ? "key " : "original icon",
                    on ? (t[0] == 1 ? "Left" : t[0] == 2 ? "Right" : t) : "");
        }
        return on ? 1 : 2;
    }
    if (s_idx < 0 || !pcpr_fmt_bc3(fmt)) return 0;
    char t[16];
    if (!pcpr_button_label(l, k_pcpr_icons[s_idx].button, t, sizeof t)) return 0;
    return pcpr_patch_bc3(data, w, h, row_bytes, (int)level, &k_pcpr_icons[s_idx], t) > 0;
}

static void pcmenu_apply_layout(void)
{
#ifdef _WIN32
    pad_keyboard_set_layout(&s_layout);
#endif
    const uint32_t v = s_layout_ver + 1u;
    s_prompt_layout[v & 1u] = s_layout;   /* the buffer the engine is not reading */
    s_layout_ver = v;
}

static uint32_t pcmenu_text(int k, const char* t)
{
    const uint32_t ea = PCMENU_TEXT + 128u * (uint32_t)k;
    size_t n = strlen(t);
    if (n > 127) n = 127;
    memcpy(vm_base + ea, t, n);
    vm_base[ea + n] = 0;
    return ea;
}

/* A key row's capture, once the keyboard has an answer. Called whenever a row's
 * text is asked for (every frame while the page is up). */
static void pcmenu_keys_pump(void)
{
    if (s_cap_act < 0) return;
#ifdef _WIN32
    const int r = pad_keyboard_capture_poll();
#else
    const int r = -1;
#endif
    if (r == 0) return;
    const int act = s_cap_act;
    s_cap_act = -1;
    char a[24];
    if (r < 0) { fprintf(stderr, "[pc-menu] key.%s: cancelled\n", k_pck_actions[act].key); return; }
    const int lost = pck_bind(&s_layout, act, r);
    char v[64];
    pck_format_keys(&s_layout, act, v, sizeof v);
    fprintf(stderr, "[pc-menu] key.%s = %s (%s)%s%s\n", k_pck_actions[act].key, v, pck_vk_name(r, a, sizeof a),
            lost >= 0 ? ", taken from key." : "", lost >= 0 ? k_pck_actions[lost].key : "");
    pcmenu_apply_layout();
    pcmenu_save();
}

/* A choice made on the page: kept, written, and put into effect now when the
 * setting allows it (the MSPR_PATCH code patches ask mspr_patch_on each time). */
static void pcmenu_step(int row, int dir)
{
    const int was = s_pcs.idx[row];
    if (pcs_step(&s_pcs, row, dir) == was) return;
    const pcs_def* d = &k_pcs_defs[row];
    if (!d->env && !d->restart) {
        static const struct { const char* name; uint32_t bit; } bits[] = {
            { "60fps", 1u }, { "vfps", 2u }, { "drs", 4u }, { "mblur", 8u } };
        for (const auto& b : bits) {
            if (!strcmp(d->values[was], b.name)) mspr_patch_set(b.bit, 0);
            if (!strcmp(d->values[s_pcs.idx[row]], b.name)) mspr_patch_set(b.bit, 1);
        }
    }
    if (d->env && !strncmp(d->env, "PAD_WHEEL", 9)) {
        /* wheel choices take effect at once: the variable (also at the default choice) and a re-read in cellPad */
#ifdef _WIN32
        _putenv_s(d->env, d->values[s_pcs.idx[row]]);
        pad_wheel_reload();
#endif
    }
    if (!strcmp(d->key, "prompts")) {   /* at once: the engine re-uploads the prompt textures (pcmenu_prompts_gen) */
#ifdef _WIN32
        _putenv_s(d->env, d->values[s_pcs.idx[row]]);
#endif
        s_prompts_mode = pcmenu_prompts_mode_of(d->values[s_pcs.idx[row]]);
    }
    pcmenu_save();
    const char* why = pcmenu_avail(d->key, s_pcs.idx[row]);
    fprintf(stderr, "[pc-menu] %s = %s%s%s\n", d->key, d->labels[s_pcs.idx[row]], why ? " - not applied: " : "", why ? why : "");
}

static void pcmenu_call(int k, ppu_context* ctx)
{
    char t[128];
    if (k < PCF_ROWS_END) {
        const int row = k / PCF_PER_ROW, kind = k % PCF_PER_ROW;
        const int is_key = row >= PCS_COUNT, act = row - PCS_COUNT;
        if (kind == PCF_VALUE) pcmenu_keys_pump();
        switch (kind) {
        case PCF_NAME:
            /* a row hidden by pcs_row_hidden (Shadows with Fidelity Enhanced): blank, and its info says why */
            ctx->gpr[3] = pcmenu_text(k, is_key ? k_pck_actions[act].name
                                                : pcs_row_hidden(&s_pcs, row) ? "" : k_pcs_defs[row].name);
            return;
        case PCF_VALUE:
            if (is_key) {
                if (s_cap_act == act) snprintf(t, sizeof t, "Press a key...");
                else pck_format_keys(&s_layout, act, t, sizeof t);
            } else if (pcs_row_hidden(&s_pcs, row)) {
                t[0] = 0;
            } else {
                const pcs_def* d = &k_pcs_defs[row];
                const char* why = pcmenu_avail(d->key, s_pcs.idx[row]);
                /* a row with no effect at this Fidelity (Volumetric Fog with Original) shows that, the choice kept */
                if (!why && pcs_row_unused(&s_pcs, row)) why = pcs_unused_why(row);
                if (why) snprintf(t, sizeof t, "%s (%s)", d->labels[s_pcs.idx[row]], why);
                else snprintf(t, sizeof t, "%s", d->labels[s_pcs.idx[row]]);
            }
            ctx->gpr[3] = pcmenu_text(k, t);
            return;
        case PCF_INFO:
            if (is_key)
                snprintf(t, sizeof t, "%s Accept, then press a key. Left/Right: default.", k_pck_actions[act].info);
            else if (pcs_row_hidden(&s_pcs, row))
                snprintf(t, sizeof t, "%s", "Hidden: Fidelity is Enhanced. Set Fidelity to Original to show this row.");
            else
                snprintf(t, sizeof t, "%s%s", k_pcs_defs[row].info,
                         k_pcs_defs[row].restart && s_pcs.idx[row] != s_pcs_boot.idx[row] ? " Restart the game to apply." : "");
            ctx->gpr[3] = pcmenu_text(k, t);
            return;
        case PCF_NEXT:
        case PCF_PREV:
            if (!is_key) { if (!pcs_row_hidden(&s_pcs, row)) pcmenu_step(row, kind == PCF_NEXT ? 1 : -1); }
            else if (s_cap_act < 0 && !pck_is_default(&s_layout, act)) {
                pck_reset(&s_layout, act);
                fprintf(stderr, "[pc-menu] key.%s = default\n", k_pck_actions[act].key);
                pcmenu_apply_layout();
                pcmenu_save();
            }
            return;
        case PCF_KEY:
            if (is_key && s_cap_act < 0) {
                s_cap_act = act;
#ifdef _WIN32
                pad_keyboard_capture_begin();
#endif
                fprintf(stderr, "[pc-menu] key.%s: waiting for a key\n", k_pck_actions[act].key);
            }
            return;
        }
    }
    if (k >= PCF_LAN) {   /* the LAN play screen: text functions return a string, bool functions a flag */
        const int r = lanmenu_call(k - PCF_LAN, t, sizeof t);
        if (lm_sig(k - PCF_LAN) == LM_SIG_TEXT) ctx->gpr[3] = pcmenu_text(k, t);
        else ctx->gpr[3] = (uint64_t)(r != 0);
        return;
    }
    if (k >= PCF_HUB_LABEL && k < PCF_HUB_INFO) { ctx->gpr[3] = pcmenu_text(k, k_pcp_pages[k - PCF_HUB_LABEL].label); return; }
    if (k >= PCF_HUB_INFO && k < PCF_TITLE) { ctx->gpr[3] = pcmenu_text(k, k_pcp_pages[k - PCF_HUB_INFO].info); return; }
    if (k >= PCF_TITLE && k < PCF_MENU_LABEL) {
        const int p = k - PCF_TITLE;
        ctx->gpr[3] = pcmenu_text(k, p == 0 ? "PC Settings" : k_pcp_pages[p - 1].title);
        return;
    }
    switch (k) {
    case PCF_MENU_LABEL: ctx->gpr[3] = pcmenu_text(k, "PC SETTINGS"); return;
    case PCF_MENU_INFO:  ctx->gpr[3] = pcmenu_text(k, "Display, upscaling, graphics and key options of the PC version."); return;
    case PCF_SAVE:       pcmenu_save(); return;
    }
}

template <int K> static void pcmenu_entry(ppu_context* ctx) { pcmenu_call(K, ctx); }
template <int... K> static void pcmenu_register(std::integer_sequence<int, K...>)
{
    static const pcmenu_fn fns[] = { pcmenu_entry<K>... };
    for (int k = 0; k < (int)(sizeof fns / sizeof fns[0]); k++) {
        const uint32_t code = PCMENU_CODE + 4u * (uint32_t)k, opd = PCMENU_OPD + 8u * (uint32_t)k;
        vm_write32(PCMENU_FUNCTOR + 8u * (uint32_t)k, 0);
        vm_write32(PCMENU_FUNCTOR + 8u * (uint32_t)k + 4u, opd);
        vm_write32(opd, code);
        vm_write32(opd + 4u, PCMENU_TOC);
        ppu_register_function(code, fns[k]);
    }
}

/* The number at the end of a function name (one or two digits), or -1. */
static int pcmenu_num(const char* s)
{
    if (s[0] < '0' || s[0] > '9') return -1;
    if (!s[1]) return s[0] - '0';
    if (s[1] < '0' || s[1] > '9' || s[2]) return -1;
    return (s[0] - '0') * 10 + (s[1] - '0');
}

/* The function and signature a name stands for, or -1. */
static int pcmenu_find(const char* n, uint32_t* sig)
{
    if (!strcmp(n, "PcMenuLabel")) { *sig = PCMENU_SIG_TEXT; return PCF_MENU_LABEL; }
    if (!strcmp(n, "PcMenuInfo"))  { *sig = PCMENU_SIG_TEXT; return PCF_MENU_INFO; }
    if (!strcmp(n, "PcSave"))      { *sig = PCMENU_SIG_VOID; return PCF_SAVE; }
    {   /* Lan*: the LAN play screen */
        int ls;
        const int f = lm_find(n, &ls);
        if (f >= 0) { *sig = (uint32_t)ls; return PCF_LAN + f; }
    }
    struct { const char* p; int base, count; } pg[] = {
        { "PcHubLabel", PCF_HUB_LABEL, PCP_COUNT }, { "PcHubInfo", PCF_HUB_INFO, PCP_COUNT },
        { "PcTitle", PCF_TITLE, PCP_COUNT + 1 } };
    for (const auto& g : pg) {
        const size_t l = strlen(g.p);
        if (strncmp(n, g.p, l)) continue;
        const int i = pcmenu_num(n + l);
        if (i < 0 || i >= g.count) return -1;
        *sig = PCMENU_SIG_TEXT;
        return g.base + i;
    }
    for (int kind = 0; kind < PCF_PER_ROW; kind++) {
        const size_t l = strlen(k_pcf_kind[kind]);
        if (strncmp(n, k_pcf_kind[kind], l)) continue;
        const int row = pcmenu_num(n + l);
        if (row < 0 || row >= PCP_ROWS) return -1;
        *sig = (kind == PCF_NEXT || kind == PCF_PREV || kind == PCF_KEY) ? PCMENU_SIG_VOID : PCMENU_SIG_TEXT;
        return row * PCF_PER_ROW + kind;
    }
    return -1;
}

/* The lookup's result for a name it has no function for: the page's. */
static void pcmenu_answer(ppu_context* ctx, uint32_t out, uint32_t name)
{
    if (!s_ready || vm_read32(out + 4) != PCMENU_MISS) return;
    char n[24];
    size_t i = 0;
    for (; i < sizeof n - 1 && vm_base[name + i]; i++) n[i] = (char)vm_base[name + i];
    n[i] = 0;
    uint32_t sig;
    /* Pc* (the PC Settings pages) and Lan* (the LAN screen, lan_menu.h): the only names this answers */
    const int k = (n[0] == 'P' && n[1] == 'c') || (n[0] == 'L' && n[1] == 'a' && n[2] == 'n') ? pcmenu_find(n, &sig) : -1;
    if (k < 0) return;
    vm_write32(out, PCMENU_FUNCTOR + 8u * (uint32_t)k);
    vm_write32(out + 4, sig);
    (void)ctx;
}

/* The page loader's resource load, r5 = the page path: a page the game has and the overlay replaces
 * (gui/options.gui: the Options page with PC SETTINGS; gui/wreckreation.gui: the Wreckreation page whose
 * ONLINE item opens the LAN screen) is read from its overlay copy (same length, one letter changed:
 * optionz, wreckreatioz), the path restored after. The overlay never shadows a disc file, hence the alias. */
static const struct { const char path[24]; unsigned at; char orig; } k_pcmenu_alias[] = {
    { "gui/options.gui", 10, 's' },
    { "gui/wreckreation.gui", 15, 'n' },
};
static int s_alias_on[2];   /* the overlay has the alias copy */

static int pcmenu_alias_begin(uint32_t p)
{
    static int s_logged;
    for (size_t k = 0; k < sizeof k_pcmenu_alias / sizeof k_pcmenu_alias[0]; k++) {
        const size_t n = strlen(k_pcmenu_alias[k].path) + 1;
        if (!s_alias_on[k] || memcmp(vm_base + p, k_pcmenu_alias[k].path, n) != 0) continue;
        vm_base[p + k_pcmenu_alias[k].at] = 'z';
        if (s_logged++ < 8) fprintf(stderr, "[pc-menu] page %s: overlay copy\n", k_pcmenu_alias[k].path);
        return (int)k + 1;   /* for pcmenu_alias_end */
    }
    return 0;
}

static void pcmenu_alias_end(uint32_t p, int alias)
{
    vm_base[p + k_pcmenu_alias[alias - 1].at] = k_pcmenu_alias[alias - 1].orig;
}

#ifndef PORT_V103
/* 1.02: func_00594C10(out, mgr, name), with the page's functions found when the
 * game has none of that name; the page loader's call 0x001F5DA8 goes through the
 * trampoline 0x00752C98 to the loader 0x00536A30. */
extern "C" void pcmenu_lookup(ppu_context* ctx)
{
    const uint32_t out = (uint32_t)ctx->gpr[3], name = (uint32_t)ctx->gpr[5];
    func_00594C10(ctx);
    pcmenu_drain(ctx);
    pcmenu_answer(ctx, out, name);
}

extern "C" void pcmenu_page_load(ppu_context* ctx)
{
    const uint32_t p = (uint32_t)ctx->gpr[5];
    const int alias = pcmenu_alias_begin(p);
    func_00752C98(ctx);   /* a tail branch to the loader 0x00536A30 */
    pcmenu_drain(ctx);
    if (alias) pcmenu_alias_end(p, alias);
}
#else
/* 1.03 (PARTIAL: matched by code shape, not yet run; generated/analysis/pcmenu/
 * tools/pcmenu_lifted_103.py makes the edits): the lookup is func_005604C8
 * (callers 0x00561DA4, 0x00564214), the resource load is func_00503718, reached
 * by the trampoline func_0071C408, whose g_trampoline_fn the script points here. */
extern "C" void pcmenu_lookup(ppu_context* ctx)
{
    const uint32_t out = (uint32_t)ctx->gpr[3], name = (uint32_t)ctx->gpr[5];
    func_005604C8(ctx);
    pcmenu_drain(ctx);
    pcmenu_answer(ctx, out, name);
}

extern "C" void pcmenu_load_sync(void* v)
{
    ppu_context* ctx = (ppu_context*)v;
    static int s_seen;
    const uint32_t p = (uint32_t)ctx->gpr[5];
    if (s_seen < 24 && !memcmp(vm_base + p, "gui/options", 11)) {
        s_seen++;
        fprintf(stderr, "[pc-menu] resource load: %s\n", (const char*)(vm_base + p));
    }
    const int alias = pcmenu_alias_begin(p);
    func_00503718(ctx);
    pcmenu_drain(ctx);
    if (alias) pcmenu_alias_end(p, alias);
}
#endif

static void pcmenu_exe_dir(char* out, size_t cap, const char* argv0)
{
    snprintf(out, cap, "%s", argv0);
#ifdef _WIN32
    GetModuleFileNameA(NULL, out, (DWORD)cap);
#endif
    for (char* p = out; *p; p++) if (*p == '\\') *p = '/';
    char* s = strrchr(out, '/');
    if (s) *s = 0; else snprintf(out, cap, ".");
}

static const char* pcmenu_getenv(const char* n) { return getenv(n); }
static void pcmenu_setenv(const char* n, const char* v)
{
#ifdef _WIN32
    _putenv_s(n, v);
#else
    setenv(n, v, 1);
#endif
    fprintf(stderr, "[pc-menu] settings.ini: %s=%s\n", n, v);
}

/* The DXC compiler the ray-traced shadows need: RSX_RT_DXC, else dxc/dxc.exe or
 * dxc.exe beside the executable (the launcher puts it there), else on PATH. */
static void pcmenu_find_dxc(void)
{
    char p[1100];
    const char* e = getenv("RSX_RT_DXC");
    if (e && *e) { s_dxc_ok = pcmenu_exists(e); return; }
    s_dxc_ok = 0;
    static const char* const rel[] = { "dxc/dxc.exe", "dxc.exe" };
    for (const char* r : rel) {
        snprintf(p, sizeof p, "%s/%s", s_dir, r);
        if (pcmenu_exists(p)) {
#ifdef _WIN32
            _putenv_s("RSX_RT_DXC", p);
#else
            setenv("RSX_RT_DXC", p, 1);
#endif
            s_dxc_ok = 1;
            return;
        }
    }
#ifdef _WIN32
    char found[MAX_PATH];
    if (SearchPathA(NULL, "dxc.exe", NULL, sizeof found, found, NULL)) s_dxc_ok = 1;   /* the backend runs "dxc.exe" */
#endif
}

/* Does settings.ini own this variable (a motorstorm.cfg line for it is ignored)? main.cpp. */
extern "C" int pcmenu_owns_env(const char* name)
{
    return pcs_owns_env(&s_pcs, name);
}

/* Start, before motorstorm.cfg and the port's defaults are read: settings.ini
 * into the environment, the key layout to the pad code, and the overlay folder
 * if there is one. */
extern "C" void pcmenu_boot(const char* argv0)
{
    char text[8192];
    pcmenu_exe_dir(s_dir, sizeof s_dir, argv0);
    snprintf(s_ini, sizeof s_ini, "%s/settings.ini", s_dir);
    pcs_defaults(&s_pcs);
    s_layout = pad_kb_layout_default();
    pcw_cfg_default(&s_wcfg);
    pcmenu_find_dxc();
    if (FILE* f = fopen(s_ini, "rb")) {
        const size_t n = fread(text, 1, sizeof text - 1, f);
        fclose(f);
        text[n] = 0;
        pcs_parse(&s_pcs, text);
        s_unlock_vehicles = pcs_unlock_vehicles(text);
        s_unlock_tracks = pcs_unlock_tracks(text);
        s_screens = pcs_screens(text);
        s_audio_thread = pcs_audio_thread(text);
        s_thread_place = pcs_thread_place(text);
        pcs_player_name(text, s_player);
        const int nk = pck_parse(&s_layout, text);
        pcw_parse(&s_wcfg, text);
#ifdef _WIN32
        pad_wheel_set_ini(text);
#endif
        const int mspr_env = getenv("MSPR_PATCH") != NULL;   /* a set variable wins over audiothread = Off */
        pcs_apply(&s_pcs, s_dir, pcmenu_getenv, pcmenu_setenv, pcmenu_avail);
        if (s_thread_place && !getenv("PS3_CPU_PLACEMENT")) {   /* CPU Thread Placement Auto (main.cpp main_core_setup) */
            pcmenu_setenv("PS3_CPU_PLACEMENT", "auto");
            fprintf(stderr, "[pc-menu] CPU thread placement: auto\n");
        }
        if (!s_audio_thread && !mspr_env) {   /* Audio thread Off: the patch list without audiothread */
            char spec[256];
            const char* cur = getenv("MSPR_PATCH");
            snprintf(spec, sizeof spec, "%s", cur ? cur : PCS_MSPR_DEFAULT);
            pcs_mspr_drop(spec, sizeof spec, "audiothread");
            pcmenu_setenv("MSPR_PATCH", spec);
            fprintf(stderr, "[pc-menu] audio thread: off (MSPR_PATCH=%s)\n", spec);
        }
        if (nk) fprintf(stderr, "[pc-menu] settings.ini: %d key binding(s)\n", nk);
    }
    {   /* Cheats: MSPR_UNLOCK_VEHICLES (alias MSPR_UNLOCK_ALL) and MSPR_UNLOCK_TRACKS; a set variable wins */
        int v = pcs_env_switch(getenv("MSPR_UNLOCK_VEHICLES"));
        if (v < 0) v = pcs_env_switch(getenv("MSPR_UNLOCK_ALL"));
        if (v >= 0) s_unlock_vehicles = v;
        const int t = pcs_env_switch(getenv("MSPR_UNLOCK_TRACKS"));
        if (t >= 0) s_unlock_tracks = t;
        if (s_unlock_vehicles) fprintf(stderr, "[pc-menu] unlock all vehicles: on\n");
        if (s_unlock_tracks) fprintf(stderr, "[pc-menu] unlock all tracks: on\n");
    }
    {   /* Screens: PS3RECOMP_VK_SPAN for the Vulkan window (rsx_multiscreen.h); a set variable wins */
        const char* span = pcs_screens_env(s_screens);
        if (span && !getenv("PS3RECOMP_VK_SPAN")) pcmenu_setenv("PS3RECOMP_VK_SPAN", span);
        if (span) fprintf(stderr, "[pc-menu] screens: %s (PS3RECOMP_VK_SPAN=%s)\n", k_pcs_screens[s_screens - 1],
                          getenv("PS3RECOMP_VK_SPAN"));
    }
    if (s_player[0]) {   /* Player name: the NP online ID and the system user name, unless set (pcs_player_env) */
        pcs_player_env(s_player, pcmenu_getenv, pcmenu_setenv);
        fprintf(stderr, "[pc-menu] player name: %s (PS3_NP_ONLINE_ID=%s, PS3_USER_NAME=%s)\n", s_player,
                getenv("PS3_NP_ONLINE_ID"), getenv("PS3_USER_NAME"));
    }
    pcmenu_apply_layout();
    /* Button prompts: MSPR_PROMPTS (set by the file's "prompts" line unless the environment had it), Keyboard by default */
    s_prompts_mode = pcmenu_prompts_mode_of(getenv("MSPR_PROMPTS"));
    rsx_draw_engine_set_tex_patch(pcmenu_prompts_patch, pcmenu_prompts_gen);
    fprintf(stderr, "[prompts] mode %s\n", s_prompts_mode == PCPR_MODE_CONTROLLER ? "controller" :
            s_prompts_mode == PCPR_MODE_AUTO ? "auto" : "keyboard");
    {   /* Lighting: Enhanced (RSX_LIGHTING=1) brings its parts along unless each is set: the classic AO
         * (GTAO still smears the sky) and screen-space shadows overlapping the map's end. The sun shadows are
         * the world-fixed tiles in both lightings (RSX_SHADOW_TILES=1 from k_defaults; =0 only for testing).
         * The ground toe defaults on inside the scene pass itself. */
        const char* l = getenv("RSX_LIGHTING");
        if (l && *l == '1') {
            /* Effects Quality Light/Minimal (RSX_FX_QUALITY >= 1, settings.ini, loaded before this) takes the AO out:
             * the bundle's own AO choice must not put it back (Kfq1: AO stayed on) */
            const char* q = getenv("RSX_FX_QUALITY");
            const char* ao = q && atoi(q) >= 1 ? "0" : "old";
            const char* const k[][2] = {
                { "RSX_FX_AO", ao }, { "RSX_FX_SSSHADOW_FAR", "450" },
            };
            for (const auto& kv : k) if (!getenv(kv[0])) pcmenu_setenv(kv[0], kv[1]);
        }
    }
    s_pcs_boot = s_pcs;
    struct stat st;
    char ov[1100];
    if (!getenv("PS3_VFS_OVERLAY")) {
        snprintf(ov, sizeof ov, "%s/pcmenu", s_dir);
        if (stat(ov, &st) == 0) pcmenu_setenv("PS3_VFS_OVERLAY", ov);
    }
    const char* o = getenv("PS3_VFS_OVERLAY");
    snprintf(ov, sizeof ov, "%s/gui/optionz.gui", o ? o : "");
    s_alias = o && *o && stat(ov, &st) == 0;
    s_alias_on[0] = s_alias;
    snprintf(ov, sizeof ov, "%s/gui/wreckreatioz.gui", o ? o : "");
    s_alias_on[1] = o && *o && stat(ov, &st) == 0;
}

/* After the ELF is loaded: the guest functors and their host functions. */
extern "C" void pcmenu_init(void)
{
    pcmenu_register(std::make_integer_sequence<int, PCF_COUNT>{});
    s_ready = 1;
    fprintf(stderr, "[pc-menu] %d functions at 0x%08X, options page %s, dxc %s\n", PCF_COUNT, PCMENU_EA,
            s_alias ? "from the overlay" : "original", s_dxc_ok ? "found" : "missing");
}

/* The label a row is running with: read back from its variable (pcs_apply set it from settings.ini, and a variable
 * that was already set won over the file), or from MSPR_PATCH for the patch rows; a row whose variable is unset runs
 * at its default, which is the boot choice. A variable value no choice has is shown as "<value> (<variable>)". */
static const char* pcmenu_bench_label(int i, char* buf, size_t cap)
{
    const pcs_def* d = &k_pcs_defs[i];
    if (d->env) {
        const char* v = getenv(d->env);
        if (v) {
            for (int j = 0; j < d->count; j++)
                if (d->folder ? (!*v) == (!*d->values[j]) : !strcmp(v, d->values[j])) return d->labels[j];
            snprintf(buf, cap, "%s (%s)", v, d->env);
            return buf;
        }
    } else if (const char* mp = getenv("MSPR_PATCH")) {   /* a patch row: its patch name in the list, or none */
        auto has = [mp](const char* name) {
            const size_t n = strlen(name);
            for (const char* p = mp; (p = strstr(p, name)) != NULL; p += n)
                if ((p == mp || p[-1] == ',') && (p[n] == 0 || p[n] == ',')) return true;
            return false;
        };
        for (int j = 0; j < d->count; j++) if (*d->values[j] && has(d->values[j])) return d->labels[j];
        for (int j = 0; j < d->count; j++) if (!*d->values[j]) return d->labels[j];
    }
    return d->labels[s_pcs_boot.idx[i]];
}

/* The benchmark result's "settings" (bench_run.h): every page row as the game runs it, as a JSON array of
 * {"key", "name", "value", "applied"} (applied false: kept in the file but not used with this Fidelity, as the page
 * shows it), then the launcher's Screens. Rows the page hides (pcs_row_hidden) are left out. Returns the length. */
extern "C" int pcmenu_bench_settings(char* out, size_t cap)
{
    char lbuf[160];
    size_t w = 0;
    auto put = [&](const char* t) { const size_t n = strlen(t); if (w + n + 1 < cap) { memcpy(out + w, t, n); w += n; } };
    auto str = [&](const char* t) {   /* a JSON string: the labels are plain text; quotes and backslashes escaped */
        put("\"");
        for (; t && *t; t++) {
            const bool q = *t == '"' || *t == '\\';
            const char c[3] = { q ? '\\' : *t, q ? *t : '\0', '\0' };
            if ((unsigned char)*t >= 0x20) put(c);
        }
        put("\"");
    };
    if (!cap) return 0;
    put("[");
    int first = 1;
    for (int i = 0; i < PCS_COUNT; i++) {
        if (pcs_row_hidden(&s_pcs_boot, i)) continue;
        put(first ? "\n    { \"key\": " : ",\n    { \"key\": ");
        first = 0;
        str(k_pcs_defs[i].key);
        put(", \"name\": "); str(k_pcs_defs[i].name);
        put(", \"value\": "); str(pcmenu_bench_label(i, lbuf, sizeof lbuf));
        put(pcs_row_unused(&s_pcs_boot, i) ? ", \"applied\": false }" : ", \"applied\": true }");
    }
    put(first ? "\n    { \"key\": \"screens\", \"name\": \"Screens\", \"value\": " : ",\n    { \"key\": \"screens\", \"name\": \"Screens\", \"value\": ");
    str(k_pcs_screens[(s_screens >= 1 && s_screens <= 3 ? s_screens : 1) - 1]);
    put(", \"applied\": true }\n  ]");
    out[w] = 0;
    return (int)w;
}
