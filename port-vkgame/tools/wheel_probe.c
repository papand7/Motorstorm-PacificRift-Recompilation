/* wheel_probe: lists the DirectInput game controllers (VID/PID, axes, buttons, hat, force feedback), shows the
 * live values with the pad state the game would get, and calibrates a wheel. READ ONLY: devices are opened
 * non-exclusively for reading and no force is ever sent.
 *
 *   wheel_probe                      list the devices and how the port would treat them
 *   wheel_probe --live [secs] [--device N] [--lines]
 *                                    raw axes, buttons and hat, and the resulting pad state, until a key or secs
 *   wheel_probe --calibrate [--device N]
 *                                    guided: find the steering, throttle and brake axes and the pedal ends, and
 *                                    print the settings.ini lines (wheel.*) for them
 *   --any                            treat any joystick as a wheel candidate (the port's "Any Device" mode)
 *
 * Build: port-wheel\tools\build_wheel_tests.cmd (clang ... wheel_probe.c -luser32). It uses libs/input's
 * pad_wheel.h (the mapping the game uses) and pad_wheel_dinput.h (the DirectInput layer).
 *
 * Exit codes: 0 done, 2 no device found / DirectInput unavailable, 1 usage or device error. */
#define PAD_WHEEL_NO_HUB
#include "pad_wheel_dinput.h"
#include <conio.h>
#include <math.h>

static HWND make_window(void)
{
    return CreateWindowExW(0, L"STATIC", L"wheel_probe", WS_POPUP, 0, 0, 1, 1, NULL, NULL, GetModuleHandleW(NULL), NULL);
}

static void axes_text(unsigned mask, char* out, size_t n)
{
    out[0] = 0;
    for (int i = 0; i < PCW_AXES; i++)
        if (mask & (1u << i)) snprintf(out + strlen(out), n - strlen(out), "%s%s", out[0] ? " " : "", k_pcw_axis_names[i]);
    if (!out[0]) snprintf(out, n, "(none)");
}

static const char* type_name(int t)
{
    switch (t) {
    case 0x11: return "mouse"; case 0x12: return "keyboard"; case 0x13: return "joystick(DI8 0x13)";
    case 0x14: return "joystick"; case 0x15: return "gamepad"; case 0x16: return "driving";
    case 0x17: return "flight"; case 0x18: return "1st-person"; case 0x19: return "device control";
    case 0x1A: return "screen pointer"; case 0x1B: return "remote"; case 0x1C: return "supplemental";
    }
    return "other";
}

static int list_devices(pwdi_info* list, int max, int any)
{
    const int n = pwdi_enum(list, max);
    pcw_cfg ca, cy;
    pcw_cfg_default(&ca);
    pcw_cfg_default(&cy);
    cy.mode = PCW_MODE_ANY;
    HWND w = make_window();
    printf("DirectInput game controllers: %d\n", n);
    for (int i = 0; i < n; i++) {
        pwdi_info* d = &list[i];
        pwdi_dev dev;
        const int opened = pwdi_open(&dev, d, w, 0);
        if (opened) { d->axes = dev.info.axes; d->buttons = dev.info.buttons; d->povs = dev.info.povs; d->ffb = dev.info.ffb;
                      d->axes_present = dev.info.axes_present; }
        char ax[64];
        axes_text(d->axes_present, ax, sizeof ax);
        const int ra = pcw_device_rank(&ca, d->vid, d->pid, d->devtype, d->product, opened ? d->axes : 99, opened ? d->buttons : 99);
        const int ry = pcw_device_rank(&cy, d->vid, d->pid, d->devtype, d->product, opened ? d->axes : 99, opened ? d->buttons : 99);
        const pcw_profile* p = pcw_profile_by_id(d->vid, d->pid);
        printf("\n[%d] %s\n", i, d->product);
        printf("    instance name : %s\n", d->name);
        printf("    VID:PID       : %04X:%04X  (settings.ini: wheel.device = %04X:%04X)\n", d->vid, d->pid, d->vid, d->pid);
        printf("    DI type       : 0x%02X %s, subtype 0x%02X\n", d->devtype, type_name(d->devtype), d->subtype);
        if (opened)
            printf("    axes %d (%s), buttons %d, hats %d, force feedback %s\n", d->axes, ax, d->buttons, d->povs, d->ffb ? "yes" : "no");
        else
            printf("    could not be opened for reading\n");
        printf("    profile       : %s\n", p ? p->name : "(none in the table)");
        if (p) printf("    assumed layout: steer %s, throttle %s, brake %s, lock %d deg  [HYPOTHESIS: confirm with --live]\n",
                      pcw_axis_name(p->steer), pcw_axis_name(p->throttle), pcw_axis_name(p->brake), p->lock_deg);
        printf("    the port takes it: Auto %s, Any Device %s\n", ra ? "YES" : "no", ry ? "YES" : "no");
        if (opened) pwdi_close(&dev);
    }
    if (w) DestroyWindow(w);
    (void)any;
    return n;
}

static int pick(const pwdi_info* list, int n, int index, int any)
{
    if (index >= 0) return index < n ? index : -1;
    pcw_cfg c;
    pcw_cfg_default(&c);
    if (any) c.mode = PCW_MODE_ANY;
    int best = -1, rank = 0;
    for (int i = 0; i < n; i++) {
        const int r = pcw_device_rank(&c, list[i].vid, list[i].pid, list[i].devtype, list[i].product, 99, 99);
        if (r > rank) { rank = r; best = i; }
    }
    return best;
}

static int live(const pwdi_info* list, int n, int index, int any, int secs, int lines)
{
    const int k = pick(list, n, index, any);
    if (k < 0) { printf("no wheel found (use --device N or --any)\n"); return 2; }
    HWND w = make_window();
    pwdi_dev d;
    if (!pwdi_open(&d, &list[k], w, 0)) { printf("cannot open device %d\n", k); return 1; }
    pcw_cfg cfg;
    pcw_cfg_default(&cfg);
    const pcw_profile* p = pcw_profile_pick(d.info.vid, d.info.pid, d.info.product);
    pcw_map m;
    pcw_resolve(&m, &cfg, p);
    pcw_state st;
    pcw_state_reset(&st);
    printf("%s (%04X:%04X), profile \"%s\": steer=%s throttle=%s brake=%s, range %d deg of %d. Press any key to stop.\n",
           d.info.product, d.info.vid, d.info.pid, p->name, pcw_axis_name(m.steer), pcw_axis_name(m.throttle),
           pcw_axis_name(m.brake), m.range_deg, m.lock_deg);
    printf("Move one control at a time and watch which raw axis changes. Pedals should read 0%% when released.\n");
    const DWORD t0 = GetTickCount();
    int rc = 0, bad = 0;
    for (;;) {
        if (_kbhit()) { (void)_getch(); break; }
        if (secs > 0 && GetTickCount() - t0 > (DWORD)secs * 1000u) break;
        pcw_raw r;
        const int ok = pwdi_read(&d, &r);
        if (ok < 0) { printf("\ndevice unplugged\n"); rc = 1; break; }
        if (ok == 0) { if (++bad > 100) { printf("\nno data from the device\n"); rc = 1; break; } Sleep(20); continue; }
        bad = 0;
        pcw_out o;
        pcw_process(&m, &st, &r, &o);
        char line[512], b[200] = "";
        int w2 = 0;
        for (int i = 0; i < PCW_AXES; i++)
            if (r.axes_present & (1u << i)) w2 += snprintf(line + w2, sizeof line - (size_t)w2, "%s=%5d ", k_pcw_axis_names[i], r.axis[i]);
        for (int i = 0; i < PCW_BUTTONS; i++)
            if ((r.buttons >> i) & 1u) snprintf(b + strlen(b), sizeof b - strlen(b), "%d ", i + 1);
        w2 += snprintf(line + w2, sizeof line - (size_t)w2, "| hat=%d btn[%s] | steer %+4d.%d%% thr %3d%% brk %3d%% lx=%3d r2=%3d l2=%3d pad=0x%04X",
                       r.pov, b, o.steer_milli / 10, abs(o.steer_milli % 10), o.throttle_milli / 10, o.brake_milli / 10,
                       o.lx, o.r2, o.l2, o.buttons);
        if (lines) { printf("%s\n", line); Sleep(250); }
        else { printf("\r%-230s", line); fflush(stdout); Sleep(50); }
    }
    printf("\n");
    pwdi_close(&d);
    if (w) DestroyWindow(w);
    return rc;
}

/* ---- calibration ------------------------------------------------------- */
typedef struct { int lo[PCW_AXES], hi[PCW_AXES], first[PCW_AXES]; } span_t;

static void span_reset(span_t* s, const pcw_raw* r)
{
    for (int i = 0; i < PCW_AXES; i++) s->lo[i] = s->hi[i] = s->first[i] = r->axis[i];
}

static int capture(pwdi_dev* d, const char* prompt, int secs, span_t* s, pcw_raw* last)
{
    printf("\n%s\n", prompt);
    for (int i = 3; i > 0; i--) { printf("  starting in %d...\r", i); fflush(stdout); Sleep(1000); }
    printf("  GO (%d s)            \n", secs);
    int first = 1;
    const DWORD t0 = GetTickCount();
    while (GetTickCount() - t0 < (DWORD)secs * 1000u) {
        pcw_raw r;
        const int ok = pwdi_read(d, &r);
        if (ok < 0) { printf("device unplugged\n"); return 0; }
        if (ok == 0) { Sleep(10); continue; }
        if (first) { span_reset(s, &r); first = 0; }
        for (int i = 0; i < PCW_AXES; i++) {
            if (r.axis[i] < s->lo[i]) s->lo[i] = r.axis[i];
            if (r.axis[i] > s->hi[i]) s->hi[i] = r.axis[i];
        }
        *last = r;
        Sleep(8);
    }
    return !first;
}

/* The axis (among those the device has, not in `skip`) that moved the most, or -1 when none moved 25%. */
static int widest(const pwdi_dev* d, const span_t* s, unsigned skip, int* span)
{
    int best = -1, bs = 0;
    for (int i = 0; i < PCW_AXES; i++) {
        if (!(d->info.axes_present & (1u << i)) || (skip & (1u << i))) continue;
        const int sp = s->hi[i] - s->lo[i];
        if (sp > bs) { bs = sp; best = i; }
    }
    *span = bs;
    return bs >= PCW_AXIS_MAX / 4 ? best : -1;
}

static int calibrate(const pwdi_info* list, int n, int index, int any)
{
    const int k = pick(list, n, index, any);
    if (k < 0) { printf("no wheel found (use --device N or --any)\n"); return 2; }
    HWND w = make_window();
    pwdi_dev d;
    if (!pwdi_open(&d, &list[k], w, 0)) { printf("cannot open device %d\n", k); return 1; }
    printf("Calibrating %s (%04X:%04X). Read only: nothing is written; copy the printed lines to settings.ini.\n",
           d.info.product, d.info.vid, d.info.pid);
    span_t base, steer, thr, brk;
    pcw_raw last;
    if (!capture(&d, "Step 1/4: hands off the wheel (centre it) and feet OFF the pedals.", 2, &base, &last)) return 1;
    const pcw_raw rest = last;
    if (!capture(&d, "Step 2/4: turn the wheel slowly from full left lock to full right lock, then back to the centre.", 7, &steer, &last)) return 1;
    int sp_s, sp_t, sp_b;
    const int ax_s = widest(&d, &steer, 0, &sp_s);
    if (!capture(&d, "Step 3/4: press the THROTTLE pedal all the way down and release it (twice).", 5, &thr, &last)) return 1;
    const int ax_t = widest(&d, &thr, ax_s >= 0 ? 1u << ax_s : 0, &sp_t);
    if (!capture(&d, "Step 4/4: press the BRAKE pedal all the way down and release it (twice).", 5, &brk, &last)) return 1;
    const int ax_b_any = widest(&d, &brk, ax_s >= 0 ? 1u << ax_s : 0, &sp_b);

    printf("\n==== result ====\n");
    if (ax_s < 0) printf("steering: no axis moved by more than 25%% (try --live to see what the wheel reports)\n");
    else printf("steering: axis %s, observed %d .. %d (span %d of 65535), rest %d\n", k_pcw_axis_names[ax_s], steer.lo[ax_s], steer.hi[ax_s], sp_s, rest.axis[ax_s]);
    if (ax_s >= 0 && sp_s < 52000) printf("  note: the span is below the full range; the driver's rotation setting (the \"lock\") may be lower than the wheel's: set wheel.steer.lock to match\n");
    char lines[2048] = "";
    pcw_cfg c;
    pcw_cfg_default(&c);
    if (ax_s >= 0 && ax_s != PCW_AX_X) c.steer_axis = ax_s;
    int combined = 0;
    if (ax_t < 0) printf("throttle: no axis moved by more than 25%%\n");
    else {
        const int rest_v = rest.axis[ax_t];
        const int far_lo = rest_v - thr.lo[ax_t], far_hi = thr.hi[ax_t] - rest_v;
        const int full = far_lo > far_hi ? thr.lo[ax_t] : thr.hi[ax_t];
        printf("throttle: axis %s, rest %d, fully pressed %d (%s)\n", k_pcw_axis_names[ax_t], rest_v, full, full < rest_v ? "inverted: the value falls when pressed" : "normal");
        c.throttle_axis = ax_t; c.rest[0] = rest_v; c.full[0] = full;
        /* the same axis moved by the brake too: combined pedals when it moved the other way from rest */
        if (ax_b_any == ax_t) {
            const int bl = rest_v - brk.lo[ax_t], bh = brk.hi[ax_t] - rest_v;
            const int bfull = bl > bh ? brk.lo[ax_t] : brk.hi[ax_t];
            if ((bfull < rest_v) != (full < rest_v)) combined = 1;
        }
    }
    if (combined) {
        printf("brake   : the same axis %s moved the other way: COMBINED pedals (throttle one side of the middle, brake the other)\n", k_pcw_axis_names[ax_t]);
        printf("          set the page's Wheel Pedals = Combined, and wheel.pedals.center = %d\n", rest.axis[ax_t]);
        c.center = rest.axis[ax_t];
        c.rest[0] = c.full[0] = -1;
        c.brake_axis = PCW_NO_AXIS;
    } else if (ax_b_any < 0) printf("brake   : no axis moved by more than 25%%\n");
    else {
        const int rest_v = rest.axis[ax_b_any];
        const int far_lo = rest_v - brk.lo[ax_b_any], far_hi = brk.hi[ax_b_any] - rest_v;
        const int full = far_lo > far_hi ? brk.lo[ax_b_any] : brk.hi[ax_b_any];
        printf("brake   : axis %s, rest %d, fully pressed %d (%s)\n", k_pcw_axis_names[ax_b_any], rest_v, full, full < rest_v ? "inverted: the value falls when pressed" : "normal");
        c.brake_axis = ax_b_any; c.rest[1] = rest_v; c.full[1] = full;
    }
    c.dev_vid = 0;
    pcw_format(&c, lines, sizeof lines);
    printf("\nsettings.ini (beside the game exe; keep the other lines):\n------------------------\n");
    if (combined) printf("wheelpedals = Combined\n");
    printf("%s------------------------\n", lines);
    printf("Also check with: wheel_probe --live   (pedals read 0%% released, 100%% pressed; steering 0%% centred).\n");
    pwdi_close(&d);
    if (w) DestroyWindow(w);
    return 0;
}

int main(int argc, char** argv)
{
    int mode = 0, index = -1, any = 0, secs = 0, lines = 0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--live")) { mode = 1; if (i + 1 < argc && argv[i + 1][0] >= '0' && argv[i + 1][0] <= '9') secs = atoi(argv[++i]); }
        else if (!strcmp(argv[i], "--calibrate")) mode = 2;
        else if (!strcmp(argv[i], "--device") && i + 1 < argc) index = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--any")) any = 1;
        else if (!strcmp(argv[i], "--lines")) lines = 1;
        else if (!strcmp(argv[i], "--list")) mode = 0;
        else { printf("usage: wheel_probe [--list | --live [secs] [--lines] | --calibrate] [--device N] [--any]\n"); return 1; }
    }
    if (!pwdi_init()) { printf("DirectInput 8 (dinput8.dll) is not available\n"); return 2; }
    pwdi_info list[16];
    int n;
    if (mode == 0) {
        n = list_devices(list, 16, any);
        if (!n) { printf("\nNo DirectInput game controller is attached. (XInput-only pads and Xbox-mode wheels such as the\nG920 do not need this port feature: the game already reads them as a gamepad.)\n"); return 2; }
        return 0;
    }
    n = pwdi_enum(list, 16);
    return mode == 1 ? live(list, n, index, any, secs, lines) : calibrate(list, n, index, any);
}
