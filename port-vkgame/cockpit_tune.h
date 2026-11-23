/* MSPR_COCKPIT_TUNE: the per-vehicle cockpit camera table behind the in-game adjuster (main.cpp
 * mspr_cock_*). Host logic only, no guest memory: the values, the key steps, the readout and the
 * cockpit_positions.json read/write. Tested by tests/test_cockpit_tune.c.
 *
 * A vehicle's entry is the cockpit camera (CAMERA 3 FORWARD of its *_camz.txt) relative to its bonnet
 * camera (CAMERA 2 FORWARD): x (the seat, absolute, +x left), dy, dz (world units, +y up, +z forward), pitch and
 * yaw (degrees added to the bonnet camera's) and focal (absolute, as in the camera list). The same keys and meaning as
 * generated/analysis/cockpit/tools/make_cockpit_overlay.py --positions. Our own tuning numbers. */
#ifndef COCKPIT_TUNE_H
#define COCKPIT_TUNE_H

#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CT_MAX 192
#define CT_NAME 32

typedef struct { char veh[CT_NAME]; float x, dy, dz, pitch, yaw, focal; int saved; } ct_entry;
typedef struct { ct_entry e[CT_MAX]; int n; } ct_table;

/* Free-flight control (no mouse): while keys are held the camera moves at a speed, scaled by the frame time.
 * Speeds per second; Shift x5, Num0 x0.2. */
#define CT_SPEED_POS 1.0f     /* units per second */
#define CT_SPEED_ANG 30.0f    /* degrees per second (pitch, yaw) */
#define CT_SPEED_FOCAL 4.0f   /* focal per second */
#define CT_FAST 5.0f
#define CT_FINE 0.2f
#define CT_FOCAL_MIN 2.0f
#define CT_FOCAL_MAX 40.0f
#define CT_POS_LIM 50.0f      /* x / dy / dz stay within +-50 units, pitch and yaw within +-180 degrees */
#define CT_ANG_LIM 180.0f

/* what is held this frame: each -1, 0 or +1 */
typedef struct { int fwd, left, up, pitch, yaw, focal; } ct_input;
/* the vehicle name the loader hands the parser ("atv22", or "atv22_LV01" for a livery list): the part
 * before "_LV", lower-case letters/digits/_ only. 0 = not a name. */
static inline int ct_norm_name(const char* in, char* out, size_t n)
{
    size_t k = 0;
    for (; in[k] && k + 1 < n; k++) {
        if (in[k] == '_' && in[k + 1] == 'L' && in[k + 2] == 'V') break;
        const unsigned char c = (unsigned char)in[k];
        if (!(isalnum(c) || c == '_')) return 0;
        out[k] = (char)tolower(c);
    }
    out[k] = 0;
    return k > 0 && (in[k] == 0 || in[k] == '_');
}

static inline ct_entry* ct_find(ct_table* t, const char* veh, int create)
{
    for (int i = 0; i < t->n; i++)
        if (!strcmp(t->e[i].veh, veh)) return &t->e[i];
    if (!create || t->n >= CT_MAX || strlen(veh) >= CT_NAME) return NULL;
    ct_entry* e = &t->e[t->n++];
    memset(e, 0, sizeof *e);
    strcpy(e->veh, veh);
    return e;
}

static inline float ct_clampf(float v, float lim) { return v > lim ? lim : v < -lim ? -lim : v; }

/* Move the camera for `dt` seconds of input `in` at speed multiplier `mul`. Forward and strafe follow the camera's
 * heading: `yaw_abs` is its absolute yaw in degrees in the vehicle frame (the bonnet yaw + e->yaw; the game's lists
 * have yaw -90 for the view to the left, +90 to the right, 179 to the rear). In-game test: with the stored z taken as
 * forward, I moved the view backwards, so the view direction in (x, z) is (-sin yaw, -cos yaw) and strafe-left is
 * (cos yaw, -sin yaw). Up / down are straight along the stored y. The motion stays level (pitch does not tilt it). Returns 1 if anything changed. */
static inline int ct_fly(ct_entry* e, const ct_input* in, float yaw_abs, float dt, float mul)
{
    if (!(dt > 0)) return 0;
    if (dt > 0.1f) dt = 0.1f;   /* a stalled frame does not jump the camera */
    const float d = CT_SPEED_POS * mul * dt, r = yaw_abs * 3.14159265f / 180.0f;
    const float s = sinf(r), c = cosf(r);
    const float f = (float)in->fwd * d, l = (float)in->left * d;
    if (!in->fwd && !in->left && !in->up && !in->pitch && !in->yaw && !in->focal) return 0;
    e->x += f * -s + l * c;       /* the stored +z points BACK from the seat (measured: I moved the view backwards when it */
    e->dz += -f * c + -l * s;     /* added +z), so forward is -z; x as before (strafe was right) */
    e->dy += (float)in->up * d;
    e->pitch += (float)in->pitch * CT_SPEED_ANG * mul * dt;
    e->yaw += (float)in->yaw * CT_SPEED_ANG * mul * dt;
    e->focal += (float)in->focal * CT_SPEED_FOCAL * mul * dt;
    e->x = ct_clampf(e->x, CT_POS_LIM); e->dy = ct_clampf(e->dy, CT_POS_LIM); e->dz = ct_clampf(e->dz, CT_POS_LIM);
    e->pitch = ct_clampf(e->pitch, CT_ANG_LIM); e->yaw = ct_clampf(e->yaw, CT_ANG_LIM);
    if (e->focal < CT_FOCAL_MIN) e->focal = CT_FOCAL_MIN;
    if (e->focal > CT_FOCAL_MAX) e->focal = CT_FOCAL_MAX;
    return 1;
}

/* pitch_base: the bonnet camera's pitch; the readout shows the delta and the pitch the game uses */
static inline void ct_readout(const ct_entry* e, float pitch_base, char* out, size_t n)
{
    snprintf(out, n, "cockpit %s: x %.2f dy %.2f dz %.2f pitch %+.1f (=%.1f) yaw %.1f focal %.1f%s | I/K fwd/back J/L strafe"
             " T/G (Num+/-) up/down ,/. pitch N/M turn U/O focal Shift fast Num0 slow F2 save", e->veh, e->x, e->dy, e->dz,
             e->pitch, pitch_base + e->pitch, e->yaw, e->focal, e->saved ? " (saved)" : " *unsaved*");
}

/* cockpit_positions.json: {"<veh>": {"x": 0, "dy": 0.35, "dz": -0.9, "pitch": -6, "yaw": 0, "focal": 8.5}, ...}. A small reader for
 * exactly that shape (what ct_write_json and the generator's file use): names without escapes, numbers. Entries
 * read are marked saved; a vehicle missing a field keeps 0 for it. Returns the entries read, -1 if malformed. */
static inline const char* ct_ws(const char* p) { while (*p && isspace((unsigned char)*p)) p++; return p; }

static inline const char* ct_str(const char* p, char* out, size_t n)
{
    if (*p != '"') return NULL;
    size_t k = 0;
    for (p++; *p && *p != '"'; p++) {
        if (*p == '\\' || k + 1 >= n) return NULL;
        out[k++] = *p;
    }
    if (*p != '"') return NULL;
    out[k] = 0;
    return p + 1;
}

static inline int ct_parse_json(ct_table* t, const char* s)
{
    int got = 0;
    const char* p = ct_ws(s);
    if (*p++ != '{') return -1;
    p = ct_ws(p);
    if (*p == '}') return 0;
    for (;;) {
        char veh[CT_NAME], key[16];
        p = ct_str(ct_ws(p), veh, sizeof veh);
        if (!p) return -1;
        p = ct_ws(p);
        if (*p++ != ':') return -1;
        p = ct_ws(p);
        if (*p++ != '{') return -1;
        ct_entry v;
        memset(&v, 0, sizeof v);
        p = ct_ws(p);
        if (*p != '}') for (;;) {
            p = ct_str(ct_ws(p), key, sizeof key);
            if (!p) return -1;
            p = ct_ws(p);
            if (*p++ != ':') return -1;
            char* end;
            const float f = strtof(ct_ws(p), &end);
            if (end == ct_ws(p)) return -1;
            p = ct_ws(end);
            if (!strcmp(key, "x")) v.x = f;
            else if (!strcmp(key, "dy")) v.dy = f;
            else if (!strcmp(key, "dz")) v.dz = f;
            else if (!strcmp(key, "pitch")) v.pitch = f;
            else if (!strcmp(key, "yaw")) v.yaw = f;
            else if (!strcmp(key, "focal")) v.focal = f;
            if (*p == ',') { p++; continue; }
            break;
        }
        if (*p++ != '}') return -1;
        ct_entry* e = ct_find(t, veh, 1);
        if (e) { v.saved = 1; strcpy(v.veh, e->veh); *e = v; got++; }
        p = ct_ws(p);
        if (*p == ',') { p++; continue; }
        if (*p == '}') return got;
        return -1;
    }
}

/* every entry, sorted by name; returns the bytes needed (snprintf-like) */
static inline size_t ct_write_json(const ct_table* t, char* out, size_t n)
{
    int idx[CT_MAX];
    for (int i = 0; i < t->n; i++) idx[i] = i;
    for (int i = 1; i < t->n; i++)
        for (int j = i; j > 0 && strcmp(t->e[idx[j - 1]].veh, t->e[idx[j]].veh) > 0; j--) {
            const int k = idx[j]; idx[j] = idx[j - 1]; idx[j - 1] = k;
        }
    size_t w = 0;
#define CT_PUT(...) do { const int _r = snprintf(out ? out + (w < n ? w : n) : NULL, out && w < n ? n - w : 0, __VA_ARGS__); \
                         if (_r > 0) w += (size_t)_r; } while (0)
    CT_PUT("{");
    for (int i = 0; i < t->n; i++) {
        const ct_entry* e = &t->e[idx[i]];
        CT_PUT("%s\n  \"%s\": {\"x\": %.3f, \"dy\": %.3f, \"dz\": %.3f, \"pitch\": %.2f, \"yaw\": %.2f, \"focal\": %.2f}", i ? "," : "", e->veh,
               e->x, e->dy, e->dz, e->pitch, e->yaw, e->focal);
    }
    CT_PUT("\n}\n");
#undef CT_PUT
    return w;
}

#endif
