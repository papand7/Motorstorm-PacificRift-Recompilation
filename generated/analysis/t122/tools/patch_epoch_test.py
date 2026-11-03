"""T122: PS3_TEX_SNAPSHOT_EPOCH cases in tests/test_tex_snapshot.c (tree = argv[1])."""
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


T = 'tests/test_tex_snapshot.c'
sub(T, ''' * falls back to guest memory, and a write during the capture is counted. */''',
''' * falls back to guest memory, and a write during the capture is counted.
 *
 * Sync epoch (T122): a third backend gives the store an epoch the drain bumps
 * when it publishes the signal; it must stay untorn too. Unit cases: inside one
 * epoch a key is reused without a hash, even if the bytes changed (the guest
 * cannot have known the RSX was past the earlier draw); a bump, another key,
 * another size or no epoch source all hash again. */''')
sub(T, '''    int      snapshot;          /* backend mode */
''', '''    int      snapshot;          /* backend mode: 0 old, 1 snapshot, 2 snapshot + sync epoch */
    long     epoch;             /* the drain's sync epoch (mode 2) */
''')
sub(T, '''    s->rec_frame = f;
    s->queued = -1;
    s->consumed = f;                              /* published in FIFO order */
''', '''    s->rec_frame = f;
    s->queued = -1;
    s->consumed = f;                              /* published in FIFO order */
    s->epoch++;                                   /* the published signal is a sync point */
''')
sub(T, '''    s->rec_frame = -1; s->guest_phase = phase; s->snapshot = snapshot;
''', '''    s->rec_frame = -1; s->guest_phase = phase; s->snapshot = snapshot;
    if (snapshot == 2) s->store.epoch_src = &s->epoch;
''')
sub(T, '''        sim a, b;
        sim_init(&a, phase, 0); sim_init(&b, phase, 1);
        for (int beat = 0; beat < 400; beat++) {
            drain(&a); drain(&b);
            for (int g = 0; g < 3; g++) { maybe_guest(&a); maybe_guest(&b); }
            present(&a); present(&b);
            guest_step(&a); guest_step(&b);
        }
        CHECK(b.presents > 20);
        CHECK(b.torn == 0);                    /* every upload is the drawn frame */
        CHECK(b.store.evicted == 0);
        old_torn += a.torn;
        ps3_texsnap_free(&b.store);''', '''        sim a, b, c;
        sim_init(&a, phase, 0); sim_init(&b, phase, 1); sim_init(&c, phase, 2);
        for (int beat = 0; beat < 400; beat++) {
            drain(&a); drain(&b); drain(&c);
            for (int g = 0; g < 3; g++) { maybe_guest(&a); maybe_guest(&b); maybe_guest(&c); }
            present(&a); present(&b); present(&c);
            guest_step(&a); guest_step(&b); guest_step(&c);
        }
        CHECK(b.presents > 20);
        CHECK(b.torn == 0);                    /* every upload is the drawn frame */
        CHECK(b.store.evicted == 0);
        CHECK(c.presents == b.presents && c.torn == 0 && c.store.evicted == 0);
        CHECK(c.store.copies == b.store.copies && c.store.skips == 0);   /* one capture per epoch here */
        old_torn += a.torn;
        ps3_texsnap_free(&b.store);
        ps3_texsnap_free(&c.store);''')
sub(T, '''    ps3_texsnap_free(&s);
    printf("%u texture snapshot checks PASS\n", checks);''', '''    ps3_texsnap_free(&s);

    /* Sync epoch. */
    long ep = 5;
    memset(&s, 0, sizeof s);
    s.epoch_src = &ep;
    memset(t, 0x11, sizeof t);
    const uint32_t e1 = ps3_texsnap_capture(&s, 0x100, t, sizeof t);
    const uint64_t hashed1 = s.hashed;
    const uint32_t e2 = ps3_texsnap_capture(&s, 0x100, t, sizeof t);          /* same epoch: no hash */
    CHECK(e1 && e2 == e1 && s.skips == 1 && s.reuses == 1 && s.hashed == hashed1);
    t[7] = 0x44;                                                              /* an unsynchronised write */
    CHECK(ps3_texsnap_capture(&s, 0x100, t, sizeof t) == e1 && s.skips == 2 && s.copies == 1);
    const uint32_t eo = ps3_texsnap_capture(&s, 0x200, t, sizeof t);          /* another key: hashes */
    CHECK(eo && eo != e1 && s.skips == 2 && s.copies == 2);
    CHECK(ps3_texsnap_capture(&s, 0x100, t, 2048) != e1 && s.skips == 2);    /* another size: hashes */
    ep++;                                                                     /* a sync point */
    const uint32_t e3 = ps3_texsnap_capture(&s, 0x100, t, sizeof t);
    CHECK(e3 && e3 != e1 && s.skips == 2);
    const uint8_t* q3 = ps3_texsnap_get(&s, e3, 0x100, sizeof t);
    CHECK(q3 && q3[7] == 0x44);                                              /* the write is in the new capture */
    CHECK(ps3_texsnap_capture(&s, 0x100, t, sizeof t) == e3 && s.skips == 3);
    s.epoch_src = NULL;                                                       /* off: every capture hashes */
    t[8] = 0x55;
    const uint32_t e4 = ps3_texsnap_capture(&s, 0x100, t, sizeof t);
    CHECK(e4 && e4 != e3 && s.skips == 3);
    ps3_texsnap_free(&s);
    printf("%u texture snapshot checks PASS\n", checks);''')
print('ok', root)
