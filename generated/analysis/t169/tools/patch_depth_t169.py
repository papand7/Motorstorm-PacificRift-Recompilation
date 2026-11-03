"""T169: adds RSX_DEPTH_STATE and RSX_MRT_STATE to the profile and the decal-depth A/B. Anchors must match once."""
from pathlib import Path


def edit(path, pairs):
    p = Path(path)
    s = p.read_bytes().decode()
    for a, b in pairs:
        a, b = a.replace('\n', '\r\n'), b.replace('\n', '\r\n')
        assert s.count(a) == 1, a
        s = s.replace(a, b)
    p.write_bytes(s.encode())


T = 'ps3recomp-t169/'
edit(T + 'tools/test_t169_visual.py', [
    ("'RSX_RT_FEEDBACK', 'RSX_MSAA')", "'RSX_RT_FEEDBACK', 'RSX_MSAA', 'RSX_DEPTH_STATE', 'RSX_MRT_STATE')"),
])
NEW = Path(__file__).with_name('decal_depth_fixture_t169.c').read_text()
edit(T + 'libs/video/tests/test_t169_visual_ab_warp.c', [
    ('rsx_visual_profile_parse("0x80") == 0 &&', 'rsx_visual_profile_parse("0x200") == 0 &&'),
    (' *   5. Bloom input:',
     ' *   6. Decal box: the captured depth request (compare GREATER, writes off, front\n'
     ' *      culled, so back faces) against the host\'s legacy state (LESS_EQUAL, writes\n'
     ' *      on), over a scene depth with the box partly behind it: covered pixels,\n'
     ' *      depth afterwards, and pixel-shader invocations from a pipeline query.\n'
     ' *   5. Bloom input:'),
    ('\nint main(void)', '\n' + NEW + '\nint main(void)'),
    ('    test_decal_clamp();\n', '    test_decal_clamp();\n    test_decal_depth();\n'),
])
print('ok')
