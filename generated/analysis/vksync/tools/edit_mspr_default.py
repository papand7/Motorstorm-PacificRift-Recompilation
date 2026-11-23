"""MSPR_PATCH: drs on by default (user approved 2026-11-05). Unset gives the list in
port-vkgame/mspr_patch.h; "none" or empty turns every patch off. main.cpp is CRLF.

usage: py -3 edit_mspr_default.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[4] / 'port-vkgame' / 'main.cpp'
raw = p.read_bytes().decode('utf-8')
s = raw.replace('\r\n', '\n')
SUBS = [
    ('#include "ps3emu/pad_trigger.h"     /* PS3_DEV_SKIP_INTRO: one CROSS press during the intro */\n',
     '#include "ps3emu/pad_trigger.h"     /* PS3_DEV_SKIP_INTRO: one CROSS press during the intro */\n'
     '#include "mspr_patch.h"            /* MSPR_PATCH: default patch list (drs) */\n'),
    (' * MSPR_PATCH (off by default)\n', ' * MSPR_PATCH (drs by default)\n'),
    (""" * and off with the engine's in-run A/B side instead (drs:ab).
""",
     """ * and off with the engine's in-run A/B side instead (drs:ab). Unset, the list
 * is MSPR_PATCH_DEFAULT (drs, mspr_patch.h); "none" or empty turns all off.
"""),
    ("""    const char* e = getenv("MSPR_PATCH");
    if (!e || !*e) return;
""",
     """    const char* env = getenv("MSPR_PATCH");
    const char* e = mspr_patch_spec(env);
    if (!*e) {
        fprintf(stderr, "[mspr-patch] none\\n");
        return;
    }
"""),
    ("""    fprintf(stderr, "[mspr-patch] on 0x%02X, by turns 0x%02X\\n", s_mspr_patch, s_mspr_patch_ab);
""",
     """    fprintf(stderr, "[mspr-patch] on 0x%02X, by turns 0x%02X%s\\n", s_mspr_patch, s_mspr_patch_ab,
            env ? "" : " (default " MSPR_PATCH_DEFAULT ")");
"""),
]
for a, b in SUBS:
    assert s.count(a) == 1, (a[:60], s.count(a))
    s = s.replace(a, b)
p.write_bytes(s.replace('\n', '\r\n').encode('utf-8'))
print('edited', p.name)
