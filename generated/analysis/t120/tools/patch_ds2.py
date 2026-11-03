import sys
hp, bp = sys.argv[1], sys.argv[2]
h = open(hp, newline='').read()
add = '''
#if defined(__d3d12_h__)
/* Apply a full key to a pipeline's depth/stencil state; a legacy key (bit 5
 * clear) leaves it as the caller built it. */
static inline void rsx_ds_apply(uint64_t key, D3D12_DEPTH_STENCIL_DESC* ds)
{
    const rsx_ds_desc g = rsx_ds_decode(key);
    if (!g.full) return;
    if (g.depth_enable) {
        ds->DepthWriteMask = g.depth_write ? D3D12_DEPTH_WRITE_MASK_ALL : D3D12_DEPTH_WRITE_MASK_ZERO;
        ds->DepthFunc = (D3D12_COMPARISON_FUNC)g.depth_func;
    }
    if (g.stencil_enable) {
        ds->StencilEnable = TRUE;
        ds->StencilReadMask  = (UINT8)g.read_mask;
        ds->StencilWriteMask = (UINT8)g.write_mask;
        ds->FrontFace.StencilFunc        = (D3D12_COMPARISON_FUNC)g.f_func;
        ds->FrontFace.StencilFailOp      = (D3D12_STENCIL_OP)g.f_fail;
        ds->FrontFace.StencilDepthFailOp = (D3D12_STENCIL_OP)g.f_zfail;
        ds->FrontFace.StencilPassOp      = (D3D12_STENCIL_OP)g.f_zpass;
        ds->BackFace.StencilFunc         = (D3D12_COMPARISON_FUNC)g.b_func;
        ds->BackFace.StencilFailOp       = (D3D12_STENCIL_OP)g.b_fail;
        ds->BackFace.StencilDepthFailOp  = (D3D12_STENCIL_OP)g.b_zfail;
        ds->BackFace.StencilPassOp       = (D3D12_STENCIL_OP)g.b_zpass;
    }
}
#endif
'''.replace('\n', '\r\n')
tail = '\r\n#endif /* PS3RECOMP_RSX_DEPTH_STATE_H */'
assert h.count(tail) == 1
h = h.replace(tail, add + tail)
open(hp, 'w', newline='').write(h)
b = open(bp, newline='').read()
i = b.index('    /* RSX_DEPTH_STATE=1: the guest\'s write mask, compare and stencil. */\r\n    { const rsx_ds_desc g')
j = b.index('      } }\r\n', i) + len('      } }\r\n')
b = b[:i] + '    /* RSX_DEPTH_STATE=1: the guest\'s write mask, compare and stencil. */\r\n    rsx_ds_apply(depth, &pd.DepthStencilState);\r\n' + b[j:]
open(bp, 'w', newline='').write(b)
print('ok')
