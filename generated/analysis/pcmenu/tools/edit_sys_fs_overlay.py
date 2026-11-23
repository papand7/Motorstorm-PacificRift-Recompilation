"""sys_fs.c: PS3_VFS_OVERLAY lookup for disc misses in ps3_vfs_ps3game_fallback (vfs_overlay.h).
CRLF file, edited in bytes. Idempotent. usage: py -3 edit_sys_fs_overlay.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[4] / 'ps3recomp-vkgame' / 'runtime' / 'syscalls' / 'sys_fs.c'
s = p.read_bytes()
assert b'\r\n' in s
if b'vfs_overlay_path' in s:
    print('already edited')
    raise SystemExit
a = (b'void ps3_vfs_ps3game_fallback(char* path, size_t cap)\r\n{\r\n    struct stat st;\r\n'
     b'    if (!path || !*path || stat(path, &st) == 0)\r\n        return;\r\n')
assert s.count(a) == 1
b = a + (b'    /* PS3_VFS_OVERLAY: a file the disc tree lacks, from the overlay directory\r\n'
         b'     * (vfs_overlay.h). Only misses get here, so no disc file is shadowed. */\r\n'
         b'    {\r\n'
         b'        static const char* ov = NULL; static int ov_init = 0;\r\n'
         b'        char alt[1024];\r\n'
         b'        if (!ov_init) { ov = getenv("PS3_VFS_OVERLAY"); ov_init = 1; }\r\n'
         b'        if (vfs_overlay_path(alt, sizeof alt, ov, path) && stat(alt, &st) == 0) {\r\n'
         b'            snprintf(path, cap, "%s", alt);\r\n'
         b'            return;\r\n'
         b'        }\r\n'
         b'    }\r\n')
s = s.replace(a, b)
a = b'#include "../memory/vm.h"\r\n'
assert s.count(a) == 1
s = s.replace(a, a + b'#include "vfs_overlay.h"   /* PS3_VFS_OVERLAY */\r\n')
p.write_bytes(s)
print('edited', p.name)
