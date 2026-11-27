/* bench_run.h: the launcher's Benchmark page, run by the game itself (MSPR_BENCH=fly|race, off by default).
 *
 * The game records each guest frame it presents (the time and the guest's flip count), finds the measured window
 * from its own events, computes the result, writes it as JSON (MSPR_BENCH_OUT) and quits. Only guest frames count:
 * a present whose flip count did not move (the same guest frame again) adds its time to the next frame and is not
 * a frame; a present after several flips counts each of them, splitting the interval evenly.
 *
 *   fly   the disc's own benchmark (configs/benchmark_happyJungle.cfg, booted through PS3_DEV_GUEST_STR): a scripted
 *         camera flight over Kanaloa Bay, then static "HotSpot" views. The window is the flight only: from the first
 *         frame with at least BENCH_SCENE_DRAWS guest draws (the world is on screen) to the first HotSpot label the
 *         game formats (mspr_bench_hotspot, a lift hook in func_00118508 / func_00118708).
 *   race  a 16-car race on Kanaloa Bay (configs/mspr_bench_race.cfg, written by the launcher from the player's disc),
 *         the player's car driven by the game's own AI (bench_ai.h). The game presses CROSS to skip the pre-race
 *         flyover (BENCH_SKIP_*), and the window is BENCH_RACE_FROM_MS .. BENCH_RACE_TO_MS after the race starts (the
 *         first read of the player's controls by the race code, callers BENCH_LR_RACE*: about the green light).
 *         That is the window of the developer reference generated/analysis/perf60/bench_race.py (race_entry
 *         +30 s .. +120 s; race_entry is the flyover's first frame, the green light is ~8.5 s later).
 *
 * Result: avg fps = guest frames / window time; min / max fps = the slowest / fastest whole second of the window
 * (guest frames in each 1 s step from the window's start; a partial last second is left out); 1 % and 0.1 % low =
 * 1000 / the mean of the slowest 1 % / 0.1 % frame times; P50/P95/P99 and the longest frame time (ms).
 * Pure functions, no process state: tests/test_bench_run.c. */
#ifndef BENCH_RUN_H
#define BENCH_RUN_H
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { BENCH_OFF = 0, BENCH_FLY = 1, BENCH_RACE = 2 };

#define BENCH_SCENE_DRAWS 200u              /* fly: a frame with the world on screen (as the runner's race_entry) */
#define BENCH_RACE_FROM_MS 21500.0          /* race: window from the race start ... */
#define BENCH_RACE_TO_MS 111500.0           /* ... to here (90 s) */
#define BENCH_SKIP_FIRST_MS 4000.0          /* race: CROSS this long after the flyover's first frame, */
#define BENCH_SKIP_SECOND_MS 7000.0         /* again here (as the reference), */
#define BENCH_SKIP_EVERY_MS 3000.0          /* then every 3 s until the race starts, */
#define BENCH_SKIP_UNTIL_MS 60000.0         /* at most this long */
#define BENCH_LR_SKIP 0x000327A8u           /* the flyover's "Press X to Skip" check (bench_ai.h BENCH_AI_LR_SKIP) */
#define BENCH_LR_RACE1 0x007DD0D4u          /* the race code's first reads of the player's controls */
#define BENCH_LR_RACE2 0x007DD10Cu
#define BENCH_LR_RACE3 0x007DD144u
#define BENCH_FLY_MIN_MS 10000.0            /* fly: a shorter flight is not the benchmark (an early label) */
#define BENCH_START_TIMEOUT_MS 240000.0     /* no window start this long after the first present: give up */
#define BENCH_FLY_TIMEOUT_MS 180000.0       /* fly: no HotSpot this long after the start: give up */

static inline int bench_mode_of(const char* e)
{
    if (!e) return BENCH_OFF;
    if (!strcmp(e, "fly")) return BENCH_FLY;
    if (!strcmp(e, "race")) return BENCH_RACE;
    return BENCH_OFF;
}
static inline const char* bench_mode_name(int m) { return m == BENCH_FLY ? "fly" : m == BENCH_RACE ? "race" : "off"; }

/* a race-code caller (the race has started) */
static inline int bench_is_race_lr(uint32_t lr)
{
    return lr == BENCH_LR_RACE1 || lr == BENCH_LR_RACE2 || lr == BENCH_LR_RACE3;
}

/* race: when press number n (0, 1, ...) is due, in ms after the flyover's first skip check */
static inline double bench_skip_at(unsigned n)
{
    return n == 0 ? BENCH_SKIP_FIRST_MS : BENCH_SKIP_SECOND_MS + BENCH_SKIP_EVERY_MS * (double)(n - 1);
}
/* race: should CROSS press number `presses` start now? flyover_ms = the first skip check (< 0: none yet),
 * race_ms = the race start (< 0: not yet), now_ms: one clock. No press once the race runs or after SKIP_UNTIL. */
static inline int bench_skip_due(double flyover_ms, double race_ms, unsigned presses, double now_ms)
{
    if (flyover_ms < 0.0 || race_ms >= 0.0) return 0;
    const double t = now_ms - flyover_ms;
    return t >= bench_skip_at(presses) && t <= BENCH_SKIP_UNTIL_MS;
}

typedef struct bench_result {
    int ok;
    uint32_t frames;                 /* guest frames in the window */
    double span_ms;                  /* window time between its first and last present */
    double avg, min, max, low1, low01;
    double p50, p95, p99, maxft;     /* frame times, ms */
    uint32_t seconds;                /* whole seconds the min / max were taken over */
} bench_result;

static int bench_cmp_d(const void* a, const void* b)
{
    const double x = *(const double*)a, y = *(const double*)b;
    return x < y ? -1 : x > y ? 1 : 0;
}

/* flips (guest frames) presented by time t: the flip count of the last present at or before t */
static inline uint32_t bench_flips_at(const double* t, const uint32_t* fl, uint32_t n, double at)
{
    uint32_t lo = 0, hi = n;   /* first index with t > at */
    while (lo < hi) { const uint32_t m = (lo + hi) / 2; if (t[m] <= at) lo = m + 1; else hi = m; }
    return lo ? fl[lo - 1] : (n ? fl[0] : 0);
}

/* The result over the presents (t[i] ms, fl[i] cumulative guest flips, i < n, t ascending) inside [w0, w1].
 * scratch: room for the window's frame times (at least the flips in the window). ok = 0 with fewer than 2 presents
 * or no guest frame in the window. */
static inline bench_result bench_compute(const double* t, const uint32_t* fl, uint32_t n, double w0, double w1,
                                         double* scratch, uint32_t scratch_n)
{
    bench_result r;
    memset(&r, 0, sizeof r);
    uint32_t i0 = 0;
    while (i0 < n && t[i0] < w0) i0++;
    uint32_t i1 = i0;
    while (i1 + 1 < n && t[i1 + 1] <= w1) i1++;
    if (i0 >= n || i1 <= i0 || t[i1] > w1) return r;
    uint32_t k = 0;
    double acc = 0.0;
    for (uint32_t i = i0 + 1; i <= i1; i++) {
        acc += t[i] - t[i - 1];
        const uint32_t df = fl[i] - fl[i - 1];
        if (!df) continue;                     /* the same guest frame presented again: not a frame */
        for (uint32_t j = 0; j < df && k < scratch_n; j++) scratch[k++] = acc / (double)df;
        acc = 0.0;
    }
    r.frames = fl[i1] - fl[i0];
    r.span_ms = t[i1] - t[i0];
    if (!r.frames || r.span_ms <= 0.0 || !k) return r;
    r.avg = (double)r.frames * 1000.0 / r.span_ms;
    /* whole seconds from the window's first present */
    r.min = 0.0; r.max = 0.0;
    for (uint32_t s = 0;; s++) {
        const double a = t[i0] + 1000.0 * s, b = a + 1000.0;
        if (b > t[i1]) break;
        const double f = (double)(bench_flips_at(t, fl, n, b) - bench_flips_at(t, fl, n, a));
        if (!r.seconds || f < r.min) r.min = f;
        if (!r.seconds || f > r.max) r.max = f;
        r.seconds++;
    }
    if (!r.seconds) { r.min = r.max = r.avg; }
    qsort(scratch, k, sizeof scratch[0], bench_cmp_d);
    const uint32_t k1 = (uint32_t)ceil(k * 0.01) ? (uint32_t)ceil(k * 0.01) : 1u;
    const uint32_t k01 = (uint32_t)ceil(k * 0.001) ? (uint32_t)ceil(k * 0.001) : 1u;
    double s1 = 0.0, s01 = 0.0;
    for (uint32_t j = 0; j < k1; j++) s1 += scratch[k - 1 - j];
    for (uint32_t j = 0; j < k01; j++) s01 += scratch[k - 1 - j];
    r.low1 = 1000.0 / (s1 / k1);
    r.low01 = 1000.0 / (s01 / k01);
#define BENCH_PCT(p) scratch[(uint32_t)fmin((double)(k - 1), fmax(0.0, ceil((p) / 100.0 * k) - 1.0))]
    r.p50 = BENCH_PCT(50.0); r.p95 = BENCH_PCT(95.0); r.p99 = BENCH_PCT(99.0);
#undef BENCH_PCT
    r.maxft = scratch[k - 1];
    r.ok = 1;
    return r;
}

/* s as a JSON string body (quotes and backslashes escaped, control characters dropped) into out */
static inline void bench_json_str(char* out, size_t cap, const char* s)
{
    size_t w = 0;
    for (; s && *s && w + 3 < cap; s++) {
        const unsigned char c = (unsigned char)*s;
        if (c == '"' || c == '\\') { out[w++] = '\\'; out[w++] = (char)c; }
        else if (c >= 0x20) out[w++] = (char)c;
    }
    if (cap) out[w < cap ? w : cap - 1] = 0;
}

/* The result file. hw: gpu (the Vulkan device the game rendered on), cpu (brand string), ram bytes. settings_json: a
 * JSON array (the game's settings as it applied them), or NULL. error: NULL when r is the result. */
typedef struct bench_info {
    const char* gpu;
    const char* cpu;
    unsigned long long ram;
    const char* settings_json;
    double window_from_ms, window_to_ms;   /* frame-log clock (ms since the first present) */
    const char* anchor;                    /* what the window starts from */
    unsigned pipelines;                    /* graphics pipelines the renderer built on demand inside the window ... */
    double pipelines_ms;                   /* ... and the time they took (shader compiles: a cold cache, a first run) */
} bench_info;

static inline int bench_write_json(FILE* f, int mode, const bench_result* r, const bench_info* in, const char* error)
{
    char gpu[256], cpu[256], err[512], anchor[128];
    bench_json_str(gpu, sizeof gpu, in && in->gpu ? in->gpu : "");
    bench_json_str(cpu, sizeof cpu, in && in->cpu ? in->cpu : "");
    bench_json_str(err, sizeof err, error ? error : "");
    bench_json_str(anchor, sizeof anchor, in && in->anchor ? in->anchor : "");
    const int ok = !error && r && r->ok;
    fprintf(f, "{\n  \"version\": 1,\n  \"benchmark\": \"%s\",\n  \"ok\": %s,\n", bench_mode_name(mode), ok ? "true" : "false");
    if (ok) fprintf(f, "  \"error\": null,\n");
    else fprintf(f, "  \"error\": \"%s\",\n", err[0] ? err : "no result");
    fprintf(f, "  \"gpu\": \"%s\",\n  \"cpu\": \"%s\",\n  \"ram_bytes\": %llu,\n", gpu, cpu, in ? in->ram : 0ull);
    if (ok) {
        fprintf(f, "  \"fps\": { \"min\": %.2f, \"max\": %.2f, \"avg\": %.2f, \"low1\": %.2f, \"low01\": %.2f },\n",
                r->min, r->max, r->avg, r->low1, r->low01);
        fprintf(f, "  \"frame_ms\": { \"p50\": %.2f, \"p95\": %.2f, \"p99\": %.2f, \"max\": %.2f },\n",
                r->p50, r->p95, r->p99, r->maxft);
        fprintf(f, "  \"frames\": %u,\n  \"seconds\": %.2f,\n  \"whole_seconds\": %u,\n", r->frames, r->span_ms / 1000.0, r->seconds);
    }
    if (in) fprintf(f, "  \"window\": { \"from_ms\": %.1f, \"to_ms\": %.1f, \"anchor\": \"%s\" },\n"
                       "  \"pipelines_built\": %u,\n  \"pipelines_ms\": %.1f,\n",
                    in->window_from_ms, in->window_to_ms, anchor, in->pipelines, in->pipelines_ms);
    fprintf(f, "  \"settings\": %s\n}\n", in && in->settings_json && in->settings_json[0] ? in->settings_json : "[]");
    return ferror(f) ? -1 : 0;
}
#endif
