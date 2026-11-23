"""fps stability: PAD_WHEEL_ASYNC_SCAN=1 moves the racing-wheel hot-plug scan (DirectInput EnumDevices + open, every
2 s while no wheel is attached) off the game's threads. Without it, cellPadGetInfo/GetData on the game's main thread
(or on a thread holding a game lwmutex the main thread then waits on) blocks 40-160 ms every ~2-3 s: Kksr61/77/87
show 30-39 such stalls per race in [hle-wait] (nid 0x3AAAD464 cellPadGetInfo, 0x1573DC3F sys_lwmutex_lock); the
pre-wheel exe (Kksr50) shows none. Opt-in; the synchronous scan stays the default.
usage: py -3 patch_wheel_async.py <libs/input/pad_wheel_dinput.h of an ISOLATED copy>"""
import sys

p = sys.argv[1]
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:80]
    s = s.replace(a, b)


rep("static int s_pwh_atexit;\n", """static int s_pwh_atexit;
/* PAD_WHEEL_ASYNC_SCAN=1: the scan for a wheel runs on its own thread (pwh_scan_main), so the pad calls never wait
 * for DirectInput's EnumDevices (tens of ms to >100 ms on some machines) on the game's threads. */
static int s_pwh_async = -1;
static HANDLE s_pwh_scan_thread, s_pwh_scan_wake;
static volatile LONG s_pwh_stop;
""")

# split pwh_try_open: find + open into a local device (slow, no lock), then install (under the lock)
rep("""static void pwh_try_open(DWORD now)
{
    pwdi_info list[16];
    const int n = pwdi_enum(list, 16);
    int best = -1, rank = 0;
    for (int i = 0; i < n; i++) {
        const int r = pcw_device_rank(&s_pwh_cfg, list[i].vid, list[i].pid, list[i].devtype, list[i].product, 99, 99);
        if (r > rank) { rank = r; best = i; }
    }
    if (best < 0) return;
    HWND hwnd = pwdi_find_window();
    if (!hwnd) return;   /* no window yet: try again at the next scan */
    int ffb = s_pwh_cfg.ffb != PCW_FFB_OFF;
    pwdi_dev d;
    if (!pwdi_open(&d, &list[best], hwnd, ffb)) {
        if (!ffb || !pwdi_open(&d, &list[best], hwnd, 0)) return;   /* exclusive refused: still usable as an input */
        ffb = 0;
        printf("[cellPad] wheel: force feedback unavailable (exclusive access refused)\\n");
    }
    if (rank == 10 && (d.info.axes < 2 || d.info.buttons < 4)) { pwdi_close(&d); return; }
    if (!(d.info.axes_present & 1u)) { printf("[cellPad] wheel: %s has no X axis, ignored\\n", d.info.product); pwdi_close(&d); return; }
    s_pwh_dev = d;
    s_pwh_open = 1;
    s_pwh_profile = pcw_profile_pick(d.info.vid, d.info.pid, d.info.product);
    pcw_resolve(&s_pwh_map, &s_pwh_cfg, s_pwh_profile);
    pcw_state_reset(&s_pwh_state);
    if (ffb && pwdi_ffb_open(&s_pwh_dev, s_pwh_cfg.ffb, s_pwh_cfg.ffb_pct))
        printf("[cellPad] wheel: force feedback on (mode %d, %d%%)\\n", s_pwh_cfg.ffb, s_pwh_cfg.ffb_pct);
    if (!s_pwh_atexit) { s_pwh_atexit = 1; atexit(pwh_atexit); }
    printf("[cellPad] wheel: %s (%04X:%04X, profile \\"%s\\"), %d axes, %d buttons, steer=%s throttle=%s brake=%s%s\\n",
           d.info.product, d.info.vid, d.info.pid, s_pwh_profile->name, d.info.axes, d.info.buttons,
           pcw_axis_name(s_pwh_map.steer), pcw_axis_name(s_pwh_map.throttle), pcw_axis_name(s_pwh_map.brake),
           s_pwh_map.combined ? " (combined pedals)" : "");
    fflush(stdout);
    (void)now;
}""", """/* Enumerate, choose and open the best wheel for cfg into *d (the slow part: DirectInput calls, no shared state
 * written). Returns 1 with *ffb set when a device is open. */
static int pwh_find_open(const pcw_cfg* cfg, pwdi_dev* d, int* ffb_out)
{
    pwdi_info list[16];
    const int n = pwdi_enum(list, 16);
    int best = -1, rank = 0;
    for (int i = 0; i < n; i++) {
        const int r = pcw_device_rank(cfg, list[i].vid, list[i].pid, list[i].devtype, list[i].product, 99, 99);
        if (r > rank) { rank = r; best = i; }
    }
    if (best < 0) return 0;
    HWND hwnd = pwdi_find_window();
    if (!hwnd) return 0;   /* no window yet: try again at the next scan */
    int ffb = cfg->ffb != PCW_FFB_OFF;
    if (!pwdi_open(d, &list[best], hwnd, ffb)) {
        if (!ffb || !pwdi_open(d, &list[best], hwnd, 0)) return 0;   /* exclusive refused: still usable as an input */
        ffb = 0;
        printf("[cellPad] wheel: force feedback unavailable (exclusive access refused)\\n");
    }
    if (rank == 10 && (d->info.axes < 2 || d->info.buttons < 4)) { pwdi_close(d); return 0; }
    if (!(d->info.axes_present & 1u)) { printf("[cellPad] wheel: %s has no X axis, ignored\\n", d->info.product); pwdi_close(d); return 0; }
    *ffb_out = ffb;
    return 1;
}

/* Make *d the pad layer's wheel (caller holds s_pwh_lock). */
static void pwh_install(const pwdi_dev* d, int ffb)
{
    s_pwh_dev = *d;
    s_pwh_open = 1;
    s_pwh_profile = pcw_profile_pick(d->info.vid, d->info.pid, d->info.product);
    pcw_resolve(&s_pwh_map, &s_pwh_cfg, s_pwh_profile);
    pcw_state_reset(&s_pwh_state);
    if (ffb && pwdi_ffb_open(&s_pwh_dev, s_pwh_cfg.ffb, s_pwh_cfg.ffb_pct))
        printf("[cellPad] wheel: force feedback on (mode %d, %d%%)\\n", s_pwh_cfg.ffb, s_pwh_cfg.ffb_pct);
    if (!s_pwh_atexit) { s_pwh_atexit = 1; atexit(pwh_atexit); }
    printf("[cellPad] wheel: %s (%04X:%04X, profile \\"%s\\"), %d axes, %d buttons, steer=%s throttle=%s brake=%s%s\\n",
           s_pwh_dev.info.product, s_pwh_dev.info.vid, s_pwh_dev.info.pid, s_pwh_profile->name, s_pwh_dev.info.axes,
           s_pwh_dev.info.buttons, pcw_axis_name(s_pwh_map.steer), pcw_axis_name(s_pwh_map.throttle),
           pcw_axis_name(s_pwh_map.brake), s_pwh_map.combined ? " (combined pedals)" : "");
    fflush(stdout);
}

/* The synchronous scan (default): on the calling thread, with s_pwh_lock held. */
static void pwh_try_open(DWORD now)
{
    pwdi_dev d;
    int ffb = 0;
    if (pwh_find_open(&s_pwh_cfg, &d, &ffb)) pwh_install(&d, ffb);
    (void)now;
}

static void pwh_lock(void) { while (InterlockedCompareExchange(&s_pwh_lock, 1, 0) != 0) Sleep(1); }
static void pwh_unlock(void) { InterlockedExchange(&s_pwh_lock, 0); }

/* PAD_WHEEL_ASYNC_SCAN: look for a wheel every PWH_ENUM_MS (or at once when woken: a settings change) while none
 * is open. The configuration is copied under the lock; the device is found and opened without it; it is installed
 * under the lock only if no wheel was opened meanwhile, the configuration did not change and the pad layer was not
 * released. */
static DWORD WINAPI pwh_scan_main(LPVOID unused)
{
    (void)unused;
    for (;;) {
        WaitForSingleObject(s_pwh_scan_wake, PWH_ENUM_MS);
        if (s_pwh_stop) return 0;
        pwh_lock();
        const int skip = s_pwh_open || !s_pwh_cfg_loaded || s_pwh_cfg.mode == PCW_MODE_OFF;
        const pcw_cfg cfg = s_pwh_cfg;
        pwh_unlock();
        if (skip) continue;
        pwdi_dev d;
        int ffb = 0;
        if (!pwh_find_open(&cfg, &d, &ffb)) continue;
        pwh_lock();
        if (!s_pwh_open && !s_pwh_stop && memcmp(&cfg, &s_pwh_cfg, sizeof cfg) == 0) { pwh_install(&d, ffb); d.dev = NULL; }
        pwh_unlock();
        if (d.dev) pwdi_close(&d);
    }
}

/* Called with s_pwh_lock held: start the scanner once; wake it now when asked (settings changed). */
static void pwh_async_kick(int now)
{
    if (!s_pwh_scan_thread) {
        s_pwh_scan_wake = CreateEventW(NULL, FALSE, TRUE, NULL);   /* signalled: the first scan runs at once */
        if (s_pwh_scan_wake) s_pwh_scan_thread = CreateThread(NULL, 0, pwh_scan_main, NULL, 0, NULL);
        if (!s_pwh_scan_thread) { s_pwh_async = 0; return; }   /* no thread: fall back to the synchronous scan */
        printf("[cellPad] wheel: scanning on a background thread (PAD_WHEEL_ASYNC_SCAN)\\n");
        fflush(stdout);
    } else if (now) SetEvent(s_pwh_scan_wake);
}""")

rep("""    if (!s_pwh_open) {
        if (s_pwh_last_enum && now - s_pwh_last_enum < PWH_ENUM_MS) { memset(out, 0, sizeof *out); goto done; }
        s_pwh_last_enum = now ? now : 1;
        pwh_try_open(now);
    }""", """    if (s_pwh_async < 0) { const char* e = getenv("PAD_WHEEL_ASYNC_SCAN"); s_pwh_async = e && atoi(e) ? 1 : 0; }
    if (!s_pwh_open && s_pwh_async > 0) {
        pwh_async_kick(s_pwh_last_enum == 0);   /* 0 after a settings change: scan at once */
        s_pwh_last_enum = now ? now : 1;
        if (s_pwh_async > 0) { memset(out, 0, sizeof *out); goto done; }
    }
    if (!s_pwh_open) {
        if (s_pwh_last_enum && now - s_pwh_last_enum < PWH_ENUM_MS) { memset(out, 0, sizeof *out); goto done; }
        s_pwh_last_enum = now ? now : 1;
        pwh_try_open(now);
    }""")

rep("""void pad_wheel_release(void)
{
    while (InterlockedCompareExchange(&s_pwh_lock, 1, 0) != 0) Sleep(1);""", """void pad_wheel_release(void)
{
    InterlockedExchange(&s_pwh_stop, 1);
    if (s_pwh_scan_wake) SetEvent(s_pwh_scan_wake);
    while (InterlockedCompareExchange(&s_pwh_lock, 1, 0) != 0) Sleep(1);""")
open(p, 'w', encoding='utf-8').write(s)
print('patched', p)
