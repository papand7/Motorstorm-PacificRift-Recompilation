"""T137: far-plane clamp in the 2W zeta conversion; test fixes (one-shot)."""
import sys
R = sys.argv[1]


def patch(path, pairs):
    s = open(path, newline='', encoding='utf-8').read()
    for a, b in pairs:
        assert s.count(a) == 1, (path, a[:80], s.count(a))
        s = s.replace(a, b)
    open(path, 'w', newline='', encoding='utf-8').write(s)


patch(R + '/libs/video/rsx_msaa.h', [(
    '#define RSX_MSAA_ZCONV_BODY \\\n'
    '    "    uint d = (uint)(saturate(dv) * 16777215.0 + 0.5);\\n" \\\n',
    '/* d is clamped to 0xFFFFFF: in float, 1.0 * 16777215 + 0.5 rounds to 2^24,\n'
    ' * which the unclamped form (the backend\'s single-sample zconv_ps) writes as\n'
    ' * 0xFF0000 for every pixel at the far plane. */\n'
    '#define RSX_MSAA_ZCONV_BODY \\\n'
    '    "    uint d = min((uint)(saturate(dv) * 16777215.0 + 0.5), 16777215u);\\n" \\\n')])
patch(R + '/libs/video/tests/test_t137_msaa_warp.c', [
    ('    ID3D12GraphicsCommandList_ResolveSubresource(cl, rs1, 0, ms, 0, F);\n'
     '    barrier(ex, D3D12_RESOURCE_STATE_RENDER_TARGET, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);\n'
     '    srv_ms(0, ex, F, 0);',
     '    ID3D12GraphicsCommandList_ResolveSubresource(cl, rs1, 0, ms, 0, F);\n'
     '    barrier(ex, D3D12_RESOURCE_STATE_RENDER_TARGET, D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);\n'
     '    submit(); begin();   /* descriptor 0 is rewritten: the expand has executed */\n'
     '    srv_ms(0, ex, F, 0);'),
    ('    CHECK(ZEQ(e, 0, 0x40, 0, 0, 0x5A)',
     '    {   /* the legacy single-sample conversion\'s arithmetic at depth 1.0 */\n'
     '        volatile float one = 1.0f;\n'
     '        const float d1 = one * 16777215.0f + 0.5f;\n'
     '        CHECK((unsigned)d1 == 16777216u, "legacy zconv formula: depth 1.0 -> 2^24 (encodes as 0xFF0000)");\n'
     '    }\n'
     '    CHECK(ZEQ(e, 0, 0x40, 0, 0, 0x5A)'),
])
print('ok')
