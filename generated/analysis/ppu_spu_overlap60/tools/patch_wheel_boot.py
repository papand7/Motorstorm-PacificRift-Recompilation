"""fps stability (user policy 2026-11-20): the racing wheel must be connected before the game starts. The hot-plug
scan therefore runs only during the first PWH_BOOT_MS of the process (every PWH_ENUM_MS while no wheel is open);
after that no scan runs, and a lost wheel is not looked for again. Boot-time scans may block the boot thread; play
never does. PWH_BOOT_MS can be set with PAD_WHEEL_BOOT_MS (0 = old behaviour, unlimited scans).
usage: py -3 patch_wheel_boot.py <ISOLATED copy of libs/input/pad_wheel_dinput.h, original content>"""
import sys

p = sys.argv[1]
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:80]
    s = s.replace(a, b)


rep("static DWORD s_pwh_last_enum, s_pwh_fail_since;\n",
    "static DWORD s_pwh_last_enum, s_pwh_fail_since;\n"
    "/* Wheel scans happen only in the boot window, measured from the first pad poll of the process: the wheel must be\n"
    " * plugged in before the game starts. PAD_WHEEL_BOOT_MS overrides the window (0 = unlimited, the old behaviour). */\n"
    "#define PWH_BOOT_MS_DEFAULT 60000\n"
    "static DWORD s_pwh_boot_t0;\n"
    "static DWORD pwh_boot_ms(void)\n"
    "{\n"
    "    static long v = -1;\n"
    "    if (v < 0) { const char* e = getenv(\"PAD_WHEEL_BOOT_MS\"); v = e ? atol(e) : PWH_BOOT_MS_DEFAULT; }\n"
    "    return (DWORD)v;\n"
    "}\n")

rep("""    if (!s_pwh_open) {
        if (s_pwh_last_enum && now - s_pwh_last_enum < PWH_ENUM_MS) { memset(out, 0, sizeof *out); goto done; }
        s_pwh_last_enum = now ? now : 1;
        pwh_try_open(now);
    }""", """    if (!s_pwh_open) {
        if (!s_pwh_boot_t0) s_pwh_boot_t0 = now ? now : 1;
        const DWORD win = pwh_boot_ms();
        const int in_boot = win == 0 || (DWORD)(now - s_pwh_boot_t0) < win;
        if (!in_boot || (s_pwh_last_enum && now - s_pwh_last_enum < PWH_ENUM_MS)) { memset(out, 0, sizeof *out); goto done; }
        s_pwh_last_enum = now ? now : 1;
        pwh_try_open(now);
    }""")

# a lost wheel during play is not looked for again: it is dropped (no scan), and the boot window has closed
rep("""            if (!s_pwh_fail_since) s_pwh_fail_since = now ? now : 1;
            else if (now - s_pwh_fail_since > PWH_LOST_MS) pwh_drop();""",
    """            if (!s_pwh_fail_since) s_pwh_fail_since = now ? now : 1;
            else if (now - s_pwh_fail_since > PWH_LOST_MS) pwh_drop();   /* no re-scan: the wheel must be there at launch */""")
open(p, 'w', encoding='utf-8').write(s)
print('patched', p)
