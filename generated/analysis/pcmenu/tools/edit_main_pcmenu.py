"""port-vkgame: PC Settings page wiring (pc_menu.cpp). CRLF files, edited in bytes. Idempotent.
  main.cpp: pcmenu_boot(argv[0]) first (settings.ini -> environment), pcmenu_init() after
            mspr_patch_init(); mspr_patch_set() for choices that apply at once.
  CMakeLists.txt: pc_menu.cpp beside main.cpp.
usage: py -3 edit_main_pcmenu.py"""
import pathlib

PO = pathlib.Path(__file__).resolve().parents[4] / 'port-vkgame'


def edit(path, pairs):
    s = path.read_bytes()
    assert b'\r\n' in s
    for old, new in pairs:
        if new in s:
            continue
        assert s.count(old) == 1, (path.name, old)
        s = s.replace(old, new)
    path.write_bytes(s)
    print('edited', path.name)


N = b'\r\n'
edit(PO / 'main.cpp', [
    (b'#include "mspr_patch.h"            /* MSPR_PATCH: default patch list (drs) */' + N,
     b'#include "mspr_patch.h"            /* MSPR_PATCH: default patch list (drs) */' + N +
     b'extern "C" void pcmenu_boot(const char* argv0);   /* pc_menu.cpp: settings.ini, PC Settings page */' + N +
     b'extern "C" void pcmenu_init(void);' + N),
    (b'    if (s_mspr_patch & bit) return 1;' + N +
     b'    return (s_mspr_patch_ab & bit) ? rsx_draw_engine_ab_phase() : 0;' + N + b'}' + N,
     b'    if (s_mspr_patch & bit) return 1;' + N +
     b'    return (s_mspr_patch_ab & bit) ? rsx_draw_engine_ab_phase() : 0;' + N + b'}' + N + N +
     b'/* A patch turned on or off from the PC Settings page (pc_menu.cpp). */' + N +
     b'extern "C" void mspr_patch_set(uint32_t bit, int on)' + N + b'{' + N +
     b'    if (on) s_mspr_patch |= bit;' + N + b'    else s_mspr_patch &= ~bit;' + N +
     b'    fprintf(stderr, "[mspr-patch] on 0x%02X (PC Settings)\\n", s_mspr_patch);' + N + b'}' + N),
    (b'    printf("=== ps3recomp game runner ===\\n");' + N,
     b'    printf("=== ps3recomp game runner ===\\n");' + N +
     b'    pcmenu_boot(argv[0]);    /* settings.ini -> environment, before anything reads it */' + N),
    (b'    mspr_patch_init();       /* MSPR_PATCH only */' + N,
     b'    mspr_patch_init();       /* MSPR_PATCH only */' + N +
     b'    pcmenu_init();           /* PC Settings page functions (used only by its overlay pages) */' + N),
])
edit(PO / 'CMakeLists.txt', [
    (b'    main.cpp' + N + b'    stubs.cpp' + N,
     b'    main.cpp' + N + b'    pc_menu.cpp' + N + b'    stubs.cpp' + N),
])
