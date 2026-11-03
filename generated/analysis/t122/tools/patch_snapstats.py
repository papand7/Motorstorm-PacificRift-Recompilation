"""T122: texsnap captures/copies/hashed bytes in [gpu-sync] (applied to a tree given as argv[1])."""
import sys
from pathlib import Path
NL = chr(10)
root = Path(sys.argv[1])


def sub(p, old, new):
    f = root / p; raw = f.read_bytes(); crlf = b'\r\n' in raw
    t = raw.decode('utf-8').replace(chr(13), '')
    assert t.count(old) == 1, (p, old[:60], t.count(old))
    t = t.replace(old, new)
    if crlf: t = t.replace(NL, chr(13) + NL)
    f.write_bytes(t.encode('utf-8'))


H = 'include/ps3emu/tex_snapshot.h'
sub(H, '    uint64_t copies, reuses, evicted, torn, failed;\n',
       '    uint64_t copies, reuses, evicted, torn, failed;\n    uint64_t hashed;       /* bytes hashed by captures (the guest bytes, plus the copy\'s) */\n')
sub(H, '    const uint64_t pre = ps3_texsnap_hash(src, nbytes);\n',
       '    const uint64_t pre = ps3_texsnap_hash(src, nbytes);\n    s->hashed += nbytes;\n')
sub(H, '    g->hash = ps3_texsnap_hash(g->buf, nbytes);\n',
       '    g->hash = ps3_texsnap_hash(g->buf, nbytes);\n    s->hashed += nbytes;\n')
G = 'include/ps3emu/gpu_sync_stats.h'
sub(G, '    uint64_t atlas_bytes;       /* their upload bytes */\n',
       '    uint64_t atlas_bytes;       /* their upload bytes */\n'
       '    uint64_t snap_caps, snap_copies, snap_hashed;   /* PS3_TEX_SNAPSHOT captures, copies, bytes hashed */\n')
sub(G, '        " barriers=%.1f atlas=%.2f atlas_kb=%.1f |",',
       '        " barriers=%.1f atlas=%.2f atlas_kb=%.1f texsnap=%.1f copies=%.2f hashed_mb=%.1f |",')
sub(G, '        c->barriers / f, c->atlas / f, c->atlas_bytes / 1024.0 / f);\n',
       '        c->barriers / f, c->atlas / f, c->atlas_bytes / 1024.0 / f,\n'
       '        c->snap_caps / f, c->snap_copies / f, c->snap_hashed / 1048576.0 / f);\n')
B = 'libs/video/rsx_d3d12_backend.c'
sub(B, 'static unsigned long long s_gsy_bar0;   /* s_gsy_barriers at the window start */\n',
       'static unsigned long long s_gsy_bar0;   /* s_gsy_barriers at the window start */\n'
       'static ps3_texsnap s_gsy_snap0;         /* s_texsnap counters at the window start */\n')
sub(B, '    if (!s_gsy_t0) { s_gsy_t0 = now; gsy_reset(&s_gsy); s_gsy_bar0 = s_gsy_barriers; return; }   /* the first window starts here */\n',
       '    if (!s_gsy_t0) { s_gsy_t0 = now; gsy_reset(&s_gsy); s_gsy_bar0 = s_gsy_barriers; s_gsy_snap0 = s_texsnap; return; }   /* the first window starts here */\n')
sub(B, '    s_gsy.barriers = s_gsy_barriers - s_gsy_bar0;\n    s_gsy_bar0 = s_gsy_barriers;\n',
       '    s_gsy.barriers = s_gsy_barriers - s_gsy_bar0;\n    s_gsy_bar0 = s_gsy_barriers;\n'
       '    s_gsy.snap_caps = (s_texsnap.copies + s_texsnap.reuses) - (s_gsy_snap0.copies + s_gsy_snap0.reuses);\n'
       '    s_gsy.snap_copies = s_texsnap.copies - s_gsy_snap0.copies;\n'
       '    s_gsy.snap_hashed = s_texsnap.hashed - s_gsy_snap0.hashed;\n'
       '    s_gsy_snap0 = s_texsnap;\n')
T = 'libs/video/tests/test_gpu_sync_stats.c'
sub(T, '    c.barriers = 90; c.atlas = 2; c.atlas_bytes = 2 * 512 * 1024;\n',
       '    c.barriers = 90; c.atlas = 2; c.atlas_bytes = 2 * 512 * 1024;\n    c.snap_caps = 400; c.snap_copies = 4; c.snap_hashed = 400ull << 21;\n')
sub(T, '    CHECK(strstr(b, "barriers=22.5 atlas=0.50 atlas_kb=256.0 |") != NULL);\n',
       '    CHECK(strstr(b, "barriers=22.5 atlas=0.50 atlas_kb=256.0 texsnap=100.0 copies=1.00 hashed_mb=200.0 |") != NULL);\n')
print('patched', root)
