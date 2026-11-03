MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T169 continuation: the profile test reads RSXI target snapshots (as T145) rather than the display dump."""
R = (MS_ROOT + r'\ps3recomp-t169')
p = R + r'\libs\video\tests\test_t169_profile_backend.c'
s = open(p, encoding='utf-8', newline='').read()


def sub(a, b):
    global s
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)


sub(''' * Left half of the display, read from RT_S: red''', ''' * Left half of RT_G, read from RT_S: red''')
sub(''' *   test_t169_profile_backend [frames=3]''', ''' * The driver reads RT_G from an RSXI end-of-frame snapshot.
 *
 *   test_t169_profile_backend [frames=6]''')
sub('''#define Z_X      0x0D000000u
''', '''#define RT_G     0x0A000000u
#define Z_X      0x0D000000u
''')
sub('argc > 1 ? atoi(argv[1]) : 3;', 'argc > 1 ? atoi(argv[1]) : 6;')
sub('''/* ---- the display: scene on the left, the sRGB grey on the right ---- */
        target(&st, DISPLAY_OFF, Z_X);''', '''/* ---- RT_G: scene on the left, the sRGB grey on the right ---- */
        target(&st, RT_G, Z_X);''')
sub('''        s_flips++;
''', '''        /* ---- present ---- */
        target(&st, DISPLAY_OFF, Z_X);
        st.shader_packer = 0;
        st.begin_epoch++;
        notify(be, &st);
        be->draw_arrays(be->userdata, RSX_PRIMITIVE_TRIANGLES, 18, 6);
        s_flips++;
''')
open(p, 'w', encoding='utf-8', newline='').write(s)
p = R + r'\tools\test_t169_profile.py'
s = open(p, encoding='utf-8', newline='').read()
sub("""e = {**base, **env, 'CELLMARK_DUMP': '2', 'CELLMARK_DUMP_DIR': str(out), 'RSX_VISUAL_ACTIVE': '1'}""",
    """e = {**base, **env, 'RSXI': '1', 'RSXI_DIR': 'rsxi', 'RSXI_FRAMES': '5', 'RSXI_COUNT': '1', 'RSXI_SNAP': 'targets', 'RSX_VISUAL_ACTIVE': '1'}""")
sub("""[str(exe), '3']""", """[str(exe), '6']""")
sub("""dumps = sorted(out.glob('*.bmp'))""", """dumps = sorted(out.glob('rsxi/frames/*/snap*_rt_0A000000.bmp'))""")
sub("""f'{name}: a frame was dumped'""", """f'{name}: RT_G snapshot'""")
open(p, 'w', encoding='utf-8', newline='').write(s)
