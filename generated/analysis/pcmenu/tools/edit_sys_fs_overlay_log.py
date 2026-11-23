"""sys_fs.c (CRLF): log the first PS3_VFS_OVERLAY hits (file served from the overlay). Idempotent.
usage: py -3 edit_sys_fs_overlay_log.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[4] / 'ps3recomp-vkgame' / 'runtime' / 'syscalls' / 'sys_fs.c'
s = p.read_bytes()
N = b'\r\n'
old = (b'        if (vfs_overlay_path(alt, sizeof alt, ov, path) && stat(alt, &st) == 0) {' + N +
       b'            snprintf(path, cap, "%s", alt);' + N)
new = (b'        if (vfs_overlay_path(alt, sizeof alt, ov, path) && stat(alt, &st) == 0) {' + N +
       b'            static int ov_hits;' + N +
       b'            if (ov_hits++ < 16) fprintf(stderr, "[vfs-overlay] %s -> %s\\n", path, alt);' + N +
       b'            snprintf(path, cap, "%s", alt);' + N)
if new in s:
    print('already edited')
else:
    assert s.count(old) == 1
    p.write_bytes(s.replace(old, new))
    print('edited', p.name)
