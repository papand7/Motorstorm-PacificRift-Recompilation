/* test_bench_run.c: the Benchmark page's in-game result (bench_run.h).
 *   - guest frames, not presents: a repeated present of the same flip adds no frame; a present after two flips
 *     counts two;
 *   - the window: presents outside [w0, w1] are left out;
 *   - min / max over whole seconds, avg, 1 % / 0.1 % low, percentiles;
 *   - the race's CROSS schedule; the mode names;
 *   - the JSON file: gpu, cpu, ram_bytes, then fps min / max / avg, the pipelines built in the window, the settings;
 *     an error file has ok false.
 * Build: clang -std=gnu17 -Iport-vkgame port-vkgame/tests/test_bench_run.c -o test_bench_run.exe */
#define _CRT_SECURE_NO_WARNINGS
#include "bench_run.h"
#include <assert.h>
#include <stdio.h>

static double T[20000];
static uint32_t F[20000];
static double S[40000];

static int near(double a, double b, double eps) { return fabs(a - b) <= eps; }

int main(void)
{
    uint32_t n, i;
    bench_result r;

    /* 60 guest frames a second, one present each, 10 s */
    for (n = 0; n <= 600; n++) { T[n] = n * 1000.0 / 60.0; F[n] = n; }
    r = bench_compute(T, F, n, 0.0, 1e9, S, 40000);
    assert(r.ok && r.frames == 600 && near(r.avg, 60.0, 1e-9));
    assert(r.seconds == 10 && near(r.min, 60.0, 1e-9) && near(r.max, 60.0, 1e-9));
    assert(near(r.low1, 60.0, 1e-6) && near(r.p50, 1000.0 / 60.0, 1e-9));

    /* each guest frame presented twice (120 presents a second, 60 flips): still 60 fps */
    for (n = 0; n <= 1200; n++) { T[n] = n * 1000.0 / 120.0; F[n] = n / 2; }
    r = bench_compute(T, F, n, 0.0, 1e9, S, 40000);
    assert(r.ok && r.frames == 600 && near(r.avg, 60.0, 1e-6) && near(r.max, 60.0, 1e-9));
    assert(near(r.p99, 1000.0 / 60.0, 1e-6));   /* the repeated present's time goes to the frame */

    /* two flips per present at 30 presents a second: 60 frames a second, 16.7 ms each */
    for (n = 0; n <= 300; n++) { T[n] = n * 1000.0 / 30.0; F[n] = 2 * n; }
    r = bench_compute(T, F, n, 0.0, 1e9, S, 40000);
    assert(r.ok && r.frames == 600 && near(r.avg, 60.0, 1e-6) && near(r.p50, 1000.0 / 60.0, 1e-6));

    /* the window: 30 fps before 5 s, 60 after; window [5 s, 10 s] sees only 60 */
    n = 0;
    for (double t = 0.0; t < 5000.0; t += 1000.0 / 30.0) { T[n] = t; F[n] = n; n++; }
    { const uint32_t base = n; const double t0 = 5000.0;
      for (i = 0; i <= 300; i++) { T[n] = t0 + i * 1000.0 / 60.0; F[n] = base + i; n++; } }
    r = bench_compute(T, F, n, 5000.0, 10000.0, S, 40000);
    assert(r.ok && r.frames == 300 && near(r.avg, 60.0, 1e-6) && near(r.min, 60.0, 1e-9));
    /* the whole run: min 30, max 60 */
    r = bench_compute(T, F, n, 0.0, 1e9, S, 40000);
    assert(r.ok && near(r.min, 30.0, 1.0) && near(r.max, 60.0, 1e-9));

    /* one 100 ms hitch among 999 frames of 10 ms: 1 % low = 1000 / mean(slowest 10) = 1000 / 19 */
    n = 0; T[0] = 0.0; F[0] = 0;
    for (i = 1; i <= 1000; i++) { T[i] = T[i - 1] + (i == 500 ? 100.0 : 10.0); F[i] = i; }
    n = 1001;
    r = bench_compute(T, F, n, 0.0, 1e9, S, 40000);
    assert(r.ok && near(r.low1, 1000.0 / 19.0, 1e-6) && near(r.low01, 10.0, 1e-6) && near(r.maxft, 100.0, 1e-9));
    assert(near(r.avg, 1000.0 * 1000.0 / 10090.0, 1e-6));
    assert(r.min < r.max);   /* the hitch's second */

    /* empty or one-present windows: no result */
    r = bench_compute(T, F, n, 20000.0, 30000.0, S, 40000);
    assert(!r.ok);
    r = bench_compute(T, F, 1, 0.0, 1e9, S, 40000);
    assert(!r.ok);

    /* the mode names */
    assert(bench_mode_of("fly") == BENCH_FLY && bench_mode_of("race") == BENCH_RACE);
    assert(bench_mode_of(NULL) == BENCH_OFF && bench_mode_of("") == BENCH_OFF && bench_mode_of("Fly") == BENCH_OFF);
    assert(bench_is_race_lr(0x007DD0D4u) && bench_is_race_lr(0x007DD144u) && !bench_is_race_lr(BENCH_LR_SKIP));

    /* the race's CROSS presses: +4 s, +7 s, then every 3 s; none before the flyover, after the race start or 60 s */
    assert(!bench_skip_due(-1.0, -1.0, 0, 5000.0));
    assert(!bench_skip_due(1000.0, -1.0, 0, 4999.0) && bench_skip_due(1000.0, -1.0, 0, 5000.0));
    assert(!bench_skip_due(1000.0, -1.0, 1, 7999.0) && bench_skip_due(1000.0, -1.0, 1, 8000.0));
    assert(!bench_skip_due(1000.0, -1.0, 2, 10999.0) && bench_skip_due(1000.0, -1.0, 2, 11000.0));
    assert(!bench_skip_due(1000.0, 9000.0, 2, 11000.0));
    assert(!bench_skip_due(1000.0, -1.0, 30, 62000.0));

    /* the JSON file */
    {
        for (n = 0; n <= 600; n++) { T[n] = n * 1000.0 / 60.0; F[n] = n; }
        r = bench_compute(T, F, n, 0.0, 1e9, S, 40000);
        bench_info in = { "NVIDIA GeForce \"RTX\" 5060", "AMD Ryzen 5 9600X 6-Core Processor", 34359738368ull,
                          "[{\"key\": \"framerate\", \"name\": \"Frame Rate\", \"value\": \"60 FPS\"}]", 0.0, 10000.0, "test", 12, 345.6 };
        FILE* f = tmpfile();
        assert(f && bench_write_json(f, BENCH_RACE, &r, &in, NULL) == 0);
        char buf[4096];
        rewind(f);
        const size_t got = fread(buf, 1, sizeof buf - 1, f);
        buf[got] = 0;
        fclose(f);
        const char* want[] = { "\"version\": 1", "\"benchmark\": \"race\"", "\"ok\": true", "\"error\": null",
                               "\"gpu\": \"NVIDIA GeForce \\\"RTX\\\" 5060\"", "\"cpu\": \"AMD Ryzen 5 9600X 6-Core Processor\"",
                               "\"ram_bytes\": 34359738368", "\"min\": 60.00", "\"max\": 60.00", "\"avg\": 60.00",
                               "\"low1\": 60.00", "\"frames\": 600", "\"framerate\"", "\"anchor\": \"test\"",
                               "\"pipelines_built\": 12", "\"pipelines_ms\": 345.6" };
        for (i = 0; i < sizeof want / sizeof want[0]; i++)
            if (!strstr(buf, want[i])) { printf("missing %s in\n%s", want[i], buf); return 1; }
        /* the order the result screen reads: gpu, cpu, ram, then the fps */
        assert(strstr(buf, "\"gpu\"") < strstr(buf, "\"cpu\"") && strstr(buf, "\"cpu\"") < strstr(buf, "\"ram_bytes\"") &&
               strstr(buf, "\"ram_bytes\"") < strstr(buf, "\"fps\""));
        f = tmpfile();
        assert(f && bench_write_json(f, BENCH_FLY, NULL, &in, "no HotSpot") == 0);
        rewind(f);
        buf[fread(buf, 1, sizeof buf - 1, f)] = 0;
        fclose(f);
        assert(strstr(buf, "\"ok\": false") && strstr(buf, "\"error\": \"no HotSpot\"") && !strstr(buf, "\"fps\""));
        assert(strstr(buf, "\"benchmark\": \"fly\"") && strstr(buf, "\"gpu\""));
    }
    printf("test_bench_run: ok\n");
    return 0;
}
