"""Tests for RSX_RT_READBACK_EAGER in ps3recomp-vkgame/tests/test_rt_readback.c (CRLF).

usage: py -3 edit_rtrb_eager_test.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[4] / 'ps3recomp-vkgame' / 'tests' / 'test_rt_readback.c'
raw = p.read_bytes().decode('utf-8')
s = raw.replace('\r\n', '\n')
a = """    CHECK(strcmp(ps3_rtrb_result_name(PS3_RTRB_MERGED), "merged") == 0);
    ps3_rtrb_free(&t);"""
b = """    /* ---- RSX_RT_READBACK_EAGER: parsing; T13's chain with eager on. The
     * exposure target is selected from its first generation (young: the
     * caller copies it synchronously) and stays selected; the sampled level
     * never is; a target the GPU samples once falls back to the min_orphan
     * rule. Then the guest reads every frame's value from the first frame on,
     * where without eager frames 1 and 2 were never copied (case above). ---- */
    reinit(&t, "1", NULL, NULL);
    CHECK(t.eager == 0);
    ps3_rtrb_set_eager(&t, "0");  CHECK(t.eager == 0);
    ps3_rtrb_set_eager(&t, "10"); CHECK(t.eager == 0);
    ps3_rtrb_set_eager(&t, NULL); CHECK(t.eager == 0);
    ps3_rtrb_set_eager(&t, "1");  CHECK(t.eager == 1);
    memset(mem, 0, sizeof mem);
    { const uint32_t LUM = 0x2000, EXP = 0x400, LATE = 0x3000;
      for (uint32_t b = 1; b <= 6; b++) {
          ps3_rtrb_begin_batch(&t);
          const int sl = ps3_rtrb_note_write(&t, LUM, LUM, 10, 5, 128, 0x14B, 3);
          ps3_rtrb_note_sample(&t, LUM);
          const int se = ps3_rtrb_note_write(&t, EXP, 0x1000, 16, 16, 128, 0x14B, 4);
          const int sk = ps3_rtrb_note_write(&t, LATE, 0x4000, 16, 16, 128, 0x14B, 6);
          if (b == 2) ps3_rtrb_note_sample(&t, LATE);                 /* sampled once, in batch 2 */
          CHECK(sl >= 0 && se >= 0 && sk >= 0);
          CHECK(ps3_rtrb_why(&t, sl) == PS3_RTRB_WHY_SAMPLED && !ps3_rtrb_young(&t, sl));
          CHECK(ps3_rtrb_why(&t, se) == PS3_RTRB_WHY_SELECTED);
          CHECK(ps3_rtrb_young(&t, se) == (b <= 2));                  /* min_orphan 2 */
          if (b == 1) CHECK(ps3_rtrb_why(&t, sk) == PS3_RTRB_WHY_SELECTED && ps3_rtrb_young(&t, sk));
          if (b >= 2 && b <= 4) CHECK(ps3_rtrb_why(&t, sk) == PS3_RTRB_WHY_SAMPLED && !ps3_rtrb_young(&t, sk));
          if (b >= 5) CHECK(ps3_rtrb_why(&t, sk) == PS3_RTRB_WHY_SELECTED && !ps3_rtrb_young(&t, sk));
      } }
    reinit(&t, "1", NULL, NULL);
    ps3_rtrb_set_eager(&t, "1");
    memset(mem, 0, sizeof mem);
    for (uint64_t f = 1; f <= 4; f++) {
        const int q = frame_write(&t, f, (uint16_t)(0x1000 + f), 7);
        CHECK(q >= 0);
        CHECK(ps3_rtrb_young(&t, 0) == (f <= 2));
        complete(&t, f, NULL);
        CHECK(be16(0x1000) == 0x1000 + f);                           /* from frame 1 on */
    }

""" + a
assert s.count(a) == 1
s = s.replace(a, b)
p.write_bytes(s.replace('\n', '\r\n').encode('utf-8'))
print('edited', p.name)
