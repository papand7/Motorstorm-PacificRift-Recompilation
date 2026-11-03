"""T122: PS3_TEX_SNAPSHOT_EPOCH in tex_snapshot.h (tree = argv[1])."""
import sys
from pathlib import Path
NL = chr(10)
root = Path(sys.argv[1])


def sub(p, old, new):
    f = root / p; raw = f.read_bytes(); crlf = b'\r\n' in raw
    t = raw.decode('utf-8').replace(chr(13), '')
    assert t.count(old) == 1, (p, old[:70], t.count(old))
    t = t.replace(old, new)
    if crlf: t = t.replace(NL, chr(13) + NL)
    f.write_bytes(t.encode('utf-8'))


H = 'include/ps3emu/tex_snapshot.h'
sub(H, ''' * Single-threaded: capture and lookup run on the thread that drains and
 * presents. tests/test_tex_snapshot.c models the race. */''',
''' * Single-threaded: capture and lookup run on the thread that drains and
 * presents. tests/test_tex_snapshot.c models the race.
 *
 * Optional sync epoch (`epoch_src`, NULL = off): a counter the FIFO walker
 * bumps at every point where the guest can learn how far the RSX has got, or
 * where the RSX side writes guest memory -- the start of a drain pass, a
 * published `get`, a semaphore/label/report/notify/reference/flip or any
 * non-3D-class method, a render-target write-back. Between two bumps the guest
 * cannot tell whether two draws read a texture at the same instant, so a key
 * already captured in the current epoch is reused without hashing it again: a
 * texture bound on many draws of one pass costs one hash, not one per draw. */''')
sub(H, '''    uint64_t last_use;
    int      valid;
    ps3_texsnap_gen g[PS3_TEXSNAP_GENS];
} ps3_texsnap_key;''', '''    uint64_t last_use;
    int      valid;
    int      ep_valid;     /* `epoch` holds the epoch of the latest capture */
    uint32_t epoch;
    ps3_texsnap_gen g[PS3_TEXSNAP_GENS];
} ps3_texsnap_key;''')
sub(H, '''    uint64_t copies, reuses, evicted, torn, failed;
''', '''    uint64_t copies, reuses, evicted, torn, failed;
    uint64_t skips;        /* reuses inside one epoch, without a hash (counted in reuses too) */
    const volatile long* epoch_src;   /* the sync epoch, or NULL (every capture hashes) */
''')
sub(H, '''        for (int j = 0; j < PS3_TEXSNAP_GENS; j++) k->g[j].seq = 0;
        k->off = off; k->cur = 0; k->valid = 1;
    }
    ps3_texsnap_key* k = &s->k[ki];
    k->last_use = s->tick;
    const uint64_t pre = ps3_texsnap_hash(src, nbytes);''', '''        for (int j = 0; j < PS3_TEXSNAP_GENS; j++) k->g[j].seq = 0;
        k->off = off; k->cur = 0; k->valid = 1; k->ep_valid = 0;
    }
    ps3_texsnap_key* k = &s->k[ki];
    k->last_use = s->tick;
    const int ep_on = s->epoch_src != NULL;
    const uint32_t ep = ep_on ? (uint32_t)*s->epoch_src : 0u;
    {   const ps3_texsnap_gen* l = &k->g[k->cur];
        if (ep_on && k->ep_valid && k->epoch == ep && l->seq && l->nbytes == nbytes) {
            s->reuses++; s->skips++; return l->seq; } }
    k->epoch = ep; k->ep_valid = ep_on;
    const uint64_t pre = ps3_texsnap_hash(src, nbytes);''')
print('ok', root)
sub(H, "        if (!nb) { s->failed++; return 0; }", "        if (!nb) { k->ep_valid = 0; s->failed++; return 0; }")
