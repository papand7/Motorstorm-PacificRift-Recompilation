/* PC settings: the choices of the "PC Settings" options pages, kept in
 * settings.ini beside the executable (port main.cpp, pc_menu.cpp). The file
 * format and the rules are written down in docs/SETTINGS.md.
 *
 * Each setting stands for a switch the port already has: an environment
 * variable it reads (PS3RECOMP_VK_FULLSCREEN, RSX_RES_SCALE, RSX_FSR, ...) or
 * an MSPR_PATCH patch name. At start the file's choices are turned into those
 * variables, so the rest of the port is unchanged:
 *   - a variable the process was started with wins over the file;
 *   - a setting at its default sets nothing, so without a file (or with every
 *     setting at its default) the port runs exactly as before. The exception is
 *     `always` settings (the upscaler mode: FSR 3.1 is the default here, FSR 1
 *     the port's own), which set their variable at the default too, unless the
 *     choice's feature is missing (then the port's own FSR 1 applies);
 *   - the MSPR_PATCH settings together give the patch list; at their defaults
 *     it is the port's default list (PCS_MSPR_DEFAULT);
 *   - a key the file names owns its variable: a line for the same variable in
 *     motorstorm.cfg is ignored (pcs_owns_env), so one file decides;
 *   - a choice whose feature is missing here (no texture pack, no FSR 3 DLL)
 *     is not applied and the page shows why (pcs_avail_fn).
 *
 * The file is "key = choice" lines, the choice by its label ("1080p") or its
 * value ("1.5"); unknown keys and choices are ignored. The key bindings
 * ("key.accelerate = W") are pc_keys.h's. Header-only, no process state: the
 * environment and the file text are parameters, so the rules are tested
 * without them (port-vkgame/tests/test_pc_settings.c). */
#ifndef PC_SETTINGS_H
#define PC_SETTINGS_H

#include <stdio.h>
#include <string.h>
#include "mspr_patch.h"

#define PCS_MAX_CHOICES 7
/* The MSPR_PATCH list the port runs with when nothing says otherwise
 * (main.cpp k_defaults). */
#define PCS_MSPR_DEFAULT "drs,vfps,audiothread"
#define PCS_MSPR_BASE "audiothread"   /* in every list the settings give: not a player choice */
/* vfps is also in every list, at the Frame Rate row's place (after drs): it scales the game to real time,
 * which is what makes the 30, 45 and 60 FPS choices (PS3_SIM_PACE_HZ) correct. */

typedef struct pcs_def {
    const char* key;                         /* settings.ini key */
    const char* name;                        /* shown on the page */
    const char* env;                         /* variable it sets; NULL: an MSPR_PATCH name */
    int count, def;                          /* choices, default choice */
    int restart;                             /* 1: takes effect at the next start */
    int folder;                              /* 1: the value is a folder beside the executable */
    const char* labels[PCS_MAX_CHOICES];
    const char* values[PCS_MAX_CHOICES];     /* variable value, or patch name ("" = none) */
    const char* info;                        /* the line under the page */
    int always;                              /* 1: the variable is set even at the default choice (the port's
                                              * own default differs, e.g. FSR 3.1 vs the port's FSR 1) */
    const char* env2;                        /* a second variable the same choice sets (NULL: none); its own
                                              * "a set variable wins" test, ownership and default rule */
    const char* values2[PCS_MAX_CHOICES];
    const char* env3;                        /* a third one, the same rules (Shadow Quality, Effects Density) */
    const char* values3[PCS_MAX_CHOICES];
} pcs_def;

/* In page order (pc_pages.h): Display, Upscaling, Graphics. The patch settings
 * are in the order of the list they give (drs, then the frame rate patch, then
 * mblur). */
static const pcs_def k_pcs_defs[] = {
    /* Display */
    { "display", "Display Mode", "PS3RECOMP_VK_FULLSCREEN", 2, 0, 1, 0,
      { "Windowed", "Fullscreen" }, { "0", "1" },
      "Play in a window or fullscreen." },
    { "resolution", "Resolution", "RSX_RES_SCALE", 5, 1, 1, 0,
      { "480p", "720p", "1080p", "1440p", "2160p" }, { "0.667", "1", "1.5", "2", "3" },
      "The resolution the game draws at. 720p is the original; 480p for very slow PCs, with the upscaler." },
    /* Off is the default: the port's default present is non-blocking (main.cpp k_defaults
     * RSX_PRESENT_INTERVAL=0, tear-free mailbox mode); On sets 1, the blocking FIFO present. */
    { "vsync", "V-Sync", "RSX_PRESENT_INTERVAL", 2, 1, 1, 0,
      { "On", "Off" }, { "1", "0" },
      "On waits for the display between frames; Off is tear-free and keeps 60 FPS steady." },
    { "dynres", "Dynamic Resolution", NULL, 2, 1, 0, 0,
      { "On", "Off" }, { "", "drs" },
      "Let the game lower its resolution when it falls under 30 fps." },
    /* PS3_SIM_PACE_HZ is the pacing rate; the camera fix MSPR_CAM_MODE=1 is on above 30 (the shake is off
     * there). vfps is in every patch list (PCS_MSPR_BASE). Old files: "Variable" and "60fps" read as 60 FPS
     * (pcs_choice). */
    { "framerate", "Frame Rate", "PS3_SIM_PACE_HZ", 7, 0, 1, 0,
      { "30 FPS", "45 FPS", "60 FPS", "80 FPS", "120 FPS", "144 FPS", "180 FPS" }, { "30", "45", "60", "80", "120", "144", "180" },
      "30 FPS is the original speed. Above 30 is experimental: camera, shadow and vehicle glitches.", 1,
      "MSPR_CAM_MODE", { "0", "1", "1", "1", "1", "1", "1" } },
    /* Upscaling */
    /* Default FSR 1, the launcher's default (launcher/electron/settings.js); still always set */
    { "fsrmode", "Upscaler", "RSX_FSR_MODE", 2, 0, 1, 0,
      { "FSR 1", "FSR 3.1" }, { "1", "3" },
      "FSR 1 is spatial and the safest. FSR 3.1 is temporal and sharper. Used when Quality is not Off.", 1 },
    { "fsr", "Upscaler Quality", "RSX_FSR", 5, 0, 1, 0,
      { "Off", "Ultra Quality", "Quality", "Balanced", "Performance" },
      { "off", "ultra", "quality", "balanced", "performance" },
      "Draw smaller and upscale. Off draws at the Resolution above." },
    { "hdr", "HDR Output", "RSX_HDR", 2, 0, 1, 0,
      { "Off", "On" }, { "0", "1" },
      "HDR10 output. Needs an HDR display with HDR on in Windows." },
    /* Graphics */
    { "motionblur", "Motion Blur", NULL, 2, 0, 0, 0,
      { "On", "Off" }, { "", "mblur" },
      "The game's motion blur." },
    { "aniso", "Texture Filtering", "PS3_ANISO", 5, 0, 1, 0,
      { "Original", "2x", "4x", "8x", "16x" }, { "0", "2", "4", "8", "16" },
      "Sharper textures at an angle. Original uses the game's own filtering." },
    { "textures", "HD Textures", "RSX_TEX_PACK", 2, 0, 1, 1,
      { "Off", "On" }, { "", "textures/pack" },
      "Use the texture pack made in the launcher (textures/pack beside the game)." },
    { "pbr", "PBR Materials", "RSX_TEX_PBR", 2, 0, 1, 0,
      { "Off", "On" }, { "", "1" },
      "Material maps from the texture pack. Needs HD Textures and a pack made with PBR maps." },
    /* No "rtshadow" row: ray-traced shadows (RSX_RT_SHADOW=1) cost a lot of frame time and do not work with
     * Enhanced lighting, so they are not offered; the variable still works when set in the environment. */
    /* MSPR_LOD_BIAS is added to every viewportquality.xml lodBias (lower keeps finer models farther out),
     * MSPR_CULL_SCALE multiplies the screen-size cull thresholds (lower culls less); main.cpp mspr_dist_f,
     * sites patched by vksync/tools/dist_patch_lifted.py (1.00 addresses). */
    /* Low (for small GPUs and handhelds): the other way, coarser models sooner and more culling (bias +1, cull x1.5);
     * more pop-in, less CPU and GPU time. */
    /* Lowest (the draw distance choice for small GPUs, Performance work 2026-11-27): bias +2, cull x2.5 and the game's
     * shadow range 200 -> 120 m (MSPR_SHADOW_RANGE, main.cpp mspr_dist_f kind 0): scenery and trees go sooner. */
    { "lod", "Level of Detail", "MSPR_LOD_BIAS", 5, 2, 1, 0,
      { "Lowest", "Low", "Original", "High", "Ultra" }, { "2", "1", "", "-1", "-2" },
      "Lowest/Low: shorter draw distance, more pop-in, faster. High/Ultra: detail farther out, slower.", 0,
      "MSPR_CULL_SCALE", { "2.5", "1.5", "", "0.5", "0.25" },
      "MSPR_SHADOW_RANGE", { "120", "", "", "", "" } },
    /* Enhanced: the lit-program rewrite, tone curve, ground toe, AO and screen-space shadows (RSX_LIGHTING,
     * rsx_light.h / rsx_vk_scenefx.h); pc_menu.cpp adds the world-fixed shadow tiles it uses. */
    { "lighting", "Fidelity", "RSX_LIGHTING", 2, 1, 1, 0,
      { "Original", "Enhanced" }, { "0", "1" },
      "Enhanced (experimental): new lighting, AO and tone mapping. Original is the game's own lighting.", 1,
      NULL, { NULL } },
    /* The game's button prompts as key caps (pc_prompts.h, pc_menu.cpp): Keyboard always, Controller never (the
     * original icons), Auto while no gamepad or wheel is connected. The page applies a change at once. */
    { "prompts", "Button Prompts", "MSPR_PROMPTS", 3, 0, 0, 0,
      { "Keyboard", "Controller", "Auto" }, { "keyboard", "controller", "auto" },
      "Keys or controller buttons in prompts. Auto: keys unless a gamepad or wheel is connected." },
    /* Off skips the game's own shadow casters (rsx_shadow_off.h, MSPR_NO_SHADOWS, original lighting only). Shown
     * only with Fidelity Original (pcs_row_hidden); the choice is kept while it is hidden. Reflections are not
     * changed by this row. It is the last cell of the Graphics page, so a hidden row leaves the grid's last cell
     * empty and no gap between the other rows (pc_pages.h). */
    { "shadows", "Shadows", "MSPR_NO_SHADOWS", 2, 0, 0, 0,
      { "On", "Off" }, { "0", "1" },
      "Off skips the game's own shadows; reflections stay. Original look only (hidden with Enhanced)." },
    /* The driver's-eye camera (MSPR_CAM_COCKPIT) is not a setting: it is on by default (main.cpp k_defaults). */
    /* Racing Wheel (libs/input pad_wheel.h and pad_wheel_dinput.h read these variables; the page applies a
     * change at once, so none is a restart setting). The detailed keys (axes, pedal calibration, buttons) are
     * wheel.* lines, not choices: docs/SETTINGS.md. Keep the page at eight rows (pc_pages.h): the guest text
     * buffers (pc_menu.cpp PCF_COUNT) have room for 272 entries, six texts a row. */
    { "wheelmode", "Racing Wheel", "PAD_WHEEL", 3, 0, 0, 0,
      { "Auto", "Any Device", "Off" }, { "auto", "any", "off" },
      "Auto: Thrustmaster and Logitech wheels. Any Device: any joystick. A gamepad keeps working." },
    { "wheelrange", "Wheel Steering Range", "PAD_WHEEL_RANGE", 7, 2, 0, 0,
      { "Device", "180 deg", "270 deg", "360 deg", "540 deg", "720 deg", "900 deg" },
      { "device", "180", "270", "360", "540", "720", "900" },
      "Wheel rotation, lock to lock, for full steering. Device: the wheel's whole range." },
    { "wheeldeadzone", "Wheel Deadzone", "PAD_WHEEL_DEADZONE", 6, 1, 0, 0,
      { "0%", "1%", "2%", "3%", "5%", "8%" }, { "0", "1", "2", "3", "5", "8" },
      "Steering around the centre that is ignored." },
    { "wheelcurve", "Wheel Steering Curve", "PAD_WHEEL_CURVE", 5, 0, 0, 0,
      { "Linear", "Soft", "Softer", "Sharp", "Sharper" }, { "0", "1", "2", "3", "4" },
      "Soft is gentler near the centre; Sharp reacts sooner." },
    { "wheelpedals", "Wheel Pedals", "PAD_WHEEL_PEDALS", 3, 0, 0, 0,
      { "Profile", "Separate", "Combined" }, { "profile", "separate", "combined" },
      "Combined: throttle and brake share one axis (the driver's combined-pedals mode)." },
    { "wheelpedaldir", "Pedal Direction", "PAD_WHEEL_PEDAL_DIR", 3, 0, 0, 0,
      { "Auto", "Normal", "Inverted" }, { "auto", "normal", "inverted" },
      "Auto reads the released pedals at start. Set it if a pedal is stuck on or off." },
    { "wheelffb", "Wheel Force Feedback", "PAD_WHEEL_FFB", 4, 0, 0, 0,
      { "Off", "Centering", "Rumble", "Both" }, { "off", "center", "rumble", "both" },
      "Centering spring and the game's rumble; no physics forces. Takes the wheel exclusively." },
    { "wheelffbstrength", "Force Feedback Strength", "PAD_WHEEL_FFB_STRENGTH", 5, 2, 0, 0,
      { "20%", "40%", "60%", "80%", "100%" }, { "20", "40", "60", "80", "100" },
      "Overall strength of the effects above." },
    /* Effects page (pc_pages.h). The fog is the scene pass's volumetric fog (rsx_vk_scenefx.h, RSX_FX_VOLFOG=1, off
     * by default, read once at start: a restart setting). Enhanced only: with Fidelity Original the row stays on the
     * page with "(needs Fidelity Enhanced)" and sets nothing (pcs_row_unused). */
    { "volfog", "Volumetric Fog", "RSX_FX_VOLFOG", 2, 0, 1, 0,
      { "Off", "On" }, { "0", "1" },
      "Light shafts and haze in the air. Enhanced only; more GPU time.", 0, NULL, { NULL } },
    /* Wheel ruts in the scene pass (rsx_draw_engine.c / rsx_ruts.h, RSX_FX_RUTS=1, off by default, read once at start):
     * the wheels press ruts where the game lays its own tyre tracks. Enhanced only, as the fog (pcs_row_unused). */
    { "ruts", "Wheel Ruts", "RSX_FX_RUTS", 2, 0, 1, 0,
      { "Off", "On" }, { "0", "1" },
      "Wheels press ruts into the ground where the game lays its tracks. Enhanced only.", 0, NULL, { NULL } },
    /* The Enhanced scene pass's cost (rsx_vk_scenefx.h vk_fx_quality, RSX_FX_QUALITY): Light drops the ambient
     * occlusion and the light shafts, Minimal also the screen-space sun shadows. Enhanced only (pcs_row_unused). */
    { "fxquality", "Effects Quality", "RSX_FX_QUALITY", 3, 0, 1, 0,
      { "Full", "Light", "Minimal" }, { "0", "1", "2" },
      "Light: no ambient occlusion or light shafts. Minimal: also no sun contact shadows. For small GPUs.", 0, NULL, { NULL } },
    /* Extra wheel particles over the scene pass (rsx_particles.h, RSX_FX_PARTICLES 0/1/2, read once at start): dust, mud
     * clods and spray where the wheels touch the game's tracked ground. An added layer; the game's own particles stay.
     * High is the default and `always` set (the port's own default, with the variable unset, is off), so Off sets 0.
     * Enhanced only (pcs_row_unused): with Fidelity Original nothing is set and the port draws none. */
    { "particles", "Extra Particles", "RSX_FX_PARTICLES", 3, 2, 1, 0,
      { "Off", "Low", "High" }, { "0", "1", "2" },
      "Dust, mud clods and spray from the wheels. Enhanced only; a little GPU time.", 1, NULL, { NULL } },
    /* Performance page (pc_pages.h): opt-in savings for small GPUs and handhelds; every row's default is today's look
     * and sets nothing. Restart settings: each is read at start (or at the game's own data reads). The measured effect
     * of each is in generated/analysis/lowend_opts/RESULTS.md. */
    /* The world-fixed sun shadow map (rsx_shadow_tiles.h): its size in host texels (RSX_SHADOW_TILES_RES, 6144 by default:
     * 768 m of 0.125 m texels; 4096 = 512 m, 3072 = 384 m, past the game's own 300 m fade), the soft edge taps
     * (RSX_SHADOW_TILES_PCF 0 = one compare) and the stored layer (RSX_SHADOW_TILES_STATIC=0, 288 MB of video memory). */
    { "shadowq", "Shadow Quality", "RSX_SHADOW_TILES_RES", 3, 0, 1, 0,
      { "High", "Medium", "Low" }, { "", "4096", "3072" },
      "Sun shadow map size and soft edges. Low: hard edges, no stored layer (288 MB less video memory).", 0,
      "RSX_SHADOW_TILES_PCF", { "", "", "0" },
      "RSX_SHADOW_TILES_STATIC", { "", "", "0" } },
    /* RSX_TEX_DROP_MIPS (rsx_draw_engine.c): mipmapped game textures of 128 texels or more are made without their 1 or 2
     * finest levels (a quarter or a sixteenth of the memory). Texture pack replacements are not changed. */
    { "texq", "Texture Quality", "RSX_TEX_DROP_MIPS", 3, 0, 1, 0,
      { "Full", "Half", "Quarter" }, { "", "1", "2" },
      "Half or Quarter: blurrier game textures, much less video memory. HD Textures are not changed." },
    /* The game's own particle levels (lowend_patch_lifted.py, main.cpp mspr_vq_f / mspr_gopt): MSPR_FX_SCALE multiplies
     * viewportquality.xml's Particles LodScale and EmissionRate, ScreenRush ParticleLimitScalar and the options'
     * particleEmissionScale (0.6 and 0.35 are about the game's own 2- and 4-player values); Low and Minimal also turn
     * the screen rain layer off (MSPR_FX_RAIN2=0, off in the game's 2- and 4-player entries), Minimal the wheel dust and
     * mud (MSPR_FX_WHEEL=0, enableWheelParticles). */
    { "fxdensity", "Effects Density", "MSPR_FX_SCALE", 4, 0, 1, 0,
      { "Full", "Reduced", "Low", "Minimal" }, { "", "0.6", "0.35", "0.3" },
      "Fewer of the game's particles: smoke, dust, spray. Minimal: no dust or mud from the wheels.", 0,
      "MSPR_FX_RAIN2", { "", "", "0", "0" },
      "MSPR_FX_WHEEL", { "", "", "", "0" } },
    /* The other cars' and wrecks' LOD (main.cpp mspr_dist_f, viewportquality.xml group "vehicle"; the player's car is the
     * "player" group, unchanged): Reduced is the game's own 2-player bias (+1.5), Low its 4-player one (+2.7) and cull. */
    { "oppdetail", "Opponent Detail", "MSPR_VEH_LOD_BIAS", 3, 0, 1, 0,
      { "Full", "Reduced", "Low" }, { "", "1.5", "2.7" },
      "Simpler models for the other cars and wrecks sooner (the game's split-screen values).", 0,
      "MSPR_VEH_CULL_SCALE", { "", "", "1.33" } },
    /* viewportquality.xml ViewportScaling variableScalingMin (0.5 for one player), the lowest scale the game's own
     * dynamic resolution may go to (MSPR_DRS_MIN, main.cpp mspr_vq_f). Used only with Dynamic Resolution On
     * (pcs_row_unused). */
    { "drsfloor", "Dyn. Resolution Floor", "MSPR_DRS_MIN", 3, 0, 1, 0,
      { "50% (Original)", "40%", "33%" }, { "", "0.4", "0.33" },
      "How low Dynamic Resolution may go when the frame rate falls. Needs Dynamic Resolution On." },
    /* viewportquality.xml Debris Enabled (MSPR_DEBRIS=0, main.cpp mspr_vq_b): the loose parts that fly off wrecks (bolts,
     * panels: the game's debris_ms2 set), simulated by the physics. Off in the game's own 4-player entry. A gameplay-feel
     * change: no parts to hit or drive over. */
    { "debris", "Wreck Debris", "MSPR_DEBRIS", 2, 0, 1, 0,
      { "On", "Off" }, { "", "0" },
      "Off: no loose parts fly off wrecks; less physics work. Changes gameplay feel." },
    /* ms2_GameOptions.cfg enableBoostBlur (MSPR_BOOST_BLUR=0, main.cpp mspr_gopt): the radial blur while boosting. The
     * motion blur itself is the Graphics page's Motion Blur row. */
    { "boostblur", "Boost Blur", "MSPR_BOOST_BLUR", 2, 0, 1, 0,
      { "On", "Off" }, { "", "0" },
      "The game's radial blur while boosting. The motion blur is on the Graphics page." },
    /* Frame Generation (ps3recomp-vkgame libs/video rsx_vk_framegen.h, RSX_FRAMEGEN, read at start): one generated frame
     * between two real ones, so twice the frames are shown (30 -> 60). Light: the port's own motion-vector pass (cheap,
     * more ghosting); On: AMD FSR 3.1 frame generation (amd_fidelityfx_framegeneration_vk.dll beside the exe, pcmenu_avail).
     * Both need the FSR 3.1 upscaler (Upscaler FSR 3.1 with a Quality, not Off) and HDR off; without them the renderer
     * presents as before and logs why (the row is still written: nothing else is changed for it). Off sets nothing.
     * The real frame is shown half a real frame later (about 17 ms at 30 FPS). */
    { "framegen", "Frame Generation", "RSX_FRAMEGEN", 3, 0, 1, 0,
      { "Off", "Light", "On" }, { "", "light", "1" },
      "Twice the frames shown, ~17 ms more delay. Needs FSR 3.1 upscaling on, HDR off. On: AMD FSR 3." },
};
#define PCS_COUNT ((int)(sizeof k_pcs_defs / sizeof k_pcs_defs[0]))

typedef struct pcs_state {
    int idx[PCS_COUNT];
    unsigned long long explicit_mask;   /* bit i: the file named setting i (pcs_parse); 64 settings at most */
} pcs_state;

static inline void pcs_defaults(pcs_state* s)
{
    for (int i = 0; i < PCS_COUNT; i++) s->idx[i] = k_pcs_defs[i].def;
    s->explicit_mask = 0;
}

static inline int pcs_find(const char* key)
{
    for (int i = 0; i < PCS_COUNT; i++)
        if (!strcmp(k_pcs_defs[i].key, key)) return i;
    return -1;
}

/* The Shadows row is hidden (no page row text, not applied) unless Fidelity is Original. Its choice is kept
 * in s, so switching Fidelity back to Original restores it. Other rows: 0. */
static inline int pcs_row_hidden(const pcs_state* s, int i)
{
    if (strcmp(k_pcs_defs[i].key, "shadows")) return 0;
    const int lf = pcs_find("lighting");
    return lf >= 0 && s->idx[lf] != 0;
}

/* The Volumetric Fog, Wheel Ruts, Effects Quality and Extra Particles rows are shown always but have no effect unless Fidelity
 * is Enhanced, and Dyn. Resolution Floor none unless Dynamic Resolution is On: the choice is kept and not applied
 * (pcs_apply), and the page says why (pcs_unused_why). Other rows: 0. */
static inline int pcs_row_unused(const pcs_state* s, int i)
{
    if (!strcmp(k_pcs_defs[i].key, "drsfloor")) {   /* the floor only matters while the game scales (Dynamic Resolution On) */
        const int df = pcs_find("dynres");
        return df >= 0 && s->idx[df] != 0;
    }
    if (strcmp(k_pcs_defs[i].key, "volfog") && strcmp(k_pcs_defs[i].key, "ruts") && strcmp(k_pcs_defs[i].key, "fxquality") &&
        strcmp(k_pcs_defs[i].key, "particles"))
        return 0;
    const int lf = pcs_find("lighting");
    return lf >= 0 && s->idx[lf] != 1;
}

/* Why an unused row has no effect, as the page shows it after the value. */
static inline const char* pcs_unused_why(int i)
{
    return strcmp(k_pcs_defs[i].key, "drsfloor") ? "needs Fidelity Enhanced" : "needs Dynamic Resolution On";
}

static inline int pcs_ieq(const char* a, const char* b)
{
    for (; *a && *b; a++, b++) {
        char x = *a, y = *b;
        if (x >= 'A' && x <= 'Z') x += 32;
        if (y >= 'A' && y <= 'Z') y += 32;
        if (x != y) return 0;
    }
    return *a == *b;
}

/* The choice a text names (label or value, case-insensitive), or -1. */
static inline int pcs_choice(int i, const char* t)
{
    const pcs_def* d = &k_pcs_defs[i];
    for (int c = 0; c < d->count; c++)
        if (pcs_ieq(t, d->labels[c]) || (*d->values[c] && pcs_ieq(t, d->values[c]))) return c;
    /* the old frame rate file values: "Variable" and the "60fps" patch name now mean 60 FPS */
    if (!strcmp(d->key, "framerate") && (pcs_ieq(t, "Variable") || pcs_ieq(t, "60fps"))) return 2;
    return -1;
}

/* settings.ini text into s (which keeps its choice for anything not named);
 * returns the number of settings read. */
static inline int pcs_parse(pcs_state* s, const char* text)
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
        while (*v == ' ' || *v == '\t') v++;
        for (char* p = k + strlen(k); p > k && (p[-1] == ' ' || p[-1] == '\t'); ) *--p = 0;
        for (char* p = v + strlen(v); p > v && (p[-1] == ' ' || p[-1] == '\t' || p[-1] == '\r'); ) *--p = 0;
        const int i = pcs_find(k);
        const int c = i < 0 ? -1 : pcs_choice(i, v);
        if (c >= 0) { s->idx[i] = c; s->explicit_mask |= 1ull << i; got++; }
    }
    return got;
}

/* The file text for s; returns its length (truncated to n - 1). Every setting is
 * written, so after the first save the file names them all. */
static inline int pcs_format(const pcs_state* s, char* out, size_t n)
{
    int w = snprintf(out, n, "# MotorStorm PC settings (Options > PC Settings, or the launcher). A set environment variable wins.\n");
    for (int i = 0; i < PCS_COUNT && w >= 0 && (size_t)w < n; i++)
        w += snprintf(out + w, n - (size_t)w, "%s = %s\n", k_pcs_defs[i].key, k_pcs_defs[i].labels[s->idx[i]]);
    return w;
}

/* Choice c of setting i moved by dir (-1, +1), clamped like the game's own options. */
static inline int pcs_step(pcs_state* s, int i, int dir)
{
    int c = s->idx[i] + dir;
    if (c < 0) c = 0;
    if (c >= k_pcs_defs[i].count) c = k_pcs_defs[i].count - 1;
    s->idx[i] = c;
    return c;
}

/* The MSPR_PATCH list the settings give. */
static inline void pcs_mspr_spec(const pcs_state* s, char* out, size_t n)
{
    size_t w = 0;
    out[0] = 0;
    for (int i = 0; i < PCS_COUNT; i++) {
        const char* v = k_pcs_defs[i].values[s->idx[i]];
        if (!strcmp(k_pcs_defs[i].key, "framerate")) v = "vfps";
        else if (k_pcs_defs[i].env || !*v) continue;
        const int r = snprintf(out + w, n - w, "%s%s", w ? "," : "", v);
        if (r < 0 || (size_t)r >= n - w) break;
        w += (size_t)r;
    }
    snprintf(out + w, n - w, "%s%s", w ? "," : "", PCS_MSPR_BASE);
}

/* Does the file own variable name? True when it names a setting that sets it
 * (any of the patch settings for MSPR_PATCH), so a motorstorm.cfg line for the
 * same variable is to be ignored. */
static inline int pcs_owns_env(const pcs_state* s, const char* name)
{
    for (int i = 0; i < PCS_COUNT; i++) {
        if (!(s->explicit_mask & (1ull << i))) continue;
        const char* e = k_pcs_defs[i].env ? k_pcs_defs[i].env : "MSPR_PATCH";
        if (!strcmp(e, name)) return 1;
        if (k_pcs_defs[i].env2 && !strcmp(k_pcs_defs[i].env2, name)) return 1;
        if (k_pcs_defs[i].env3 && !strcmp(k_pcs_defs[i].env3, name)) return 1;
    }
    return 0;
}

typedef const char* (*pcs_get_fn)(const char* name);
typedef void (*pcs_set_fn)(const char* name, const char* value);
/* NULL when choice c of the setting named key can be used here; else why not (a
 * few words, shown on the page in place of the value). The choice can still be
 * selected and is kept in the file, but it is not applied. */
typedef const char* (*pcs_avail_fn)(const char* key, int choice);

/* Sets the variables for s through set, leaving alone any get reports as set,
 * any setting at its default (unless it is `always`), and any choice avail says
 * cannot be used here (avail may be NULL). base is the executable's folder for
 * folder values. Returns the number of variables set. */
static inline int pcs_apply(const pcs_state* s, const char* base, pcs_get_fn get, pcs_set_fn set, pcs_avail_fn avail)
{
    int done = 0;
    for (int i = 0; i < PCS_COUNT; i++) {
        const pcs_def* d = &k_pcs_defs[i];
        if (!d->env || (s->idx[i] == d->def && !d->always) || pcs_row_hidden(s, i) || pcs_row_unused(s, i)) continue;
        if (avail && avail(d->key, s->idx[i])) continue;
        if (d->env2 && !get(d->env2)) { set(d->env2, d->values2[s->idx[i]]); done++; }
        if (d->env3 && !get(d->env3)) { set(d->env3, d->values3[s->idx[i]]); done++; }
        if (get(d->env)) continue;
        const char* v = d->values[s->idx[i]];
        char path[1024];
        if (d->folder && *v) {
            snprintf(path, sizeof path, "%s/%s", base, v);
            v = path;
        }
        set(d->env, v);
        done++;
    }
    char spec[128];
    pcs_mspr_spec(s, spec, sizeof spec);
    if (!get("MSPR_PATCH") && strcmp(spec, PCS_MSPR_DEFAULT) != 0) {
        set("MSPR_PATCH", spec);
        done++;
    }
    return done;
}

/* The text the page shows for setting i: why it is missing, else the label of the choice. */
static inline const char* pcs_value_text(const pcs_state* s, int i, const char* missing)
{
    return missing ? missing : k_pcs_defs[i].labels[s->idx[i]];
}

/* The launcher's Cheats switches, "key = On|Off" lines that are not page rows (no key in k_pcs_defs), so
 * pcs_format does not write them: pcmenu_save appends each while it is on, and the in-game page keeps it.
 *   unlockvehicles  vehicle classes and tickets (the old key unlockall is read when it is absent)
 *   unlocktracks    tracks
 * pcs_ini_switch: the last line naming key wins; 1 for On (or 1), 0 for anything else, -1 if no line names it. */
static inline int pcs_ini_switch(const char* text, const char* key)
{
    const size_t kn = strlen(key);
    int on = -1;
    while (text && *text) {
        const char* e = strchr(text, '\n');
        size_t n = e ? (size_t)(e - text) : strlen(text);
        char line[96];
        if (n >= sizeof line) n = sizeof line - 1;
        memcpy(line, text, n);
        line[n] = 0;
        text = e ? e + 1 : NULL;
        char* p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '#' || *p == ';' || strncmp(p, key, kn) != 0) continue;
        p += kn;
        while (*p == ' ' || *p == '\t') p++;
        if (*p != '=') continue;
        p++;
        while (*p == ' ' || *p == '\t') p++;
        char* v = p + strlen(p);
        while (v > p && (v[-1] == ' ' || v[-1] == '\t' || v[-1] == '\r')) *--v = 0;
        on = (pcs_ieq(p, "On") || !strcmp(p, "1")) ? 1 : 0;
    }
    return on;
}

/* unlockvehicles, or the old unlockall when the file has no unlockvehicles line: 1 on, 0 off. */
static inline int pcs_unlock_vehicles(const char* text)
{
    int v = pcs_ini_switch(text, "unlockvehicles");
    if (v < 0) v = pcs_ini_switch(text, "unlockall");
    return v > 0;
}

/* unlocktracks: 1 on, 0 off. */
static inline int pcs_unlock_tracks(const char* text)
{
    return pcs_ini_switch(text, "unlocktracks") > 0;
}

/* Audio thread: "audiothread = On|Off" (launcher Performance; not a page row, the Performance page is full). On, the
 * default, keeps the audiothread patch (the game's audio update on its own guest thread, audio_thread.cpp) in the
 * MSPR_PATCH list; Off takes it out (pcs_mspr_drop). Written back by pcmenu_save while Off. 1 on, 0 off. */
static inline int pcs_audio_thread(const char* text)
{
    return pcs_ini_switch(text, "audiothread") != 0;
}

/* CPU Thread Placement: "threadplace = Auto|Off" (launcher Performance; not a page row). Auto sets PS3_CPU_PLACEMENT=auto
 * (cpu_placement.h: on a CPU with fast and slow cores, the main and render threads on the fast ones, background
 * threads on the slow ones); Off, the default, sets nothing. Written back by pcmenu_save while Auto. 1 Auto, 0 Off. */
static inline int pcs_thread_place(const char* text)
{
    int on = -1;
    while (text && *text) {
        const char* e = strchr(text, '\n');
        size_t n = e ? (size_t)(e - text) : strlen(text);
        char line[96];
        if (n >= sizeof line) n = sizeof line - 1;
        memcpy(line, text, n);
        line[n] = 0;
        text = e ? e + 1 : NULL;
        char* p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (strncmp(p, "threadplace", 11) != 0) continue;
        p += 11;
        while (*p == ' ' || *p == '\t') p++;
        if (*p++ != '=') continue;
        while (*p == ' ' || *p == '\t') p++;
        char* v = p + strlen(p);
        while (v > p && (v[-1] == ' ' || v[-1] == '\t' || v[-1] == '\r')) *--v = 0;
        if (pcs_ieq(p, "Auto") || pcs_ieq(p, "On") || !strcmp(p, "1")) on = 1;
        else if (pcs_ieq(p, "Off") || !strcmp(p, "0")) on = 0;
    }
    return on > 0;
}

/* spec (an MSPR_PATCH list, edited in place) without the patch name; "none" when nothing is left. */
static inline void pcs_mspr_drop(char* spec, size_t n, const char* name)
{
    char out[256];
    size_t w = 0;
    const size_t nl = strlen(name);
    out[0] = 0;
    for (const char* t = spec; *t;) {
        const char* e = strchr(t, ',');
        const size_t len = e ? (size_t)(e - t) : strlen(t);
        const int same = len >= nl && !strncmp(t, name, nl) && (len == nl || t[nl] == ':');
        if (len && !same && !(len == 4 && !strncmp(t, "none", 4)) && w + len + 2 < sizeof out) {
            if (w) out[w++] = ',';
            memcpy(out + w, t, len);
            w += len;
            out[w] = 0;
        }
        t = e ? e + 1 : t + len;
    }
    snprintf(spec, n, "%s", w ? out : "none");
}

/* A Cheats variable (MSPR_UNLOCK_VEHICLES, MSPR_UNLOCK_TRACKS, MSPR_UNLOCK_ALL): -1 unset or empty, else 1 for
 * 1/On/on, 0 otherwise. A set variable wins over settings.ini. */
static inline int pcs_env_switch(const char* v)
{
    if (!v || !*v) return -1;
    return (!strcmp(v, "1") || pcs_ieq(v, "On")) ? 1 : 0;
}

/* Screens: "screens = Single|Dual|Triple" (or 1|2|3), the game window over one, two or three monitors
 * (PS3RECOMP_VK_SPAN=2|3, libs/video rsx_multiscreen.h; restart). A launcher setting, not a page row: the
 * Display page is full (eight rows, pc_pages.h). Like the Cheats lines, pcmenu_save writes it back while it is
 * not Single, so the in-game page keeps it. The last line naming it with a known value wins; 1 without one. */
static const char* const k_pcs_screens[3] = { "Single", "Dual", "Triple" };

static inline int pcs_screens(const char* text)
{
    int n = 1;
    while (text && *text) {
        const char* e = strchr(text, '\n');
        size_t len = e ? (size_t)(e - text) : strlen(text);
        char line[96];
        if (len >= sizeof line) len = sizeof line - 1;
        memcpy(line, text, len);
        line[len] = 0;
        text = e ? e + 1 : NULL;
        char* p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '#' || *p == ';' || strncmp(p, "screens", 7) != 0) continue;
        p += 7;
        while (*p == ' ' || *p == '\t') p++;
        if (*p++ != '=') continue;
        while (*p == ' ' || *p == '\t') p++;
        char* v = p + strlen(p);
        while (v > p && (v[-1] == ' ' || v[-1] == '\t' || v[-1] == '\r')) *--v = 0;
        for (int i = 0; i < 3; i++)
            if (pcs_ieq(p, k_pcs_screens[i]) || (p[0] == '1' + i && !p[1])) n = i + 1;
    }
    return n;
}

/* The PS3RECOMP_VK_SPAN value for n screens: NULL for one (nothing is set). */
static inline const char* pcs_screens_env(int n)
{
    return n == 2 ? "2" : n == 3 ? "3" : NULL;
}

/* The first n characters of a are b, any case, and the next is not part of a longer key. */
static inline int pcs_ieq_n(const char* a, const char* b, size_t n)
{
    for (size_t i = 0; i < n; i++) {
        char x = a[i], y = b[i];
        if (x >= 'A' && x <= 'Z') x = (char)(x - 'A' + 'a');
        if (y >= 'A' && y <= 'Z') y = (char)(y - 'A' + 'a');
        if (!x || x != y) return 0;
    }
    return a[n] == ' ' || a[n] == '\t' || a[n] == '=';
}

/* Player name: "playername = <name>", the name other players see (a launcher setting, not a page row: the
 * page has choice rows only). The game took it from the PSN account; here it becomes PS3_NP_ONLINE_ID (sceNp
 * GetNpId / GetOnlineName, the LAN room server's member list, libs/network np_psnr.c) and PS3_USER_NAME (the
 * system user, libs/system cellUserInfo.c), each unless already set. A PSN online ID's rules: 3 to 16 letters,
 * digits, '-' or '_', starting with a letter (np_psnr.c clean_online_id; the launcher's settings.js checks the
 * same). The last line naming the key decides; an empty or invalid value means no name (today's defaults).
 * pcmenu_save writes it back while it is set, so the in-game page keeps it. */
#define PCS_NAME_MAX 16

static inline int pcs_name_valid(const char* s)
{
    int n = 0;
    if (!s) return 0;
    for (; s[n]; n++) {
        const char c = s[n];
        const int alpha = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
        if (n >= PCS_NAME_MAX || !(alpha || (c >= '0' && c <= '9') || c == '-' || c == '_')) return 0;
        if (n == 0 && !alpha) return 0;
    }
    return n >= 3;
}

/* The player name settings.ini gives into out ("" for none); 1 if there is one. */
static inline int pcs_player_name(const char* text, char out[PCS_NAME_MAX + 1])
{
    out[0] = 0;
    while (text && *text) {
        const char* e = strchr(text, '\n');
        size_t len = e ? (size_t)(e - text) : strlen(text);
        char line[96];
        if (len >= sizeof line) len = sizeof line - 1;
        memcpy(line, text, len);
        line[len] = 0;
        text = e ? e + 1 : NULL;
        char* p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '#' || *p == ';' || !pcs_ieq_n(p, "playername", 10)) continue;
        p += 10;
        while (*p == ' ' || *p == '\t') p++;
        if (*p++ != '=') continue;
        while (*p == ' ' || *p == '\t') p++;
        char* v = p + strlen(p);
        while (v > p && (v[-1] == ' ' || v[-1] == '\t' || v[-1] == '\r')) *--v = 0;
        if (pcs_name_valid(p)) snprintf(out, PCS_NAME_MAX + 1, "%s", p);
        else out[0] = 0;
    }
    return out[0] != 0;
}

/* The variables a player name gives: PS3_NP_ONLINE_ID and PS3_USER_NAME, each only if not already set (a set
 * variable wins, as for every setting). Nothing without a name. Returns how many were set. */
static inline int pcs_player_env(const char* name, pcs_get_fn get, pcs_set_fn set)
{
    static const char* const k_vars[2] = { "PS3_NP_ONLINE_ID", "PS3_USER_NAME" };
    int n = 0;
    if (!pcs_name_valid(name)) return 0;
    for (int i = 0; i < 2; i++) {
        const char* cur = get(k_vars[i]);
        if (cur && *cur) continue;
        set(k_vars[i], name);
        n++;
    }
    return n;
}

#endif
