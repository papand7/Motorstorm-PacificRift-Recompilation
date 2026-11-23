rep(r"""    w = c[c.index('void spu_wrch(spu_context* ctx, uint32_t channel, u128 value)'):]
    w = w[:w.index('\n}\n')]
""", r"""    # PS3_SPU_HWFLOAT: spu_wrch is the host-call bracket; the MFC work (and the hook) is in spu_wrch_host
    wr = c[c.index('void spu_wrch(spu_context* ctx, uint32_t channel, u128 value)\n{'):]
    wr = wr[:wr.index('\n}\n')]
    check('spu_hwf_suspend()' in wr and 'spu_wrch_host(ctx, channel, value);' in wr and 'spu_hwf_resume(hwf);' in wr,
          'spu_wrch: brackets spu_wrch_host with the SPU float mode suspended')
    w = c[c.index('void spu_wrch_host(spu_context* ctx, uint32_t channel, u128 value)\n{'):]
    w = w[:w.index('\n}\n')]
""")
